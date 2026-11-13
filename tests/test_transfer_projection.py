import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_projection import (
    reference_weights,
    select_measured_bridge,
    specific_refrigeration_state,
)


def test_projection_weights_balance_classes_and_limit_inferred_feature_source_mass():
    frame = pd.DataFrame(
        {
            "source_id": ["smart_pdm"] * 3 + ["tri_hp_faults"] * 4,
            "target_label": [0, 0, 1, 0, 1, 1, 1],
        }
    )
    weights = reference_weights(frame, 0.1)
    assert weights[:2].sum() == pytest.approx(weights[2])
    assert weights[3] == pytest.approx(weights[4:].sum())
    assert weights[3:].sum() / weights[:3].sum() == pytest.approx(0.1)
    with pytest.raises(DataValidationError):
        reference_weights(frame, 0.0)
    frame.loc[0, "source_id"] = "ulisses"
    with pytest.raises(DataValidationError):
        reference_weights(frame)


def test_bridge_filters_targets_by_held_session_support_and_regime_improvement():
    x = np.tile(np.linspace(0, 1, 30), 4)
    frame = pd.DataFrame(
        {
            "x": x,
            "control": np.zeros(len(x)),
            "target": x,
            "measurement_id": np.repeat(["a", "b", "c", "d"], 30),
            "source_id": "rwth_r290",
            "partition_name": "train",
        }
    )
    policy = {
        "model": {"n_estimators": 10, "max_depth": 5, "min_samples_leaf": 2, "random_state": 2026},
        "minimum_group_mae_improvement_over_regime": 0.2,
        "minimum_oof_r2": 0.3,
    }
    model, names, report = select_measured_bridge(frame, ["x"], ["control"], ["target"], policy)
    assert model is not None and names == ["target"]
    assert report["labels_transferred"] == 0
    assert report["results"][0]["mean_group_mae"] < report["results"][0]["control_mean_group_mae"]
    frame.loc[0, "partition_name"] = "test"
    with pytest.raises(DataValidationError):
        select_measured_bridge(frame, ["x"], ["control"], ["target"], policy)


def test_specific_work_removes_capacity_scaling_without_equating_sensor_locations():
    frame = pd.DataFrame({"power_kw": [1.0, 3.0], "mass_flow_gs": [10.0, 30.0]})
    result = specific_refrigeration_state(frame)
    assert result.specific_work_kjkg.tolist() == pytest.approx([100.0, 100.0])
    frame.loc[0, "mass_flow_gs"] = 0
    with pytest.raises(DataValidationError):
        specific_refrigeration_state(frame)


def test_operating_proxy_is_not_reported_as_incremental_failure_information():
    x = np.tile(np.linspace(0, 1, 20), 3)
    frame = pd.DataFrame(
        {
            "x": x,
            "target": x,
            "measurement_id": np.repeat(["a", "b", "c"], 20),
            "source_id": "rwth_r290",
            "partition_name": "train",
        }
    )
    policy = {
        "model": {"n_estimators": 10, "max_depth": 5, "min_samples_leaf": 2, "random_state": 2026},
        "minimum_group_mae_improvement_over_regime": 0.2,
        "minimum_oof_r2": 0.6,
        "admission_role": "operating_proxy",
        "minimum_group_mae_improvement_over_constant": 0.25,
    }
    model, names, report = select_measured_bridge(frame, ["x"], ["x"], ["target"], policy)
    assert model is not None and names == ["target"]
    assert report["results"][0]["incremental_over_regime_gate"] is False
    assert report["results"][0]["admission_role"] == "operating_proxy"
