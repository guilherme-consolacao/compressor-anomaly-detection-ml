"""Configuration tests use placeholders and never contact a database."""

import pytest

from compressor_anomaly_detection_ml import config
from compressor_anomaly_detection_ml.config import Settings, TrainingConfig
from compressor_anomaly_detection_ml.domain import ConfigurationError


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
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


def test_mysql_url_safely_handles_password_special_characters(monkeypatch):
    placeholders = {
        "DB_HOST": "example.invalid",
        "DB_NAME": "synthetic_db",
        "DB_USER": "placeholder",
        "DB_PASSWORD": "placeholder:p@ss/word?",
        "DB_PORT": "3307",
    }
    for key, value in placeholders.items():
        monkeypatch.setenv(key, value)
    settings = Settings.from_env()
    assert settings.database_url.drivername == "mysql+pymysql"
    assert settings.database_url.password == placeholders["DB_PASSWORD"]
    assert settings.database_url.port == 3307
    assert placeholders["DB_PASSWORD"] not in repr(settings)
    assert settings.poll_interval_seconds == 30
    assert settings.training == TrainingConfig()


def test_missing_database_configuration_is_explicit():
    with pytest.raises(ConfigurationError, match="DB_HOST"):
        Settings.from_env()


def test_explicit_sqlite_configuration_is_supported(monkeypatch, tmp_path):
    monkeypatch.setenv("ML_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("RF_N_ESTIMATORS", "10")
    monkeypatch.setenv("RF_N_JOBS", "1")
    settings = Settings.from_env()
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.model_dir == tmp_path.resolve()
    assert settings.log_level == "WARNING"
    assert settings.training.n_estimators == 10
    assert settings.training.n_jobs == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("POLL_INTERVAL_SECONDS", "0"),
        ("POLL_INTERVAL_SECONDS", "86401"),
        ("POLL_INTERVAL_SECONDS", "nan"),
        ("POLL_INTERVAL_SECONDS", "not-a-number"),
        ("RF_N_ESTIMATORS", "zero"),
        ("RF_N_ESTIMATORS", "0"),
        ("RF_N_JOBS", "0"),
        ("LOG_LEVEL", "invalid"),
    ],
)
def test_invalid_environment_values_fail_clearly(monkeypatch, field, value):
    monkeypatch.setenv("ML_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv(field, value)
    with pytest.raises(ConfigurationError):
        Settings.from_env()


@pytest.mark.parametrize(
    "changes",
    [
        {"n_estimators": 0},
        {"n_jobs": 0},
        {"test_size": 0},
        {"test_size": 1},
        {"class_weight": "unbalanced"},
    ],
)
def test_invalid_training_configuration_fails_before_fitting(changes):
    with pytest.raises(ConfigurationError):
        TrainingConfig(**changes)
