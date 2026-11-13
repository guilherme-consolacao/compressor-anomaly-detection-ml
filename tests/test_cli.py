"""Operational commands use isolated SQLite and synthetic datasets exclusively."""

import json
import sqlite3

import pytest
from sqlalchemy import event, inspect

from compressor_anomaly_detection_ml import cli, config, demo
from compressor_anomaly_detection_ml.config import TrainingConfig
from compressor_anomaly_detection_ml.database import (
    create_engine_for_url,
    create_isolated_schema,
    insert_isolated_measurement,
)
from compressor_anomaly_detection_ml.demo import synthetic_measurements


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for key in (
        "ML_DATABASE_URL",
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_PORT",
        "MODEL_DIR",
        "POLL_INTERVAL_SECONDS",
        "LOG_LEVEL",
        "RF_N_ESTIMATORS",
        "RF_RANDOM_STATE",
        "RF_N_JOBS",
    ):
        monkeypatch.delenv(key, raising=False)


def test_missing_configuration_has_safe_json_error(capsys):
    assert cli.main(["models"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["error"] == "ConfigurationError"
    assert "DB_HOST" in result["message"]


@pytest.mark.parametrize("command", ["check-db", "inspect-contract"])
def test_schema_diagnostics_report_missing_contract_without_creating_tables(
    command,
    monkeypatch,
    tmp_path,
    capsys,
):
    database_path = tmp_path / "empty.sqlite"
    sqlite3.connect(database_path).close()
    monkeypatch.setenv("ML_DATABASE_URL", f"sqlite:///{database_path}")
    statements = []

    def traced_engine(url):
        engine = create_engine_for_url(url)

        def record_statement(_connection, _cursor, statement, _params, _context, _many):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_statement)
        return engine

    monkeypatch.setattr(cli, "create_engine_for_url", traced_engine)
    assert cli.main([command]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["connected"] is True
    assert report["measurement_contract_available"] is False
    assert "readings" in report["missing_tables"]
    assert not any(
        statement.lstrip().upper().startswith(("CREATE", "ALTER", "INSERT", "UPDATE"))
        for statement in statements
    )
    engine = create_engine_for_url(f"sqlite:///{database_path}")
    try:
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_demo_runs_without_database_env_and_refuses_existing_database(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(demo, "TrainingConfig", lambda: TrainingConfig(n_estimators=10, n_jobs=1))
    database_path = tmp_path / "demo.sqlite"
    assert cli.main(["demo", "--database", str(database_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["synthetic"] is True
    assert result["prediction"]["created"] is True
    assert result["repeat_created"] is False
    original = database_path.read_bytes()
    assert cli.main(["demo", "--database", str(database_path)]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "LocalIOError"
    assert database_path.read_bytes() == original


def test_dataset_export_and_operational_prediction_commands(monkeypatch, tmp_path, capsys):
    database_path = tmp_path / "synthetic.sqlite"
    engine = create_engine_for_url(f"sqlite:///{database_path}")
    create_isolated_schema(engine)
    for measurement in synthetic_measurements(36):
        insert_isolated_measurement(engine, measurement)
    engine.dispose()
    monkeypatch.setenv("ML_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "trusted-models"))
    monkeypatch.setenv("RF_N_ESTIMATORS", "10")
    monkeypatch.setenv("RF_N_JOBS", "1")

    output = tmp_path / "synthetic.csv"
    assert cli.main(["prepare-data", "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["measurement_count"] == 32
    assert output.read_text(encoding="utf-8").startswith("measurement_id,temp_media,")
    original = output.read_bytes()
    assert cli.main(["prepare-data", "--output", str(output)]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "LocalIOError"
    assert output.read_bytes() == original

    assert cli.main(["train", "--version", "synthetic-cli-v1"]) == 0
    model = json.loads(capsys.readouterr().out)
    model_id = str(model["model_id"])
    assert cli.main(["evaluate", "--model-id", model_id]) == 0
    assert json.loads(capsys.readouterr().out)["metrics"] == model["metrics"]
    assert cli.main(["predict", "synthetic-035", "--model-id", model_id]) == 0
    assert json.loads(capsys.readouterr().out)["created"] is True
    assert cli.main(["predictions"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["measurement_id"] == "synthetic-035"
    assert cli.main(["models"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["version"] == "synthetic-cli-v1"
