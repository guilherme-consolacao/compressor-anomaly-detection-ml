import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.public_study import (
    make_partitions,
    validate_partition,
    week_groups,
)


def partition_fixture():
    return pd.DataFrame(
        {
            "observation_id": ["a", "b"],
            "dependency_group_id": ["same", "same"],
            "partition_name": ["train", "train"],
            "data_origin": ["public_measured"] * 2,
        }
    )


@pytest.mark.parametrize("problem", ["overlap", "duplicate", "external", "missing"])
def test_partition_refuses_leakage_and_missing_identity(problem):
    frame = partition_fixture()
    if problem == "overlap":
        frame.loc[1, "partition_name"] = "test"
    elif problem == "duplicate":
        frame.loc[1, "observation_id"] = "a"
    elif problem == "external":
        frame.loc[1, "data_origin"] = "ulisses_external"
    else:
        frame.loc[1, "dependency_group_id"] = None
    with pytest.raises(DataValidationError):
        validate_partition(frame)


def test_connected_weeks_keep_overlapping_cross_boundary_cycles_together():
    frame = pd.DataFrame(
        {
            "started_at": pd.to_datetime(
                ["2022-01-02T23:00Z", "2022-01-03T00:00Z", "2022-01-20T00:00Z"]
            ),
            "ended_at": pd.to_datetime(
                ["2022-01-03T01:00Z", "2022-01-03T02:00Z", "2022-01-20T01:00Z"]
            ),
        }
    )
    groups = week_groups(frame)
    assert groups.iloc[0] == groups.iloc[1] != groups.iloc[2]


def test_smart_group_split_is_deterministic_and_class_supported():
    days = pd.date_range("2022-01-03", periods=20, freq="7D", tz="UTC")
    frame = pd.DataFrame(
        {
            "observation_id": [str(i) for i in range(40)],
            "source_id": "smart_pdm",
            "data_origin": "public_measured",
            "dependency_group_id": "candidate",
            "started_at": days.repeat(2),
            "ended_at": days.repeat(2) + pd.Timedelta(hours=1),
            "target_label": np.tile([0, 1], 20),
        }
    )
    protocol = {"seed": 2026, "smart_min_positive_groups_per_partition": 2}
    first = make_partitions(frame, protocol)
    pd.testing.assert_frame_equal(first, make_partitions(frame, protocol))
    assert set(first.partition_name) == {"train", "validation", "test"}
    assert first.groupby("dependency_group_id").partition_name.nunique().max() == 1
