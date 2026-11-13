"""Transactional persistence over the additive ML tables.

The acquisition adapter reads the existing columns without recalibration. Only
the explicitly named SQLite fixture helpers ever create or populate readings.
"""

import math
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Connection, Engine, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from compressor_anomaly_detection_ml.domain import (
    ContractError,
    FeatureVector,
    Measurement,
    ModelNotFoundError,
    PersistenceError,
    PredictionResult,
    Reading,
)

from .models import (
    ML_TABLES,
    SOURCE_READINGS,
    Base,
    FeatureImportanceRow,
    FeatureRow,
    MeasurementReadingRow,
    MeasurementRow,
    ModelRow,
    PredictionRow,
    ProcessingRunRow,
)

MEASUREMENTS = MeasurementRow.__table__
MEMBERSHIPS = MeasurementReadingRow.__table__
FEATURES = FeatureRow.__table__
MODELS = ModelRow.__table__
PREDICTIONS = PredictionRow.__table__
RUNS = ProcessingRunRow.__table__
IMPORTANCES = FeatureImportanceRow.__table__


def _utc(value: datetime) -> datetime:
    # MySQL TIMESTAMP is returned in the connection's explicitly configured UTC
    # session; SQLite fixture DATETIME is also stored in UTC.
    if not isinstance(value, datetime):
        raise ContractError("Persisted timestamps must be datetime values.")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _stored(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractError("Measurement and reading timestamps must include a timezone.")
    return value.astimezone(UTC).replace(tzinfo=None)


def _prediction_dict(row) -> dict:
    result = dict(row)
    result["predicted_at"] = _utc(result["predicted_at"]).isoformat()
    return result


def _model_dict(row) -> dict:
    return {**row["document"], "model_id": row["model_id"]}


def _measurement(connection: Connection, measurement_id: str) -> Measurement:
    row = (
        connection.execute(
            select(MEASUREMENTS).where(MEASUREMENTS.c.measurement_id == measurement_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ContractError("Measurement was not found in the explicit acquisition contract.")
    readings = (
        connection.execute(
            select(SOURCE_READINGS)
            .join(MEMBERSHIPS, SOURCE_READINGS.c.id == MEMBERSHIPS.c.reading_id)
            .where(MEMBERSHIPS.c.measurement_id == measurement_id)
            .order_by(SOURCE_READINGS.c.timestamp, SOURCE_READINGS.c.id)
        )
        .mappings()
        .all()
    )
    return Measurement(
        measurement_id=row["measurement_id"],
        equipment_id=row["equipment_id"],
        started_at=_utc(row["started_at"]),
        ended_at=_utc(row["ended_at"]) if row["ended_at"] else None,
        status=row["status"],
        expected_reading_count=row["expected_reading_count"],
        readings=tuple(
            Reading(
                reading_id=reading["id"],
                timestamp=_utc(reading["timestamp"]),
                temperature_c=float(reading["temperature"]),
                vibration_rms_g=float(reading["rms"]),
                axis_x_g=float(reading["accel_x"]),
                axis_y_g=float(reading["accel_y"]),
                axis_z_g=float(reading["accel_z"]),
            )
            for reading in readings
        ),
        label=row["label"],
        label_source=row["label_source"],
        group_id=row["group_id"],
        acceleration_unit=row["acceleration_unit"],
        signal_definition=row["signal_definition"],
    )


def _write_features(connection: Connection, measurement_id: str, vector: FeatureVector) -> None:
    if (
        len(vector.values) != len(vector.feature_names)
        or not vector.values
        or len(set(vector.feature_names)) != len(vector.feature_names)
        or not all(math.isfinite(value) for value in vector.values)
        or vector.reading_count < 2
    ):
        raise ContractError("Feature vector does not satisfy the persistence contract.")
    row = (
        connection.execute(
            select(FEATURES).where(
                FEATURES.c.measurement_id == measurement_id,
                FEATURES.c.processing_version == vector.processing_version,
            )
        )
        .mappings()
        .first()
    )
    values = list(vector.values)
    names = list(vector.feature_names)
    if row:
        if (
            row["source_fingerprint"] != vector.source_fingerprint
            or row["values"] != values
            or row["feature_names"] != names
            or row["reading_count"] != vector.reading_count
        ):
            raise ContractError(
                "Finalized measurement or feature contract changed; history preserved."
            )
        return
    connection.execute(
        insert(FEATURES).values(
            measurement_id=measurement_id,
            processing_version=vector.processing_version,
            feature_names=names,
            values=values,
            source_fingerprint=vector.source_fingerprint,
            reading_count=vector.reading_count,
        )
    )


def _write_run(connection: Connection, measurement_id: str, model_id: int, **values) -> None:
    where = (RUNS.c.measurement_id == measurement_id, RUNS.c.model_id == model_id)
    exists = connection.execute(select(RUNS.c.status).where(*where)).scalar_one_or_none()
    values["updated_at"] = datetime.now(UTC).replace(tzinfo=None)
    if exists is None:
        connection.execute(
            insert(RUNS).values(measurement_id=measurement_id, model_id=model_id, **values)
        )
    else:
        connection.execute(update(RUNS).where(*where).values(**values))


class Repository:
    def __init__(self, engine: Engine):
        self.engine = engine

    @contextmanager
    def _read(self) -> Iterator[Connection]:
        try:
            with self.engine.connect() as connection:
                yield connection
        except SQLAlchemyError as exc:
            raise PersistenceError(
                "Database read failed; inspect connection and schema configuration."
            ) from exc

    def get_measurement(self, measurement_id: str) -> Measurement:
        with self._read() as connection:
            return _measurement(connection, measurement_id)

    def list_labeled_measurements(self) -> list[Measurement]:
        with self._read() as connection:
            ids = (
                connection.execute(
                    select(MEASUREMENTS.c.measurement_id)
                    .where(MEASUREMENTS.c.status == "FINALIZADA", MEASUREMENTS.c.label.is_not(None))
                    .order_by(MEASUREMENTS.c.measurement_id)
                )
                .scalars()
                .all()
            )
            return [_measurement(connection, measurement_id) for measurement_id in ids]

    def pending_measurement_ids(self, model_id: int, limit: int = 100) -> list[str]:
        if limit < 1:
            raise ContractError("Batch limit must be positive.")
        with self._read() as connection:
            if (
                connection.execute(
                    select(MODELS.c.model_id).where(MODELS.c.model_id == model_id)
                ).first()
                is None
            ):
                raise ModelNotFoundError("Requested model is not registered.")
            has_prediction = (
                select(PREDICTIONS.c.prediction_id)
                .where(
                    PREDICTIONS.c.measurement_id == MEASUREMENTS.c.measurement_id,
                    PREDICTIONS.c.model_id == model_id,
                )
                .exists()
            )
            has_error = (
                select(RUNS.c.measurement_id)
                .where(
                    RUNS.c.measurement_id == MEASUREMENTS.c.measurement_id,
                    RUNS.c.model_id == model_id,
                    RUNS.c.status == "ERRO",
                )
                .exists()
            )
            return list(
                connection.execute(
                    select(MEASUREMENTS.c.measurement_id)
                    .where(MEASUREMENTS.c.status == "FINALIZADA", ~has_prediction, ~has_error)
                    .order_by(MEASUREMENTS.c.started_at, MEASUREMENTS.c.measurement_id)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def save_features(self, measurement_id: str, vector: FeatureVector) -> None:
        for attempt in range(2):
            try:
                with self.engine.begin() as connection:
                    _write_features(connection, measurement_id, vector)
                return
            except IntegrityError as exc:
                if attempt:
                    raise PersistenceError(
                        "Feature persistence violated the data contract."
                    ) from exc
            except SQLAlchemyError as exc:
                raise PersistenceError(
                    "Feature persistence failed; transaction rolled back."
                ) from exc

    def complete_prediction(
        self, measurement_id: str, model_id: int, vector: FeatureVector, result: PredictionResult
    ) -> tuple[dict, bool]:
        probabilities = (result.probability_normal, result.probability_anomaly)
        if (
            result.predicted_class not in (0, 1)
            or not all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities)
            or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-8)
        ):
            raise ContractError("Prediction class or probabilities are invalid.")
        for attempt in range(3):
            try:
                with self.engine.begin() as connection:
                    measurement = (
                        connection.execute(
                            select(MEASUREMENTS)
                            .where(MEASUREMENTS.c.measurement_id == measurement_id)
                            .with_for_update()
                        )
                        .mappings()
                        .first()
                    )
                    if (
                        measurement is None
                        or measurement["status"] != "FINALIZADA"
                        or measurement["ended_at"] is None
                        or measurement["expected_reading_count"] != vector.reading_count
                    ):
                        raise ContractError(
                            "Only explicitly finalized measurements can be persisted."
                        )
                    model = (
                        connection.execute(select(MODELS).where(MODELS.c.model_id == model_id))
                        .mappings()
                        .first()
                    )
                    if model is None:
                        raise ModelNotFoundError("Requested model is not registered.")
                    if model["processing_version"] != vector.processing_version:
                        raise ContractError("Model and feature processing versions differ.")
                    if model["document"]["feature_names"] != list(vector.feature_names):
                        raise ContractError("Model and feature column orders differ.")
                    _write_features(connection, measurement_id, vector)
                    existing = (
                        connection.execute(
                            select(PREDICTIONS).where(
                                PREDICTIONS.c.measurement_id == measurement_id,
                                PREDICTIONS.c.model_id == model_id,
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if existing:
                        return _prediction_dict(existing), False
                    inserted = connection.execute(
                        insert(PREDICTIONS).values(
                            measurement_id=measurement_id,
                            model_id=model_id,
                            processing_version=vector.processing_version,
                            source_fingerprint=vector.source_fingerprint,
                            predicted_class=int(result.predicted_class),
                            probability_normal=float(result.probability_normal),
                            probability_anomaly=float(result.probability_anomaly),
                            predicted_at=datetime.now(UTC).replace(tzinfo=None),
                        )
                    )
                    _write_run(
                        connection,
                        measurement_id,
                        model_id,
                        status="PROCESSADA",
                        error_code=None,
                        error_message=None,
                    )
                    row = (
                        connection.execute(
                            select(PREDICTIONS).where(
                                PREDICTIONS.c.prediction_id == inserted.inserted_primary_key[0]
                            )
                        )
                        .mappings()
                        .one()
                    )
                    answer = _prediction_dict(row)
                return answer, True
            except IntegrityError as exc:
                if attempt == 2:
                    raise PersistenceError(
                        "Prediction persistence violated the data contract."
                    ) from exc
            except SQLAlchemyError as exc:
                raise PersistenceError(
                    "Prediction persistence failed; transaction rolled back."
                ) from exc
        raise PersistenceError("Prediction could not be persisted.")

    def record_processing_error(
        self, measurement_id: str, model_id: int, error_code: str, message: str
    ) -> None:
        # The message must already be a safe application-level message, never a
        # rendered driver exception (which can contain SQL parameters).
        for attempt in range(2):
            try:
                with self.engine.begin() as connection:
                    measurement = connection.execute(
                        select(MEASUREMENTS.c.measurement_id)
                        .where(MEASUREMENTS.c.measurement_id == measurement_id)
                        .with_for_update()
                    ).first()
                    model = connection.execute(
                        select(MODELS.c.model_id).where(MODELS.c.model_id == model_id)
                    ).first()
                    if measurement is None or model is None:
                        return
                    exists = connection.execute(
                        select(PREDICTIONS.c.prediction_id).where(
                            PREDICTIONS.c.measurement_id == measurement_id,
                            PREDICTIONS.c.model_id == model_id,
                        )
                    ).first()
                    if not exists:
                        _write_run(
                            connection,
                            measurement_id,
                            model_id,
                            status="ERRO",
                            error_code=error_code[:64],
                            error_message=message[:2000],
                        )
                return
            except IntegrityError as exc:
                if attempt:
                    raise PersistenceError("Processing error could not be recorded.") from exc
            except SQLAlchemyError as exc:
                raise PersistenceError("Processing error persistence failed.") from exc

    def register_model(self, metadata: dict, importances: dict[str, float]) -> int:
        required = {"name", "version", "processing_version", "feature_names"}
        if not required.issubset(metadata) or set(importances) != set(metadata["feature_names"]):
            raise ContractError(
                "Model metadata and feature importances must describe the same features."
            )
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in importances.values()):
            raise ContractError("Feature importances must be finite probabilities.")
        try:
            with self.engine.begin() as connection:
                inserted = connection.execute(
                    insert(MODELS).values(
                        name=metadata["name"],
                        version=metadata["version"],
                        processing_version=metadata["processing_version"],
                        document=metadata,
                    )
                )
                model_id = int(inserted.inserted_primary_key[0])
                connection.execute(
                    insert(IMPORTANCES),
                    [
                        {"model_id": model_id, "feature_name": name, "importance": float(value)}
                        for name, value in importances.items()
                    ],
                )
            return model_id
        except IntegrityError as exc:
            raise ContractError(
                "Model name and version already exist or metadata is invalid."
            ) from exc
        except SQLAlchemyError as exc:
            raise PersistenceError("Model registration failed; transaction rolled back.") from exc

    def get_model(self, model_id: int) -> dict:
        with self._read() as connection:
            row = (
                connection.execute(select(MODELS).where(MODELS.c.model_id == model_id))
                .mappings()
                .first()
            )
            if row is None:
                raise ModelNotFoundError("Requested model is not registered.")
            return _model_dict(row)

    def list_models(self) -> list[dict]:
        with self._read() as connection:
            return [
                _model_dict(row)
                for row in connection.execute(select(MODELS).order_by(MODELS.c.model_id)).mappings()
            ]

    def get_prediction(self, measurement_id: str, model_id: int) -> dict | None:
        with self._read() as connection:
            row = (
                connection.execute(
                    select(PREDICTIONS).where(
                        PREDICTIONS.c.measurement_id == measurement_id,
                        PREDICTIONS.c.model_id == model_id,
                    )
                )
                .mappings()
                .first()
            )
            return _prediction_dict(row) if row else None

    def list_predictions(self, limit: int = 100) -> list[dict]:
        if limit < 1:
            raise ContractError("Query limit must be positive.")
        with self._read() as connection:
            return [
                _prediction_dict(row)
                for row in connection.execute(
                    select(PREDICTIONS).order_by(PREDICTIONS.c.prediction_id.desc()).limit(limit)
                ).mappings()
            ]


def create_isolated_schema(engine: Engine) -> None:
    """Create a demonstrator schema only on SQLite, never on MySQL/MariaDB."""
    if engine.dialect.name != "sqlite":
        raise ContractError("Automatic schema initialization is restricted to isolated SQLite.")
    Base.metadata.create_all(engine, tables=[SOURCE_READINGS, *ML_TABLES])


def insert_isolated_measurement(engine: Engine, measurement: Measurement) -> None:
    """Fixture/demo-only ingestion; production acquisition owns memberships."""
    if engine.dialect.name != "sqlite":
        raise ContractError("Synthetic ingestion is restricted to isolated SQLite.")
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(MEASUREMENTS).values(
                    measurement_id=measurement.measurement_id,
                    equipment_id=measurement.equipment_id,
                    started_at=_stored(measurement.started_at),
                    ended_at=_stored(measurement.ended_at),
                    status=measurement.status,
                    expected_reading_count=measurement.expected_reading_count,
                    label=measurement.label,
                    label_source=measurement.label_source,
                    group_id=measurement.group_id,
                    acceleration_unit=measurement.acceleration_unit,
                    signal_definition=measurement.signal_definition,
                )
            )
            if measurement.readings:
                connection.execute(
                    insert(SOURCE_READINGS),
                    [
                        {
                            "id": reading.reading_id,
                            "temperature": reading.temperature_c,
                            "accel_x": reading.axis_x_g,
                            "accel_y": reading.axis_y_g,
                            "accel_z": reading.axis_z_g,
                            "rms": reading.vibration_rms_g,
                            "timestamp": _stored(reading.timestamp),
                        }
                        for reading in measurement.readings
                    ],
                )
                connection.execute(
                    insert(MEMBERSHIPS),
                    [
                        {
                            "reading_id": reading.reading_id,
                            "measurement_id": measurement.measurement_id,
                        }
                        for reading in measurement.readings
                    ],
                )
    except SQLAlchemyError as exc:
        raise PersistenceError(
            "Isolated fixture ingestion failed; transaction rolled back."
        ) from exc
