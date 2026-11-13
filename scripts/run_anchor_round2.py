"""Execute the predeclared SMART feature-family ablation; keep final test sealed."""

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
from compressor_anomaly_detection_ml.transfer_analysis import anchor_diagnostics


def main():
    protocol_path = Path("config/transfer-round2-analysis.json")
    partition_path = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    parent = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
    if (
        protocol["external_data_allowed"]
        or hashlib.sha256(partition_path.read_bytes()).hexdigest()
        != parent["parent_partitions_sha256"]
    ):
        raise DataValidationError("External input or changed public reservations.")
    code = (
        Path("src/compressor_anomaly_detection_ml/transfer_analysis.py").read_bytes()
        + Path(__file__).read_bytes()
    )
    digest = hashlib.sha256(
        code + protocol_path.read_bytes() + partition_path.read_bytes()
    ).hexdigest()
    run_id = "anchor-round2-" + digest[:20]
    output = Path("reports/research") / run_id
    engine = create_engine_for_url(Settings.from_env().database_url)
    started = False
    try:
        repository = ResearchRepository(engine)
        with engine.connect() as connection:
            previous = connection.execute(
                select(repository.tables["study_runs"].c.status).where(
                    repository.tables["study_runs"].c.run_id == run_id
                )
            ).scalar_one_or_none()
            artifacts = [
                dict(row)
                for row in connection.execute(
                    select(repository.tables["study_artifacts"]).where(
                        repository.tables["study_artifacts"].c.source_id == "smart_pdm",
                        repository.tables["study_artifacts"].c.artifact_kind == "raw",
                    )
                ).mappings()
                if Path(row["relative_path"]).name
                in {"fridge_metadata.csv", "F_ExtractedFeatures.csv"}
            ]
        if previous:
            if previous != "completed":
                raise DataValidationError("An incomplete diagnostic requires inspection.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        if len(artifacts) != 2 or any(
            hashlib.sha256(Path(row["relative_path"]).read_bytes()).hexdigest()
            != row["content_sha256"]
            for row in artifacts
        ):
            raise DataValidationError("Verified SMART source artifacts are required.")
        now = datetime.now(UTC).replace(tzinfo=None)
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_anchor_diagnostic",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {
                            "raw_artifacts": [row["artifact_id"] for row in artifacts],
                            "parent_partition_sha256": parent["parent_partitions_sha256"],
                            "reserved_test_opened": False,
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
        frame, names, _ = smart_pdm_tables(Path("data/public/raw/smart_pdm/7245198"))
        partition = pd.read_csv(partition_path)
        frame = frame.merge(
            partition[["observation_id", "source_id", "dependency_group_id", "partition_name"]],
            on="observation_id",
            validate="one_to_one",
        )
        development = frame.loc[frame.partition_name.ne("test")].copy()
        reports, predictions = anchor_diagnostics(development, names)
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            if row["source_id"] == "smart_pdm"
        )
        summary = {
            "run_id": run_id,
            "evaluations": len(reports),
            "development_rows": len(development),
            "positive_rows": int(development.target_label.sum()),
            "positive_dependency_groups": 3,
            "reserved_test_rows": int(frame.partition_name.eq("test").sum()),
            "reserved_test_used_for_fit_or_selection": False,
            "external_data_read": False,
            "results": reports,
        }
        files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(
                output / "predictions.csv",
                predictions.to_csv(index=False, lineterminator="\n").encode(),
            ),
        ]
        stats = []
        for report in reports:
            for metric in (
                "balanced_accuracy",
                "precision",
                "recall",
                "f1",
                "average_precision",
                "brier",
                "log_loss",
                "prevalence",
                "tp",
                "fp",
                "tn",
                "fn",
            ):
                stats.append(
                    {
                        "run_id": run_id,
                        "statistic_key": report["model_id"] + ":" + metric,
                        "source_id": "smart_pdm",
                        "source_version": "7245198",
                        "statistic_name": "anchor_group_oof",
                        "feature_name": metric,
                        "numeric_value": report[metric],
                        "sample_count": len(development),
                        "group_count": 9,
                        "dimensions_json": {
                            "model_id": report["model_id"],
                            "family": report["family"],
                            "evaluation": report["evaluation"],
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
        started = False
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluations": len(reports),
                    "by_family": [
                        {
                            "family": family,
                            "best_development_f1": max(
                                row["f1"] for row in reports if row["family"] == family
                            ),
                        }
                        for family in sorted({row["family"] for row in reports})
                    ],
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
    main()
