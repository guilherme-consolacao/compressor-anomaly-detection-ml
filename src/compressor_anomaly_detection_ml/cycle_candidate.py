"""Frozen public cycle classifier; separate from the legacy sensor-vector model."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression

from .domain import DataValidationError, ModelCompatibilityError
from .temporal_confirmation import FEATURE, development_folds, fit_reference_classifier
from .transfer_novelty import META_NAMES, crossfit_normality, fit_normality, normality_vectors
from .transfer_temporal import completed_cycle_context

CONTRACT = "cycle-context-normality-v1"


def train_cycle_candidate(smart, auxiliary, calibration_scores, protocol):
    smart = smart.copy()
    smart["bucket"] = development_folds(smart).to_numpy()
    if set(calibration_scores.observation_id) != set(smart.observation_id):
        raise DataValidationError(
            "Calibration must cover exactly the held-group development cases."
        )
    calibration = smart[["observation_id", "target_label"]].merge(
        calibration_scores[["observation_id", "reference", "score"]],
        on="observation_id",
        validate="one_to_one",
    )
    if not calibration.target_label.eq(calibration.reference).all():
        raise DataValidationError("Calibration reference changed.")
    meta = crossfit_normality(smart, [FEATURE], "bucket")
    training = pd.concat([smart[["source_id", "target_label"]], meta], axis=1)
    forest = fit_reference_classifier(training, auxiliary, protocol["variant"], protocol)
    normality = fit_normality(smart.loc[smart.target_label.eq(0), [FEATURE]])
    sigmoid = LogisticRegression(C=1, max_iter=1000, random_state=2026).fit(
        calibration[["score"]].to_numpy(), calibration.target_label
    )
    return {
        "artifact_format": "public-cycle-1",
        "contract_version": CONTRACT,
        "sklearn_version": sklearn.__version__,
        "feature_names": META_NAMES,
        "normality": normality,
        "forest": forest,
        "sigmoid": sigmoid,
        "threshold": protocol["raw_decision_threshold"],
        "cycle_context": protocol["cycle_context"],
        "probability_support": protocol["probability_support"],
        "local_portability_status": protocol["local_portability_status"],
    }, meta


def score_meta(artifact, vectors):
    raw = artifact["forest"].predict_proba(vectors[META_NAMES])[:, 1]
    mapped = artifact["sigmoid"].predict_proba(raw[:, None])[:, 1]
    return raw, mapped


def score_ratios(artifact, ratios):
    ratios = np.asarray(ratios, float).reshape(-1, 1)
    if not len(ratios) or not np.isfinite(ratios).all() or (ratios <= 0).any():
        raise DataValidationError("Positive finite completed-cycle duration ratios are required.")
    return score_meta(artifact, normality_vectors(artifact["normality"], ratios))


def load_cycle_candidate(manifest_path: Path, model_dir: Path):
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        path = Path(manifest["artifact_path"]).resolve()
        if not path.is_relative_to(model_dir.resolve()):
            raise ValueError
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifact_sha256"]:
            raise ValueError
        # joblib is pickle-based; only locally generated artifacts in MODEL_DIR are trusted.
        try:
            artifact = joblib.load(path)
        except Exception:
            raise ModelCompatibilityError("Cannot load the trusted cycle artifact.") from None
        if (
            artifact.get("artifact_format") != "public-cycle-1"
            or artifact.get("contract_version") != CONTRACT
            or artifact.get("sklearn_version") != sklearn.__version__
            or artifact.get("feature_names") != META_NAMES
            or manifest.get("contract_version") != CONTRACT
            or not artifact.get("version")
            or not artifact.get("dataset_version")
            or any(
                artifact.get(key) != manifest.get(key)
                for key in ("version", "dataset_version", "threshold")
            )
        ):
            raise ValueError
        return artifact, manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise ModelCompatibilityError(
            "Unavailable or incompatible trusted cycle artifact."
        ) from None


def predict_completed_cycles(artifact, records):
    required = {"cycle_id", "equipment_id", "started_at", "ended_at", "closed", "boundary_evidence"}
    if not isinstance(records, list) or not records or len(records) > 10000:
        raise DataValidationError("Provide 1 to 10000 confirmed completed cycles.")
    normalized = []
    now = pd.Timestamp(datetime.now(UTC))
    for record in records:
        if not isinstance(record, dict) or set(record) != required or record["closed"] is not True:
            raise DataValidationError(
                "Only explicitly closed cycles with boundary evidence qualify."
            )
        for key in ("cycle_id", "equipment_id", "boundary_evidence"):
            if (
                not isinstance(record[key], str)
                or not record[key].strip()
                or len(record[key]) > 255
            ):
                raise DataValidationError(
                    "Cycle identity, equipment and evidence must be explicit."
                )
        times = []
        for key in ("started_at", "ended_at"):
            try:
                timestamp = pd.Timestamp(record[key])
                if pd.isna(timestamp) or timestamp.tzinfo is None or timestamp > now:
                    raise ValueError
                times.append(timestamp.tz_convert("UTC"))
            except (ValueError, TypeError):
                raise DataValidationError(
                    "Cycle boundaries require past timezone-aware times."
                ) from None
        normalized.append(
            {
                "observation_id": json.dumps([record["equipment_id"], record["cycle_id"]]),
                "dependency_group_id": record["equipment_id"],
                "started_at": times[0],
                "ended_at": times[1],
            }
        )
    frame = completed_cycle_context(pd.DataFrame(normalized), **artifact["cycle_context"])
    output = []
    for record, (_, row) in zip(records, frame.iterrows(), strict=True):
        result = {
            "cycle_id": record["cycle_id"],
            "equipment_id": record["equipment_id"],
            "history_cycles_support": int(row.history_cycles_support),
            "scope": "public research reference; local performance unvalidated",
        }
        if pd.isna(row.duration_relative_history):
            result.update({"status": "insufficient_context", "predicted_class": None})
        else:
            raw, mapped = score_ratios(artifact, [row.duration_relative_history])
            result.update(
                {
                    "status": "classified",
                    "predicted_class": int(raw[0] >= artifact["threshold"]),
                    "uncalibrated_reference_score": float(raw[0]),
                    "experimental_reference_probability": float(mapped[0]),
                    "probability_support": artifact["probability_support"],
                    "duration_relative_history": float(row.duration_relative_history),
                }
            )
        output.append(result)
    return output
