"""Same-provider mechanical controls; never claim washer faults are refrigerator defects."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from .domain import DataValidationError
from .public_experiments import binary_metrics
from .transfer_analysis import SMART_FOLDS


def washer_tables(folder: Path):
    metadata = pd.read_csv(folder / "washing_machine_metadata.csv", header=None)
    features = pd.read_csv(folder / "WM_ExtractedFeatures.csv")
    if metadata.shape[1] != 11 or features.shape[1] != 76 or features.columns[0] != "Id":
        raise DataValidationError("SMART washer table schema changed.")
    metadata = metadata.iloc[:, :10].copy()
    metadata.columns = [
        "original_id",
        "timestamp_begin",
        "timestamp_end",
        "brand",
        "model",
        "program",
        "temperature",
        "spin",
        "load",
        "failure",
    ]
    if not set(metadata.failure) <= {"Working", "Heating", "Motor", "Bearings"}:
        raise DataValidationError("An unknown washer reference cannot be mapped automatically.")
    raw_metadata_rows, raw_feature_rows = len(metadata), len(features)
    metadata = metadata.drop_duplicates()
    conflicting_metadata = sorted(
        metadata.loc[metadata.original_id.duplicated(keep=False), "original_id"].unique()
    )
    metadata = metadata.loc[~metadata.original_id.isin(conflicting_metadata)]
    features = features.drop_duplicates()
    conflicting_features = sorted(features.loc[features.Id.duplicated(keep=False), "Id"].unique())
    features = features.loc[~features.Id.isin(conflicting_features)]
    frame = features.merge(
        metadata, left_on="Id", right_on="original_id", how="inner", validate="one_to_one"
    )
    names = [name for name in features if name != "Id"]
    numeric = frame[names].apply(pd.to_numeric, errors="raise").astype(float)
    if np.isinf(numeric.to_numpy()).any():
        raise DataValidationError("Infinite published washer features need explicit quarantine.")
    frame[names] = numeric
    frame["source_id"] = "smart_pdm_washers"
    frame["target_label"] = frame.failure.ne("Working").astype(int)
    frame["group_id"] = (
        "washer:model-day:"
        + frame.brand.astype(str)
        + ":"
        + frame.model.astype(str)
        + ":"
        + frame.original_id.str[:10]
    )
    frame["observation_id"] = frame.original_id.map(
        lambda value: "smart_pdm_washers:7245198:" + hashlib.sha256(value.encode()).hexdigest()[:32]
    )
    return (
        frame,
        names,
        {
            "metadata_rows": raw_metadata_rows,
            "feature_rows": raw_feature_rows,
            "unambiguous_joined_cycles": len(frame),
            "conflicting_metadata_ids": conflicting_metadata,
            "conflicting_feature_ids": conflicting_features,
            "missing_feature_counts": frame[names]
            .isna()
            .sum()[frame[names].isna().any()]
            .to_dict(),
            "reference_counts": frame.failure.value_counts().to_dict(),
            "mechanical_fault_models": frame.loc[
                frame.failure.isin(["Motor", "Bearings"]), "model"
            ].nunique(),
            "auxiliary_only": True,
            "compressor_failure_labels": False,
        },
    )


def auxiliary_comparison(smart, auxiliary, protocol):
    if (
        not smart.source_id.eq("smart_pdm").all()
        or smart.partition_name.eq("test").any()
        or not auxiliary.source_id.eq("smart_pdm_washers").all()
    ):
        raise DataValidationError(
            "Mechanical-control comparison excludes external/reserved sources."
        )
    folds = smart.dependency_group_id.str.removeprefix("smart_pdm:week-block:").map(SMART_FOLDS)
    if folds.isna().any():
        raise DataValidationError("Every SMART development group requires its fixed fold.")
    common = sorted(set(smart) & set(auxiliary))
    feature_names = [
        name
        for name in common
        if name.startswith(("Vibration__", "Current__", "ActP__"))
        and not name.endswith(".1")
        and name not in protocol["excluded_features"]
    ]
    families = {
        "vibration": [name for name in feature_names if name.startswith("Vibration__")],
        "current": [name for name in feature_names if name.startswith("Current__")],
        "all_shared": feature_names,
    }
    reports, predictions = [], []
    for family, names in families.items():
        if (
            not names
            or not np.isfinite(smart[names].to_numpy(float)).all()
            or not np.isfinite(auxiliary[names].to_numpy(float)).all()
        ):
            raise DataValidationError(
                "Only explicitly finite shared feature families can be compared."
            )
        for reference_policy in ("anchor_only", "mechanical_only", "all_malfunctions"):
            control = (
                auxiliary.loc[~auxiliary.failure.eq("Heating")]
                if reference_policy == "mechanical_only"
                else auxiliary
            )
            masses = (
                [0.0] if reference_policy == "anchor_only" else protocol["auxiliary_source_mass"]
            )
            for mass in masses:
                for depth in (5, None):
                    for leaf in (3, 10):
                        score = np.full(len(smart), np.nan)
                        for fold in range(3):
                            fit = smart.loc[folds.ne(fold)].copy()
                            if mass:
                                fit = pd.concat([fit, control], ignore_index=True)
                            weights = np.zeros(len(fit))
                            for source, source_mass in (
                                ("smart_pdm", 1.0),
                                ("smart_pdm_washers", mass),
                            ):
                                if not source_mass:
                                    continue
                                for label in (0, 1):
                                    selected = fit.source_id.eq(source) & fit.target_label.eq(label)
                                    if not selected.any():
                                        raise DataValidationError(
                                            "Both reference classes are required "
                                            "per contributing source."
                                        )
                                    weights[selected] = source_mass / (2 * selected.sum())
                            weights *= len(weights) / weights.sum()
                            model = RandomForestClassifier(
                                n_estimators=200,
                                max_depth=depth,
                                min_samples_leaf=leaf,
                                random_state=2026,
                                n_jobs=1,
                            )
                            model.fit(
                                fit[names], fit.target_label.astype(int), sample_weight=weights
                            )
                            score[folds.eq(fold)] = model.predict_proba(
                                smart.loc[folds.eq(fold), names]
                            )[:, 1]
                        identifier = (
                            family
                            + ":"
                            + reference_policy
                            + ":mass="
                            + str(mass)
                            + ":depth="
                            + str(depth)
                            + ":leaf="
                            + str(leaf)
                        )
                        labels = smart.target_label.to_numpy(int)
                        metrics = binary_metrics(labels, score >= 0.5, score)
                        reports.append(
                            {
                                "model_id": identifier,
                                "family": family,
                                "auxiliary_reference_policy": reference_policy,
                                "auxiliary_mass": mass,
                                "features": names,
                                "false_positive_rate": metrics["fp"]
                                / (metrics["fp"] + metrics["tn"]),
                                "auxiliary_cycles": len(control) if mass else 0,
                                "evaluation": (
                                    "SMART measured references, held week groups; "
                                    "auxiliary own-domain accuracy is not claimed"
                                ),
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
                                smart.observation_id, labels, score, strict=True
                            )
                        )
    return reports, pd.DataFrame(predictions)
