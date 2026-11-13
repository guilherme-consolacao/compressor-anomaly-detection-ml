import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import GroupShuffleSplit

from ..config import TrainingConfig
from ..domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    SIGNAL_DEFINITION,
    Measurement,
    TrainingError,
)
from ..features import extract_features
from .artifacts import save_artifact


@dataclass(frozen=True)
class TrainingDataset:
    frame: pd.DataFrame
    labels: np.ndarray
    measurement_ids: tuple[str, ...]
    groups: tuple[str, ...]
    fingerprints: tuple[str, ...]
    label_sources: tuple[str, ...]

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "measurement_id": mid,
                "group_id": group,
                "fingerprint": fingerprint,
                "label": int(label),
                "label_source": source,
            }
            for mid, group, fingerprint, label, source in zip(
                self.measurement_ids,
                self.groups,
                self.fingerprints,
                self.labels,
                self.label_sources,
                strict=True,
            )
        ]


def prepare_dataset(measurements: list[Measurement]) -> TrainingDataset:
    if not measurements:
        raise TrainingError("No finalized labeled measurements available.")
    measurements = sorted(measurements, key=lambda measurement: measurement.measurement_id)
    ids = tuple(m.measurement_id for m in measurements)
    if len(set(ids)) != len(ids):
        raise TrainingError("Repeated measurement IDs in training data.")
    for m in measurements:
        if isinstance(m.label, bool) or not isinstance(m.label, (int, np.integer)):
            raise TrainingError(f"Measurement {m.measurement_id}: label must be integer 0 or 1.")
        if m.label not in (0, 1):
            raise TrainingError(f"Measurement {m.measurement_id}: label must be 0 or 1.")
        if not isinstance(m.label_source, str) or not m.label_source.strip():
            raise TrainingError(f"Measurement {m.measurement_id}: label provenance is required.")
        if not isinstance(m.group_id, str) or not m.group_id.strip():
            raise TrainingError(f"Measurement {m.measurement_id}: explicit group_id is required.")
    labels = np.array([m.label for m in measurements], dtype=int)
    if set(labels) != {0, 1}:
        raise TrainingError("Supervised binary training requires both classes 0 and 1.")
    vectors = [extract_features(m) for m in measurements]
    return TrainingDataset(
        pd.DataFrame([vector.values for vector in vectors], columns=FEATURE_NAMES),
        labels,
        ids,
        tuple(m.group_id for m in measurements),
        tuple(vector.source_fingerprint for vector in vectors),
        tuple(m.label_source for m in measurements),
    )


def evaluate(classifier: Any, frame: pd.DataFrame, labels: np.ndarray) -> dict[str, Any]:
    if tuple(frame.columns) != FEATURE_NAMES or set(labels) != {0, 1}:
        raise TrainingError("Evaluation requires the ordered features and both known classes.")
    predicted = classifier.predict(frame)
    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predicted,
        labels=[0, 1],
        zero_division=0,
    )
    return {
        "confusion_matrix": confusion_matrix(labels, predicted, labels=[0, 1]).tolist(),
        "class_order": [0, 1],
        "accuracy": float(accuracy_score(labels, predicted)),
        "precision": float(precision[1]),
        "recall": float(recall[1]),
        "f1": float(f1[1]),
        "per_class": {
            str(label): {
                "precision": float(precision[label]),
                "recall": float(recall[label]),
                "f1": float(f1[label]),
                "support": int(support[label]),
            }
            for label in (0, 1)
        },
    }


def train_model(
    dataset: TrainingDataset,
    version: str,
    model_dir: Path,
    config: TrainingConfig | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    config = config or TrainingConfig()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", version):
        raise TrainingError(
            "Model version must be 1-100 letters, digits, dots, hyphens or underscores."
        )
    if set(dataset.labels) != {0, 1}:
        raise TrainingError("Supervised binary training requires both classes 0 and 1.")
    groups = np.array(dataset.groups)
    for label in (0, 1):
        if len(set(groups[dataset.labels == label])) < 2:
            raise TrainingError("Each class requires at least two independent groups.")
    splitter = GroupShuffleSplit(
        n_splits=100,
        test_size=config.test_size,
        random_state=config.random_state,
    )
    split = next(
        (
            (train, test)
            for train, test in splitter.split(dataset.frame, dataset.labels, groups)
            if set(dataset.labels[train]) == {0, 1} and set(dataset.labels[test]) == {0, 1}
        ),
        None,
    )
    if split is None:
        raise TrainingError("Could not form a grouped holdout with both classes on each side.")
    train, test = split
    classifier = RandomForestClassifier(
        n_estimators=config.n_estimators,
        class_weight=config.class_weight,
        random_state=config.random_state,
        n_jobs=config.n_jobs,
    )
    classifier.fit(dataset.frame.iloc[train], dataset.labels[train])
    metrics = evaluate(classifier, dataset.frame.iloc[test], dataset.labels[test])
    manifest = dataset.manifest()
    training_info = {
        "measurement_count": len(dataset.labels),
        "class_distribution": {str(c): int(sum(dataset.labels == c)) for c in (0, 1)},
        "evaluation_strategy": "GroupShuffleSplit; first valid split of 100 seeded candidates",
        "group_contract": "Explicit producer-provided correlation groups; no inferred groups",
        "random_state": config.random_state,
        "test_size": config.test_size,
        "train_ids": [dataset.measurement_ids[i] for i in train],
        "test_ids": [dataset.measurement_ids[i] for i in test],
        "train_groups": sorted(set(groups[train].tolist())),
        "test_groups": sorted(set(groups[test].tolist())),
        "manifest": manifest,
        "dataset_fingerprint": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        ).hexdigest(),
        "synthetic": any(
            source.lower().startswith("synthetic:") for source in dataset.label_sources
        ),
        "sklearn_version": sklearn.__version__,
    }
    metadata = {
        "name": "compressor-random-forest",
        "version": version,
        "trained_at": datetime.now(UTC).isoformat(),
        "feature_names": list(FEATURE_NAMES),
        "processing_version": PROCESSING_VERSION,
        "signal_definition": SIGNAL_DEFINITION,
        "parameters": asdict(config),
        "metrics": metrics,
        "training_info": training_info,
    }
    artifact = {**metadata, "classifier": classifier, "artifact_format": 1}
    path, digest = save_artifact(artifact, model_dir, version)
    metadata.update(artifact_path=str(path), artifact_sha256=digest)
    importances = dict(zip(FEATURE_NAMES, map(float, classifier.feature_importances_), strict=True))
    return metadata, importances
