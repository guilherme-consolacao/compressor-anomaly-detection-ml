"""Opt-in integration test; requires an EMPTY, dedicated MySQL test database.

No database is created automatically. Set MYSQL_TEST_URL to a database whose
name starts with ml_test_ or test_, plus MYSQL_TEST_ALLOW_WRITES=1. Existing
tables cause a refusal before any DDL, including the source ``readings`` table.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, inspect
from sqlalchemy.engine import make_url

from compressor_anomaly_detection_ml.database import (
    Repository,
    create_engine_for_url,
    inspect_contract,
)
from compressor_anomaly_detection_ml.database.models import (
    SOURCE_READINGS,
    Base,
    MeasurementReadingRow,
    MeasurementRow,
)
from compressor_anomaly_detection_ml.domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    SIGNAL_DEFINITION,
    FeatureVector,
    PredictionResult,
)


@pytest.mark.mysql
def test_isolated_mysql_roundtrip_and_idempotence():
    raw_url = os.getenv("MYSQL_TEST_URL")
    if not raw_url or os.getenv("MYSQL_TEST_ALLOW_WRITES") != "1":
        pytest.skip("Isolated MySQL URL and explicit write opt-in were not supplied.")
    parsed = make_url(raw_url)
    if parsed.get_backend_name() not in {"mysql", "mariadb"} or not (
        parsed.database or ""
    ).startswith(("ml_test_", "test_")):
        pytest.fail("MySQL integration requires a dedicated test_ or ml_test_ database.")
    engine = create_engine_for_url(parsed)
    inspector = inspect(engine)
    if inspector.get_table_names() or inspector.get_view_names():
        engine.dispose()
        pytest.fail("Refusing integration DDL because the dedicated database is not empty.")
    try:
        Base.metadata.create_all(engine)
        start = datetime(2026, 1, 1)
        with engine.begin() as connection:
            connection.execute(
                insert(SOURCE_READINGS),
                [
                    {
                        "id": index + 1,
                        "temperature": 30 + index,
                        "accel_x": 0.1,
                        "accel_y": 0.2,
                        "accel_z": 0.3,
                        "rms": 0.2,
                        "timestamp": start + timedelta(seconds=index),
                    }
                    for index in range(2)
                ],
            )
            connection.execute(
                insert(MeasurementRow).values(
                    measurement_id="synthetic-mysql-1",
                    equipment_id="synthetic-device",
                    started_at=start,
                    ended_at=start + timedelta(seconds=1),
                    status="FINALIZADA",
                    expected_reading_count=2,
                    label=0,
                    label_source="artificial MySQL integration fixture",
                    group_id="synthetic-group",
                    acceleration_unit="g",
                    signal_definition=SIGNAL_DEFINITION,
                )
            )
            connection.execute(
                insert(MeasurementReadingRow),
                [
                    {"reading_id": index + 1, "measurement_id": "synthetic-mysql-1"}
                    for index in range(2)
                ],
            )
        repository = Repository(engine)
        model_id = repository.register_model(
            {
                "name": "synthetic",
                "version": "mysql-v1",
                "processing_version": PROCESSING_VERSION,
                "feature_names": list(FEATURE_NAMES),
                "trained_at": datetime.now(UTC).isoformat(),
            },
            dict.fromkeys(FEATURE_NAMES, 0.05),
        )
        assert repository.get_measurement("synthetic-mysql-1").readings[0].timestamp.tzinfo == UTC
        features = FeatureVector(tuple(float(index) for index in range(20)), "a" * 64, 2)
        prediction, created = repository.complete_prediction(
            "synthetic-mysql-1", model_id, features, PredictionResult(1, 0.1, 0.9)
        )
        repeated, recreated = repository.complete_prediction(
            "synthetic-mysql-1", model_id, features, PredictionResult(1, 0.1, 0.9)
        )
        assert created and not recreated and repeated == prediction
        assert inspect_contract(engine)["measurement_contract_available"]
    finally:
        # Only objects created after the empty-database check are removed.
        Base.metadata.drop_all(engine)
        engine.dispose()
