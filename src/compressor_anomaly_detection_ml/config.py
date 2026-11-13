import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

from .domain import ConfigurationError


@dataclass(frozen=True)
class TrainingConfig:
    n_estimators: int = 200
    class_weight: str = "balanced"
    random_state: int = 42
    n_jobs: int = -1
    test_size: float = 0.25

    def __post_init__(self) -> None:
        if self.n_estimators < 1 or self.n_jobs == 0 or not 0 < self.test_size < 1:
            raise ConfigurationError("Invalid Random Forest or holdout configuration.")
        if self.class_weight != "balanced":
            raise ConfigurationError("This processing contract requires balanced class weights.")


@dataclass(frozen=True)
class Settings:
    database_url: str | URL = field(repr=False)
    model_dir: Path = Path("models")
    poll_interval_seconds: float = 30
    log_level: str = "INFO"
    training: TrainingConfig = TrainingConfig()

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        database_url: str | URL = os.getenv("ML_DATABASE_URL", "")
        try:
            if not database_url:
                required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
                if any(os.getenv(key) is None for key in required):
                    raise ConfigurationError("Configure DB_HOST/DB_NAME/DB_USER/DB_PASSWORD.")
                database_url = URL.create(
                    "mysql+pymysql",
                    username=os.environ["DB_USER"],
                    password=os.environ["DB_PASSWORD"],
                    host=os.environ["DB_HOST"],
                    port=int(os.getenv("DB_PORT", "3306")),
                    database=os.environ["DB_NAME"],
                    query={"charset": "utf8mb4"},
                )
            interval = float(os.getenv("POLL_INTERVAL_SECONDS", "30"))
            if not 1 <= interval <= 86400:
                raise ConfigurationError("POLL_INTERVAL_SECONDS must be between 1 and 86400.")
            training = TrainingConfig(
                n_estimators=int(os.getenv("RF_N_ESTIMATORS", "200")),
                random_state=int(os.getenv("RF_RANDOM_STATE", "42")),
                n_jobs=int(os.getenv("RF_N_JOBS", "-1")),
            )
        except ValueError:
            raise ConfigurationError("Invalid numeric environment configuration.") from None
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("Invalid LOG_LEVEL.")
        return cls(
            database_url,
            Path(os.getenv("MODEL_DIR", "models")).resolve(),
            interval,
            log_level,
            training,
        )
