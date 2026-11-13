from datetime import UTC, datetime, timedelta

import pytest

from compressor_anomaly_detection_ml import reading_measurements
from compressor_anomaly_detection_ml.domain import DataValidationError


def sample(equipment, reading_id, seconds):
    return {
        "equipment_id": equipment,
        "reading_id": reading_id,
        "timestamp": (datetime(2025, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)).isoformat(),
    }


def test_time_groups_keep_membership_and_score_only_with_bounded_history(monkeypatch):
    artifact = {
        "cycle_context": {"history_size": 10, "minimum_history": 3, "maximum_gap_hours": 12},
        "threshold": 0.5,
    }
    offsets = [0, 5, 100, 110, 200, 210, 300, 310, 400, 410, 410, 420, 500, 505]
    readings = [sample("a", index, seconds) for index, seconds in enumerate(offsets)]
    readings += [sample("b", 0, 410)]
    scored = []

    def score(artifact, ratios):
        scored.extend(ratios)
        return [0.75], [0.9]

    monkeypatch.setattr(reading_measurements, "score_ratios", score)
    predict = reading_measurements.predict_reading_measurements
    result = predict(artifact, list(reversed(readings)), gap_seconds=10)
    assert result == predict(artifact, readings, gap_seconds=10)
    assert [row["status"] for row in result] == [
        "snapshot_boundary",
        "insufficient_context",
        "insufficient_context",
        "insufficient_context",
        "exploratory_scored",
        "snapshot_boundary",
        "snapshot_boundary",
    ]
    group = result[4]
    assert group["observed_span_seconds"] == 20
    assert group["reading_ids"] == ["8", "10", "9", "11"]
    assert group["prior_measurements"] == 3
    assert scored == [2.0, 2.0]
    assert group["exploratory_alert"] is True
    assert "experimental_reference_probability" not in group


def test_time_groups_reject_duplicate_ids_and_timestamps_without_offset():
    reading = sample("a", 1, 0)
    predict = reading_measurements.predict_reading_measurements
    with pytest.raises(DataValidationError, match="unique"):
        predict({}, [reading, sample("a", "1", 1)], gap_seconds=10)
    with pytest.raises(DataValidationError, match="timezone"):
        predict({}, [{**reading, "timestamp": "2025-01-01T00:00:00"}], gap_seconds=10)
