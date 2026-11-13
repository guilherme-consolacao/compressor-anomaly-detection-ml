"""Group-held-out diagnostics and measured bridges, never external training."""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .domain import DataValidationError
from .public_experiments import binary_metrics

SMART_FOLDS = {
    "2022-09": 0,
    "2022-10": 0,
    "2022-13": 0,
    "2022-11": 1,
    "2022-14": 1,
    "2022-23": 1,
    "2022-16": 2,
    "2022-26": 2,
    "2022-36": 2,
}


def anchor_diagnostics(frame: pd.DataFrame, names: list[str]) -> tuple[list[dict], pd.DataFrame]:
    if frame.partition_name.eq("test").any() or not frame.source_id.eq("smart_pdm").all():
        raise DataValidationError("Anchor diagnostics require only public SMART development rows.")
    folds = frame.dependency_group_id.str.removeprefix("smart_pdm:week-block:").map(SMART_FOLDS)
    if folds.isna().any():
        raise DataValidationError("Every development group needs a predeclared held-out fold.")
    families = {
        "all_published": names,
        "vibration": [n for n in names if n.startswith("Vibration__")],
        "current_fast": [n for n in names if n.startswith("Current__")],
        "power_cycle": [n for n in names if n.startswith("ActP__") and not n.endswith(".1")],
        "last24h_provider": [n for n in names if n.endswith(".1")],
        "electrical": [n for n in names if not n.startswith("Vibration__")],
    }
    labels = frame.target_label.to_numpy(dtype=int)
    reports, predictions = [], []
    for family, features in families.items():
        if not features or not np.isfinite(frame[features].to_numpy(float)).all():
            raise DataValidationError("Explicit finite feature families are required.")
        for depth in (5, None):
            for leaf in (3, 10):
                scores = np.full(len(frame), np.nan)
                fold_metrics = []
                for fold in range(3):
                    train, validation = folds.ne(fold).to_numpy(), folds.eq(fold).to_numpy()
                    if set(labels[train]) != {0, 1} or set(labels[validation]) != {0, 1}:
                        raise DataValidationError(
                            "Each anchor fold requires independent class support."
                        )
                    model = RandomForestClassifier(
                        n_estimators=200,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        class_weight="balanced",
                        random_state=2026,
                        n_jobs=2,
                    )
                    model.fit(frame.loc[train, features], labels[train])
                    scores[validation] = model.predict_proba(frame.loc[validation, features])[:, 1]
                    fold_metrics.append(
                        {
                            "fold": fold,
                            **binary_metrics(
                                labels[validation], scores[validation] >= 0.5, scores[validation]
                            ),
                        }
                    )
                model_id = family + ":depth=" + str(depth) + ":leaf=" + str(leaf)
                report = {
                    "model_id": model_id,
                    "family": family,
                    "features": features,
                    "evaluation": (
                        "known development, fixed 3 group-held-out folds; not sealed test"
                    ),
                    "positive_groups": 3,
                    "fold_metrics": fold_metrics,
                    **binary_metrics(labels, scores >= 0.5, scores),
                    "brier": float(brier_score_loss(labels, scores)),
                    "log_loss": float(log_loss(labels, scores, labels=[0, 1])),
                    "prevalence": float(labels.mean()),
                    "probability_status": "uncalibrated reference-class score",
                }
                reports.append(report)
                predictions.extend(
                    {
                        "model_id": model_id,
                        "observation_id": obs,
                        "fold": int(fold),
                        "reference": int(label),
                        "score": float(score),
                    }
                    for obs, fold, label, score in zip(
                        frame.observation_id, folds, labels, scores, strict=True
                    )
                )
    return reports, pd.DataFrame(predictions)


