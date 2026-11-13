"""Application-level checks on isolated SQLite and explicitly synthetic signals."""

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from compressor_anomaly_detection_ml.config import TrainingConfig
from compressor_anomaly_detection_ml.database import (
    Repository,
    create_engine_for_url,
    create_isolated_schema,
    insert_isolated_measurement,
)
from compressor_anomaly_detection_ml.database.models import (
    FeatureRow,
    MeasurementRow,
    PredictionRow,
    ProcessingRunRow,
)
from compressor_anomaly_detection_ml.demo import synthetic_measurements
from compressor_anomaly_detection_ml.domain import (
    FEATURE_NAMES,
    DataValidationError,
    ModelNotFoundError,
    PersistenceError,
    TrainingError,
)
from compressor_anomaly_detection_ml.services import MLService

FAST_CONFIG = TrainingConfig(n_estimators=10, n_jobs=1)


@pytest.fixture
def service(tmp_path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'synthetic.sqlite'}")
    create_isolated_schema(engine)
    for measurement in synthetic_measurements(36):
        insert_isolated_measurement(engine, measurement)
    result = MLService(Repository(engine), tmp_path / "models")
    yield result
    engine.dispose()


def test_measurement_training_evaluation_and_prediction_history(service):
    features = service.extract("synthetic-000")
    assert tuple(features["features"]) == FEATURE_NAMES
    assert features["reading_count"] == 16
    model = service.train("synthetic-v1", FAST_CONFIG)
    model_id = model["model_id"]
    assert model["training_info"]["synthetic"] is True
    assert model["training_info"]["measurement_count"] == 32
    assert service.evaluate_model(model_id)["metrics"] == model["metrics"]

    prediction = service.predict("synthetic-035", model_id)
    assert prediction["created"] is True
    assert prediction["measurement_id"] == "synthetic-035"
    assert prediction["probability_normal"] + prediction["probability_anomaly"] == pytest.approx(1)
    repeated = service.predict("synthetic-035", model_id)
    assert repeated == {**prediction, "created": False}
    assert service.repository.get_prediction("synthetic-035", model_id) == {
        key: value for key, value in prediction.items() if key != "created"
    }

    second = service.train("synthetic-v2", FAST_CONFIG)
    assert "synthetic-035" in service.repository.pending_measurement_ids(second["model_id"])
    batch = service.process_pending(second["model_id"])
    assert batch["examined"] == batch["created"] == 36
    assert batch["errors"] == []
    assert service.process_pending(second["model_id"])["created"] == 0
    assert len(service.repository.list_predictions()) == 37
    assert (
        service.repository.get_prediction("synthetic-035", model_id)["prediction_id"]
        == (prediction["prediction_id"])
    )
    with service.repository.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FeatureRow)) == 36
        assert connection.scalar(select(func.count()).select_from(PredictionRow)) == 37


def test_invalid_finalized_measurement_records_error_without_prediction(service):
    model = service.train("synthetic-v1", FAST_CONFIG)
    source = synthetic_measurements(36)[-1]
    invalid = replace(
        source,
        measurement_id="synthetic-invalid-count",
        expected_reading_count=17,
        readings=tuple(
            replace(reading, reading_id=reading.reading_id + 1000) for reading in source.readings
        ),
    )
    insert_isolated_measurement(service.repository.engine, invalid)
    with pytest.raises(DataValidationError, match="count"):
        service.predict(invalid.measurement_id, model["model_id"])
    assert service.repository.get_prediction(invalid.measurement_id, model["model_id"]) is None
    with service.repository.engine.connect() as connection:
        run = connection.execute(select(ProcessingRunRow.__table__)).mappings().one()
        assert run["status"] == "ERRO"
        assert run["error_code"] == "DataValidationError"
        assert connection.scalar(select(func.count()).select_from(FeatureRow)) == 0


