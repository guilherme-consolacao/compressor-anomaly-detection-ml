import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.temporal_confirmation import (
    development_folds,
    fit_reference_classifier,
    training_threshold,
)
from compressor_anomaly_detection_ml.transfer_novelty import META_NAMES


def test_threshold_respects_normal_budget_and_can_abstain_from_all_alerts():
    labels = np.array([0] * 10 + [1, 1])
    scores = np.array([0.1] * 9 + [0.8, 0.7, 0.9])
    threshold = training_threshold(labels, scores)
    assert threshold == pytest.approx(0.7)
    assert (scores[:10] >= threshold).mean() <= 0.1
    assert training_threshold([0, 1], [0.9, 0.1], maximum_fpr=0) > 0.9


def test_fit_rejects_missing_reference_class_and_reserved_development():
    frame = pd.DataFrame({name: np.linspace(0, 1, 40) for name in META_NAMES})
    frame["source_id"] = "smart_pdm"
    frame["target_label"] = 0
    with pytest.raises(DataValidationError):
        fit_reference_classifier(frame, frame.iloc[:0], {"sources": []}, {})
    frame["partition_name"] = "test"
    frame["dependency_group_id"] = "smart_pdm:week-block:2022-09"
    with pytest.raises(DataValidationError):
        development_folds(frame)