def paired_bridge(
    frame: pd.DataFrame, predictors: list[str], targets: list[str], group_column: str, *, name: str
) -> dict:
    """Compare paired prediction with a train-group mean, not marginal correlation."""
    if group_column in predictors or set(predictors) & set(targets):
        raise DataValidationError("Bridge identifiers and outcomes cannot be predictors.")
    if (
        frame[group_column].nunique() < 3
        or not np.isfinite(frame[predictors + targets].to_numpy(float)).all()
    ):
        raise DataValidationError("A finite paired bridge requires at least three groups.")
    reports = []
    for target in targets:
        truth = frame[target].to_numpy(float)
        output = {kind: np.zeros(len(frame)) for kind in ("group_mean", "ridge", "random_forest")}
        for group in sorted(frame[group_column].unique()):
            train, validation = frame[group_column].ne(group), frame[group_column].eq(group)
            output["group_mean"][validation] = frame.loc[train, target].mean()
            for kind, model in (
                ("ridge", make_pipeline(StandardScaler(), Ridge(alpha=10.0))),
                (
                    "random_forest",
                    RandomForestRegressor(
                        n_estimators=200,
                        max_depth=5,
                        min_samples_leaf=3,
                        random_state=2026,
                        n_jobs=2,
                    ),
                ),
            ):
                model.fit(frame.loc[train, predictors], frame.loc[train, target])
                output[kind][validation] = model.predict(frame.loc[validation, predictors])
        for kind, predicted in output.items():
            reports.append(
                {
                    "target": target,
                    "model": kind,
                    "n": len(frame),
                    "groups": int(frame[group_column].nunique()),
                    "mae": float(mean_absolute_error(truth, predicted)),
                    "r2": float(r2_score(truth, predicted)),
                    "mean_group_mae": float(
                        np.mean(
                            [
                                mean_absolute_error(
                                    truth[frame[group_column].eq(group)],
                                    predicted[frame[group_column].eq(group)],
                                )
                                for group in sorted(frame[group_column].unique())
                            ]
                        )
                    ),
                }
            )
    return {
        "name": name,
        "predictors": predictors,
        "targets": targets,
        "evaluation": "leave-one-measurement-session-out",
        "joint_support": len(frame),
        "labels_transferred": 0,
        "results": reports,
    }


def refrigeration_ablation(train, validation, features) -> tuple[list[dict], pd.DataFrame]:
    """Compare measured reference sources without treating unknown RWTH charge as a fault."""
    for frame in (train, validation):
        if (
            not set(frame.source_id) <= {"tri_hp_faults", "nist_hvac"}
            or frame.target_label.isna().any()
            or not np.isfinite(frame[features].to_numpy(float)).all()
        ):
            raise DataValidationError("Thermal comparisons require verified public references.")
    if set(train.group_id) & set(validation.group_id):
        raise DataValidationError("Complete thermal equipment/session groups must be held out.")
    reports, predictions = [], []
    families = {
        "all_shared_thermal": features,
        "thermal_differences": [
            "temperature_lift_c",
            "discharge_above_condensing_c",
            "subcooling_c",
        ],
    }
    for training_sources in (["nist_hvac"], ["tri_hp_faults"], ["nist_hvac", "tri_hp_faults"]):
        fit = train[train.source_id.isin(training_sources)]
        if set(fit.target_label.astype(int)) != {0, 1}:
            raise DataValidationError("Both reference classes are required for the RF comparison.")
        cases = fit.groupby(["source_id", "experiment_id"]).observation_id.transform("size")
        case_counts = fit.groupby("source_id").experiment_id.transform("nunique")
        weights = 1 / (cases.to_numpy(float) * case_counts.to_numpy(float))
        weights *= len(weights) / weights.sum()
        for family, names in families.items():
            for depth in (5, None):
                for leaf in (3, 10):
                    model = RandomForestClassifier(
                        n_estimators=200,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        class_weight="balanced",
                        random_state=2026,
                        n_jobs=2,
                    )
                    model.fit(fit[names], fit.target_label.astype(int), sample_weight=weights)
                    score = model.predict_proba(validation[names])[:, 1]
                    identifier = (
                        "+".join(training_sources)
                        + ":"
                        + family
                        + ":depth="
                        + str(depth)
                        + ":leaf="
                        + str(leaf)
                    )
                    for source in sorted(validation.source_id.unique()):
                        selected = validation.source_id.eq(source)
                        labels = validation.loc[selected, "target_label"].to_numpy(int)
                        probability = score[selected]
                        metrics = binary_metrics(labels, probability >= 0.5, probability)
                        reports.append(
                            {
                                "model_id": identifier,
                                "training_sources": training_sources,
                                "evaluation_source": source,
                                "features": names,
                                "evaluation": (
                                    "predeclared held-out equipment/load development groups"
                                ),
                                "validation_groups": int(
                                    validation.loc[selected, "group_id"].nunique()
                                ),
                                "validation_experiments": int(
                                    validation.loc[selected, "experiment_id"].nunique()
                                ),
                                "brier": float(brier_score_loss(labels, probability)),
                                "log_loss": float(log_loss(labels, probability, labels=[0, 1])),
                                "prevalence": float(labels.mean()),
                                "false_positive_rate": metrics["fp"]
                                / (metrics["fp"] + metrics["tn"]),
                                **metrics,
                            }
                        )
                    predictions.extend(
                        {
                            "model_id": identifier,
                            "observation_id": obs,
                            "reference": int(label),
                            "score": float(value),
                        }
                        for obs, label, value in zip(
                            validation.observation_id, validation.target_label, score, strict=True
                        )
                    )
    return reports, pd.DataFrame(predictions)
