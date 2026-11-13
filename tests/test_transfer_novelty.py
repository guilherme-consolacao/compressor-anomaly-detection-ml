import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_novelty import (
    META_NAMES,
    crossfit_normality,
    fit_normality,
    normality_vectors,
)


def test_normality_vectors_are_finite_and_separate_large_public_signal_deviation():
    normal = np.random.default_rng(2026).normal(size=(80, 3))
    model = fit_normality(normal)
    near = normality_vectors(model, np.zeros((1, 3)))
    far = normality_vectors(model, np.full((1, 3), 100.0))
    assert list(far) == META_NAMES
    assert far.mean_tail_rarity.iloc[0] > near.mean_tail_rarity.iloc[0]
    assert (far.to_numpy() >= 0).all() and (far.to_numpy() <= 1).all()
    with pytest.raises(DataValidationError):
        normality_vectors(model, [[np.nan, 0, 0]])


def test_crossfit_never_borrows_held_group_normals_to_make_training_possible():
    frame = pd.DataFrame(
        {
            "value": np.arange(60, dtype=float),
            "target_label": [0] * 30 + [1] * 30,
            "group": ["a"] * 30 + ["b"] * 30,
        }
    )
    with pytest.raises(DataValidationError):
        crossfit_normality(frame, ["value"], "group")
