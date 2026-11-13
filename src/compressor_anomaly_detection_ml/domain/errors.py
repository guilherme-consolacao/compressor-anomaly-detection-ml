"""Application errors have safe messages; driver errors must not reach CLI output."""


class MLBackendError(Exception):
    """Expected application failure."""


class ConfigurationError(MLBackendError):
    pass


class ContractError(MLBackendError):
    pass


class DataValidationError(MLBackendError):
    pass


class TrainingError(MLBackendError):
    pass


class ModelCompatibilityError(MLBackendError):
    pass


class ModelNotFoundError(MLBackendError):
    pass


class PersistenceError(MLBackendError):
    pass
