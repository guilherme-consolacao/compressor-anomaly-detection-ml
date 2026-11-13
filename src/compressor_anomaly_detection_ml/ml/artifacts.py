import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
import sklearn

from ..domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    SIGNAL_DEFINITION,
    ModelCompatibilityError,
    ModelNotFoundError,
    TrainingError,
)


def save_artifact(artifact: dict[str, Any], model_dir: Path, version: str) -> tuple[Path, str]:
    model_dir = model_dir.resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / f"{version}.joblib"
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".training-", dir=model_dir)
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            joblib.dump(artifact, stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows rename is exclusive; POSIX rename would replace an old version.
        # Both branches publish the complete file without overwriting a version.
        if os.name == "nt":
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
        return target, hashlib.sha256(target.read_bytes()).hexdigest()
    except FileExistsError:
        raise TrainingError("A model artifact with this version already exists.") from None
    except OSError:
        raise TrainingError("Could not save the model artifact in MODEL_DIR.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_artifact(metadata: dict[str, Any], model_dir: Path) -> dict[str, Any]:
    try:
        path = Path(metadata["artifact_path"]).resolve()
        if not path.is_relative_to(model_dir.resolve()):
            raise ModelCompatibilityError(
                "Model artifact is outside the configured trusted MODEL_DIR."
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (FileNotFoundError, KeyError):
        raise ModelNotFoundError("The registered model artifact is unavailable.") from None
    except OSError:
        raise ModelNotFoundError("Cannot read the registered model artifact.") from None
    if digest != metadata.get("artifact_sha256"):
        raise ModelCompatibilityError("Model artifact checksum does not match its registry entry.")
    # joblib is pickle-based: only artifacts created locally in the trusted directory are supported.
    try:
        artifact = joblib.load(path)
    except Exception:
        raise ModelCompatibilityError(
            "Could not load the registered trusted model artifact."
        ) from None
    if not isinstance(artifact, dict):
        raise ModelCompatibilityError("Invalid model artifact format.")
    for key in ("version", "processing_version", "feature_names", "signal_definition"):
        if artifact.get(key) != metadata.get(key):
            raise ModelCompatibilityError(f"Registry and artifact disagree on {key}.")
    if (
        artifact.get("artifact_format") != 1
        or tuple(artifact.get("feature_names", ())) != FEATURE_NAMES
        or artifact.get("processing_version") != PROCESSING_VERSION
        or artifact.get("signal_definition") != SIGNAL_DEFINITION
        or artifact.get("training_info", {}).get("sklearn_version") != sklearn.__version__
    ):
        raise ModelCompatibilityError(
            "Incompatible artifact, signal, features or scikit-learn version."
        )
    return artifact
