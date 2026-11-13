"""Isolated SQLite persistence tests; all sensor data in this module is artificial."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, func, insert, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from compressor_anomaly_detection_ml.database import (
    Repository,
    create_engine_for_url,
    create_isolated_schema,
    insert_isolated_measurement,
    inspect_contract,
)
from compressor_anomaly_detection_ml.database.models import (
    FeatureImportanceRow,
    FeatureRow,
    MeasurementReadingRow,
    MeasurementRow,
    PredictionRow,
    ProcessingRunRow,
)
from compressor_anomaly_detection_ml.domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    ContractError,
    FeatureVector,
    Measurement,
    ModelNotFoundError,
    PersistenceError,
    PredictionResult,
    Reading,
)


@pytest.fixture
def engine(tmp_path):
    result = create_engine_for_url(f"sqlite:///{tmp_path / 'isolated.sqlite'}")
    create_isolated_schema(result)
    yield result
    result.dispose()


def synthetic_measurement(measurement_id="synthetic-1", first_reading_id=1, **changes):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    measurement = Measurement(
        measurement_id=measurement_id,
        equipment_id="synthetic-compressor",
        started_at=start,
        ended_at=start + timedelta(seconds=1),
        status="FINALIZADA",
        expected_reading_count=2,
        readings=(
            Reading(first_reading_id, start, 30.0, 0.2, -0.1, 0.2, 0.3),
            Reading(first_reading_id + 1, start + timedelta(seconds=1), 32.0, 0.3, 0.4, -0.2, 0.5),
        ),
        label=0,
        label_source="artificial test fixture",
        group_id="synthetic-cycle-1",
        acceleration_unit="g",
    )
    return replace(measurement, **changes)


def vector():
    return FeatureVector(tuple(float(index) for index in range(20)), "a" * 64, 2)


def model_metadata(version="synthetic-v1"):
    return {
        "name": "synthetic-random-forest",
        "version": version,
        "processing_version": PROCESSING_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "artifact_path": "models/synthetic.joblib",
        "artifact_sha256": "b" * 64,
        "parameters": {},
        "metrics": {},
        "training_info": {"synthetic": True},
        "trained_at": datetime.now(UTC).isoformat(),
    }


def register(repository, version="synthetic-v1"):
    return repository.register_model(model_metadata(version), dict.fromkeys(FEATURE_NAMES, 0.05))


def test_source_adapter_and_contract_are_explicit(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    repository = Repository(engine)
    measurement = repository.get_measurement("synthetic-1")
    assert measurement.readings[0].axis_x_g == -0.1  # no repeated offset/calibration
    assert measurement.started_at.tzinfo == UTC
    assert measurement.readings[0].timestamp.tzinfo == UTC
    assert measurement.expected_reading_count == 2
    assert len(repository.list_labeled_measurements()) == 1
    report = inspect_contract(engine)
    assert report["source_compatible"] and report["measurement_contract_available"]
    assert report["production_ready"] is False  # schema presence cannot prove signal units


def test_inspection_does_not_initialize_database(tmp_path):
    empty = create_engine_for_url(f"sqlite:///{tmp_path / 'empty.sqlite'}")
    try:
        report = inspect_contract(empty)
        assert not report["source_available"]
        assert "readings" in report["missing_tables"]
    finally:
        empty.dispose()


def test_inspection_rejects_source_columns_with_incompatible_types(tmp_path):
    incompatible = create_engine_for_url(f"sqlite:///{tmp_path / 'wrong-types.sqlite'}")
    try:
        with incompatible.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE readings (id VARCHAR(64) PRIMARY KEY, temperature TEXT NOT NULL, "
                    "accel_x REAL NOT NULL, accel_y REAL NOT NULL, accel_z REAL NOT NULL, "
                    "rms REAL NOT NULL, timestamp VARCHAR(32) NOT NULL)"
                )
            )
        report = inspect_contract(incompatible)
        assert set(report["source_type_mismatches"]) == {"id", "temperature", "timestamp"}
        assert not report["source_compatible"]
        assert not report["measurement_contract_available"]
        assert "readings" not in report["missing_columns"]
    finally:
        incompatible.dispose()


@pytest.mark.parametrize("invalid", [None, "2026-01-01", 123])
def test_persisted_timestamp_type_has_safe_contract_error(invalid):
    from compressor_anomaly_detection_ml.database.repository import _utc

    with pytest.raises(ContractError, match="datetime"):
        _utc(invalid)


def test_automatic_schema_and_synthetic_ingestion_refuse_mysql():
    class MySQL:
        class dialect:
            name = "mysql"

    with pytest.raises(ContractError, match="SQLite"):
        create_isolated_schema(MySQL())
    with pytest.raises(ContractError, match="SQLite"):
        insert_isolated_measurement(MySQL(), synthetic_measurement())


def test_missing_measurement_and_model_raise_safe_errors(engine):
    repository = Repository(engine)
    with pytest.raises(ContractError, match="not found"):
        repository.get_measurement("missing")
    with pytest.raises(ModelNotFoundError):
        repository.get_model(999)
    with pytest.raises(ModelNotFoundError):
        repository.pending_measurement_ids(999)


def test_features_are_idempotent_and_immutable(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    repository = Repository(engine)
    repository.save_features("synthetic-1", vector())
    repository.save_features("synthetic-1", vector())
    with pytest.raises(ContractError, match="history preserved"):
        repository.save_features("synthetic-1", replace(vector(), source_fingerprint="c" * 64))
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FeatureRow)) == 1


def test_prediction_idempotence_preserves_model_history_and_importances(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    repository = Repository(engine)
    model_id = register(repository)
    assert repository.pending_measurement_ids(model_id) == ["synthetic-1"]
    first, created = repository.complete_prediction(
        "synthetic-1", model_id, vector(), PredictionResult(1, 0.2, 0.8)
    )
    assert created and first["predicted_class"] == 1
    repeated, created = repository.complete_prediction(
        "synthetic-1", model_id, vector(), PredictionResult(0, 0.9, 0.1)
    )
    assert not created and repeated == first
    assert repository.pending_measurement_ids(model_id) == []
    next_model = register(repository, "synthetic-v2")
    assert repository.pending_measurement_ids(next_model) == ["synthetic-1"]
    repository.complete_prediction(
        "synthetic-1", next_model, vector(), PredictionResult(0, 0.9, 0.1)
    )
    assert len(repository.list_models()) == 2
    assert len(repository.list_predictions()) == 2
    assert repository.get_prediction("synthetic-1", model_id) == first
    assert repository.get_model(next_model)["version"] == "synthetic-v2"
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FeatureImportanceRow)) == 40
        assert connection.scalar(select(MeasurementRow.status)) == "FINALIZADA"


def test_model_version_cannot_be_overwritten(engine):
    repository = Repository(engine)
    register(repository)
    with pytest.raises(ContractError, match="already exist"):
        register(repository)
    assert len(repository.list_models()) == 1


def test_prediction_and_feature_insert_roll_back_together(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    repository = Repository(engine)
    model_id = register(repository)

    def reject_prediction(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO ml_predictions"):
            raise OperationalError(statement, {}, Exception("artificial persistence failure"))

    event.listen(engine, "before_cursor_execute", reject_prediction)
    try:
        with pytest.raises(PersistenceError, match="rolled back"):
            repository.complete_prediction(
                "synthetic-1", model_id, vector(), PredictionResult(0, 0.9, 0.1)
            )
    finally:
        event.remove(engine, "before_cursor_execute", reject_prediction)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FeatureRow)) == 0
        assert connection.scalar(select(func.count()).select_from(PredictionRow)) == 0
    repository.record_processing_error("synthetic-1", model_id, "PersistenceError", "Safe error")
    with engine.connect() as connection:
        assert connection.scalar(select(ProcessingRunRow.status)) == "ERRO"
    repository.complete_prediction("synthetic-1", model_id, vector(), PredictionResult(0, 0.9, 0.1))
    with engine.connect() as connection:
        row = connection.execute(select(ProcessingRunRow.__table__)).mappings().one()
        assert row["status"] == "PROCESSADA" and row["error_message"] is None
    repository.record_processing_error(
        "synthetic-1", model_id, "LateError", "Late concurrent error"
    )
    with engine.connect() as connection:
        assert connection.scalar(select(ProcessingRunRow.status)) == "PROCESSADA"


def test_concurrent_workers_persist_one_prediction(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    repository = Repository(engine)
    model_id = register(repository)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _: Repository(engine).complete_prediction(
                    "synthetic-1", model_id, vector(), PredictionResult(1, 0.1, 0.9)
                ),
                range(4),
            )
        )
    assert sum(created for _, created in results) == 1
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(PredictionRow)) == 1
        assert connection.scalar(select(func.count()).select_from(FeatureRow)) == 1


def test_failed_measurements_do_not_starve_later_batches(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    insert_isolated_measurement(engine, synthetic_measurement("synthetic-2", 3))
    repository = Repository(engine)
    model_id = register(repository)
    assert repository.pending_measurement_ids(model_id, limit=1) == ["synthetic-1"]
    repository.record_processing_error("synthetic-1", model_id, "ContractError", "Invalid data")
    assert repository.pending_measurement_ids(model_id, limit=1) == ["synthetic-2"]
    # An explicit predict request can retry a corrected measurement and clear its error.
    repository.complete_prediction("synthetic-1", model_id, vector(), PredictionResult(0, 0.9, 0.1))
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(ProcessingRunRow.status).where(
                    ProcessingRunRow.measurement_id == "synthetic-1"
                )
            )
            == "PROCESSADA"
        )


def test_error_for_missing_measurement_or_model_preserves_original_error(engine):
    repository = Repository(engine)
    model_id = register(repository)
    repository.record_processing_error("missing-measurement", model_id, "ContractError", "Missing")
    insert_isolated_measurement(engine, synthetic_measurement())
    repository.record_processing_error("synthetic-1", 999, "ModelNotFoundError", "Missing")
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ProcessingRunRow)) == 0


def test_open_measurements_and_unlabeled_examples_are_excluded(engine):
    insert_isolated_measurement(engine, synthetic_measurement(status="ABERTA", ended_at=None))
    insert_isolated_measurement(
        engine, synthetic_measurement("synthetic-2", 3, label=None, label_source=None)
    )
    repository = Repository(engine)
    model_id = register(repository)
    assert repository.list_labeled_measurements() == []
    assert repository.pending_measurement_ids(model_id) == ["synthetic-2"]
    with pytest.raises(ContractError, match="finalized"):
        repository.complete_prediction(
            "synthetic-1", model_id, vector(), PredictionResult(0, 1.0, 0.0)
        )


def test_membership_fk_and_reading_uniqueness_are_enforced(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                insert(MeasurementReadingRow).values(reading_id=9999, measurement_id="synthetic-1")
            )


def test_prediction_probabilities_and_processing_version_are_checked(engine):
    insert_isolated_measurement(engine, synthetic_measurement())
    repository = Repository(engine)
    model_id = register(repository)
    with pytest.raises(ContractError, match="probabilities"):
        repository.complete_prediction(
            "synthetic-1", model_id, vector(), PredictionResult(0, 0.2, 0.2)
        )
    with pytest.raises(ContractError, match="versions"):
        repository.complete_prediction(
            "synthetic-1",
            model_id,
            replace(vector(), processing_version="other-v1"),
            PredictionResult(0, 0.8, 0.2),
        )
