"""Nested public-only controls for the completed-cycle reference classifier."""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from .domain import DataValidationError
from .public_experiments import binary_metrics
from .transfer_analysis import SMART_FOLDS
from .transfer_novelty import META_NAMES, crossfit_normality, fit_normality, normality_vectors

FEATURE = "duration_relative_history"


def development_folds(frame):
    if not frame.source_id.eq("smart_pdm").all() or frame.partition_name.eq("test").any():
        raise DataValidationError("Only public SMART development groups may fit this pipeline.")
    folds = frame.dependency_group_id.str.removeprefix("smart_pdm:week-block:").map(SMART_FOLDS)
    if folds.isna().any() or frame.target_label.isna().any():
        raise DataValidationError("Explicit known public groups and references are required.")
    return folds.astype(int)


def prepare_reference(frame, held):
    training = frame.loc[~held].copy().reset_index(drop=True)
    training["bucket"] = development_folds(training).to_numpy()
    group = "bucket" if training.bucket.nunique() >= 2 else "dependency_group_id"
    meta = crossfit_normality(training, [FEATURE], group)
    vectors = pd.concat([training[["source_id", "target_label"]], meta], axis=1)
    normality = fit_normality(training.loc[training.target_label.eq(0), [FEATURE]])
    validation = normality_vectors(normality, frame.loc[held, [FEATURE]])
    return vectors, validation, normality


def fit_reference_classifier(training, auxiliary, variant, protocol, *, shuffle_seed=None):
    auxiliary = auxiliary.loc[auxiliary.source_id.isin(variant["sources"])].copy()
    if shuffle_seed is not None:
        rng = np.random.default_rng(shuffle_seed)
        for source in sorted(auxiliary.source_id.unique()):
            selected = auxiliary.source_id.eq(source)
            auxiliary.loc[selected, "target_label"] = rng.permutation(
                auxiliary.loc[selected, "target_label"].to_numpy()
            )
    fit = pd.concat([training, auxiliary], ignore_index=True)
    weights = np.zeros(len(fit))
    for source in sorted(fit.source_id.unique()):
        mass = 1.0 if source == "smart_pdm" else 1.0 / len(variant["sources"])
        for label in (0, 1):
            selected = fit.source_id.eq(source) & fit.target_label.eq(label)
            if not selected.any():
                raise DataValidationError("Every source must support both reference classes.")
            weights[selected] = mass / (2 * selected.sum())
    weights *= len(weights) / weights.sum()
    model = RandomForestClassifier(
        n_estimators=protocol["classifier"]["n_estimators"],
        max_depth=protocol["classifier"]["max_depth"],
        min_samples_leaf=variant["leaf"],
        random_state=protocol["classifier"]["seed"],
        n_jobs=1,
    )
    return model.fit(fit[META_NAMES], fit.target_label.astype(int), sample_weight=weights)


def training_threshold(labels, scores, maximum_fpr=0.1):
    labels, scores = np.asarray(labels, int), np.asarray(scores, float)
    if set(labels) != {0, 1} or not np.isfinite(scores).all():
        raise DataValidationError("Threshold fitting needs both finite public reference classes.")
    candidates = np.unique(np.r_[scores, np.nextafter(scores.max(), np.inf)])
    ranked = []
    for threshold in candidates:
        predicted = scores >= threshold
        fpr = predicted[labels == 0].mean()
        recall = predicted[labels == 1].mean()
        if fpr <= maximum_fpr:
            ranked.append((recall, (recall + 1 - fpr) / 2, threshold))
    return float(max(ranked)[2])


def nested_confirmation(smart, auxiliary, protocol):
    folds = development_folds(smart)
    prepared = {}
    for fold in sorted(folds.unique()):
        held = folds.eq(fold)
        outer_training, outer_validation, _ = prepare_reference(smart, held)
        outer_fit = smart.loc[~held].copy().reset_index(drop=True)
        inner_folds = development_folds(outer_fit)
        inner = []
        for inner_fold in sorted(inner_folds.unique()):
            inner_held = inner_folds.eq(inner_fold)
            training, validation, _ = prepare_reference(outer_fit, inner_held)
            inner.append((inner_held.to_numpy(), training, validation))
        prepared[fold] = (held, outer_training, outer_validation, outer_fit, inner)
    outputs = []
    for variant in protocol["candidate_variants"]:
        seeds = [None] + (protocol["permutation_seeds"] if variant["sources"] else [])
        for seed in seeds:
            for fold, (held, training, validation, outer_fit, inner) in prepared.items():
                inner_scores = np.full(len(outer_fit), np.nan)
                for inner_held, inner_training, inner_validation in inner:
                    forest = fit_reference_classifier(
                        inner_training, auxiliary, variant, protocol, shuffle_seed=seed
                    )
                    inner_scores[inner_held] = forest.predict_proba(inner_validation)[:, 1]
                labels = outer_fit.target_label.to_numpy(int)
                sigmoid = LogisticRegression(C=1, max_iter=1000, random_state=2026).fit(
                    inner_scores[:, None], labels
                )
                forest = fit_reference_classifier(
                    training, auxiliary, variant, protocol, shuffle_seed=seed
                )
                scores = forest.predict_proba(validation)[:, 1]
                calibrated = sigmoid.predict_proba(scores[:, None])[:, 1]
                calibrated_training = sigmoid.predict_proba(inner_scores[:, None])[:, 1]
                thresholds = {
                    "raw_fixed": 0.5,
                    "raw_tuned": training_threshold(labels, inner_scores),
                    "sigmoid_tuned": training_threshold(labels, calibrated_training),
                }
                for mode, threshold in thresholds.items():
                    probability = calibrated if mode == "sigmoid_tuned" else scores
                    for (_, row), score in zip(
                        smart.loc[held].iterrows(), probability, strict=True
                    ):
                        outputs.append(
                            {
                                "variant": variant["id"],
                                "shuffle_seed": seed if seed is not None else -1,
                                "mode": mode,
                                "fold": fold,
                                "observation_id": row.observation_id,
                                "reference": int(row.target_label),
                                "score": float(score),
                                "threshold": threshold,
                                "predicted": int(score >= threshold),
                                "calibration_training_positives": int(labels.sum()),
                            }
                        )
    predictions = pd.DataFrame(outputs)
    reports = []
    for (variant, seed, mode), frame in predictions.groupby(
        ["variant", "shuffle_seed", "mode"], sort=True
    ):
        metrics = binary_metrics(frame.reference, frame.predicted, frame.score)
        reports.append(
            {
                "variant": variant,
                "shuffle_seed": int(seed),
                "mode": mode,
                **metrics,
                "false_positive_rate": metrics["fp"] / (metrics["fp"] + metrics["tn"]),
                "brier": float(brier_score_loss(frame.reference, frame.score)),
                "log_loss": float(log_loss(frame.reference, frame.score, labels=[0, 1])),
                "prevalence": float(frame.reference.mean()),
                "minimum_calibration_positives": int(frame.calibration_training_positives.min()),
            }
        )
    return reports, predictions
