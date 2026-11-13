"""Freeze the public multibase candidate, its training snapshot and relational lineage."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from compressor_anomaly_detection_ml.config import Settings
from compressor_anomaly_detection_ml.cycle_candidate import CONTRACT, train_cycle_candidate
from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.datasets import save_immutable
from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.ml.artifacts import save_artifact
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_importers import smart_pdm_tables
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_bridges import file_manifest
from compressor_anomaly_detection_ml.transfer_novelty import META_NAMES
from compressor_anomaly_detection_ml.transfer_temporal import cycle_context


def main():
    protocol_path = Path("config/cycle-candidate-freeze.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["external_data_allowed"]:
        raise DataValidationError("Local data cannot enter the public candidate.")
    partition = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
    auxiliary_path = Path(protocol["auxiliary_vectors"])
    confirmation_path = Path("reports/research") / protocol["confirmation_run"] / "predictions.csv"
    folder = Path("data/public/raw/smart_pdm/7245198")
    input_files = file_manifest(
        [
            partition,
            auxiliary_path,
            confirmation_path,
            folder / "fridge_metadata.csv",
            folder / "F_ExtractedFeatures.csv",
        ]
    )
    original = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
    if hashlib.sha256(partition.read_bytes()).hexdigest() != original["parent_partitions_sha256"]:
        raise DataValidationError("Original reservations changed.")
    code_files = [Path(__file__)] + [
        Path("src/compressor_anomaly_detection_ml") / (name + ".py")
        for name in (
            "cycle_candidate",
            "transfer_temporal",
            "temporal_confirmation",
            "transfer_novelty",
            "transfer_analysis",
            "public_importers",
            "ml/artifacts",
        )
    ]
    code = b"\n".join(path.read_bytes() for path in code_files)
    digest = hashlib.sha256(
        code + protocol_path.read_bytes() + document_bytes(input_files)
    ).hexdigest()
    run_id = "cycle-freeze-" + digest[:20]
    dataset_version = "cycle-reference-" + digest[:20]
    output = Path("reports/research") / run_id
    settings = Settings.from_env()
    engine = create_engine_for_url(settings.database_url)
    repository = ResearchRepository(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    running = False
    try:
        with engine.connect() as connection:
            previous = connection.execute(
                select(repository.tables["study_runs"].c.status).where(
                    repository.tables["study_runs"].c.run_id == run_id
                )
            ).scalar_one_or_none()
            parent = connection.execute(
                select(repository.tables["study_runs"].c.status).where(
                    repository.tables["study_runs"].c.run_id == protocol["confirmation_run"]
                )
            ).scalar_one()
            registered = (
                connection.execute(select(repository.tables["study_artifacts"])).mappings().all()
            )
        if previous:
            if previous != "completed":
                raise DataValidationError("Inspect incomplete freeze before retrying.")
            print((output / "manifest.json").read_text(encoding="utf-8"))
            return
        if parent != "completed":
            raise DataValidationError("Confirmation has not completed.")
        for path in (auxiliary_path, confirmation_path):
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if not any(
                r["relative_path"] == path.as_posix() and r["content_sha256"] == sha
                for r in registered
            ):
                raise DataValidationError("Registered development artifact hash differs.")
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_cycle_freeze",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {"files": input_files, "external_data_read": False},
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
        smart = cycle_context(
            smart[smart.partition_name.ne("test")].copy(), **protocol["cycle_context"]
        )
        smart = smart[smart.duration_relative_history.notna()].copy().reset_index(drop=True)
        auxiliary = pd.read_csv(auxiliary_path)
        scores = pd.read_csv(confirmation_path)
        scores = scores[
            (scores.variant == protocol["variant"]["id"])
            & (scores.shuffle_seed == -1)
            & (scores["mode"] == "raw_fixed")
        ]
        frozen = pd.concat(
            [
                smart[
                    [
                        "observation_id",
                        "source_id",
                        "dependency_group_id",
                        "target_label",
                        "duration_relative_history",
                    ]
                ],
                auxiliary,
            ],
            ignore_index=True,
        )
        training_file = save_immutable(
            output / "training-inputs.csv", frozen.to_csv(index=False).encode()
        )
        artifact, smart_meta = train_cycle_candidate(smart, auxiliary, scores, protocol)
        artifact["version"] = run_id
        artifact["dataset_version"] = dataset_version
        artifact_path, artifact_sha = save_artifact(artifact, settings.model_dir, run_id)
        manifest = {
            "run_id": run_id,
            "version": run_id,
            "dataset_version": dataset_version,
            "contract_version": CONTRACT,
            "artifact_path": artifact_path.as_posix(),
            "artifact_sha256": artifact_sha,
            "training_inputs": training_file,
            "smart_training_cases": len(smart),
            "auxiliary_training_cases": len(auxiliary),
            "source_counts": {
                "smart_pdm": len(smart),
                **auxiliary.source_id.value_counts().to_dict(),
            },
            "feature_names": META_NAMES,
            "threshold": artifact["threshold"],
            "status": "frozen_public_research_candidate",
            "public_test_used_at_freeze": False,
            "external_data_read": False,
            "scope": protocol["scope"],
            "probability_support": protocol["probability_support"],
            "local_portability_status": protocol["local_portability_status"],
        }
        registry = json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        sources = {row["source_id"]: row for row in registry}
        roots = [
            {
                "node_id": source,
                "data_origin": "public_measured",
                "parent_ids": [],
                "source_id": source,
                "source_version": sources[source]["source_version"],
            }
            for source in ["smart_pdm", *protocol["variant"]["sources"]]
        ]
        observations, labels, feature_rows = [], [], []
        for _, row in auxiliary.iterrows():
            source = sources[row.source_id]
            original_id = "normality-case:" + row.experiment_id
            obs = row.source_id + ":case:" + hashlib.sha256(original_id.encode()).hexdigest()[:32]
            row_root = next(root for root in roots if root["node_id"] == row.source_id)
            observations.append(
                {
                    "observation_id": obs,
                    "source_id": row.source_id,
                    "source_version": source["source_version"],
                    "original_id": original_id,
                    "analysis_unit": "experiment_summary",
                    "dependency_group_id": row.source_id + ":reference-collection",
                    "equipment_id": None,
                    "started_at": None,
                    "ended_at": None,
                    "quality_status": "valid",
                    "condition_json": {"experiment_id": row.experiment_id},
                    "provenance_json": {
                        "provenance_nodes": [row_root],
                        "parent_run": "temporal-round7-c2f700026e1cc1c77edd",
                        "aggregation": "median of group-cross-fitted per-row normality descriptors",
                        "independence": "conservative whole-source group; no equipment invented",
                    },
                    "created_at": now,
                }
            )
            labels.append(
                {
                    "observation_id": obs,
                    "label_version": CONTRACT,
                    "original_label": str(int(row.target_label)),
                    "target_label": int(row.target_label),
                    "label_status": "reference",
                    "method": "unchanged label-consistent original experiment reference",
                    "confidence": None,
                    "evidence_artifact_id": None,
                    "evidence_json": {
                        "input_artifact": auxiliary_path.as_posix(),
                        "experiment_id": row.experiment_id,
                        "component_specific_fault": False,
                    },
                    "recorded_at": now,
                }
            )
            for name in META_NAMES:
                feature_rows.append(
                    {"observation_id": obs, "feature_name": name, "numeric_value": float(row[name])}
                )
        for (_, row), (_, meta) in zip(smart.iterrows(), smart_meta.iterrows(), strict=True):
            for name in META_NAMES:
                feature_rows.append(
                    {
                        "observation_id": row.observation_id,
                        "feature_name": name,
                        "numeric_value": float(meta[name]),
                    }
                )
        feature_contract = CONTRACT + "-" + digest[:12]
        feature_rows = [
            {
                **row,
                "feature_contract_version": feature_contract,
                "unit": "1",
                "value_status": "derived",
                "run_id": run_id,
                "definition_json": {
                    "role": "training input, held-group normality",
                    "contract": CONTRACT,
                    "physical_cross_source_correlation": False,
                },
            }
            for row in feature_rows
        ]
        repository.persist(
            {
                "study_observations": observations,
                "study_labels": labels,
                "study_feature_values": feature_rows,
            },
            scope="public",
        )
        with engine.connect() as connection:
            label_table = repository.tables["study_labels"]
            all_labels = (
                connection.execute(
                    select(label_table).where(
                        label_table.c.label_version == CONTRACT,
                        label_table.c.observation_id.in_(
                            [row["observation_id"] for row in observations]
                        ),
                    )
                )
                .mappings()
                .all()
            )
            parent_members = repository.tables["study_dataset_members"]
            original_ids = dict(
                connection.execute(
                    select(parent_members.c.observation_id, parent_members.c.label_id).where(
                        parent_members.c.dataset_version == "public-study-87d04baa2e265aeb"
                    )
                ).all()
            )
        group_map = dict(zip(smart.observation_id, smart.dependency_group_id, strict=True))
        label_map = {obs: original_ids[obs] for obs in smart.observation_id}
        group_map.update({r["observation_id"]: r["dependency_group_id"] for r in observations})
        label_map.update(
            {
                r["observation_id"]: r["label_id"]
                for r in all_labels
                if r["label_version"] == CONTRACT
            }
        )
        manifest["feature_contract_version"] = feature_contract
        files = [training_file, save_immutable(output / "manifest.json", document_bytes(manifest))]
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(sources["smart_pdm"], file, "report", {"run_id": run_id}, now)
                    for file in files
                ],
                "study_datasets": [
                    {
                        "dataset_version": dataset_version,
                        "status": "frozen",
                        "manifest_sha256": hashlib.sha256(document_bytes(manifest)).hexdigest(),
                        "feature_contract_json": {
                            "version": feature_contract,
                            "features": META_NAMES,
                            "source_specific_encoders": True,
                        },
                        "manifest_json": {**manifest, "provenance_nodes": roots},
                        "run_id": run_id,
                        "created_at": now,
                    }
                ],
                "study_dataset_members": [
                    {
                        "dataset_version": dataset_version,
                        "observation_id": obs,
                        "label_id": label_map[obs],
                        "partition_name": "train",
                        "dependency_group_id": group,
                    }
                    for obs, group in group_map.items()
                ],
                "ml_models": [
                    {
                        "name": "public_cycle_reference_forest",
                        "version": run_id,
                        "processing_version": CONTRACT,
                        "document": manifest,
                    }
                ],
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        running = False
        print(json.dumps(manifest, indent=2))
    except Exception as error:
        if running:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
