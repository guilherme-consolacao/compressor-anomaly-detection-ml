"""Synthetic measurements exercise validation and exact statistical behavior."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pytest

from compressor_anomaly_detection_ml.domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    ContractError,
    DataValidationError,
    Measurement,
    Reading,
)
from compressor_anomaly_detection_ml.features import extract_features


@pytest.fixture
def measurement():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return Measurement(
        measurement_id="synthetic-measurement",
        equipment_id="synthetic-equipment",
        started_at=start,
        ended_at=start + timedelta(seconds=15),
        status="FINALIZADA",
        expected_reading_count=2,
        readings=(
            Reading(1, start + timedelta(seconds=1), -2.0, 1.0, -7.0, 2.0, -3.0),
            Reading(2, start + timedelta(seconds=2), 6.0, 5.0, 3.0, -4.0, 9.0),
        ),
        acceleration_unit="g",
    )


def test_exact_population_statistics_and_feature_order(measurement):
    features = extract_features(measurement)
    assert features.feature_names == FEATURE_NAMES
    assert tuple(features.as_dict()) == FEATURE_NAMES
    assert features.processing_version == PROCESSING_VERSION
    assert features.reading_count == 2
    assert features.values == pytest.approx(
        (2, 6, 8, 4, 3, 5, 4, 2, -2, 7, 10, 5, -1, 4, 6, 3, 3, 9, 12, 6)
    )
    assert len(features.source_fingerprint) == 64


def test_reversed_input_is_deterministic_and_is_not_mutated(measurement):
    reversed_measurement = replace(measurement, readings=measurement.readings[::-1])
    assert extract_features(reversed_measurement) == extract_features(measurement)
    assert reversed_measurement.readings[0].reading_id == 2


def test_equal_second_timestamps_are_valid_and_deterministic(measurement):
    readings = tuple(replace(row, timestamp=measurement.started_at) for row in measurement.readings)
    first = replace(measurement, readings=readings)
    second = replace(measurement, readings=readings[::-1])
    assert extract_features(first) == extract_features(second)


def test_equivalent_timezones_have_the_same_fingerprint(measurement):
    offset = timezone(timedelta(hours=-3))
    converted = replace(
        measurement,
        started_at=measurement.started_at.astimezone(offset),
        ended_at=measurement.ended_at.astimezone(offset),
        readings=tuple(
            replace(row, timestamp=row.timestamp.astimezone(offset)) for row in measurement.readings
        ),
    )
    assert extract_features(converted) == extract_features(measurement)


def test_decimal_and_numpy_numeric_values_are_accepted(measurement):
    readings = tuple(
        replace(
            row, temperature_c=Decimal(str(row.temperature_c)), axis_x_g=np.float64(row.axis_x_g)
        )
        for row in measurement.readings
    )
    assert extract_features(replace(measurement, readings=readings)) == extract_features(
        measurement
    )


@pytest.mark.parametrize(
    "field", ["temperature_c", "vibration_rms_g", "axis_x_g", "axis_y_g", "axis_z_g"]
)
@pytest.mark.parametrize("value", [None, "1.2", True, np.nan, np.inf, -np.inf, Decimal("NaN")])
def test_missing_nonnumeric_and_nonfinite_values_fail(measurement, field, value):
    readings = (replace(measurement.readings[0], **{field: value}), measurement.readings[1])
    with pytest.raises(DataValidationError, match=field):
        extract_features(replace(measurement, readings=readings))


def test_negative_rms_fails(measurement):
    readings = (replace(measurement.readings[0], vibration_rms_g=-0.1), measurement.readings[1])
    with pytest.raises(DataValidationError, match="nonnegative"):
        extract_features(replace(measurement, readings=readings))


@pytest.mark.parametrize("status", ["ABERTA", "PROCESSADA", "ERRO", "", None])
def test_only_finalized_acquisition_measurements_are_processed(measurement, status):
    with pytest.raises(ContractError, match="FINALIZADA"):
        extract_features(replace(measurement, status=status))


@pytest.mark.parametrize("unit", ["unknown", "m/s2", "", None])
def test_acceleration_unit_requires_explicit_confirmation(measurement, unit):
    with pytest.raises(ContractError, match="confirmed"):
        extract_features(replace(measurement, acceleration_unit=unit))


def test_signal_definition_cannot_change_silently(measurement):
    with pytest.raises(ContractError, match="signal definition"):
        extract_features(replace(measurement, signal_definition="temporal-rms"))


@pytest.mark.parametrize("field", ["started_at", "ended_at"])
@pytest.mark.parametrize("value", [None, "2026-01-01", datetime(2026, 1, 1)])
def test_missing_or_naive_measurement_timestamps_fail(measurement, field, value):
    with pytest.raises(DataValidationError, match="timestamp"):
        extract_features(replace(measurement, **{field: value}))


def test_end_before_start_fails(measurement):
    with pytest.raises(DataValidationError, match="precede"):
        extract_features(
            replace(measurement, ended_at=measurement.started_at - timedelta(seconds=1))
        )


@pytest.mark.parametrize("seconds", [-1, 16])
def test_readings_outside_explicit_measurement_boundaries_fail(measurement, seconds):
    readings = (
        replace(
            measurement.readings[0], timestamp=measurement.started_at + timedelta(seconds=seconds)
        ),
        measurement.readings[1],
    )
    with pytest.raises(DataValidationError, match="outside"):
        extract_features(replace(measurement, readings=readings))


def test_naive_reading_timestamp_fails(measurement):
    readings = (
        replace(measurement.readings[0], timestamp=datetime(2026, 1, 1)),
        measurement.readings[1],
    )
    with pytest.raises(DataValidationError, match="timestamp"):
        extract_features(replace(measurement, readings=readings))


@pytest.mark.parametrize("readings", [(), (None,), ({"temperature_c": 1.0},)])
def test_empty_incomplete_and_untyped_readings_fail(measurement, readings):
    with pytest.raises(DataValidationError):
        extract_features(
            replace(measurement, readings=readings, expected_reading_count=len(readings))
        )


def test_two_samples_are_a_required_minimum(measurement):
    with pytest.raises(DataValidationError, match="at least"):
        extract_features(
            replace(measurement, readings=measurement.readings[:1], expected_reading_count=1)
        )


def test_configurable_minimum_is_enforced(measurement):
    with pytest.raises(DataValidationError, match="at least 3"):
        extract_features(measurement, min_samples=3)


@pytest.mark.parametrize("minimum", [0, 1, True, 2.0, "2"])
def test_invalid_minimum_configuration_fails(measurement, minimum):
    with pytest.raises(ContractError, match="min_samples"):
        extract_features(measurement, min_samples=minimum)


@pytest.mark.parametrize("count", [3, 0, -1, None, True, 2.0])
def test_invalid_or_inconsistent_expected_count_fails(measurement, count):
    with pytest.raises(DataValidationError):
        extract_features(replace(measurement, expected_reading_count=count))


@pytest.mark.parametrize("reading_id", [0, -1, True, "3", 1.0])
def test_reading_ids_are_positive_integers(measurement, reading_id):
    readings = (replace(measurement.readings[0], reading_id=reading_id), measurement.readings[1])
    with pytest.raises(DataValidationError, match="reading_id"):
        extract_features(replace(measurement, readings=readings))


def test_duplicate_reading_ids_fail(measurement):
    readings = (measurement.readings[0], replace(measurement.readings[1], reading_id=1))
    with pytest.raises(DataValidationError, match="duplicate"):
        extract_features(replace(measurement, readings=readings))


@pytest.mark.parametrize("field", ["equipment_id", "measurement_id"])
def test_missing_measurement_identifiers_fail(measurement, field):
    with pytest.raises(DataValidationError, match=field):
        extract_features(replace(measurement, **{field: " "}))


def test_overflow_is_a_validation_error(measurement):
    readings = (
        replace(measurement.readings[0], temperature_c=-1e308),
        replace(measurement.readings[1], temperature_c=1e308),
    )
    with pytest.raises(DataValidationError, match="limits"):
        extract_features(replace(measurement, readings=readings))


def test_changed_samples_and_boundaries_change_fingerprint(measurement):
    original = extract_features(measurement)
    changed_readings = (
        replace(measurement.readings[0], temperature_c=0.0),
        measurement.readings[1],
    )
    assert extract_features(replace(measurement, readings=changed_readings)).source_fingerprint != (
        original.source_fingerprint
    )
    assert (
        extract_features(
            replace(measurement, ended_at=measurement.ended_at + timedelta(seconds=1))
        ).source_fingerprint
        != original.source_fingerprint
    )


def test_labels_are_not_part_of_feature_fingerprint(measurement):
    assert extract_features(replace(measurement, label=1, label_source="synthetic")) == (
        extract_features(measurement)
    )
