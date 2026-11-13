"""Test estimated cross-modal features against measured, held-out references."""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error, r2_score

from .domain import DataValidationError
from .public_experiments import binary_metrics
from .transfer_analysis import SMART_FOLDS


def specific_refrigeration_state(frame):
    result = frame.copy()
    if (result.power_kw <= 0).any() or (result.mass_flow_gs <= 0).any():
        raise DataValidationError(
            "Positive compressor power and refrigerant mass flow are required."
        )
    result["specific_work_kjkg"] = 1000 * result.power_kw / result.mass_flow_gs
    if not np.isfinite(result.specific_work_kjkg).all():
        raise DataValidationError("Specific compression work must be finite.")
    return result


def select_measured_bridge(frame, predictors, control, targets, policy):
    if (
        not frame.source_id.eq("rwth_r290").all()
        or not frame.partition_name.eq("train").all()
        or frame.measurement_id.nunique() < 3
    ):
        raise DataValidationError("Bridge selection uses only public RWTH training sessions.")
    if not np.isfinite(frame[predictors + control + targets].to_numpy(float)).all():
        raise DataValidationError("The paired representation must be finite.")
    truth = frame[targets].to_numpy(float)
    predictions = {
        name: np.zeros_like(truth) for name in ("measured", "operating_control", "constant")
    }
    for group in sorted(frame.measurement_id.unique()):
        fit, validation = frame.measurement_id.ne(group), frame.measurement_id.eq(group)
        predictions["constant"][validation] = truth[fit].mean(axis=0)
        for kind, features in (("measured", predictors), ("operating_control", control)):
            model = RandomForestRegressor(**policy["model"], n_jobs=1)
            target_values = frame.loc[fit, targets].to_numpy(float)
            model.fit(
                frame.loc[fit, features],
                target_values.ravel() if len(targets) == 1 else target_values,
            )
            predictions[kind][validation] = np.asarray(
                model.predict(frame.loc[validation, features])
            ).reshape(int(validation.sum()), len(targets))
    reports, accepted = [], []
    for index, target in enumerate(targets):
        measured_error = mean_absolute_error(truth[:, index], predictions["measured"][:, index])
        control_error = mean_absolute_error(
            truth[:, index], predictions["operating_control"][:, index]
        )
        group_errors = {
            kind: float(
                np.mean(
                    [
                        mean_absolute_error(
                            truth[frame.measurement_id.eq(group), index],
                            predicted[frame.measurement_id.eq(group), index],
                        )
                        for group in sorted(frame.measurement_id.unique())
                    ]
                )
            )
            for kind, predicted in predictions.items()
        }
        gain = (
            float(1 - group_errors["measured"] / group_errors["operating_control"])
            if group_errors["operating_control"] > 1e-12
            else None
        )
        r2 = float(r2_score(truth[:, index], predictions["measured"][:, index]))
        fault_specific = (
            gain is not None
            and gain >= policy["minimum_group_mae_improvement_over_regime"]
            and r2 >= policy["minimum_oof_r2"]
        )
        role = policy.get("admission_role", "incremental_over_regime")
        if role not in {"incremental_over_regime", "operating_proxy"}:
            raise DataValidationError("Unknown bridge admission role.")
        constant_gain = (
            1 - group_errors["measured"] / group_errors["constant"]
            if group_errors["constant"] > 1e-12
            else None
        )
        eligible = (
            fault_specific
            if role == "incremental_over_regime"
            else (
                r2 >= policy["minimum_oof_r2"]
                and constant_gain is not None
                and constant_gain >= policy["minimum_group_mae_improvement_over_constant"]
            )
        )
        if eligible:
            accepted.append(target)
        reports.append(
            {
                "target": target,
                "r2": r2,
                "mae": float(measured_error),
                "control_mae": float(control_error),
                "mean_group_mae": group_errors["measured"],
                "control_mean_group_mae": group_errors["operating_control"],
                "mae_relative_improvement": gain,
                "mae_improvement_over_constant": constant_gain,
                "incremental_over_regime_gate": fault_specific,
                "admission_role": role,
                "eligible_for_projection_experiment": eligible,
            }
        )
    model = None
    if accepted:
        model = RandomForestRegressor(**policy["model"], n_jobs=1)
        target_values = frame[accepted].to_numpy(float)
        model.fit(frame[predictors], target_values.ravel() if len(accepted) == 1 else target_values)
    return (
        model,
        accepted,
        {
            "results": reports,
            "paired_conditions": len(frame),
            "groups": int(frame.measurement_id.nunique()),
            "selection_scope": "leave-training-session-out only; not final test",
            "labels_transferred": 0,
        },
    )


