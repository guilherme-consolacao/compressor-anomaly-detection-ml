"""Typed data contracts shared by extraction, persistence, and machine learning."""

from .entities import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    SIGNAL_DEFINITION,
    FeatureVector,
    Measurement,
    PredictionResult,
    Reading,
)
from .errors import (
    ConfigurationError,
    ContractError,
    DataValidationError,
    MLBackendError,
    ModelCompatibilityError,
    ModelNotFoundError,
    PersistenceError,
    TrainingError,
)

__all__ = [
    "FEATURE_NAMES",
    "PROCESSING_VERSION",
    "SIGNAL_DEFINITION",
    "FeatureVector",
    "Measurement",
    "PredictionResult",
    "Reading",
    "ConfigurationError",
    "ContractError",
    "DataValidationError",
    "MLBackendError",
    "ModelCompatibilityError",
    "ModelNotFoundError",
    "PersistenceError",
    "TrainingError",
]
