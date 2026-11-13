"""Audit same-provider controls, then test their contribution on held-out SMART weeks."""

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
from compressor_anomaly_detection_ml.public_acquisition import artifact_row, source_row
from compressor_anomaly_detection_ml.public_importers import smart_pdm_tables
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_auxiliary import auxiliary_comparison, washer_tables


def main():
    protocol_path = Path("config/transfer-round5-auxiliary.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["external_data_allowed"] or protocol["public_test_opened"]:
        raise DataValidationError("This auxiliary experiment is public development only.")
    acquired = json.loads(
        Path(
            "reports/research/transfer-protocol-2b941b65972c76bd9371/washer-table-acquisition.json"
        ).read_text(encoding="utf-8")
    )
    files = acquired["files"]
    for file in files:
        if (
            hashlib.sha256(Path(file["relative_path"]).read_bytes()).hexdigest()
            != file["content_sha256"]
        ):
            raise DataValidationError("Washer auxiliary input changed after acquisition.")
    folder = Path(files[0]["relative_path"]).parent
    auxiliary, names, quality = washer_tables(folder)
    code = (
        Path(__file__).read_bytes()
        + Path("src/compressor_anomaly_detection_ml/transfer_auxiliary.py").read_bytes()
    )
    digest = hashlib.sha256(code + protocol_path.read_bytes() + document_bytes(files)).hexdigest()
    run_id = "auxiliary-round5-" + digest[:20]
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
                raise DataValidationError("Inspect incomplete auxiliary analysis before retrying.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            if row["source_id"] == "smart_pdm_washers"
        )
        artifacts = [
            artifact_row(
                source,
                file,
                "raw",
                {
                    "archive_member": file["archive_member"],
                    "zip_crc32": file["zip_crc32"],
                    "full_archive_checksum_verified": False,
                    "auxiliary_only": True,
                },
                now,
            )
            for file in files
        ]
        roots = [
            {
                "node_id": row["artifact_id"],
                "source_id": source["source_id"],
                "source_version": source["source_version"],
                "data_origin": "public_measured",
                "parent_ids": [],
                "content_sha256": row["content_sha256"],
            }
            for row in artifacts
        ]
        repository.persist(
            {
                "study_sources": [source_row(source, now)],
                "study_artifacts": artifacts,
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_auxiliary_transfer",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {"provenance_nodes": roots, "auxiliary_only": True},
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ],
            },
            scope="public",
        )
        started = True
        output.mkdir(parents=True, exist_ok=False)
        save_immutable(output / "protocol.json", protocol_path.read_bytes())
        save_immutable(output / "executed-code.txt", code)
        observations, labels, values = [], [], []
        for row in auxiliary.to_dict("records"):
            obs_id = row["observation_id"]
            observations.append(
                {
                    "observation_id": obs_id,
                    "source_id": source["source_id"],
                    "source_version": source["source_version"],
                    "original_id": row["original_id"],
                    "analysis_unit": "appliance_cycle",
                    "dependency_group_id": row["group_id"],
                    "equipment_id": None,
                    "started_at": None,
                    "ended_at": None,
                    "quality_status": "valid",
                    "condition_json": {
                        "brand": row["brand"],
                        "model": row["model"],
                        "program": row["program"],
                        "auxiliary_only": True,
                    },
                    "provenance_json": {
                        "provenance_nodes": [
                            *roots,
                            {
                                "node_id": obs_id,
                                "data_origin": "derived",
                                "parent_ids": [root["node_id"] for root in roots],
                            },
                        ]
                    },
                    "created_at": now,
                }
            )
            labels.append(
                {
                    "observation_id": obs_id,
                    "label_version": "washer-provider-broad-v1",
                    "original_label": row["failure"],
                    "target_label": int(row["target_label"]),
                    "label_status": "reference",
                    "method": "provider washer state; separate mechanical-only and broad ablations",
                    "confidence": None,
                    "evidence_artifact_id": artifacts[0]["artifact_id"],
                    "evidence_json": {
                        "scope": "washing machine, not refrigerator compressor",
                        "mechanical_only_policy": "Heating is excluded, never relabelled normal",
                    },
                    "recorded_at": now,
                }
            )
            for name in names:
                missing = pd.isna(row[name])
                values.append(
                    {
                        "observation_id": obs_id,
                        "feature_contract_version": "washer-published-v1-" + digest[:12],
                        "feature_name": name,
                        "numeric_value": None if missing else float(row[name]),
                        "unit": None,
                        "value_status": "missing" if missing else "observed",
                        "definition_json": {
                            "provider_feature": name,
                            "vibration_scale": "unconfirmed",
                            "auxiliary_only": True,
                        },
                        "run_id": run_id,
                    }
                )
        repository.persist(
            {"study_observations": observations, "study_labels": labels}, scope="public"
        )
        for offset in range(0, len(values), 2500):
            repository.persist(
                {"study_feature_values": values[offset : offset + 2500]}, scope="public"
            )
        smart, _, _ = smart_pdm_tables(Path("data/public/raw/smart_pdm/7245198"))
        partition_path = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
        parent = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
        if (
            hashlib.sha256(partition_path.read_bytes()).hexdigest()
            != parent["parent_partitions_sha256"]
        ):
            raise DataValidationError("Original public reservations changed.")
        partition = pd.read_csv(partition_path)
        smart = smart.merge(
            partition[["observation_id", "source_id", "dependency_group_id", "partition_name"]],
            on="observation_id",
            validate="one_to_one",
        )
        smart = smart[smart.partition_name.ne("test")].copy()
        reports, predictions = auxiliary_comparison(smart, auxiliary, protocol)
        summary = {
            "run_id": run_id,
            "quality": quality,
            "anchor_development_cycles": len(smart),
            "anchor_development_positives": int(smart.target_label.sum()),
            "external_data_read": False,
            "reserved_smart_test_used": False,
            "independent_refrigeration_reference_claimed": False,
            "results": reports,
        }
        files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(
                output / "predictions.csv",
                predictions.to_csv(index=False, lineterminator="\n").encode(),
            ),
            save_immutable(output / "washer-quality.json", document_bytes(quality)),
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
                        "statistic_name": "auxiliary_mechanical_ablation",
                        "feature_name": metric,
                        "numeric_value": report[metric],
                        "sample_count": len(smart),
                        "group_count": int(smart.dependency_group_id.nunique()),
                        "dimensions_json": {
                            "model_id": report["model_id"],
                            "auxiliary_mass": report["auxiliary_mass"],
                            "reference_policy": report["auxiliary_reference_policy"],
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
                    "comparisons": len(reports),
                    "auxiliary_cycles": len(auxiliary),
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
    main()
