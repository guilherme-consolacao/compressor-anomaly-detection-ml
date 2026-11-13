"""Register additional source audits and expose the frozen test scores for BI."""

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
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_bridges import file_manifest


def main():
    now = datetime.now(UTC).replace(tzinfo=None)
    source_folders = {
        "smart_manufacturing": Path(
            "data/public/raw/smart_manufacturing/ae6d6bf256e80c0044dc52aafec32b0378eec5f9"
        ),
        "ornl_co2": Path("data/public/raw/ornl_co2/13232627.v1"),
    }
    public_test = Path("reports/research/cycle-freeze-8af6bb44817d037a836c/public-test")
    paths = [Path("config/external-cycle-protocol.json"), Path("docs/cycle-candidate-report.md")]
    source_files = {
        source: file_manifest([p for p in folder.iterdir() if p.is_file()])
        for source, folder in source_folders.items()
    }
    document_files = file_manifest(paths)
    code = Path(__file__).read_bytes()
    digest = hashlib.sha256(
        code + document_bytes(source_files) + document_bytes(document_files)
    ).hexdigest()
    run_id = "research-handoff-" + digest[:20]
    contract = "frozen-test-score-" + digest[:16]
    engine = create_engine_for_url(Settings.from_env().database_url)
    repository = ResearchRepository(engine)
    running = False
    try:
        with engine.connect() as connection:
            runs = repository.tables["study_runs"]
            previous = connection.execute(
                select(runs.c.status).where(runs.c.run_id == run_id)
            ).scalar_one_or_none()
            artifacts = (
                connection.execute(select(repository.tables["study_artifacts"])).mappings().all()
            )
        if previous:
            if previous != "completed":
                raise DataValidationError("Inspect incomplete research handoff first.")
            print(json.dumps({"run_id": run_id, "status": "already_completed"}))
            return
        score_path = public_test / "predictions.csv"
        score_sha = hashlib.sha256(score_path.read_bytes()).hexdigest()
        if not any(
            r["relative_path"] == score_path.as_posix() and r["content_sha256"] == score_sha
            for r in artifacts
        ):
            raise DataValidationError("Frozen reserved-test score artifact changed.")
        registry = json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        sources = {r["source_id"]: r for r in registry}
        repository.persist(
            {
                "study_sources": [source_row(sources[source], now) for source in source_folders],
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_research_handoff",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "external_data_read": False,
                            "test_score_role": "immutable outputs; excluded from training",
                        },
                        "input_manifest_json": {
                            "new_source_audits": source_files,
                            "documents": document_files,
                            "score_sha256": score_sha,
                        },
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ],
            },
            scope="public",
        )
        running = True
        file_records = [
            artifact_row(
                sources[source],
                file,
                "source_audit",
                {"run_id": run_id, "used_in_model": False},
                now,
            )
            for source, files in source_files.items()
            for file in files
        ]
        file_records.extend(
            artifact_row(sources["smart_pdm"], file, "report", {"run_id": run_id}, now)
            for file in document_files
        )
        existing = {r["artifact_id"]: dict(r) for r in artifacts}
        file_records = [existing.get(r["artifact_id"], r) for r in file_records]
        predictions = pd.read_csv(score_path)
        if predictions.observation_id.duplicated().any() or set(predictions.source_id) != {
            "smart_pdm",
            "tri_hp_faults",
        }:
            raise DataValidationError("Frozen test score identities or source scope changed.")
        tri = sources["tri_hp_faults"]
        root = {
            "node_id": "tri",
            "source_id": tri["source_id"],
            "source_version": tri["source_version"],
            "data_origin": "public_measured",
            "parent_ids": [],
        }
        observations, labels, values = [], [], []
        for row in predictions.itertuples():
            if row.source_id == "tri_hp_faults":
                observations.append(
                    {
                        "observation_id": row.observation_id,
                        "source_id": row.source_id,
                        "source_version": tri["source_version"],
                        "original_id": "normality-case:" + row.observation_id.rsplit(":", 1)[-1],
                        "analysis_unit": "experiment_summary",
                        "dependency_group_id": row.group,
                        "equipment_id": None,
                        "started_at": None,
                        "ended_at": None,
                        "quality_status": "valid",
                        "condition_json": {
                            "reserved_condition": row.observation_id,
                            "role": "test only",
                        },
                        "provenance_json": {
                            "provenance_nodes": [root],
                            "parent_evaluation": "cycle-test-9446332f4eb72f0bb4de",
                            "source_clock": "unknown timezone; no UTC fabricated",
                        },
                        "created_at": now,
                    }
                )
                labels.append(
                    {
                        "observation_id": row.observation_id,
                        "label_version": "reserved-tri-oc-v1",
                        "original_label": "OC",
                        "target_label": 1,
                        "label_status": "reference",
                        "method": "original reserved overcharge experiment",
                        "confidence": None,
                        "evidence_artifact_id": None,
                        "evidence_json": {"provider": tri["primary_url"], "test_only": True},
                        "recorded_at": now,
                    }
                )
            outputs = {
                "raw_reference_score": row.score,
                "predicted_reference_class": int(row.score >= 0.5),
            }
            if pd.notna(row.experimental_reference_probability):
                outputs["experimental_reference_probability"] = (
                    row.experimental_reference_probability
                )
            for name, value in outputs.items():
                values.append(
                    {
                        "observation_id": row.observation_id,
                        "feature_contract_version": contract,
                        "feature_name": name,
                        "numeric_value": float(value),
                        "unit": "1",
                        "value_status": "derived",
                        "definition_json": {
                            "model_version": "cycle-freeze-8af6bb44817d037a836c",
                            "parent_evaluation": "cycle-test-9446332f4eb72f0bb4de",
                            "evaluation_role": "consumed reserved public test",
                            "not_a_training_input": True,
                            "probability_scope": "SMART cohort; calibration support limited",
                        },
                        "run_id": run_id,
                    }
                )
        assert (
            len(values)
            == 2 * len(predictions) + predictions.experimental_reference_probability.notna().sum()
        )
        repository.persist(
            {
                "study_artifacts": file_records,
                "study_observations": observations,
                "study_feature_values": values,
                "study_labels": labels,
            },
            scope="public",
        )
        output = Path("reports/research") / run_id / "summary.json"
        report = {
            "run_id": run_id,
            "new_audited_sources": list(source_folders),
            "registered_files": len(file_records),
            "frozen_test_cases": len(predictions),
            "frozen_test_derived_values": len(values),
            "feature_contract_version": contract,
            "external_data_read": False,
        }
        file = save_immutable(output, document_bytes(report))
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(sources["smart_pdm"], file, "report", {"run_id": run_id}, now)
                ]
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        running = False
        print(json.dumps(report, indent=2))
    except Exception as error:
        if running:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
