"""Public-only partitioning and research; a failed feasibility gate never emits a model."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sqlalchemy import select

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import save_immutable
from .domain import DataValidationError
from .provenance import load_registry, validate_public_provenance


def document_bytes(document):
    return json.dumps(
        document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False, default=str
    ).encode()


def validate_partition(frame: pd.DataFrame) -> None:
    required = {"observation_id", "dependency_group_id", "partition_name", "data_origin"}
    if not required <= set(frame) or frame.empty or frame[list(required)].isna().any().any():
        raise DataValidationError("Partition identity, role, group and origin are required.")
    if frame.observation_id.duplicated().any():
        raise DataValidationError("An observation occurs more than once in the partition.")
    if set(frame.data_origin) != {"public_measured"}:
        raise DataValidationError("Public partitions cannot contain external or synthetic data.")
    if (frame.groupby("dependency_group_id").partition_name.nunique() > 1).any():
        raise DataValidationError("A dependency group crosses partition boundaries.")
    if not set(frame.partition_name) <= {"train", "validation", "test", "discovery"}:
        raise DataValidationError("Unknown public partition role.")


def week_groups(frame: pd.DataFrame) -> pd.Series:
    """Merge whole weeks touched by a cycle so overlapping cycles cannot cross a split."""
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        if parent[key] != key:
            parent[key] = find(parent[key])
        return parent[key]

    spans = []
    for start, end in zip(frame.started_at, frame.ended_at, strict=True):
        if pd.isna(start) or pd.isna(end) or end < start:
            raise DataValidationError("Cycle limits are required for dependency grouping.")
        days = pd.date_range(
            pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq="D"
        )
        keys = sorted(set(day.strftime("%G-%V") for day in days))
        for key in keys:
            parent[find(key)] = find(keys[0])
        spans.append(keys[0])
    return pd.Series(["smart_pdm:week-block:" + find(key) for key in spans], index=frame.index)


def make_partitions(frame: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    result = frame.copy()
    result["partition_name"] = "train"
    smart = result.loc[result.source_id == "smart_pdm"].copy()
    if not smart.empty:
        smart["dependency_group_id"] = week_groups(smart)
        result.loc[smart.index, "dependency_group_id"] = smart.dependency_group_id
        minimum = protocol["smart_min_positive_groups_per_partition"]
        if smart.loc[smart.target_label == 1].dependency_group_id.nunique() < 3 * minimum:
            raise DataValidationError("Insufficient positive independent groups for three roles.")
        found = False
        for attempt in range(1000):
            splitter = GroupShuffleSplit(
                n_splits=1, test_size=0.25, random_state=protocol["seed"] + attempt
            )
            rest, test = next(splitter.split(smart, groups=smart.dependency_group_id))
            splitter2 = GroupShuffleSplit(
                n_splits=1, test_size=0.34, random_state=protocol["seed"] + attempt
            )
            train_sub, validation_sub = next(
                splitter2.split(smart.iloc[rest], groups=smart.iloc[rest].dependency_group_id)
            )
            roles = {
                "train": smart.iloc[rest[train_sub]],
                "validation": smart.iloc[rest[validation_sub]],
                "test": smart.iloc[test],
            }
            train_supported = roles["train"].loc[
                roles["train"].target_label == 1
            ].dependency_group_id.nunique() >= protocol.get(
                "smart_min_training_positive_groups", minimum
            ) and roles["train"].target_label.sum() >= protocol.get(
                "smart_min_training_positive_examples", 1
            )
            if train_supported and all(
                set(part.target_label) == {0, 1}
                and part.loc[part.target_label == 1].dependency_group_id.nunique() >= minimum
                for part in roles.values()
            ):
                for role, part in roles.items():
                    result.loc[part.index, "partition_name"] = role
                result.attrs["selected_split_seed"] = protocol["seed"] + attempt
                found = True
                break
        if not found:
            raise DataValidationError(
                "Insufficient positive independent groups for the frozen public split."
            )
    kaist = result.source_id == "kaist"
    if kaist.any():
        for index, row in result.loc[kaist].iterrows():
            load = str(row["condition_json"]["load_nm"]) + "Nm"
            if load not in protocol["kaist_partitions"]:
                raise DataValidationError("KAIST load is absent from the frozen protocol.")
            result.loc[index, "partition_name"] = protocol["kaist_partitions"][load]
    for source in ["rwth_r290", "ult_freezers"]:
        subset = result.loc[result.source_id == source]
        groups = sorted(subset.dependency_group_id.unique())
        reserved = set(groups[2::3])
        result.loc[
            (result.source_id == source) & result.dependency_group_id.isin(reserved),
            "partition_name",
        ] = "validation"
    validate_partition(result)
    return result


def load_public(
    repository: ResearchRepository, allowed: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    observations = repository.tables["study_observations"]
    sources = repository.tables["study_sources"]
    labels = repository.tables["study_labels"]
    values = repository.tables["study_feature_values"]
    runs = repository.tables["study_runs"]
    with repository.engine.connect() as connection:
        frame = pd.DataFrame(
            connection.execute(
                select(
                    observations,
                    sources.c.data_origin,
                    labels.c.label_id,
                    labels.c.target_label,
                    labels.c.label_status,
                    labels.c.label_version,
                )
                .join(
                    sources,
                    (observations.c.source_id == sources.c.source_id)
                    & (observations.c.source_version == sources.c.source_version),
                )
                .join(labels, observations.c.observation_id == labels.c.observation_id)
                .where(sources.c.source_id.in_(allowed), sources.c.data_origin == "public_measured")
            ).mappings()
        )
        long = pd.DataFrame(
            connection.execute(
                select(values)
                .join(observations, values.c.observation_id == observations.c.observation_id)
                .join(runs, values.c.run_id == runs.c.run_id)
                .where(
                    observations.c.source_id.in_(allowed),
                    runs.c.data_scope == "public",
                    runs.c.status == "completed",
                    runs.c.stage.in_(["public_source_preparation", "sample_canonical_audit"]),
                )
            ).mappings()
        )
    if (
        frame.empty
        or set(frame.source_id) != set(allowed)
        or frame.observation_id.duplicated().any()
    ):
        raise DataValidationError(
            "All four audited sources with one explicit label version are required."
        )
    registry = load_registry(Path("config/dataset-sources.json"))
    for document in frame.provenance_json:
        validate_public_provenance(document["provenance_nodes"], registry)
    if long.duplicated(["observation_id", "feature_name"]).any():
        raise DataValidationError(
            "Multiple feature contracts found; select an explicit study revision."
        )
    if set(frame.observation_id) != set(long.observation_id):
        raise DataValidationError("Incomplete preparation cannot enter the public study.")
    return (
        frame.sort_values("observation_id").reset_index(drop=True),
        long.sort_values(["observation_id", "feature_name"]).reset_index(drop=True),
    )


def partition_public(root: Path = Path(".")) -> dict:
    protocol_path = root / "config/public-study-v1.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    engine = create_engine_for_url(Settings.from_env().database_url)
    try:
        repository = ResearchRepository(engine)
        frame, long = load_public(repository, protocol["allowed_sources"])
        inputs = {
            "observation_ids": sorted(frame.observation_id),
            "feature_runs": sorted(long.run_id.unique()),
            "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            "label_policy_sha256": hashlib.sha256(
                (root / "config/label-policy-v1.json").read_bytes()
            ).hexdigest(),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        version = "public-study-" + hashlib.sha256(document_bytes(inputs)).hexdigest()[:16]
        output = root / "reports/research" / version
        if (output / "partitions.json").exists():
            return json.loads((output / "partitions.json").read_text(encoding="utf-8"))
        partitioned = make_partitions(frame, protocol)
        roots = {}
        for provenance in frame.provenance_json:
            for node in provenance["provenance_nodes"]:
                if node["data_origin"] != "derived":
                    roots[node["node_id"]] = node
        manifest = {
            **inputs,
            "provenance_nodes": list(roots.values()),
            "purpose": "public research snapshot; not final eligible training dataset",
            "external_data_read": False,
            "partition_members_sha256": hashlib.sha256(
                document_bytes(
                    partitioned[
                        ["observation_id", "dependency_group_id", "partition_name", "label_id"]
                    ]
                    .sort_values("observation_id")
                    .to_dict(orient="records")
                )
            ).hexdigest(),
        }
        now = datetime.now(UTC).replace(tzinfo=None)
        run_id = version + "-split"
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_partitions",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": manifest,
                        "code_fingerprint": inputs["code_sha256"],
                    }
                ],
                "study_datasets": [
                    {
                        "dataset_version": version,
                        "status": "research",
                        "manifest_sha256": hashlib.sha256(document_bytes(manifest)).hexdigest(),
                        "feature_contract_json": {
                            "kind": (
                                "source-specific research features; no universal inference contract"
                            )
                        },
                        "manifest_json": manifest,
                        "run_id": run_id,
                        "created_at": now,
                    }
                ],
            },
            scope="public",
        )
        repository.persist(
            {
                "study_dataset_members": [
                    {
                        "dataset_version": version,
                        "observation_id": row["observation_id"],
                        "label_id": int(row["label_id"]),
                        "partition_name": row["partition_name"],
                        "dependency_group_id": row["dependency_group_id"],
                    }
                    for row in partitioned.to_dict(orient="records")
                ]
            },
            scope="public",
        )
        output.mkdir(parents=True, exist_ok=False)
        columns = [
            "observation_id",
            "source_id",
            "source_version",
            "data_origin",
            "dependency_group_id",
            "partition_name",
            "label_id",
            "label_status",
        ]
        save_immutable(output / "partitions.csv", partitioned[columns].to_csv(index=False).encode())
        save_immutable(output / "public-protocol.json", protocol_path.read_bytes())
        save_immutable(
            output / "label-policy.json", (root / "config/label-policy-v1.json").read_bytes()
        )
        balance = (
            partitioned.groupby(["source_id", "partition_name"], dropna=False)
            .agg(
                observations=("observation_id", "size"),
                groups=("dependency_group_id", "nunique"),
                positive=("target_label", "sum"),
                labelled=("target_label", "count"),
            )
            .reset_index()
            .to_dict(orient="records")
        )
        report = {
            "dataset_version": version,
            "run_id": run_id,
            "inputs": inputs,
            "balance": balance,
            "external_data_read": False,
            "test_used_for_fit": False,
            "group_policy": protocol["smart_group"],
            "selected_split_seed": partitioned.attrs.get("selected_split_seed"),
            "partitions_sha256": hashlib.sha256(
                (output / "partitions.csv").read_bytes()
            ).hexdigest(),
        }
        save_immutable(output / "partitions.json", document_bytes(report))
        repository.finish_run(run_id, "completed")
        return report
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(json.dumps(partition_public(), indent=2, default=str))
