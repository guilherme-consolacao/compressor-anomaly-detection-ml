"""Transactional, version-preserving research persistence; no DDL or raw SQL input."""

import json
import math
from datetime import UTC, datetime

from sqlalchemy import JSON, Float, MetaData, Table, and_, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from ..domain import DataValidationError, PersistenceError
from ..provenance import validate_public_provenance

TABLES = (
    "study_sources",
    "study_artifacts",
    "study_runs",
    "study_observations",
    "study_feature_values",
    "study_labels",
    "study_datasets",
    "study_dataset_members",
    "study_statistics",
    "study_clusters",
    "ml_models",
    "study_external_cases",
    "study_external_case_readings",
    "study_external_ground_truth",
    "study_external_predictions",
)
LOGICAL_KEYS = {
    "study_labels": ("observation_id", "label_version"),
    "study_statistics": ("run_id", "statistic_key"),
    "ml_models": ("name", "version"),
}
EXTERNAL_TABLES = {name for name in TABLES if name.startswith("study_external_")}


class ResearchRepository:
    def __init__(self, engine):
        self.engine = engine
        metadata = MetaData()
        self.tables = {name: Table(name, metadata, autoload_with=engine) for name in TABLES}
        # MariaDB represents JSON as LONGTEXT plus JSON_VALID; restore Python JSON typing.
        for table in self.tables.values():
            for column in table.columns:
                if column.name.endswith("_json") or column.name == "document":
                    column.type = JSON()
                elif isinstance(column.type, Float):
                    # Reflected MySQL DOUBLE defaults to Decimal with scale rounding.
                    column.type.asdecimal = False

    def _source(self, connection, source_id, source_version):
        cache = connection.info["research_validation_cache"].setdefault("sources", {})
        key = (source_id, source_version)
        if key in cache:
            return cache[key]
        table = self.tables["study_sources"]
        result = (
            connection.execute(
                select(table).where(
                    table.c.source_id == source_id, table.c.source_version == source_version
                )
            )
            .mappings()
            .first()
        )
        if result is None:
            raise DataValidationError("Research source/version is not registered.")
        cache[key] = result
        return result

    def _observation_scope(self, connection, observation_id, scope):
        checked = connection.info["research_validation_cache"].setdefault("observations", set())
        if (observation_id, scope) in checked:
            return
        table = self.tables["study_observations"]
        row = (
            connection.execute(select(table).where(table.c.observation_id == observation_id))
            .mappings()
            .first()
        )
        if row is None:
            raise DataValidationError("Research observation is not registered.")
        self._check_source_scope(connection, row["source_id"], row["source_version"], scope)
        checked.add((observation_id, scope))

    def _check_source_scope(self, connection, source_id, source_version, scope):
        source = self._source(connection, source_id, source_version)
        if scope == "public" and (
            source["data_origin"] != "public_measured" or not source["license_name"]
        ):
            raise DataValidationError(
                "External/unlicensed/synthetic data cannot enter public development."
            )
        if scope == "external" and source["data_origin"] != "ulisses_external":
            raise DataValidationError(
                "External evaluation requires explicitly reserved local origin."
            )

    def _check_scope(self, connection, name, row, scope):
        if name in EXTERNAL_TABLES and scope != "external":
            raise DataValidationError("External evaluation records are not public development.")
        if name == "study_runs" and row.get("data_scope") != scope:
            raise DataValidationError("Run scope differs from the transaction scope.")
        if name in {"study_observations", "study_artifacts"}:
            self._check_source_scope(connection, row["source_id"], row["source_version"], scope)
        if "observation_id" in row and name != "study_observations":
            self._observation_scope(connection, row["observation_id"], scope)
        if "run_id" in row and name != "study_runs":
            runs = self.tables["study_runs"]
            cache = connection.info["research_validation_cache"].setdefault("runs", {})
            if row["run_id"] not in cache:
                cache[row["run_id"]] = connection.execute(
                    select(runs.c.data_scope).where(runs.c.run_id == row["run_id"])
                ).scalar_one_or_none()
            run_scope = cache[row["run_id"]]
            if run_scope != scope:
                raise DataValidationError("Referenced run has a different/missing scope.")
        if scope == "public" and name in {"study_observations", "study_datasets"}:
            field = "provenance_json" if name == "study_observations" else "manifest_json"
            document = row.get(field, {})
            sources = self.tables["study_sources"]
            cache = connection.info["research_validation_cache"]
            if "registry" not in cache:
                cache["registry"] = {
                    (r["source_id"], r["source_version"]): {
                        **dict(r),
                        "resource_kind": r["metadata_json"].get("resource_kind"),
                    }
                    for r in connection.execute(select(sources)).mappings()
                }
            validate_public_provenance(document.get("provenance_nodes"), cache["registry"])

    def persist(self, records: dict[str, list[dict]], *, scope: str) -> dict:
        if scope not in {"public", "external", "synthetic_test"} or not records:
            raise DataValidationError("Explicit scope and a nonempty research batch are required.")
        if set(records) - set(TABLES):
            raise DataValidationError("Research writes are restricted to the declared tables.")
        counts = {"created": 0, "unchanged": 0}
        identities = {}
        try:
            with self.engine.begin() as connection:
                connection.info["research_validation_cache"] = {}
                for name in TABLES:
                    table = self.tables[name]
                    for incoming in records.get(name, []):
                        row = dict(incoming)
                        if set(row) - set(table.c.keys()):
                            raise DataValidationError("Unknown column in research input.")
                        for key, value in row.items():
                            if isinstance(value, float) and not math.isfinite(value):
                                raise DataValidationError(
                                    "Research values must be finite or explicitly missing."
                                )
                            if isinstance(table.c[key].type, JSON):
                                json.dumps(value, allow_nan=False)
                            if isinstance(value, datetime) and value.tzinfo is not None:
                                row[key] = value.astimezone(UTC).replace(tzinfo=None)
                        self._check_scope(connection, name, row, scope)
                        keys = LOGICAL_KEYS.get(name, tuple(c.name for c in table.primary_key))
                        if any(key not in row or row[key] is None for key in keys):
                            raise DataValidationError(
                                "Stable research identity/version is required."
                            )
                        condition = and_(*(table.c[key] == row[key] for key in keys))
                        previous = (
                            connection.execute(select(table).where(condition)).mappings().first()
                        )
                        if previous:
                            if any(
                                previous[key] != value
                                for key, value in row.items()
                                if key not in {"created_at", "recorded_at"}
                            ):
                                raise DataValidationError(
                                    "Immutable research version conflicts with existing data."
                                )
                            counts["unchanged"] += 1
                            identity = tuple(previous[c.name] for c in table.primary_key)
                        else:
                            result = connection.execute(insert(table).values(**row))
                            counts["created"] += 1
                            identity = tuple(result.inserted_primary_key)
                        identities.setdefault(name, []).append(identity)
            return {**counts, "identities": identities}
        except SQLAlchemyError:
            raise PersistenceError("Research transaction failed and was rolled back.") from None
        except (TypeError, ValueError):
            raise DataValidationError("Invalid research value or JSON document.") from None

    def finish_run(self, run_id: str, status: str, *, error_message: str | None = None) -> None:
        if status not in {"completed", "failed", "blocked"}:
            raise DataValidationError("Invalid terminal run status.")
        table = self.tables["study_runs"]
        try:
            with self.engine.begin() as connection:
                result = connection.execute(
                    update(table)
                    .where(table.c.run_id == run_id, table.c.status == "running")
                    .values(
                        status=status,
                        ended_at=datetime.now(UTC).replace(tzinfo=None),
                        error_message=error_message,
                    )
                )
                if result.rowcount != 1:
                    raise DataValidationError(
                        "Only an existing running experiment can be finished."
                    )
        except SQLAlchemyError:
            raise PersistenceError("Research run update failed.") from None
