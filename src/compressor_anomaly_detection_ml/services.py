import json
import logging
from pathlib import Path
from typing import Any

from .config import TrainingConfig
from .database import Repository
from .domain import MLBackendError, PersistenceError, TrainingError
from .features import extract_features
from .ml import evaluate, load_artifact, predict_features, prepare_dataset, train_model

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self, repository: Repository, model_dir: Path):
        self.repository = repository
        self.model_dir = model_dir.resolve()

    def extract(self, measurement_id: str) -> dict[str, Any]:
        features = extract_features(self.repository.get_measurement(measurement_id))
        self.repository.save_features(measurement_id, features)
        return {
            "measurement_id": measurement_id,
            "features": features.as_dict(),
            "processing_version": features.processing_version,
            "source_fingerprint": features.source_fingerprint,
            "reading_count": features.reading_count,
        }

    def dataset(self):
        return prepare_dataset(self.repository.list_labeled_measurements())

    def export_dataset(self, path: Path) -> dict[str, Any]:
        dataset = self.dataset()
        frame = dataset.frame.copy()
        frame.insert(0, "measurement_id", dataset.measurement_ids)
        frame["label"] = dataset.labels
        frame["group_id"] = dataset.groups
        frame["label_source"] = dataset.label_sources
        frame["source_fingerprint"] = dataset.fingerprints
        # Exclusive creation protects an earlier exported training set.
        with path.open("x", encoding="utf-8", newline="") as stream:
            frame.to_csv(stream, index=False)
        return {
            "path": str(path.resolve()),
            "measurement_count": len(frame),
            "class_distribution": {str(c): int(sum(dataset.labels == c)) for c in (0, 1)},
        }

    def train(self, version: str, config: TrainingConfig | None = None) -> dict[str, Any]:
        if any(model["version"] == version for model in self.repository.list_models()):
            raise TrainingError("A registered model with this version already exists.")
        dataset = self.dataset()
        metadata, importances = train_model(dataset, version, self.model_dir, config)
        try:
            model_id = self.repository.register_model(metadata, importances)
        except Exception:
            # A connection can fail after the server commits. Remove this new
            # file only when a registry read confirms it is not referenced.
            try:
                registered = self.repository.list_models()
                referenced = any(
                    model.get("artifact_path") == metadata["artifact_path"]
                    and model.get("artifact_sha256") == metadata["artifact_sha256"]
                    for model in registered
                )
                if not referenced:
                    Path(metadata["artifact_path"]).unlink(missing_ok=True)
            except (MLBackendError, OSError):
                logger.error(
                    "model registration outcome uncertain; artifact retained version=%s", version
                )
            raise
        logger.info(
            "trained model_id=%s version=%s measurements=%s", model_id, version, len(dataset.labels)
        )
        return {**metadata, "model_id": model_id, "feature_importances": importances}

    def evaluate_model(self, model_id: int) -> dict[str, Any]:
        metadata = self.repository.get_model(model_id)
        artifact = load_artifact(metadata, self.model_dir)
        info = artifact["training_info"]
        if set(info["test_ids"]) & set(info["train_ids"]):
            raise TrainingError("The registered evaluation split overlaps training measurements.")
        dataset = prepare_dataset(
            [self.repository.get_measurement(mid) for mid in info["test_ids"]]
        )
        expected = {item["measurement_id"]: item for item in info["manifest"]}
        if any(item != expected.get(item["measurement_id"]) for item in dataset.manifest()):
            raise TrainingError("Evaluation data changed since training; holdout replay refused.")
        return {
            "model_id": model_id,
            "version": metadata["version"],
            "evaluation": "replay of the registered held-out groups",
            "measurement_ids": list(dataset.measurement_ids),
            "metrics": evaluate(artifact["classifier"], dataset.frame, dataset.labels),
        }

    def predict(self, measurement_id: str, model_id: int) -> dict[str, Any]:
        metadata = self.repository.get_model(model_id)
        artifact = load_artifact(metadata, self.model_dir)
        return self._predict(measurement_id, model_id, artifact)

    def _predict(self, measurement_id: str, model_id: int, artifact: dict) -> dict[str, Any]:
        logger.info("processing measurement_id=%s model_id=%s", measurement_id, model_id)
        try:
            features = extract_features(self.repository.get_measurement(measurement_id))
            result = predict_features(artifact, features)
            prediction, created = self.repository.complete_prediction(
                measurement_id,
                model_id,
                features,
                result,
            )
            logger.info(
                "completed measurement_id=%s model_id=%s readings=%s created=%s",
                measurement_id,
                model_id,
                features.reading_count,
                created,
            )
            return {**prediction, "created": created}
        except MLBackendError as exc:
            logger.warning(
                "failed measurement_id=%s model_id=%s error=%s",
                measurement_id,
                model_id,
                type(exc).__name__,
            )
            try:
                self.repository.record_processing_error(
                    measurement_id,
                    model_id,
                    type(exc).__name__,
                    str(exc),
                )
            except MLBackendError:
                logger.error(
                    "could not record processing error measurement_id=%s model_id=%s",
                    measurement_id,
                    model_id,
                )
            raise

    def process_pending(self, model_id: int, limit: int = 100) -> dict[str, Any]:
        metadata = self.repository.get_model(model_id)
        artifact = load_artifact(metadata, self.model_dir)
        ids = self.repository.pending_measurement_ids(model_id, limit)
        predictions, errors = [], []
        for measurement_id in ids:
            try:
                predictions.append(self._predict(measurement_id, model_id, artifact))
            except PersistenceError:
                # Stop this batch so watch can back off instead of repeating a
                # failing database operation once for every selected measurement.
                raise
            except MLBackendError as exc:
                errors.append({"measurement_id": measurement_id, "error": type(exc).__name__})
        return {
            "model_id": model_id,
            "examined": len(ids),
            "created": sum(item["created"] for item in predictions),
            "predictions": predictions,
            "errors": errors,
        }

    def model_details(self, model_id: int) -> dict[str, Any]:
        # Check that metadata is JSON serializable without ever loading a pickle.
        return json.loads(json.dumps(self.repository.get_model(model_id)))
