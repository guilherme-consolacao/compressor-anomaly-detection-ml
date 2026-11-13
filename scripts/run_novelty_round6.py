"""Test cross-fitted common deviation descriptors with the supervised forest."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from compressor_anomaly_detection_ml.config import Settings
from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.datasets import save_immutable
from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.nist_refrigeration import nist_table
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_importers import smart_pdm_tables
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_bridges import file_manifest, refrigeration_common
from compressor_anomaly_detection_ml.transfer_inputs import tri_hp_main
from compressor_anomaly_detection_ml.transfer_novelty import (
    META_NAMES,
    crossfit_normality,
    novelty_reference_comparison,
)
from compressor_anomaly_detection_ml.transfer_temporal import cycle_context


def main(protocol_path=Path("config/transfer-round6-normality-reference.json")):
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["external_data_allowed"] or protocol["public_test_opened"]:
        raise DataValidationError("This normality-reference experiment is public development only.")
    partition_path = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
    parent = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
    if (
        hashlib.sha256(partition_path.read_bytes()).hexdigest()
        != parent["parent_partitions_sha256"]
    ):
        raise DataValidationError("Original SMART reservations changed.")
    smart_folder = Path("data/public/raw/smart_pdm/7245198")
    tri_path = Path(
        "data/public/raw/tri_hp_faults/5155136.v1/H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
    )
    nist_path = Path("data/public/raw/nist_hvac/nist-fdd-14-16seer.xlsx")
    inputs = file_manifest(
        [
            smart_folder / "fridge_metadata.csv",
            smart_folder / "F_ExtractedFeatures.csv",
            tri_path,
            nist_path,
        ]
    )
    code = (
        Path(__file__).read_bytes()
        + Path("src/compressor_anomaly_detection_ml/transfer_novelty.py").read_bytes()
        + Path("src/compressor_anomaly_detection_ml/transfer_temporal.py").read_bytes()
    )
    digest = hashlib.sha256(code + protocol_path.read_bytes() + document_bytes(inputs)).hexdigest()
    run_id = protocol["round_name"] + "-" + digest[:20]
    output = Path("reports/research") / run_id
    engine = create_engine_for_url(Settings.from_env().database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    started = False
    try:
        repository = ResearchRepository(engine)
        with engine.connect() as connection:
            previous = connection.execute(
                select(repository.tables["study_runs"].c.status).where(
                    repository.tables["study_runs"].c.run_id == run_id
                )
            ).scalar_one_or_none()
        if previous:
            if previous != "completed":
                raise DataValidationError("Inspect incomplete normality-reference analysis first.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_novelty_transfer",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {
                            "public_inputs": inputs,
                            "external_data_read": False,
                            "parent_partition_sha256": parent["parent_partitions_sha256"],
                        },
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ]
            },
            scope="public",
        )
        started = True
        output.mkdir(parents=True, exist_ok=False)
        save_immutable(output / "protocol.json", protocol_path.read_bytes())
        save_immutable(output / "executed-code.txt", code)
        tri, _ = tri_hp_main(tri_path)
        tri = tri[~tri.sheet.str.startswith("OC")].copy()
        tri, _ = refrigeration_common(tri, "tri_hp_faults")
        tri["normality_group"] = tri.load_kw.astype(str)
        tri["experiment_id"] = tri["Test code"]
        nist, _, _ = nist_table(nist_path)
        nist = nist[nist.target_label.notna()].copy()
        nist["normality_group"] = nist.equipment_stratum
        nist["experiment_id"] = nist.Filename
        vectors = []
        for source, frame in (("tri_hp_faults", tri), ("nist_hvac", nist)):
            if frame.groupby("experiment_id").target_label.nunique().gt(1).any():
                raise DataValidationError(
                    "An auxiliary experiment has conflicting reference states."
                )
            meta = crossfit_normality(frame, protocol["auxiliary_features"], "normality_group")
            prepared = pd.concat(
                [frame[["source_id", "experiment_id", "target_label"]], meta], axis=1
            )
            aggregate = (
                prepared.groupby(["source_id", "experiment_id", "target_label"], sort=True)[
                    META_NAMES
                ]
                .median()
                .reset_index()
            )
            vectors.append(aggregate)
            print(
                json.dumps(
                    {
                        "normality_source": source,
                        "rows": len(frame),
                        "reference_experiments": len(aggregate),
                    }
                ),
                flush=True,
            )
        auxiliary = pd.concat(vectors, ignore_index=True)
        smart, names, _ = smart_pdm_tables(smart_folder)
        partition = pd.read_csv(partition_path)
        smart = smart.merge(
            partition[["observation_id", "source_id", "dependency_group_id", "partition_name"]],
            on="observation_id",
            validate="one_to_one",
        )
        smart = smart[smart.partition_name.ne("test")].copy()
        if protocol.get("primary_representation") == "causal_cycle_context":
            smart = cycle_context(smart, **protocol["cycle_context"])
            families = {
                "elapsed_cycle": ["elapsed_seconds"],
                "relative_cycle_duration": ["duration_relative_history"],
                "elapsed_and_relative": ["elapsed_seconds", "duration_relative_history"],
            }
        else:
            families = {
                "vibration_published": [name for name in names if name.startswith("Vibration__")],
                "vibration_shape": [
                    name
                    for name in names
                    if name.startswith("Vibration__")
                    and (
                        name.endswith("__skewness")
                        or name.endswith("__kurtosis")
                        or "fourier_entropy" in name
                        or name.endswith('aggtype_"skew"')
                        or name.endswith('aggtype_"kurtosis"')
                    )
                ],
            }
        reports, prediction_frames = [], []
        for family, features in families.items():
            selected = smart.loc[smart[features].notna().all(axis=1)].copy()
            results, predictions = novelty_reference_comparison(
                selected, features, auxiliary, protocol
            )
            for row in results:
                row["input_cycles"] = len(smart)
                row["eligible_cycles"] = len(selected)
                row["eligible_positive_cycles"] = int(selected.target_label.sum())
                row["context_rejections"] = len(smart) - len(selected)
                row["family"] = family
                row["model_id"] = family + ":" + row["model_id"]
            predictions["model_id"] = family + ":" + predictions.model_id
            reports.extend(results)
            prediction_frames.append(predictions)
            print(json.dumps({"family_completed": family, "comparisons": len(results)}), flush=True)
        summary = {
            "run_id": run_id,
            "anchor_cycles": len(smart),
            "anchor_positives": int(smart.target_label.sum()),
            "auxiliary_experiments": len(auxiliary),
            "meta_features": META_NAMES,
            "external_data_read": False,
            "reserved_smart_test_used": False,
            "tri_oc_test_used": False,
            "physical_cross_source_correlation_claimed": False,
            "derived_binary_labels_accepted": 0,
            "results": reports,
        }
        files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(
                output / "auxiliary-normality-experiments.csv",
                auxiliary.to_csv(index=False, lineterminator="\n").encode(),
            ),
            save_immutable(
                output / "predictions.csv",
                pd.concat(prediction_frames, ignore_index=True)
                .to_csv(index=False, lineterminator="\n")
                .encode(),
            ),
        ]
        stats = []
        for report in reports:
            for metric in (
                "balanced_accuracy",
                "recall",
                "false_positive_rate",
                "f1",
                "average_precision",
            ):
                stats.append(
                    {
                        "run_id": run_id,
                        "statistic_key": report["model_id"] + ":" + metric,
                        "source_id": "smart_pdm",
                        "source_version": "7245198",
                        "statistic_name": "normality_reference_ablation",
                        "feature_name": metric,
                        "numeric_value": report[metric],
                        "sample_count": report["n"],
                        "group_count": int(smart.dependency_group_id.nunique()),
                        "dimensions_json": {
                            "model_id": report["model_id"],
                            "family": report["family"],
                            "auxiliary_sources": report["auxiliary_sources"],
                            "evaluation": report["evaluation"],
                        },
                    }
                )
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            if row["source_id"] == "smart_pdm"
        )
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
        started = False
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "comparisons": len(reports),
                    "best_development_f1": max(row["f1"] for row in reports),
                },
                indent=2,
            )
        )
    except Exception as error:
        if started:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main(
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path("config/transfer-round6-normality-reference.json")
    )
