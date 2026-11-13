"""Cross-fitted normality descriptors for a supervised reference-state forest."""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import RobustScaler

from .domain import DataValidationError
from .public_experiments import binary_metrics
from .transfer_analysis import SMART_FOLDS

META_NAMES = [
    "mean_tail_rarity",
    "maximum_tail_rarity",
    "rare_feature_fraction",
    "isolation_percentile",
]


def fit_normality(normal):
    normal = np.asarray(normal, float)
    if normal.ndim != 2 or len(normal) < 20 or not np.isfinite(normal).all():
        raise DataValidationError("A finite public reference-normal sample is required.")
    scaler = RobustScaler().fit(normal)
    transformed = scaler.transform(normal)
    forest = IsolationForest(
        n_estimators=200, max_samples=min(256, len(normal)), random_state=2026, n_jobs=1
    ).fit(transformed)
    return {
        "scaler": scaler,
        "forest": forest,
        "absolute_normal": np.abs(transformed),
        "normal_scores": np.sort(-forest.score_samples(transformed)),
    }


def normality_vectors(model, values):
    values = np.asarray(values, float)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise DataValidationError("Normality descriptors cannot silently impute invalid signals.")
    transformed = model["scaler"].transform(values)
    baseline = model["absolute_normal"]
    rarity = np.empty_like(transformed)
    for column in range(transformed.shape[1]):
        sorted_values = np.sort(baseline[:, column])
        rarity[:, column] = np.searchsorted(
            sorted_values, np.abs(transformed[:, column]), side="left"
        ) / (len(baseline) + 1)
    scores = -model["forest"].score_samples(transformed)
    percentile = np.searchsorted(model["normal_scores"], scores, side="right") / (len(baseline) + 1)
    return pd.DataFrame(
        np.column_stack(
            [rarity.mean(axis=1), rarity.max(axis=1), (rarity >= 0.95).mean(axis=1), percentile]
        ),
        columns=META_NAMES,
    )


def crossfit_normality(frame, names, group):
    if frame[group].nunique() < 2:
        raise DataValidationError("Normality construction needs complete held-out groups.")
    result = np.full((len(frame), len(META_NAMES)), np.nan)
    for held_group in sorted(frame[group].unique()):
        held = frame[group].eq(held_group).to_numpy()
        normal = ~held & frame.target_label.eq(0).to_numpy()
        model = fit_normality(frame.loc[normal, names].to_numpy(float))
        result[held] = normality_vectors(model, frame.loc[held, names].to_numpy(float)).to_numpy()
    if not np.isfinite(result).all():
        raise DataValidationError("Incomplete cross-fitted normality descriptors.")
    return pd.DataFrame(result, columns=META_NAMES, index=frame.index)


def novelty_reference_comparison(smart, names, auxiliary_vectors, protocol):
    if not smart.source_id.eq("smart_pdm").all() or smart.partition_name.eq("test").any():
        raise DataValidationError("Novelty transfer uses public SMART development references only.")
    if set(auxiliary_vectors.source_id) - {"nist_hvac", "tri_hp_faults"}:
        raise DataValidationError("Only the registered measured thermal references may contribute.")
    folds = smart.dependency_group_id.str.removeprefix("smart_pdm:week-block:").map(SMART_FOLDS)
    if folds.isna().any():
        raise DataValidationError("A SMART group is outside the fixed public development folds.")
    prepared = {}
    for fold in range(3):
        training = smart[folds.ne(fold)].copy().reset_index(drop=True)
        training["inner_fold"] = training.dependency_group_id.str.removeprefix(
            "smart_pdm:week-block:"
        ).map(SMART_FOLDS)
        meta = crossfit_normality(training, names, "inner_fold")
        train_vectors = pd.concat([training[["source_id", "target_label"]], meta], axis=1)
        model = fit_normality(training.loc[training.target_label.eq(0), names].to_numpy(float))
        validation = normality_vectors(model, smart.loc[folds.eq(fold), names].to_numpy(float))
        prepared[fold] = (train_vectors, validation)
    reports, prediction_rows = [], []
    for auxiliary_sources in ([], ["nist_hvac"], ["tri_hp_faults"], ["nist_hvac", "tri_hp_faults"]):
        for auxiliary_mass in [0.0] if not auxiliary_sources else protocol["auxiliary_source_mass"]:
            for depth in (5, None):
                for leaf in (3, 10):
                    scores = np.full(len(smart), np.nan)
                    for fold, (training, validation) in prepared.items():
                        fit = pd.concat(
                            [
                                training,
                                auxiliary_vectors[
                                    auxiliary_vectors.source_id.isin(auxiliary_sources)
                                ],
                            ],
                            ignore_index=True,
                        )
                        weights = np.zeros(len(fit))
                        for source in sorted(fit.source_id.unique()):
                            mass = (
                                1.0
                                if source == "smart_pdm"
                                else auxiliary_mass / len(auxiliary_sources)
                            )
                            for label in (0, 1):
                                selected = fit.source_id.eq(source) & fit.target_label.eq(label)
                                if not selected.any():
                                    raise DataValidationError(
                                        "Every contributing source requires both reference classes."
                                    )
                                weights[selected] = mass / (2 * selected.sum())
                        weights *= len(weights) / weights.sum()
                        classifier = RandomForestClassifier(
                            n_estimators=200,
                            max_depth=depth,
                            min_samples_leaf=leaf,
                            random_state=2026,
                            n_jobs=1,
                        )
                        classifier.fit(
                            fit[META_NAMES], fit.target_label.astype(int), sample_weight=weights
                        )
                        scores[folds.eq(fold)] = classifier.predict_proba(validation[META_NAMES])[
                            :, 1
                        ]
                    labels = smart.target_label.to_numpy(int)
                    identifier = (
                        "+".join(["smart_pdm", *auxiliary_sources])
                        + ":mass="
                        + str(auxiliary_mass)
                        + ":depth="
                        + str(depth)
                        + ":leaf="
                        + str(leaf)
                    )
                    metrics = binary_metrics(labels, scores >= 0.5, scores)
                    reports.append(
                        {
                            "model_id": identifier,
                            "auxiliary_sources": auxiliary_sources,
                            "auxiliary_mass": auxiliary_mass,
                            "false_positive_rate": metrics["fp"] / (metrics["fp"] + metrics["tn"]),
                            "evaluation": (
                                "fixed SMART outer held-week folds; novelty training vectors "
                                "are inner group-cross-fitted"
                            ),
                            "probability_status": (
                                "uncalibrated reference-state score; normality percentiles "
                                "are not defect probabilities"
                            ),
                            **metrics,
                        }
                    )
                    prediction_rows.extend(
                        {
                            "model_id": identifier,
                            "observation_id": obs,
                            "reference": int(label),
                            "score": float(score),
                        }
                        for obs, label, score in zip(
                            smart.observation_id, labels, scores, strict=True
                        )
                    )
    return reports, pd.DataFrame(prediction_rows)
