"""Make new reservations and shared public features queryable in the research DB."""

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
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_bridges import (
    refrigeration_common,
    rwth_spectral_table,
)
from compressor_anomaly_detection_ml.transfer_inputs import tri_hp_main


def main():
    parent = Path("reports/research/bridge-round2-9154a7b7f7ac5737b9e7")
    parent_report = json.loads((parent / "summary.json").read_text(encoding="utf-8"))
    partition = pd.read_csv(parent / "partitions.csv")
    protocol = json.loads((parent / "protocol.json").read_text(encoding="utf-8"))
    partition_hash = hashlib.sha256((parent / "partitions.csv").read_bytes()).hexdigest()
    run_id = (
        "bridge-materialize-"
        + hashlib.sha256(Path(__file__).read_bytes() + partition_hash.encode()).hexdigest()[:20]
    )
    dataset_version = "thermal-references-" + partition_hash[:16]
    output = Path("reports/research") / run_id
    engine = create_engine_for_url(Settings.from_env().database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    started = False
    try:
        repository = ResearchRepository(engine)
        with engine.connect() as connection:
            runs = repository.tables["study_runs"]
            if (
                connection.execute(
                    select(runs.c.status).where(runs.c.run_id == parent_report["run_id"])
                ).scalar_one()
                != "completed"
            ):
                raise DataValidationError("Only a completed public bridge can be materialized.")
            previous = connection.execute(
                select(runs.c.status).where(runs.c.run_id == run_id)
            ).scalar_one_or_none()
            artifacts = [
                dict(row)
                for row in connection.execute(
                    select(repository.tables["study_artifacts"]).where(
                        repository.tables["study_artifacts"].c.source_id.in_(
                            ["tri_hp_faults", "nist_hvac", "rwth_r290"]
                        ),
                        repository.tables["study_artifacts"].c.artifact_kind == "raw",
                    )
                ).mappings()
            ]
            labels = {
                row["observation_id"]: row["label_id"]
                for row in connection.execute(
                    select(
                        repository.tables["study_labels"].c.observation_id,
                        repository.tables["study_labels"].c.label_id,
                    ).where(
                        repository.tables["study_labels"].c.observation_id.in_(
                            partition.observation_id.tolist()
                        )
                    )
                ).mappings()
            }
        if previous:
            if previous != "completed":
                raise DataValidationError("Inspect incomplete materialization before retrying.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        if len(labels) != len(partition) or partition.observation_id.duplicated().any():
            raise DataValidationError(
                "Each reserved observation needs one registered label version."
            )
        roots = [
            {
                "node_id": row["artifact_id"],
                "source_id": row["source_id"],
                "source_version": row["source_version"],
                "data_origin": "public_measured",
                "parent_ids": [],
                "content_sha256": row["content_sha256"],
            }
            for row in artifacts
        ]
        manifest = {
            "parent_bridge_run": parent_report["run_id"],
            "partitions_sha256": partition_hash,
            "public_only": True,
            "external_data_read": False,
            "provenance_nodes": [
                *roots,
                {
                    "node_id": dataset_version,
                    "data_origin": "derived",
                    "parent_ids": [node["node_id"] for node in roots],
                },
            ],
        }
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_transfer_materialize",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "dataset_version": dataset_version,
                            "fitting_performed": False,
                        },
                        "input_manifest_json": manifest,
                        "code_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    }
                ],
                "study_datasets": [
                    {
                        "dataset_version": dataset_version,
                        "status": "research",
                        "manifest_sha256": hashlib.sha256(document_bytes(manifest)).hexdigest(),
                        "feature_contract_json": {
                            "shared_thermal_features": protocol["shared_thermal_features"],
                            "scope": (
                                "refrigeration line/saturation temperatures and mass flow; "
                                "not carcass input"
                            ),
                        },
                        "manifest_json": manifest,
                        "run_id": run_id,
                        "created_at": now,
                    }
                ],
            },
            scope="public",
        )
        started = True
        members = [
            {
                "dataset_version": dataset_version,
                "observation_id": row.observation_id,
                "label_id": labels[row.observation_id],
                "partition_name": row.partition_name,
                "dependency_group_id": row.group_id,
            }
            for row in partition.itertuples()
        ]
        for offset in range(0, len(members), 1000):
            repository.persist(
                {"study_dataset_members": members[offset : offset + 1000]}, scope="public"
            )
        rwth, _ = rwth_spectral_table(Path("data/public/raw/rwth_r290/22097811"))
        tri, _ = tri_hp_main(
            Path(
                "data/public/raw/tri_hp_faults/5155136.v1/H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
            )
        )
        tri, _ = refrigeration_common(tri, "tri_hp_faults")
        tri["observation_id"] = (
            "tri_hp_faults:5155136.v1:" + tri.sheet + ":" + tri.provider_row.astype(str)
        )
        feature_rows = []
        for frame, names, contract in (
            (
                rwth,
                [
                    name
                    for name in rwth
                    if name.startswith("psd_")
                    or name.startswith("vibration_spectral_")
                    or name.startswith("vibration_band_fraction_")
                    or name == "compressor_rms_spatial"
                ],
                "rwth-common-spectra-v2",
            ),
            (tri, protocol["shared_thermal_features"], "tri-common-thermal-v2"),
        ):
            for row in frame.to_dict("records"):
                for name in names:
                    unit = (
                        "m/s²"
                        if "rms" in name
                        else "degC"
                        if name.endswith("_c")
                        else "g/s"
                        if name.endswith("_gs")
                        else "1"
                    )
                    feature_rows.append(
                        {
                            "observation_id": row["observation_id"],
                            "feature_contract_version": contract,
                            "feature_name": name,
                            "numeric_value": float(row[name]),
                            "unit": unit,
                            "value_status": "derived",
                            "definition_json": {
                                "parent_run": parent_report["run_id"],
                                "band_hz": [10, 1000] if contract.startswith("rwth") else None,
                                "hypothesis": (
                                    "shared representation; physical transfer not assumed"
                                ),
                            },
                            "run_id": run_id,
                        }
                    )
        for offset in range(0, len(feature_rows), 2500):
            repository.persist(
                {"study_feature_values": feature_rows[offset : offset + 2500]}, scope="public"
            )
        output.mkdir(parents=True, exist_ok=False)
        summary = {
            "run_id": run_id,
            "dataset_version": dataset_version,
            "members": len(members),
            "new_feature_values": len(feature_rows),
            "partitions_sha256": partition_hash,
            "external_data_read": False,
        }
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            if row["source_id"] == "rwth_r290"
        )
        file = save_immutable(output / "summary.json", document_bytes(summary))
        repository.persist(
            {"study_artifacts": [artifact_row(source, file, "report", {"run_id": run_id}, now)]},
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        started = False
        print(json.dumps(summary, indent=2))
    except Exception as error:
        if started:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
