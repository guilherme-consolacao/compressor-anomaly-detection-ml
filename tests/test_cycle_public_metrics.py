import pandas as pd

from scripts.evaluate_cycle_candidate import measured_metrics


def test_public_metrics_keep_unsupported_false_positive_rate_undefined():
    frame = pd.DataFrame({"reference": [1, 1], "score": [0.8, 0.1], "group": ["day", "day"]})
    result = measured_metrics(frame, 0.5)
    assert result["tp"] == result["fn"] == 1
    assert result["recall"] == 0.5
    assert result["false_positive_rate"] is None
    assert result["balanced_accuracy"] is None
    assert result["positive_groups"] == 1
