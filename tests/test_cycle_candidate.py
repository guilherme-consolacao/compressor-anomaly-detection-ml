import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.cycle_candidate import (
    CONTRACT,
    load_cycle_candidate,
    predict_completed_cycles,
    score_ratios,
    train_cycle_candidate,
)
from compressor_anomaly_detection_ml.domain import DataValidationError, ModelCompatibilityError
from compressor_anomaly_detection_ml.ml.artifacts import save_artifact
from compressor_anomaly_detection_ml.transfer_novelty import META_NAMES


@pytest.fixture
def artifact():
    smart = pd.DataFrame(
        [
            {
                "observation_id": f"fixture-{group}-{i}",
                "source_id": "smart_pdm",
                "partition_name": "train",
                "dependency_group_id": "smart_pdm:week-block:" + group,
                "target_label": int(i == 40),
                "duration_relative_history": 0.8 + i / 100,
            }
            for group in ("2022-09", "2022-11", "2022-16")
            for i in range(41)
        ]
    )
    auxiliary = pd.DataFrame({name: np.linspace(0, 1, 40) for name in META_NAMES})
    auxiliary["source_id"] = "tri_hp_faults"
    auxiliary["target_label"] = [0] * 20 + [1] * 20
    calibration = smart[["observation_id", "target_label"]].rename(
        columns={"target_label": "reference"}
    )
    calibration["score"] = 0.1 + calibration.reference * 0.7
    model, _ = train_cycle_candidate(
        smart,
        auxiliary,
        calibration,
        {
            "variant": {"sources": ["tri_hp_faults"], "leaf": 3},
            "classifier": {"n_estimators": 5, "max_depth": 5, "seed": 2026},
            "raw_decision_threshold": 0.5,
            "probability_support": "fixture only",
            "cycle_context": {"history_size": 10, "minimum_history": 3, "maximum_gap_hours": 12},
            "local_portability_status": "not validated",
        },
    )
    model["version"] = "fixture"
    model["dataset_version"] = "fixture-dataset"
    return model


def records():
    return [
        {
            "cycle_id": str(i),
            "equipment_id": "fixture",
            "started_at": f"2025-01-01T0{i}:00:00Z",
            "ended_at": f"2025-01-01T0{i}:30:00Z",
            "closed": True,
            "boundary_evidence": "synthetic fixture only",
        }
        for i in range(5)
    ]


def test_real_contract_requires_history_and_cannot_treat_packet_as_cycle(artifact):
    output = predict_completed_cycles(artifact, records())
    assert [row["status"] for row in output[:3]] == ["insufficient_context"] * 3
    assert output[3]["status"] == "classified"
    assert 0 <= output[3]["experimental_reference_probability"] <= 1
    with pytest.raises(DataValidationError):
        predict_completed_cycles(artifact, [{"temperature": 30, "x": 1, "y": 2, "z": 3}])
    changed = records()
    changed[4]["ended_at"] = "2025-01-01T07:00:00Z"
    assert predict_completed_cycles(artifact, changed)[:4] == output[:4]


def test_boundaries_must_be_aware_closed_past_and_unique(artifact):
    for key, value in (
        ("closed", False),
        ("boundary_evidence", ""),
        ("ended_at", "2025-01-01T00:30:00"),
        ("ended_at", "2099-01-01T00:30:00Z"),
    ):
        changed = records()
        changed[0][key] = value
        with pytest.raises(DataValidationError):
            predict_completed_cycles(artifact, changed)
    with pytest.raises(DataValidationError):
        predict_completed_cycles(artifact, [records()[0], records()[0]])


def test_artifact_roundtrip_checks_hash_trusted_directory_and_contract(artifact, tmp_path):
    path, sha = save_artifact(artifact, tmp_path / "models", "fixture")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifact_path": str(path),
                "artifact_sha256": sha,
                "contract_version": CONTRACT,
                "version": artifact["version"],
                "dataset_version": artifact["dataset_version"],
                "threshold": artifact["threshold"],
            }
        )
    )
    actual, _ = load_cycle_candidate(manifest, tmp_path / "models")
    np.testing.assert_allclose(score_ratios(artifact, [1, 1.5]), score_ratios(actual, [1, 1.5]))
    original = json.loads(manifest.read_text())
    manifest.write_text(json.dumps({**original, "version": "different"}))
    with pytest.raises(ModelCompatibilityError):
        load_cycle_candidate(manifest, tmp_path / "models")
    manifest.write_text(json.dumps(original))
    with pytest.raises(ModelCompatibilityError):
        load_cycle_candidate(manifest, tmp_path / "different")
    path.write_bytes(path.read_bytes() + b"tamper")
    assert hashlib.sha256(path.read_bytes()).hexdigest() != sha
    with pytest.raises(ModelCompatibilityError):
        load_cycle_candidate(manifest, tmp_path / "models")
    path.write_bytes(b"")
    data = json.loads(manifest.read_text())
    data["artifact_sha256"] = hashlib.sha256(b"").hexdigest()
    manifest.write_text(json.dumps(data))
    with pytest.raises(ModelCompatibilityError):
        load_cycle_candidate(manifest, tmp_path / "models")