def reference_weights(frame, projected_mass=1.0):
    if not np.isfinite(projected_mass) or projected_mass <= 0:
        raise DataValidationError("An explicit positive projected source mass is required.")
    if not set(frame.source_id) <= {"smart_pdm", "tri_hp_faults"}:
        raise DataValidationError(
            "Unknown or external sources cannot receive public reference weights."
        )
    weights = np.zeros(len(frame), dtype=float)
    for source in sorted(frame.source_id.unique()):
        selected = frame.source_id.eq(source).to_numpy()
        for label in (0, 1):
            cell = selected & frame.target_label.eq(label).to_numpy()
            if not cell.any():
                raise DataValidationError("Each contributing reference source needs both classes.")
            mass = 1.0 if source == "smart_pdm" else projected_mass
            weights[cell] = mass / (2 * cell.sum())
    return weights * len(frame) / weights.sum()


def spectral_reference_comparison(smart, projected, shared_names, protocol):
    if not smart.source_id.eq("smart_pdm").all() or smart.partition_name.eq("test").any():
        raise DataValidationError("Only SMART public development cycles are admissible.")
    if not projected.empty and (
        not projected.source_id.eq("tri_hp_faults").all()
        or not projected.partition_name.eq("train").all()
    ):
        raise DataValidationError("Projected references require TRI-HP public training conditions.")
    folds = smart.dependency_group_id.str.removeprefix("smart_pdm:week-block:").map(SMART_FOLDS)
    if folds.isna().any():
        raise DataValidationError("Every SMART week requires a fixed held-out fold.")
    variants = []
    vibration = sorted(name for name in smart if name.startswith("vibration_"))
    current = sorted(name for name in smart if name.startswith("current_"))
    for family, names in (
        ("vibration", vibration),
        ("current", current),
        ("vibration_and_current", vibration + current),
    ):
        variants.append((family, names, False, "none", 0.0))
    if shared_names:
        variants.append(("bridge_selected_baseline", shared_names, False, "none", 0.0))
    if shared_names and not projected.empty and set(projected.target_label.astype(int)) == {0, 1}:
        for alignment in protocol["classifiers"]["alignment"]:
            for mass in protocol["classifiers"]["projected_source_mass"]:
                variants.append(("projected_multibase", shared_names, True, alignment, mass))
    reports, output = [], []
    for family, names, include_projected, alignment, mass in variants:
        if not names or not np.isfinite(smart[names].to_numpy(float)).all():
            raise DataValidationError("Explicit finite spectral feature families are required.")
        for depth in protocol["classifiers"]["max_depth"]:
            for leaf in protocol["classifiers"]["min_samples_leaf"]:
                scores = np.full(len(smart), np.nan)
                for fold in range(3):
                    training = smart.loc[
                        folds.ne(fold), ["source_id", "target_label", *names]
                    ].copy()
                    validation = smart.loc[folds.eq(fold), names]
                    if set(training.target_label.astype(int)) != {0, 1}:
                        raise DataValidationError(
                            "A held-out spectral fold lacks reference support."
                        )
                    if include_projected:
                        addition = projected[["source_id", "target_label", *names]].copy()
                        if alignment == "training-normal mean shift":
                            shift = (
                                training.loc[training.target_label.eq(0), names].mean()
                                - addition.loc[addition.target_label.eq(0), names].mean()
                            )
                            addition[names] = addition[names] + shift
                        training = pd.concat([training, addition], ignore_index=True)
                    weights = reference_weights(training, mass if include_projected else 1.0)
                    model = RandomForestClassifier(
                        n_estimators=200,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        random_state=2026,
                        n_jobs=1,
                    )
                    model.fit(
                        training[names], training.target_label.astype(int), sample_weight=weights
                    )
                    scores[folds.eq(fold)] = model.predict_proba(validation)[:, 1]
                identifier = (
                    family
                    + ":align="
                    + alignment
                    + ":mass="
                    + str(mass)
                    + ":depth="
                    + str(depth)
                    + ":leaf="
                    + str(leaf)
                )
                labels = smart.target_label.to_numpy(int)
                metrics = binary_metrics(labels, scores >= 0.5, scores)
                reports.append(
                    {
                        "model_id": identifier,
                        "family": family,
                        "features": names,
                        "alignment": alignment,
                        "projected_mass": mass,
                        "projected_reference_conditions": len(projected)
                        if include_projected
                        else 0,
                        "false_positive_rate": metrics["fp"] / (metrics["fp"] + metrics["tn"]),
                        "brier": float(brier_score_loss(labels, scores)),
                        "positive_groups": int(
                            smart.loc[smart.target_label.eq(1), "dependency_group_id"].nunique()
                        ),
                        "evaluation": (
                            "fixed held-week SMART development folds; "
                            "measured vibration reference, "
                            "not agreement with projected labels"
                        ),
                        **metrics,
                    }
                )
                output.extend(
                    {
                        "model_id": identifier,
                        "observation_id": obs,
                        "fold": int(fold),
                        "reference": int(label),
                        "score": float(score),
                    }
                    for obs, fold, label, score in zip(
                        smart.observation_id, folds, labels, scores, strict=True
                    )
                )
    return reports, pd.DataFrame(output)
