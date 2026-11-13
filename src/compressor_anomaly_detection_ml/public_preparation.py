"""Source-specific preparation, persisted before any final-model training."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import save_immutable
from .domain import DataValidationError
from .public_acquisition import artifact_row
from .public_importers import rwth_tables, smart_pdm_tables

SOURCES = {"smart_pdm": ("7245198", smart_pdm_tables), "rwth_r290": ("22097811", rwth_tables)}


def prepare_source(source_id: str, revision: str = "v1", root: Path = Path(".")) -> dict:
    if source_id not in SOURCES:
        raise DataValidationError("This importer accepts only verified public source tables.")
    version, loader = SOURCES[source_id]
    registry = json.loads((root / "config/dataset-sources.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == source_id)
    folder = root / "data/public/raw" / source_id / version
    frame, names, quality = loader(folder)
    engine = create_engine_for_url(Settings.from_env().database_url)
    try:
        repository = ResearchRepository(engine)
        artifacts_table = repository.tables["study_artifacts"]
        with engine.connect() as connection:
            raw_artifacts = [
                dict(row)
                for row in connection.execute(
                    select(artifacts_table).where(
                        artifacts_table.c.source_id == source_id,
                        artifacts_table.c.source_version == version,
                        artifacts_table.c.artifact_kind == "raw",
                    )
                ).mappings()
            ]
        wanted = (
            {"fridge_metadata.csv", "F_ExtractedFeatures.csv"}
            if source_id == "smart_pdm"
            else {"thermodynamic_averaged_with_uncertainty.csv", "rms_by_charge.csv"}
        )
        raw_artifacts = [row for row in raw_artifacts if Path(row["relative_path"]).name in wanted]
        if len(raw_artifacts) != 2:
            raise DataValidationError(
                "Both verified raw tables must be registered before preparation."
            )
        for artifact in raw_artifacts:
            if (
                hashlib.sha256(Path(artifact["relative_path"]).read_bytes()).hexdigest()
                != artifact["content_sha256"]
            ):
                raise DataValidationError("Raw public input changed since acquisition.")
        code_hash = hashlib.sha256(
            Path(__file__).read_bytes()
            + Path(__file__).with_name("public_importers.py").read_bytes()
        ).hexdigest()
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "revision": revision,
                    "code": code_hash,
                    "inputs": sorted(row["content_sha256"] for row in raw_artifacts),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        run_id = source_id + "-prepare-" + fingerprint[:20]
        contract = source_id + "-source-v1-" + fingerprint[:12]
        output = root / "reports/research" / run_id
        runs = repository.tables["study_runs"]
        with engine.connect() as connection:
            previous = connection.execute(
                select(runs.c.status).where(runs.c.run_id == run_id)
            ).scalar_one_or_none()
        if previous:
            if previous == "completed" and (output / "import.json").exists():
                return json.loads((output / "import.json").read_text(encoding="utf-8"))
            raise DataValidationError(
                "Incomplete prior preparation exists; inspect it and use a new revision."
            )
        now = datetime.now(UTC).replace(tzinfo=None)
        roots = [
            {
                "node_id": row["artifact_id"],
                "data_origin": "public_measured",
                "source_id": source_id,
                "source_version": version,
                "parent_ids": [],
                "content_sha256": row["content_sha256"],
            }
            for row in raw_artifacts
        ]
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_source_preparation",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "code_fingerprint": code_hash,
                        "configuration_json": {
                            "revision": revision,
                            "feature_contract_version": contract,
                        },
                        "input_manifest_json": {"provenance_nodes": roots},
                    }
                ]
            },
            scope="public",
        )
        observations, labels, values = [], [], []
        definitions = {
            name: {
                "provider_feature_name": name,
                "source_id": source_id,
                "physical_equivalence_to_other_sources": "not_assumed",
                "role": "condition_only"
                if name in {"refrigerant_charge_g", "f_comp_set_Hz"}
                else "research_candidate",
                "signal_semantics": "published cycle statistic; vibration scale unconfirmed"
                if source_id == "smart_pdm"
                else "thermodynamic condition or temporal RMS, band 10-1000 Hz",
            }
            for name in names
        }
        metadata_artifact = next(
            (
                row["artifact_id"]
                for row in raw_artifacts
                if Path(row["relative_path"]).name == "fridge_metadata.csv"
            ),
            None,
        )
        for row in frame.to_dict(orient="records"):
            obs_id = row["observation_id"]
            observations.append(
                {
                    "observation_id": obs_id,
                    "source_id": source_id,
                    "source_version": version,
                    "original_id": row["original_id"],
                    "analysis_unit": "appliance_cycle"
                    if source_id == "smart_pdm"
                    else "operating_condition",
                    "dependency_group_id": row["candidate_group"],
                    "equipment_id": None,
                    "started_at": row.get("started_at").to_pydatetime()
                    if row.get("started_at") is not None
                    else None,
                    "ended_at": row.get("ended_at").to_pydatetime()
                    if row.get("ended_at") is not None
                    else None,
                    "quality_status": "valid",
                    "condition_json": {
                        "group_status": "candidate_temporal_block"
                        if source_id == "smart_pdm"
                        else "provider_measurement_session",
                        "brand": row.get("brand"),
                        "model": row.get("model"),
                        "measurement_session": row.get("measurement_id"),
                    },
                    "provenance_json": {
                        "provenance_nodes": [
                            *roots,
                            {
                                "node_id": obs_id,
                                "data_origin": "derived",
                                "parent_ids": [node["node_id"] for node in roots],
                            },
                        ]
                    },
                    "created_at": now,
                }
            )
            labels.append(
                {
                    "observation_id": obs_id,
                    "label_version": "provider-reference-v1"
                    if source_id == "smart_pdm"
                    else "unlabelled-condition-v1",
                    "original_label": row.get("failure"),
                    "target_label": int(row["target_label"]) if source_id == "smart_pdm" else None,
                    "label_status": "reference" if source_id == "smart_pdm" else "indeterminate",
                    "method": "provider appliance-maintenance assessment"
                    if source_id == "smart_pdm"
                    else "no binary failure label supplied; charge is an experimental condition",
                    "confidence": None,
                    "evidence_artifact_id": metadata_artifact,
                    "evidence_json": {
                        "scope": "appliance-level, not a compressor-specific diagnosis"
                    }
                    if source_id == "smart_pdm"
                    else {"binary_label_not_invented": True},
                    "recorded_at": now,
                }
            )
            for name in names:
                unit = None
                if source_id == "rwth_r290":
                    unit = (
                        "m/s²"
                        if name.startswith("compressor_rms_")
                        else "degC"
                        if name.startswith("T_") and name.endswith("_C")
                        else None
                    )
                values.append(
                    {
                        "observation_id": obs_id,
                        "feature_contract_version": contract,
                        "feature_name": name,
                        "numeric_value": float(row[name]),
                        "unit": unit,
                        "value_status": "derived",
                        "definition_json": definitions[name],
                        "run_id": run_id,
                    }
                )
        try:
            repository.persist(
                {"study_observations": observations, "study_labels": labels}, scope="public"
            )
            for start in range(0, len(values), 2500):
                repository.persist(
                    {"study_feature_values": values[start : start + 2500]}, scope="public"
                )
                print(
                    json.dumps(
                        {
                            "source": source_id,
                            "values_persisted": min(start + 2500, len(values)),
                            "total": len(values),
                        }
                    ),
                    flush=True,
                )
            report = {
                "run_id": run_id,
                "source_id": source_id,
                "source_version": version,
                "feature_contract_version": contract,
                "quality": quality,
                "observations": len(observations),
                "feature_values": len(values),
                "labels": len(labels),
                "external_data_read": False,
                "input_sha256": [row["content_sha256"] for row in raw_artifacts],
            }
            output.mkdir(parents=True, exist_ok=False)
            document = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
            file = save_immutable(output / "import.json", document)
            stat_rows = []
            for key, value in quality.items():
                if isinstance(value, (int, float, bool)):
                    stat_rows.append(
                        {
                            "run_id": run_id,
                            "statistic_key": source_id + ":" + key,
                            "source_id": source_id,
                            "source_version": version,
                            "statistic_name": "source_import_audit",
                            "feature_name": key,
                            "numeric_value": float(value),
                            "sample_count": len(frame),
                            "group_count": int(frame.candidate_group.nunique()),
                            "dimensions_json": {"quality_report": str(output / "import.json")},
                        }
                    )
            repository.persist(
                {
                    "study_artifacts": [
                        artifact_row(source, file, "report", {"run_id": run_id}, now)
                    ],
                    "study_statistics": stat_rows,
                },
                scope="public",
            )
            repository.finish_run(run_id, "completed")
            return report
        except Exception as error:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
            raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    import sys

    print(json.dumps(prepare_source(sys.argv[1]), indent=2, ensure_ascii=False))
