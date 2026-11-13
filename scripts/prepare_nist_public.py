"""Persist inspected NIST public summaries; no acquisition or external side effects."""

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
from compressor_anomaly_detection_ml.nist_refrigeration import nist_table
from compressor_anomaly_detection_ml.public_acquisition import artifact_row, source_row
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_bridges import file_manifest


def main():
    source = next(
        row
        for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        if row["source_id"] == "nist_hvac"
    )
    folder = Path("data/public/raw/nist_hvac")
    frame, names, quality = nist_table(folder / "nist-fdd-14-16seer.xlsx")
    files = file_manifest(
        [folder / "nist-fdd-14-16seer.xlsx", folder / "description-14-16seer.xlsx"]
    )
    code = (
        Path(__file__).read_bytes()
        + Path("src/compressor_anomaly_detection_ml/nist_refrigeration.py").read_bytes()
    )
    digest = hashlib.sha256(code + document_bytes(files)).hexdigest()
    run_id = "nist-prepare-" + digest[:20]
    output = Path("reports/research") / run_id
    now = datetime.now(UTC).replace(tzinfo=None)
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
        if previous:
            if previous != "completed":
                raise DataValidationError("Incomplete NIST preparation requires inspection.")
            print((output / "import.json").read_text(encoding="utf-8"))
            return
        artifacts = [
            artifact_row(
                source,
                file,
                "raw" if file["relative_path"].endswith("nist-fdd-14-16seer.xlsx") else "metadata",
                {
                    "primary_url": source["primary_url"],
                    "license_url": source["license_url"],
                    "provider_checksum_available": False,
                    "hypotheses": ["H03", "H05", "H07"],
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
                        "stage": "public_transfer_input",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "feature_contract": "nist-main-v1-" + digest[:12],
                            "test_policy": (
                                "14 SEER train, 16 SEER validation; full equipment strata"
                            ),
                            "label_flag_is_inverted": True,
                        },
                        "input_manifest_json": {"provenance_nodes": roots},
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ],
            },
            scope="public",
        )
        started = True
        observations, labels, values = [], [], []
        for row in frame.to_dict("records"):
            obs_id = row["observation_id"]
            reference = None if pd.isna(row["target_label"]) else int(row["target_label"])
            metadata = {
                key: None if pd.isna(row[key]) else row[key]
                for key in (
                    "Filename",
                    "provider_row",
                    "equipment_stratum",
                    "Long/Short (0/1)",
                    "EF",
                    "CF",
                    "LL",
                    "UC/OC",
                )
            }
            observations.append(
                {
                    "observation_id": obs_id,
                    "source_id": source["source_id"],
                    "source_version": source["source_version"],
                    "original_id": "excel-row:" + str(row["provider_row"]),
                    "analysis_unit": "steady_state_summary",
                    "dependency_group_id": row["group_id"],
                    "equipment_id": None,
                    "started_at": None,
                    "ended_at": None,
                    "quality_status": "valid",
                    "condition_json": metadata,
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
                    "label_version": "nist-provider-nf-inverted-v1",
                    "original_label": None if reference is None else str(1 - reference),
                    "target_label": reference,
                    "label_status": row["label_status"],
                    "method": "documented NIST NF flag: 1=no fault, 0=physical test fault",
                    "confidence": None,
                    "evidence_artifact_id": artifacts[0]["artifact_id"],
                    "evidence_json": {
                        "label_column": "NF(NO=0,Yes=1)",
                        "missing_reference_preserved": reference is None,
                        "scope": "heat-pump system fault, not necessarily compressor defect",
                    },
                    "recorded_at": now,
                }
            )
            for name in names:
                values.append(
                    {
                        "observation_id": obs_id,
                        "feature_contract_version": "nist-main-v1-" + digest[:12],
                        "feature_name": name,
                        "numeric_value": float(row[name]),
                        "unit": "degC"
                        if name.endswith("_c")
                        else "g/s"
                        if name.endswith("_gs")
                        else "kW",
                        "value_status": "derived",
                        "definition_json": {
                            "provider_units_converted": True,
                            "outdoor_power_not_compressor_power": True,
                            "no_label_columns_as_predictors": True,
                        },
                        "run_id": run_id,
                    }
                )
        for offset in range(0, len(observations), 500):
            repository.persist(
                {
                    "study_observations": observations[offset : offset + 500],
                    "study_labels": labels[offset : offset + 500],
                },
                scope="public",
            )
        for offset in range(0, len(values), 2500):
            repository.persist(
                {"study_feature_values": values[offset : offset + 2500]}, scope="public"
            )
            print(
                json.dumps(
                    {
                        "source": "nist_hvac",
                        "values_persisted": min(offset + 2500, len(values)),
                        "total": len(values),
                    }
                ),
                flush=True,
            )
        output.mkdir(parents=True, exist_ok=False)
        report = {
            "run_id": run_id,
            "quality": quality,
            "observations": len(observations),
            "feature_values": len(values),
            "external_data_read": False,
            "files": files,
        }
        file = save_immutable(output / "import.json", document_bytes(report))
        repository.persist(
            {"study_artifacts": [artifact_row(source, file, "report", {"run_id": run_id}, now)]},
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        started = False
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "observations": len(observations),
                    "feature_values": len(values),
                    "indeterminate_rows": quality["indeterminate_rows"],
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
