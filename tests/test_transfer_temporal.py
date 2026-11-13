import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_temporal import cycle_context


def fixture():
    starts = pd.date_range("2026-01-01", periods=6, freq="20s")
    return pd.DataFrame(
        {
            "observation_id": list("abcdef"),
            "dependency_group_id": "one",
            "started_at": starts,
            "ended_at": starts + pd.Timedelta(seconds=10),
            "target_label": [0, 0, 0, 1, 0, 1],
            "partition_name": "train",
        }
    )


def test_causal_context_excludes_current_and_future_duration_and_all_labels_from_baseline():
    frame = fixture()
    frame.loc[3, "ended_at"] += pd.Timedelta(seconds=5)
    expected = cycle_context(frame)
    assert expected.duration_relative_history.iloc[3] == pytest.approx(1.5)
    assert np.isnan(expected.duration_relative_history.iloc[2])
    changed = frame.copy()
    changed.loc[5, "ended_at"] += pd.Timedelta(seconds=100)
    changed["target_label"] = 1 - changed.target_label
    actual = cycle_context(changed)
    columns = ["elapsed_seconds", "duration_relative_history", "history_cycles_support"]
    pd.testing.assert_frame_equal(expected.iloc[:5][columns], actual.iloc[:5][columns])


def test_context_resets_at_group_boundary_and_refuses_development_test_access():
    frame = fixture()
    frame.loc[4:, "dependency_group_id"] = "two"
    assert np.isnan(cycle_context(frame).duration_relative_history.iloc[4])
    frame.loc[5, "partition_name"] = "test"
    with pytest.raises(DataValidationError):
        cycle_context(frame)
