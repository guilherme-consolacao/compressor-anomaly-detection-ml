"""Synthetic fixtures verify the supervised workflow, never real-world performance."""

import copy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.config import TrainingConfig
from compressor_anomaly_detection_ml.domain import (
    FEATURE_NAMES,
    PROCESSING_VERSION,
    SIGNAL_DEFINITION,
    Measurement,
    ModelCompatibilityError,
    ModelNotFoundError,
    Reading,
    TrainingError,
)
from compressor_anomaly_detection_ml.features import extract_features
from compressor_anomaly_detection_ml.ml.artifacts import load_artifact, save_artifact
from compressor_anomaly_detection_ml.ml.inference import predict_features
from compressor_anomaly_detection_ml.ml.training import evaluate, prepare_dataset, train_model


def synthetic_measurements() -> list[Measurement]:
    """Independent synthetic cycles, each with normal and anomalous examples."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    measurements = []
    for group in range(8):
        for label in (0, 1):
            index = group * 2 + label
            timestamp = start + timedelta(minutes=index)
            measurements.append(
                Measurement(
                    measurement_id=f"synthetic-{index:02d}",
                    equipment_id="synthetic-compressor",
                    started_at=timestamp,
                    ended_at=timestamp + timedelta(seconds=15),
                    status="FINALIZADA",
                    expected_reading_count=3,
                    readings=tuple(
                        Reading(
                            reading_id=index * 3 + sample + 1,
                            timestamp=timestamp + timedelta(seconds=sample),
                            temperature_c=20 + 25 * label + group / 10 + sample / 10,
                            vibration_rms_g=0.5 + 2 * label + sample / 10,
                            axis_x_g=-0.3 - label - sample / 10,
                            axis_y_g=0.2 + label + sample / 10,
                            axis_z_g=0.1 + 2 * label + sample / 10,
                        )
                        for sample in range(3)
                    ),
                    label=label,
                    label_source="synthetic:controlled-test-fixture",
                    group_id=f"synthetic-cycle-{group}",
                    acceleration_unit="g",
                )
            )
    return measurements


@pytest.fixture(scope="module")
def measurements():
    return synthetic_measurements()


@pytest.fixture(scope="module")
def dataset(measurements):
    return prepare_dataset(measurements)


@pytest.fixture(scope="module")
def trained(dataset, tmp_path_factory):
    model_dir = tmp_path_factory.mktemp("synthetic-models")
    metadata, importances = train_model(
        dataset,
        "synthetic-v1",
        model_dir,
        TrainingConfig(n_estimators=10, n_jobs=1),
    )
    return metadata, importances, model_dir


def test_dataset_has_one_ordered_feature_row_per_measurement(measurements):
    dataset = prepare_dataset(measurements[::-1])
    assert tuple(dataset.frame.columns) == FEATURE_NAMES
    assert dataset.frame.shape == (16, 20)
    assert dataset.measurement_ids == tuple(sorted(m.measurement_id for m in measurements))
    assert set(dataset.labels) == {0, 1}
    assert len(set(dataset.groups)) == 8
    assert dataset.frame.iloc[0].tolist() == list(extract_features(measurements[0]).values)
    assert dataset.manifest()[0] == {
        "measurement_id": measurements[0].measurement_id,
        "group_id": measurements[0].group_id,
        "fingerprint": extract_features(measurements[0]).source_fingerprint,
        "label": 0,
        "label_source": measurements[0].label_source,
    }


def test_empty_and_duplicate_measurements_are_rejected(measurements):
    with pytest.raises(TrainingError, match="No finalized"):
        prepare_dataset([])
    with pytest.raises(TrainingError, match="Repeated"):
        prepare_dataset([*measurements, measurements[0]])


@pytest.mark.parametrize("label", [None, True, "1", 0.0, -1, 2])
def test_invalid_labels_are_rejected(measurements, label):
    with pytest.raises(TrainingError, match="label"):
        prepare_dataset([replace(measurements[0], label=label), *measurements[1:]])


@pytest.mark.parametrize("field", ["label_source", "group_id"])
@pytest.mark.parametrize("value", [None, "", "   ", 42])
def test_missing_label_provenance_and_groups_are_rejected(measurements, field, value):
    with pytest.raises(TrainingError):
        prepare_dataset([replace(measurements[0], **{field: value}), *measurements[1:]])


def test_one_class_cannot_masquerade_as_binary_training(measurements):
    with pytest.raises(TrainingError, match="both classes"):
        prepare_dataset([replace(measurement, label=0) for measurement in measurements])


def test_grouped_holdout_has_no_measurement_or_group_leakage(trained, dataset):
    metadata, _, _ = trained
    trace = metadata["training_info"]
    assert set(trace["train_ids"]).isdisjoint(trace["test_ids"])
    assert set(trace["train_groups"]).isdisjoint(trace["test_groups"])
    assert set(trace["train_ids"]) | set(trace["test_ids"]) == set(dataset.measurement_ids)
    manifest = {row["measurement_id"]: row for row in trace["manifest"]}
    for split in ("train", "test"):
        assert {manifest[mid]["label"] for mid in trace[f"{split}_ids"]} == {0, 1}
        assert {manifest[mid]["group_id"] for mid in trace[f"{split}_ids"]} == set(
            trace[f"{split}_groups"]
        )
    assert trace["measurement_count"] == 16
    assert trace["class_distribution"] == {"0": 8, "1": 8}
    assert trace["synthetic"] is True
    assert len(trace["dataset_fingerprint"]) == 64


def test_model_metrics_and_importances_are_recorded_per_version(trained):
    metadata, importances, _ = trained
    metrics = metadata["metrics"]
    assert metrics["class_order"] == [0, 1]
    assert np.asarray(metrics["confusion_matrix"]).shape == (2, 2)
    assert set(metrics["per_class"]) == {"0", "1"}
    assert sum(metrics["per_class"][str(c)]["support"] for c in (0, 1)) == 4
    for key in ("accuracy", "precision", "recall", "f1"):
        assert 0 <= metrics[key] <= 1
    assert tuple(importances) == FEATURE_NAMES
    assert sum(importances.values()) == pytest.approx(1)
    assert all(value >= 0 for value in importances.values())
    assert metadata["parameters"]["n_estimators"] == 10
    assert metadata["parameters"]["n_jobs"] == 1
    assert metadata["processing_version"] == PROCESSING_VERSION
    assert metadata["signal_definition"] == SIGNAL_DEFINITION


def test_each_class_needs_multiple_independent_groups(measurements, tmp_path):
    correlated = [
        replace(measurement, group_id="one-normal-cycle") if measurement.label == 0 else measurement
        for measurement in measurements
    ]
    with pytest.raises(TrainingError, match="independent groups"):
        train_model(
            prepare_dataset(correlated),
            "invalid",
            tmp_path,
            TrainingConfig(n_estimators=10, n_jobs=1),
        )
    assert not list(tmp_path.glob("*.joblib"))


@pytest.mark.parametrize("version", ["", "../escape", "with space", "a" * 101])
def test_unsafe_or_invalid_model_versions_are_rejected(dataset, tmp_path, version):
    with pytest.raises(TrainingError, match="version"):
        train_model(dataset, version, tmp_path, TrainingConfig(n_estimators=10, n_jobs=1))


def test_artifact_round_trip_recovers_model_and_compatibility_contract(trained, measurements):
    metadata, _, model_dir = trained
    artifact = load_artifact(metadata, model_dir)
    assert artifact["version"] == metadata["version"]
    assert artifact["feature_names"] == list(FEATURE_NAMES)
    assert artifact["classifier"].n_estimators == 10
    assert set(artifact["classifier"].classes_) == {0, 1}
    prediction = predict_features(artifact, extract_features(measurements[0]))
    assert prediction.predicted_class in (0, 1)
    assert prediction.probability_normal + prediction.probability_anomaly == pytest.approx(1)


def test_published_model_version_cannot_be_overwritten(trained):
    metadata, _, model_dir = trained
    artifact = load_artifact(metadata, model_dir)
    original_bytes = Path(metadata["artifact_path"]).read_bytes()
    with pytest.raises(TrainingError, match="already exists"):
        save_artifact(artifact, model_dir, metadata["version"])
    assert Path(metadata["artifact_path"]).read_bytes() == original_bytes
    assert not list(model_dir.glob(".training-*"))


def test_missing_artifact_is_reported(trained, tmp_path):
    metadata, _, _ = trained
    with pytest.raises(ModelNotFoundError):
        load_artifact({**metadata, "artifact_path": str(tmp_path / "missing.joblib")}, tmp_path)


def test_artifact_outside_trusted_directory_is_rejected(trained, tmp_path):
    metadata, _, _ = trained
    with pytest.raises(ModelCompatibilityError, match="outside"):
        load_artifact(metadata, tmp_path)


def test_checksum_mismatch_is_rejected_before_deserialization(trained, monkeypatch):
    metadata, _, model_dir = trained
    calls = []
    monkeypatch.setattr(joblib, "load", lambda _: calls.append(True))
    with pytest.raises(ModelCompatibilityError, match="checksum"):
        load_artifact({**metadata, "artifact_sha256": "0" * 64}, model_dir)
    assert calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", "different-version"),
        ("processing_version", "different-processing"),
        ("feature_names", list(FEATURE_NAMES[::-1])),
        ("signal_definition", "different-signal"),
    ],
)
def test_registry_and_artifact_contract_must_agree(trained, field, value):
    metadata, _, model_dir = trained
    with pytest.raises(ModelCompatibilityError, match="disagree"):
        load_artifact({**metadata, field: value}, model_dir)


@pytest.mark.parametrize("change", ["format", "sklearn", "processing", "features", "signal"])
def test_self_consistent_but_unsupported_artifacts_are_rejected(trained, tmp_path, change):
    metadata, _, model_dir = trained
    artifact = copy.deepcopy(load_artifact(metadata, model_dir))
    registry = dict(metadata)
    if change == "format":
        artifact["artifact_format"] = 999
    elif change == "sklearn":
        artifact["training_info"]["sklearn_version"] = "0.0.synthetic"
    else:
        key, value = {
            "processing": ("processing_version", "incompatible"),
            "features": ("feature_names", list(FEATURE_NAMES[::-1])),
            "signal": ("signal_definition", "temporal-rms"),
        }[change]
        artifact[key] = value
        registry[key] = value
    path, digest = save_artifact(artifact, tmp_path, f"invalid-{change}")
    registry.update(artifact_path=str(path), artifact_sha256=digest)
    with pytest.raises(ModelCompatibilityError, match="Incompatible"):
        load_artifact(registry, tmp_path)


class FixedClassifier:
    classes_ = np.array([1, 0])
    feature_names_in_ = np.array(FEATURE_NAMES)

    def predict(self, frame):
        return np.ones(len(frame), dtype=int)

    def predict_proba(self, frame):
        return np.tile([0.7, 0.3], (len(frame), 1))


@pytest.fixture
def fake_artifact():
    return {
        "feature_names": list(FEATURE_NAMES),
        "processing_version": PROCESSING_VERSION,
        "classifier": FixedClassifier(),
    }


def test_probabilities_follow_classes_instead_of_assuming_array_order(fake_artifact, measurements):
    result = predict_features(fake_artifact, extract_features(measurements[0]))
    assert result.predicted_class == 1
    assert result.probability_normal == 0.3
    assert result.probability_anomaly == 0.7


@pytest.mark.parametrize(
    "changes",
    [
        {"feature_names": FEATURE_NAMES[::-1]},
        {"processing_version": "future-processing"},
        {"values": (0.0,) * 19},
        {"values": (float("nan"),) * 20},
        {"values": (float("inf"),) * 20},
        {"values": ("invalid",) * 20},
        {"values": (None,) * 20},
    ],
)
def test_incompatible_input_order_version_shape_and_values_fail(
    fake_artifact, measurements, changes
):
    features = replace(extract_features(measurements[0]), **changes)
    with pytest.raises(ModelCompatibilityError, match="incompatible"):
        predict_features(fake_artifact, features)


def test_classifier_feature_names_and_classes_are_validated(fake_artifact, measurements):
    features = extract_features(measurements[0])
    fake_artifact["classifier"].feature_names_in_ = np.array(FEATURE_NAMES[::-1])
    with pytest.raises(ModelCompatibilityError, match="feature names"):
        predict_features(fake_artifact, features)
    fake_artifact["classifier"].feature_names_in_ = np.array(FEATURE_NAMES)
    fake_artifact["classifier"].classes_ = np.array([0])
    with pytest.raises(ModelCompatibilityError, match="classes"):
        predict_features(fake_artifact, features)


@pytest.mark.parametrize("probabilities", [[0.1, 0.1], [-0.1, 1.1], [np.nan, 0.0], [1.0]])
def test_invalid_classifier_probabilities_are_rejected(fake_artifact, measurements, probabilities):
    fake_artifact["classifier"].predict_proba = lambda _: [probabilities]
    with pytest.raises(ModelCompatibilityError, match="invalid prediction"):
        predict_features(fake_artifact, extract_features(measurements[0]))


def test_metrics_use_explicit_normal_anomaly_order():
    class KnownPredictions:
        def predict(self, _):
            return np.array([0, 1, 1, 0])

    metrics = evaluate(
        KnownPredictions(),
        pd.DataFrame(np.zeros((4, 20)), columns=FEATURE_NAMES),
        np.array([0, 0, 1, 1]),
    )
    assert metrics["confusion_matrix"] == [[1, 1], [1, 1]]
    assert metrics["class_order"] == [0, 1]
    for key in ("accuracy", "precision", "recall", "f1"):
        assert metrics[key] == 0.5


def test_evaluation_requires_both_classes_and_exact_feature_order():
    with pytest.raises(TrainingError, match="ordered features"):
        evaluate(FixedClassifier(), pd.DataFrame(np.zeros((2, 20))), np.array([0, 1]))
    with pytest.raises(TrainingError, match="both known classes"):
        evaluate(
            FixedClassifier(),
            pd.DataFrame(np.zeros((2, 20)), columns=FEATURE_NAMES),
            np.array([0, 0]),
        )
