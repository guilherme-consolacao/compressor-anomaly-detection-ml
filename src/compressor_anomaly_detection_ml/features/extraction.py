"""Extract the same twenty features for training and inference.

The incoming RMS is the acquisition API's spatial combination of three axes.
It is consumed unchanged; this module never recalibrates or derives temporal RMS.
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from numbers import Integral, Real

import numpy as np

from compressor_anomaly_detection_ml.domain import (
    PROCESSING_VERSION,
    SIGNAL_DEFINITION,
    ContractError,
    DataValidationError,
    FeatureVector,
    Measurement,
    Reading,
)

_SENSOR_FIELDS = (
    "temperature_c",
    "vibration_rms_g",
    "axis_x_g",
    "axis_y_g",
    "axis_z_g",
)


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise DataValidationError(f"{field}: timestamp must include a timezone")
    return value.astimezone(UTC)


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise DataValidationError(f"{field}: expected a finite numeric value")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise DataValidationError(f"{field}: expected a finite numeric value") from exc
    if not np.isfinite(result):
        raise DataValidationError(f"{field}: expected a finite numeric value")
    return result


def _positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise DataValidationError(f"{field}: expected a positive integer")
    return int(value)


def extract_features(measurement: Measurement, min_samples: int = 2) -> FeatureVector:
    """Validate one explicitly finalized measurement and return population statistics.

    All samples must be valid. Equal timestamps are allowed because acquisition
    stores only whole seconds; reading IDs provide deterministic tie breaking.
    The minimum of two samples is a software guard, not a vibration quality claim.
    """
    if isinstance(min_samples, bool) or not isinstance(min_samples, Integral) or min_samples < 2:
        raise ContractError("min_samples must be an integer of at least two")
    if not isinstance(measurement, Measurement):
        raise DataValidationError("measurement: expected the typed Measurement contract")
    if measurement.status != "FINALIZADA":
        raise ContractError("measurement must be FINALIZADA before processing")
    if measurement.acceleration_unit != "g":
        raise ContractError("acceleration unit must be explicitly confirmed as g")
    if measurement.signal_definition != SIGNAL_DEFINITION:
        raise ContractError("measurement signal definition is incompatible with this processing")
    for field in ("measurement_id", "equipment_id"):
        value = getattr(measurement, field)
        if not isinstance(value, str) or not value.strip():
            raise DataValidationError(f"{field}: a nonempty identifier is required")
    started_at = _utc(measurement.started_at, "started_at")
    ended_at = _utc(measurement.ended_at, "ended_at")
    if ended_at < started_at:
        raise DataValidationError("ended_at must not precede started_at")
    expected_count = _positive_integer(measurement.expected_reading_count, "expected_reading_count")
    if not isinstance(measurement.readings, (tuple, list)):
        raise DataValidationError("readings: a collection of typed Reading objects is required")
    if len(measurement.readings) != expected_count:
        raise DataValidationError("reading count does not match the finalized measurement")
    if expected_count < min_samples:
        raise DataValidationError(f"measurement requires at least {min_samples} samples")

    seen_ids: set[int] = set()
    samples: list[tuple[datetime, int, tuple[float, ...]]] = []
    for reading in measurement.readings:
        if not isinstance(reading, Reading):
            raise DataValidationError("readings: every entry must provide the typed Reading fields")
        reading_id = _positive_integer(reading.reading_id, "reading_id")
        if reading_id in seen_ids:
            raise DataValidationError(f"duplicate reading_id: {reading_id}")
        seen_ids.add(reading_id)
        timestamp = _utc(reading.timestamp, f"reading {reading_id} timestamp")
        if not started_at <= timestamp <= ended_at:
            raise DataValidationError(f"reading {reading_id} timestamp is outside the measurement")
        values = tuple(
            _number(getattr(reading, field), f"reading {reading_id} {field}")
            for field in _SENSOR_FIELDS
        )
        if values[1] < 0:
            raise DataValidationError(f"reading {reading_id} vibration_rms_g must be nonnegative")
        samples.append((timestamp, reading_id, values))
    samples.sort(key=lambda row: (row[0], row[1]))
    data = np.asarray([row[2] for row in samples], dtype=np.float64)
    statistics: list[float] = []
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for index in range(len(_SENSOR_FIELDS)):
                series = data[:, index]
                peak = np.max(series) if index < 2 else np.max(np.abs(series))
                statistics.extend(
                    float(value)
                    for value in (
                        np.mean(series),
                        peak,
                        np.max(series) - np.min(series),
                        np.std(series, ddof=0),
                    )
                )
    except (FloatingPointError, OverflowError) as exc:
        raise DataValidationError(
            "sensor magnitudes exceed safe statistical calculation limits"
        ) from exc
    if not np.isfinite(statistics).all():
        raise DataValidationError("statistical features must all be finite")

    source = {
        "measurement_id": measurement.measurement_id,
        "equipment_id": measurement.equipment_id,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "reading_count": expected_count,
        "acceleration_unit": measurement.acceleration_unit,
        "signal_definition": measurement.signal_definition,
        "processing_version": PROCESSING_VERSION,
        "readings": [
            [timestamp.isoformat(), reading_id, [value.hex() for value in values]]
            for timestamp, reading_id, values in samples
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FeatureVector(tuple(statistics), fingerprint, expected_count)
