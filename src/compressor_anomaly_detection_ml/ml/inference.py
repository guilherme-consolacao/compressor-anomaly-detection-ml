from typing import Any

import numpy as np
import pandas as pd

from ..domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    FeatureVector,
    ModelCompatibilityError,
    PredictionResult,
)


def predict_features(artifact: dict[str, Any], features: FeatureVector) -> PredictionResult:
    try:
        finite = all(
            isinstance(value, (float, int, np.number))
            and not isinstance(value, bool)
            and np.isfinite(value)
            for value in features.values
        )
    except (AttributeError, TypeError, ValueError):
        finite = False
    if (
        features.feature_names != FEATURE_NAMES
        or features.processing_version != PROCESSING_VERSION
        or tuple(artifact.get("feature_names", ())) != features.feature_names
        or artifact.get("processing_version") != features.processing_version
        or len(features.values) != len(FEATURE_NAMES)
        or not finite
    ):
        raise ModelCompatibilityError(
            "Model and input feature order/version/values are incompatible."
        )
    classifier = artifact.get("classifier")
    try:
        classes = list(classifier.classes_)
        if len(classes) != 2 or set(classes) != {0, 1}:
            raise ModelCompatibilityError("The classifier must contain classes 0 and 1.")
        if (
            hasattr(classifier, "feature_names_in_")
            and tuple(classifier.feature_names_in_) != FEATURE_NAMES
        ):
            raise ModelCompatibilityError("The classifier has incompatible feature names.")
        frame = pd.DataFrame([features.values], columns=features.feature_names)
        predicted = classifier.predict(frame)[0]
        probabilities = np.asarray(classifier.predict_proba(frame)[0], dtype=float)
        if (
            predicted not in (0, 1)
            or probabilities.shape != (2,)
            or not np.isfinite(probabilities).all()
            or ((probabilities < 0) | (probabilities > 1)).any()
            or not np.isclose(probabilities.sum(), 1)
        ):
            raise ModelCompatibilityError("The classifier returned an invalid prediction.")
        return PredictionResult(
            int(predicted),
            float(probabilities[classes.index(0)]),
            float(probabilities[classes.index(1)]),
        )
    except ModelCompatibilityError:
        raise
    except Exception:
        raise ModelCompatibilityError(
            "The classifier could not predict the supplied features."
        ) from None