def test_failed_model_registration_removes_its_unpublished_artifact(service, monkeypatch):
    def reject_registration(_metadata, _importances):
        raise PersistenceError("Artificial registry failure")

    monkeypatch.setattr(service.repository, "register_model", reject_registration)
    with pytest.raises(PersistenceError, match="Artificial"):
        service.train("synthetic-registry-failure", FAST_CONFIG)
    assert not list(service.model_dir.glob("*.joblib"))
    assert not list(service.model_dir.glob(".training-*"))
    assert service.repository.list_models() == []


def test_retraining_an_existing_version_preserves_artifact_and_registry(service):
    model = service.train("synthetic-v1", FAST_CONFIG)
    artifact_path = Path(model["artifact_path"])
    original = artifact_path.read_bytes()
    with pytest.raises(TrainingError, match="already exists"):
        service.train("synthetic-v1", FAST_CONFIG)
    assert artifact_path.read_bytes() == original
    assert len(service.repository.list_models()) == 1


def test_evaluation_replay_refuses_changed_holdout_label_provenance(service):
    model = service.train("synthetic-v1", FAST_CONFIG)
    changed_id = model["training_info"]["test_ids"][0]
    with service.repository.engine.begin() as connection:
        connection.execute(
            update(MeasurementRow)
            .where(MeasurementRow.measurement_id == changed_id)
            .values(label_source="synthetic:modified-after-training")
        )
    with pytest.raises(TrainingError, match="changed"):
        service.evaluate_model(model["model_id"])


def test_missing_model_is_reported_without_creating_a_prediction(service):
    with pytest.raises(ModelNotFoundError):
        service.predict("synthetic-035", 999)
    assert service.repository.list_predictions() == []


def test_export_dataset_keeps_metadata_and_refuses_to_overwrite(service, tmp_path):
    import pandas as pd

    output = tmp_path / "synthetic-training.csv"
    summary = service.export_dataset(output)
    assert summary["measurement_count"] == 32
    frame = pd.read_csv(output)
    assert tuple(frame.columns[1:21]) == FEATURE_NAMES
    assert set(frame["label"]) == {0, 1}
    assert frame["label_source"].str.startswith("synthetic:").all()
    assert frame["source_fingerprint"].str.len().eq(64).all()
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        service.export_dataset(output)
    assert output.read_bytes() == original


def test_pending_batch_stops_after_first_persistence_failure(service, monkeypatch):
    model = service.train("synthetic-batch-failure", FAST_CONFIG)
    attempted = []
    failure = PersistenceError("Artificial connection loss")

    def connection_lost(measurement_id, _model_id, _artifact):
        attempted.append(measurement_id)
        raise failure

    pending = service.repository.pending_measurement_ids(model["model_id"], limit=3)
    assert len(pending) == 3
    monkeypatch.setattr(service, "_predict", connection_lost)
    with pytest.raises(PersistenceError, match="connection loss") as raised:
        service.process_pending(model["model_id"], limit=3)
    assert raised.value is failure
    assert attempted == pending[:1]
    assert service.repository.list_predictions() == []


def test_uncertain_registration_preserves_artifact_when_registry_cannot_be_checked(
    service,
    monkeypatch,
):
    original_list_models = service.repository.list_models
    checks = []
    failure = PersistenceError("Artificial uncertain registration outcome")

    def registry_unavailable_after_initial_check():
        checks.append(True)
        if len(checks) == 1:
            return original_list_models()
        raise PersistenceError("Artificial registry check connection loss")

    def registration_outcome_unknown(_metadata, _importances):
        raise failure

    monkeypatch.setattr(service.repository, "list_models", registry_unavailable_after_initial_check)
    monkeypatch.setattr(service.repository, "register_model", registration_outcome_unknown)
    with pytest.raises(PersistenceError, match="uncertain registration") as raised:
        service.train("synthetic-uncertain", FAST_CONFIG)
    assert raised.value is failure
    assert len(checks) == 2
    artifacts = list(service.model_dir.glob("*.joblib"))
    assert [path.name for path in artifacts] == ["synthetic-uncertain.joblib"]
    assert artifacts[0].stat().st_size > 0
    assert not list(service.model_dir.glob(".training-*"))
