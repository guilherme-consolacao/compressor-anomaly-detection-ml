"""Record nested confirmation controls without opening either reserved public test."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from compressor_anomaly_detection_ml.config import Settings
from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.datasets import save_immutable
from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_importers import smart_pdm_tables
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.temporal_confirmation import nested_confirmation
from compressor_anomaly_detection_ml.transfer_bridges import file_manifest
from compressor_anomaly_detection_ml.transfer_temporal import cycle_context


def main():
    protocol_path = Path("config/transfer-round8-confirmation.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["external_data_allowed"] or protocol["public_test_opened"]:
        raise DataValidationError("Confirmation requires sealed public tests and no external data.")
    partition = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
    expected = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
    if hashlib.sha256(partition.read_bytes()).hexdigest() != expected["parent_partitions_sha256"]:
        raise DataValidationError("Reserved partition manifest changed.")
    folder = Path("data/public/raw/smart_pdm/7245198")
    auxiliary_path = (
        Path("reports/research") / protocol["parent_run"] / "auxiliary-normality-experiments.csv"
    )
    inputs = file_manifest(
        [
            folder / "fridge_metadata.csv",
            folder / "F_ExtractedFeatures.csv",
            auxiliary_path,
            partition,
        ]
    )
    paths = [
        Path(__file__),
        *[
            Path("src/compressor_anomaly_detection_ml") / (name + ".py")
            for name in (
                "temporal_confirmation",
                "transfer_temporal",
                "transfer_novelty",
                "transfer_analysis",
                "public_importers",
                "public_experiments",
            )
        ],
    ]
    code = b"\n".join(path.read_bytes() for path in paths)
    digest = hashlib.sha256(code + protocol_path.read_bytes() + document_bytes(inputs)).hexdigest()
    run_id = protocol["round_name"] + "-" + digest[:20]
    output = Path("reports/research") / run_id
    engine = create_engine_for_url(Settings.from_env().database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    running = False
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
                raise DataValidationError("Inspect incomplete confirmation first.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_temporal_confirmation",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {"files": inputs, "external_data_read": False},
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ]
            },
            scope="public",
        )
        running = True
        output.mkdir(parents=True, exist_ok=False)
        save_immutable(output / "protocol.json", protocol_path.read_bytes())
        save_immutable(output / "executed-code.txt", code)
        smart, _, _ = smart_pdm_tables(folder)
        smart = smart.merge(
            pd.read_csv(partition)[
                ["observation_id", "source_id", "dependency_group_id", "partition_name"]
            ],
            on="observation_id",
            validate="one_to_one",
        )
        smart = smart[smart.partition_name.ne("test")].copy()
        smart = cycle_context(smart, **protocol["cycle_context"])
        eligible = smart.loc[smart.duration_relative_history.notna()].copy().reset_index(drop=True)
        reports, predictions = nested_confirmation(eligible, pd.read_csv(auxiliary_path), protocol)
        summary = {
            "run_id": run_id,
            "input_cycles": len(smart),
            "eligible_cycles": len(eligible),
            "context_rejections": len(smart) - len(eligible),
            "external_data_read": False,
            "reserved_smart_test_used": False,
            "tri_oc_test_used": False,
            "calibration_support": "few positive groups; cohort reference, not universal defect P",
            "results": reports,
        }
        files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(
                output / "predictions.csv", predictions.to_csv(index=False).encode("utf-8")
            ),
        ]
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            if row["source_id"] == "smart_pdm"
        )
        stats = []
        for report in reports:
            identifier = f"{report['variant']}:{report['shuffle_seed']}:{report['mode']}"
            for metric in (
                "balanced_accuracy",
                "recall",
                "false_positive_rate",
                "average_precision",
                "brier",
                "log_loss",
            ):
                stats.append(
                    {
                        "run_id": run_id,
                        "statistic_key": identifier + ":" + metric,
                        "source_id": "smart_pdm",
                        "source_version": "7245198",
                        "statistic_name": "nested_temporal_confirmation",
                        "feature_name": metric,
                        "numeric_value": report[metric],
                        "sample_count": report["n"],
                        "group_count": int(eligible.dependency_group_id.nunique()),
                        "dimensions_json": {
                            "variant": report["variant"],
                            "mode": report["mode"],
                            "shuffle_seed": report["shuffle_seed"],
                            "scope": "nested public group development; no reserved test",
                        },
                    }
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
        running = False
        print(json.dumps({"run_id": run_id, "results": reports}, indent=2))
    except Exception as error:
        if running:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
