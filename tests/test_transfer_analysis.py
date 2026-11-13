import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_analysis import anchor_diagnostics, paired_bridge


def test_anchor_refuses_reserved_or_unknown_groups_before_training():
    frame = pd.DataFrame({"partition_name": ["test"], "source_id": ["smart_pdm"]})
    with pytest.raises(DataValidationError):
        anchor_diagnostics(frame, [])
    frame["partition_name"] = "train"
    frame["dependency_group_id"] = "local-machine"
    with pytest.raises(DataValidationError):
        anchor_diagnostics(frame, [])


def test_measured_bridge_generalizes_a_known_relation_with_groups_and_no_label_transfer():
    x = np.tile(np.arange(10, dtype=float), 3)
    frame = pd.DataFrame({"x": x, "y": 2 * x + 3, "session": np.repeat(["a", "b", "c"], 10)})
    report = paired_bridge(frame, ["x"], ["y"], "session", name="fixture")
    ridge = next(row for row in report["results"] if row["model"] == "ridge")
    baseline = next(row for row in report["results"] if row["model"] == "group_mean")
    assert ridge["mae"] < baseline["mae"]
    assert report["labels_transferred"] == 0
    with pytest.raises(DataValidationError):
        paired_bridge(frame, ["session"], ["y"], "session", name="leaking")
