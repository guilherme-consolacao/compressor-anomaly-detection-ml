"""Clearly artificial data for a local SQLite demonstration only."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from .config import TrainingConfig
from .database import (
    Repository,
    create_engine_for_url,
    create_isolated_schema,
    insert_isolated_measurement,
)
from .domain import Measurement, Reading
from .services import MLService


def synthetic_measurements(count: int = 36) -> list[Measurement]:
    rng = np.random.default_rng(42)
    measurements = []
    for index in range(count):
        anomaly = index % 2
        start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
        readings = []
        for sample in range(16):
            axes = rng.normal(0, 0.03 if not anomaly else 0.25, size=3)
            readings.append(
                Reading(
                    index * 16 + sample + 1,
                    start + timedelta(seconds=sample),
                    float(rng.normal(30 if not anomaly else 50, 0.5)),
                    float(np.sqrt(np.mean(axes**2))),
                    *map(float, axes),
                )
            )
        measurements.append(
            Measurement(
                f"synthetic-{index:03}",
                "synthetic-compressor",
                start,
                start + timedelta(seconds=15),
                "FINALIZADA",
                len(readings),
                tuple(readings),
                label=anomaly if index < count - 4 else None,
                label_source="synthetic:software-demo-only" if index < count - 4 else None,
                group_id=f"synthetic-cycle-{index // 2:03}",
                acceleration_unit="g",
            )
        )
    return measurements


def run_demo(database_path: Path) -> dict:
    database_path = database_path.resolve()
    # Reject existing files before initializing any tables.
    with database_path.open("xb"):
        pass
    engine = create_engine_for_url(f"sqlite:///{database_path.as_posix()}")
    try:
        create_isolated_schema(engine)
        for measurement in synthetic_measurements():
            insert_isolated_measurement(engine, measurement)
        service = MLService(
            Repository(engine), database_path.parent / "models" / database_path.stem
        )
        model = service.train("synthetic-v1", TrainingConfig())
        result = service.predict("synthetic-035", model["model_id"])
        repeated = service.predict("synthetic-035", model["model_id"])
        return {
            "synthetic": True,
            "purpose": "software flow validation only; no real fault evidence",
            "database_path": str(database_path),
            "model_id": model["model_id"],
            "model_version": model["version"],
            "metrics": model["metrics"],
            "prediction": result,
            "repeat_created": repeated["created"],
        }
    finally:
        engine.dispose()
