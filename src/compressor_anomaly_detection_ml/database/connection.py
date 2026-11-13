"""Connection configuration and strictly read-only contract diagnostics."""

from typing import Any

from sqlalchemy import (
    DateTime,
    Engine,
    Float,
    Integer,
    Numeric,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.pool import StaticPool

from compressor_anomaly_detection_ml.domain import ConfigurationError, PersistenceError

from .models import ML_TABLES, SOURCE_READINGS


def create_engine_for_url(url: str | URL) -> Engine:
    try:
        parsed = make_url(url) if isinstance(url, str) else url
        if parsed.get_backend_name() not in {"mysql", "mariadb", "sqlite"}:
            raise ConfigurationError("Supported databases: MySQL/MariaDB and isolated SQLite.")
        options: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
        if parsed.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if parsed.database in {None, "", ":memory:"}:
                options["poolclass"] = StaticPool
        else:
            options["connect_args"] = {"connect_timeout": 10}
        engine = create_engine(parsed, **options)
    except (ArgumentError, ValueError, TypeError) as exc:
        raise ConfigurationError("Invalid database connection configuration.") from exc

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def sqlite_foreign_keys(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    else:

        @event.listens_for(engine, "connect")
        def mysql_utc(dbapi_connection, _connection_record):
            with dbapi_connection.cursor() as cursor:
                cursor.execute("SET time_zone = '+00:00'")

    return engine


def inspect_contract(engine: Engine) -> dict:
    """Inspect metadata only; this never initializes or migrates a schema."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            required = {SOURCE_READINGS.name: set(SOURCE_READINGS.c.keys())}
            required.update({table.name: set(table.c.keys()) for table in ML_TABLES})
            missing_tables = sorted(set(required) - tables)
            schema_metadata = {}
            missing_foreign_keys = {}
            missing_unique_constraints = {}
            for name in sorted(set(required) & tables):
                columns = inspector.get_columns(name)
                primary_key = inspector.get_pk_constraint(name)
                unique_constraints = inspector.get_unique_constraints(name)
                indexes = inspector.get_indexes(name)
                foreign_keys = inspector.get_foreign_keys(name)
                schema_metadata[name] = {
                    "columns": [
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": column["nullable"],
                            "default": column.get("default"),
                        }
                        for column in columns
                    ],
                    "primary_key": primary_key,
                    "unique_constraints": unique_constraints,
                    "indexes": indexes,
                    "foreign_keys": foreign_keys,
                }
                expected = (
                    SOURCE_READINGS
                    if name == "readings"
                    else next(table for table in ML_TABLES if table.name == name)
                )
                actual_foreign_keys = {
                    (
                        tuple(item["constrained_columns"]),
                        item["referred_table"],
                        tuple(item["referred_columns"]),
                    )
                    for item in foreign_keys
                }
                for constraint in expected.foreign_key_constraints:
                    reference = (
                        tuple(element.parent.name for element in constraint.elements),
                        constraint.referred_table.name,
                        tuple(element.column.name for element in constraint.elements),
                    )
                    if reference not in actual_foreign_keys:
                        missing_foreign_keys.setdefault(name, []).append(
                            {
                                "columns": list(reference[0]),
                                "referred_table": reference[1],
                                "referred_columns": list(reference[2]),
                            }
                        )
                expected_uniques = {tuple(column.name for column in expected.primary_key.columns)}
                expected_uniques.update(
                    tuple(column.name for column in constraint.columns)
                    for constraint in expected.constraints
                    if constraint.__class__.__name__ == "UniqueConstraint"
                )
                actual_uniques = {tuple(primary_key.get("constrained_columns") or ())}
                actual_uniques.update(tuple(item["column_names"]) for item in unique_constraints)
                actual_uniques.update(
                    tuple(item["column_names"]) for item in indexes if item["unique"]
                )
                for columns in expected_uniques:
                    if columns and columns not in actual_uniques:
                        missing_unique_constraints.setdefault(name, []).append(list(columns))
            missing_columns = {
                name: sorted(columns - {column["name"] for column in inspector.get_columns(name)})
                for name, columns in required.items()
                if name in tables
            }
            missing_columns = {
                name: columns for name, columns in missing_columns.items() if columns
            }
            source_available = "readings" in tables
            source_type_mismatches = {}
            if source_available:
                source_types = {
                    column["name"]: column["type"] for column in inspector.get_columns("readings")
                }
                expected_types = {
                    "id": ((Integer,), "integer"),
                    "timestamp": ((DateTime,), "datetime/timestamp"),
                    **{
                        name: ((Numeric, Float, Integer), "numeric")
                        for name in ("temperature", "accel_x", "accel_y", "accel_z", "rms")
                    },
                }
                for name, (types, description) in expected_types.items():
                    actual = source_types.get(name)
                    if actual is not None and not isinstance(actual, types):
                        source_type_mismatches[name] = {
                            "actual": str(actual),
                            "expected": description,
                        }
            source_compatible = (
                source_available
                and "readings" not in missing_columns
                and not source_type_mismatches
            )
            measurement_available = not any(
                (
                    missing_tables,
                    missing_columns,
                    missing_foreign_keys,
                    missing_unique_constraints,
                    source_type_mismatches,
                )
            )
            return {
                "connected": True,
                "dialect": engine.dialect.name,
                "source_available": source_available,
                "source_compatible": source_compatible,
                "source_type_mismatches": source_type_mismatches,
                "measurement_contract_available": measurement_available,
                "missing_tables": missing_tables,
                "missing_columns": missing_columns,
                "missing_foreign_keys": missing_foreign_keys,
                "missing_unique_constraints": missing_unique_constraints,
                "schema_metadata": schema_metadata,
                "production_ready": False,
                "notes": [
                    "Metadata presence does not confirm acquisition units "
                    "or finalization behavior.",
                    "Production requires approved schema, explicit memberships, confirmed g units, "
                    "and immutable finalized measurements.",
                    "Timestamp ties are expected in the acquisition schema (second precision).",
                ],
            }
    except SQLAlchemyError as exc:
        raise PersistenceError(
            "Database connection or read-only schema inspection failed."
        ) from exc
