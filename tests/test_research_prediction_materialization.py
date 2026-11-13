import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from scripts.materialize_research_predictions import canonical_scores


def test_canonical_selection_keeps_controls_and_refuses_duplicate_or_invalid_scores():
    frame = pd.DataFrame(
        {
            "variant": ["real", "control"],
            "shuffle_seed": [-1, 2026],
            "mode": ["raw_fixed"] * 2,
            "observation_id": ["a", "a"],
            "score": [0.2, 0.8],
        }
    )
    assert len(canonical_scores(frame)) == 2
    with pytest.raises(DataValidationError):
        canonical_scores(pd.concat([frame, frame]))
    frame.loc[0, "score"] = float("inf")
    with pytest.raises(DataValidationError):
        canonical_scores(frame)
