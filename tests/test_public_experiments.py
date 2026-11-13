import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.public_experiments import (
    binary_metrics,
    candidate_matrix,
    coupling_sensitivity,
    source_weights,
    transfer_experiments,
    unit_label,
)


def test_unpaired_marginals_cannot_identify_cross_source_correlation():
    report = coupling_sensitivity(np.arange(20), np.arange(20) ** 2)
    assert report["scenarios"]["same_quantile"]["spearman"] == pytest.approx(1)
    assert report["scenarios"]["opposite_quantile"]["spearman"] == pytest.approx(-1)
    assert "not observed" in report["kind"]
    with pytest.raises(DataValidationError):
        coupling_sensitivity(np.zeros(10), np.arange(10))


def test_undefined_binary_metrics_remain_absent():
    result = binary_metrics([0, 0], [0, 0], [0.1, 0.2])
    assert result["recall"] is None and result["balanced_accuracy"] is None
    assert result["precision"] is None and result["average_precision"] is None
    assert result["accuracy"] == 1


def test_unknown_unit_survives_dataframe_null_materialization():
    assert all(unit_label(value) == "unit unconfirmed" for value in [None, np.nan, pd.NA, ""])
    assert unit_label("degC") == "degC"


def test_candidate_features_reject_constant_signal_instead_of_zero_imputation():
    frame = pd.DataFrame({"observation_id": ["a"], "source_id": ["smart_pdm"]})
    values = pd.DataFrame(
        {
            "observation_id": ["a"] * 5,
            "feature_name": [
                "Vibration__skewness",
                "Vibration__kurtosis",
                "Vibration__maximum",
                "Vibration__minimum",
                "Vibration__standard_deviation",
            ],
            "numeric_value": [0, 0, 1, 1, 0],
        }
    )
    with pytest.raises(DataValidationError, match="undefined"):
        candidate_matrix(frame, values)


def comparison_fixture():
    rows = []
    for source in ["smart_pdm", "kaist"]:
        for role in ["train", "validation", "test"]:
            for i in range(12):
                label = i % 2
                rows.append(
                    {
                        "observation_id": f"{source}:{role}:{i}",
                        "source_id": source,
                        "partition_name": role,
                        "target_label": label,
                        "dependency_group_id": f"{source}:{role}:group",
                        "condition_json": {"recording": role + str(label)},
                        "skewness": float(label),
                        "kurtosis": float(label + i / 10),
                        "range_over_std": 3.0 + label,
                    }
                )
    return pd.DataFrame(rows).set_index("observation_id")


def test_transfer_does_not_fit_or_evaluate_reserved_test():
    protocol = json.loads(Path("config/public-study-v1.json").read_text())
    frame = comparison_fixture()
    first, predictions = transfer_experiments(frame, protocol)
    assert not first["test_used"] and first["pseudo_labels_accepted"] == 0
    frame.loc[frame.partition_name == "test", protocol["candidate_features"]] = 9999
    second, changed_predictions = transfer_experiments(frame, protocol)
    assert first == second
    pd.testing.assert_frame_equal(predictions, changed_predictions)
    weights = source_weights(frame.loc[frame.partition_name == "train"])
    weighted = frame.loc[frame.partition_name == "train"].assign(weight=weights)
    assert weighted.groupby("source_id").weight.sum().nunique() == 1
