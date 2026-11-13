"""One-time reserved public evaluation of the already frozen cycle candidate."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from compressor_anomaly_detection_ml.config import Settings
from compressor_anomaly_detection_ml.cycle_candidate import (
    load_cycle_candidate,
    score_meta,
    score_ratios,
)
from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.datasets import save_immutable
from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_experiments import binary_metrics
from compressor_anomaly_detection_ml.public_importers import smart_pdm_tables
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_bridges import refrigeration_common
from compressor_anomaly_detection_ml.transfer_inputs import tri_hp_main
from compressor_anomaly_detection_ml.transfer_novelty import (
    META_NAMES,
    fit_normality,
    normality_vectors,
)
from compressor_anomaly_detection_ml.transfer_temporal import completed_cycle_context


def measured_metrics(frame, threshold):
    result = binary_metrics(frame.reference, frame.score >= threshold, frame.score)
    result["false_positive_rate"] = (
        result["fp"] / (result["fp"] + result["tn"]) if result["fp"] + result["tn"] else None
    )
    result["positive_groups"] = int(frame.loc[frame.reference.eq(1), "group"].nunique())
    result["normal_groups"] = int(frame.loc[frame.reference.eq(0), "group"].nunique())
    return result


def group_intervals(frame, threshold):
    rng = np.random.default_rng(2026)
    groups = sorted(frame.group.unique())
    results = []
    for _ in range(2000):
        sample = pd.concat(
            [frame[frame.group.eq(group)] for group in rng.choice(groups, len(groups))]
        )
        if sample.reference.nunique() == 2:
            results.append(measured_metrics(sample, threshold))
    return {
        "method": "2000 complete-group bootstrap samples; few groups, descriptive uncertainty only",
        "valid_samples_with_both_classes": len(results),
        "intervals": {
            metric: np.quantile([row[metric] for row in results], [0.025, 0.975]).tolist()
            for metric in ("balanced_accuracy", "recall", "false_positive_rate")
        }
        if results
        else {},
    }


def main(manifest_path):
    settings = Settings.from_env()
    artifact, manifest = load_cycle_candidate(manifest_path, settings.model_dir)
    output = manifest_path.parent / "public-test"
    if output.exists():
        if (output / "summary.json").exists():
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        raise DataValidationError(
            "Reserved test access has already started; inspect the preserved run."
        )
    parent = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
    partitions = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
    if hashlib.sha256(partitions.read_bytes()).hexdigest() != parent["parent_partitions_sha256"]:
        raise DataValidationError("Original reserved partitions changed.")
    engine = create_engine_for_url(settings.database_url)
    repository = ResearchRepository(engine)
    run_id = "cycle-test-" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:20]
    now = datetime.now(UTC).replace(tzinfo=None)
    running = False
    try:
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_cycle_test",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "frozen_candidate": manifest,
                            "rule": "one reserved evaluation, no refitting",
                        },
                        "input_manifest_json": {
                            "manifest_sha256": hashlib.sha256(
                                manifest_path.read_bytes()
                            ).hexdigest(),
                            "external_data_read": False,
                        },
                        "code_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    }
                ]
            },
            scope="public",
        )
        running = True
        output.mkdir(exist_ok=False)
        save_immutable(
            output / "access-record.json",
            document_bytes(
                {
                    "opened_at_utc": now.isoformat() + "Z",
                    "frozen_candidate": manifest,
                    "reserved_data_now_consumed": True,
                }
            ),
        )
        save_immutable(output / "executed-code.txt", Path(__file__).read_bytes())
        smart, _, _ = smart_pdm_tables(Path("data/public/raw/smart_pdm/7245198"))
        smart = smart.merge(
            pd.read_csv(partitions)[
                ["observation_id", "source_id", "dependency_group_id", "partition_name"]
            ],
            on="observation_id",
            validate="one_to_one",
        )
        reserved = smart[smart.partition_name.eq("test")].copy()
        if len(reserved) != 293:
            raise DataValidationError("Unexpected SMART test support.")
        context = completed_cycle_context(reserved, **artifact["cycle_context"])
        eligible = context[context.duration_relative_history.notna()].copy()
        raw, mapped = score_ratios(artifact, eligible.duration_relative_history)
        predictions = pd.DataFrame(
            {
                "observation_id": eligible.observation_id,
                "source_id": "smart_pdm",
                "group": eligible.dependency_group_id,
                "reference": eligible.target_label.astype(int),
                "score": raw,
                "experimental_reference_probability": mapped,
            }
        )
        tri_path = Path(
            "data/public/raw/tri_hp_faults/5155136.v1/H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
        )
        tri, _ = tri_hp_main(tri_path)
        tri, _ = refrigeration_common(tri, "tri_hp_faults")
        thermal_names = json.loads(Path("config/transfer-round7-temporal.json").read_text())[
            "auxiliary_features"
        ]
        tri_test = []
        for load in sorted(tri.load_kw.unique()):
            normal = tri.target_label.eq(0) & tri.load_kw.ne(load)
            test = tri.sheet.str.startswith("OC") & tri.load_kw.eq(load)
            if not tri.loc[test, "target_label"].eq(1).all():
                raise DataValidationError("Reserved TRI condition reference changed.")
            encoder = fit_normality(tri.loc[normal, thermal_names])
            meta = normality_vectors(encoder, tri.loc[test, thermal_names]).set_index(
                tri.loc[test].index
            )
            meta["experiment_id"] = tri.loc[test, "Test code"]
            aggregate = meta.groupby("experiment_id")[META_NAMES].median()
            scores, _ = score_meta(artifact, aggregate)
            tri_test.extend(
                {
                    "observation_id": "tri_hp_faults:reserved:" + code,
                    "source_id": "tri_hp_faults",
                    "group": "tri_hp_faults:OC-day",
                    "reference": 1,
                    "score": float(score),
                    "experimental_reference_probability": None,
                }
                for code, score in zip(aggregate.index, scores, strict=True)
            )
        combined = pd.concat([predictions, pd.DataFrame(tri_test)], ignore_index=True)
        aggregate_metrics = measured_metrics(combined, artifact["threshold"])
        gates = parent["prototype_public_acceptance"]
        passed = (
            aggregate_metrics["tp"] + aggregate_metrics["fn"]
            >= gates["minimum_reference_positives_for_aggregate_claim"]
            and aggregate_metrics["positive_groups"] >= gates["minimum_positive_dependency_groups"]
            and aggregate_metrics["normal_groups"] >= gates["minimum_normal_dependency_groups"]
            and aggregate_metrics["balanced_accuracy"] >= gates["balanced_accuracy"]
            and aggregate_metrics["recall"] >= gates["recall_anomaly"]
            and aggregate_metrics["false_positive_rate"] <= gates["maximum_false_positive_rate"]
            and aggregate_metrics["average_precision"] > combined.reference.mean()
        )
        prior = 13 / manifest["smart_training_cases"]
        reliability = []
        for left, right in zip(
            [0, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5],
            [0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1],
            strict=True,
        ):
            selected = predictions[
                (predictions.experimental_reference_probability >= left)
                & (predictions.experimental_reference_probability < right)
            ]
            reliability.append(
                {
                    "left": left,
                    "right": right,
                    "n": len(selected),
                    "positive_cases": int(selected.reference.sum()),
                    "mean_probability": float(selected.experimental_reference_probability.mean())
                    if len(selected)
                    else None,
                }
            )
        summary = {
            "run_id": run_id,
            "frozen_candidate": manifest["version"],
            "public_integration_decision": "prototype_discrimination_pass"
            if passed
            else "criteria_not_met",
            "public_probability_support": "limited; sparse independent positive groups",
            "local_portability_status": manifest["local_portability_status"],
            "external_release_decision": "not_released; no local campaign or boundary confirmation",
            "reserved_smart_input": len(reserved),
            "smart_eligible": len(eligible),
            "context_rejections": len(reserved) - len(eligible),
            "rejected_positive_cases": int(
                context.loc[context.duration_relative_history.isna(), "target_label"].sum()
            ),
            "reserved_tri_conditions": len(tri_test),
            "aggregate": aggregate_metrics,
            "by_source": {
                source: measured_metrics(frame, artifact["threshold"])
                for source, frame in combined.groupby("source_id")
            },
            "group_uncertainty": group_intervals(combined, artifact["threshold"]),
            "smart_probability": {
                "brier": float(brier_score_loss(predictions.reference, mapped)),
                "log_loss": float(log_loss(predictions.reference, mapped, labels=[0, 1])),
                "constant_training_prior": prior,
                "prior_brier": float(
                    brier_score_loss(predictions.reference, np.full(len(predictions), prior))
                ),
                "prior_log_loss": float(
                    log_loss(predictions.reference, np.full(len(predictions), prior), labels=[0, 1])
                ),
                "reliability": reliability,
            },
            "reserved_test_consumed": True,
            "external_data_read": False,
            "claim": "after-cycle maintenance reference; no universal compressor failure claim",
        }
        files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(output / "predictions.csv", combined.to_csv(index=False).encode()),
        ]
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text())["sources"]
            if row["source_id"] == "smart_pdm"
        )
        stats = [
            {
                "run_id": run_id,
                "statistic_key": scope + ":" + metric,
                "source_id": None,
                "source_version": None,
                "statistic_name": "frozen_public_cycle_test",
                "feature_name": metric,
                "numeric_value": value,
                "sample_count": result["n"],
                "group_count": None,
                "dimensions_json": {"evaluation_source": scope, "candidate": manifest["version"]},
            }
            for scope, result in {"aggregate": aggregate_metrics, **summary["by_source"]}.items()
            for metric, value in result.items()
            if metric != "n"
        ]
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(source, file, "report", {"run_id": run_id}, now) for file in files
                ],
                "study_statistics": stats,
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        running = False
        print(json.dumps(summary, indent=2))
    except Exception as error:
        if running:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
