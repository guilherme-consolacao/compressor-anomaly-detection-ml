"""Reproducible public EDA and fixed transfer experiments, with a release gate."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    adjusted_rand_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    silhouette_score,
)
from sklearn.preprocessing import RobustScaler
from sqlalchemy import select

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import save_immutable
from .domain import DataValidationError
from .public_acquisition import artifact_row
from .public_study import document_bytes, load_public, validate_partition


def unit_label(unit):
    return unit if isinstance(unit, str) and unit else "unit unconfirmed"


def candidate_matrix(frame: pd.DataFrame, values: pd.DataFrame) -> pd.DataFrame:
    selected = frame.loc[frame.source_id.isin(["smart_pdm", "kaist"])].copy()
    wide = values.loc[values.observation_id.isin(selected.observation_id)].pivot(
        index="observation_id", columns="feature_name", values="numeric_value"
    )
    result = selected.set_index("observation_id")
    for name in ["skewness", "kurtosis", "range_over_std"]:
        result[name] = np.nan
    smart = result.source_id == "smart_pdm"
    for name in ["skewness", "kurtosis"]:
        if smart.any():
            result.loc[smart, name] = wide.loc[result.index[smart], "Vibration__" + name]
        if (~smart).any():
            result.loc[~smart, name] = wide.loc[result.index[~smart], name]
    if smart.any():
        result.loc[smart, "range_over_std"] = (
            wide.loc[result.index[smart], "Vibration__maximum"]
            - wide.loc[result.index[smart], "Vibration__minimum"]
        ) / wide.loc[result.index[smart], "Vibration__standard_deviation"].replace(0, np.nan)
    if (~smart).any():
        result.loc[~smart, "range_over_std"] = wide.loc[result.index[~smart], "range_over_std"]
    if not np.isfinite(result[["skewness", "kurtosis", "range_over_std"]]).all().all():
        raise DataValidationError("Candidate features are undefined; no automatic zero imputation.")
    return result


def coupling_sensitivity(first, second, seed=2026) -> dict:
    """Counterexample: identical marginal quantiles admit contradictory pairings."""
    first, second = np.asarray(first), np.asarray(second)
    if (
        min(len(first), len(second)) < 8
        or not np.isfinite(first).all()
        or not np.isfinite(second).all()
    ):
        raise DataValidationError("Coupling illustration requires finite nontrivial marginals.")
    probabilities = np.linspace(0.01, 0.99, 128)
    a, b = np.quantile(first, probabilities), np.quantile(second, probabilities)
    if np.ptp(a) == 0 or np.ptp(b) == 0:
        raise DataValidationError("Constant marginals cannot define a rank-coupling illustration.")
    scenarios = {
        "same_quantile": b,
        "opposite_quantile": b[::-1],
        "random_permutation": np.random.default_rng(seed).permutation(b),
    }
    return {
        "kind": "hypothetical sensitivity, not observed correlation",
        "support": {"first": len(first), "second": len(second)},
        "scenarios": {
            name: {
                "pearson": float(np.corrcoef(a, paired)[0, 1]),
                "spearman": float(pd.Series(a).corr(pd.Series(paired), method="spearman")),
            }
            for name, paired in scenarios.items()
        },
        "conclusion": (
            "Marginal distributions alone do not identify the cross-source joint "
            "distribution; no paired training row or label is created."
        ),
    }


def binary_metrics(labels, predicted, probabilities) -> dict:
    labels = np.asarray(labels, dtype=int)
    predicted = np.asarray(predicted, dtype=int)
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predicted, labels=[1], zero_division=0
    )
    both = set(labels) == {0, 1}
    return {
        "n": len(labels),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)) if both else None,
        "precision": float(precision[0]) if tp + fp else None,
        "recall": float(recall[0]) if tp + fn else None,
        "f1": float(f1[0]) if tp + fn else None,
        "average_precision": float(average_precision_score(labels, probabilities))
        if both
        else None,
        "accuracy": float(np.mean(labels == predicted)),
    }


def source_weights(frame: pd.DataFrame) -> np.ndarray:
    weight = pd.Series(index=frame.index, dtype=float)
    for source, subset in frame.groupby("source_id"):
        group = (
            subset.condition_json.map(lambda value: value.get("recording", ""))
            if source == "kaist"
            else subset.dependency_group_id
        )
        counts = group.map(group.value_counts())
        weight.loc[subset.index] = 1.0 / counts / group.nunique()
    return weight.to_numpy() * len(frame) / weight.sum()


def transfer_experiments(candidate: pd.DataFrame, protocol: dict) -> tuple[dict, pd.DataFrame]:
    names = protocol["candidate_features"]
    train = candidate.loc[candidate.partition_name == "train"]
    validation = candidate.loc[candidate.partition_name == "validation"]
    if train.empty or validation.empty or (set(train.index) & set(validation.index)):
        raise DataValidationError("Transfer requires disjoint public development and validation.")
    comparisons, predictions = [], []
    for kind, sources in [
        ("smart_only", ["smart_pdm"]),
        ("kaist_only", ["kaist"]),
        ("combined_references", ["smart_pdm", "kaist"]),
    ]:
        subset = train.loc[train.source_id.isin(sources)]
        if set(subset.target_label) != {0, 1}:
            raise DataValidationError("Both reference classes are required for a fixed comparison.")
        config = protocol["model_comparison"]
        model = RandomForestClassifier(
            n_estimators=config["n_estimators"],
            max_depth=config["max_depth"],
            min_samples_leaf=config["min_samples_leaf"],
            class_weight=config["class_weight"],
            random_state=protocol["seed"],
            n_jobs=1,
        )
        model.fit(
            subset[names], subset.target_label.astype(int), sample_weight=source_weights(subset)
        )
        for source, target in validation.groupby("source_id"):
            probability = model.predict_proba(target[names])[:, list(model.classes_).index(1)]
            predicted = (probability >= config["threshold"]).astype(int)
            metrics = binary_metrics(target.target_label, predicted, probability)
            comparisons.append(
                {
                    "training": kind,
                    "validation_source": source,
                    "validation_groups": target.dependency_group_id.nunique(),
                    "training_groups": subset.dependency_group_id.nunique(),
                    **metrics,
                }
            )
            predictions.extend(
                {
                    "observation_id": key,
                    "experiment": kind,
                    "source_id": source,
                    "reference": int(label),
                    "prediction": int(prediction),
                    "score": float(score),
                }
                for key, label, prediction, score in zip(
                    target.index, target.target_label, predicted, probability, strict=True
                )
            )
    for source, target in validation.groupby("source_id"):
        comparisons.append(
            {
                "training": "majority_normal",
                "validation_source": source,
                "validation_groups": target.dependency_group_id.nunique(),
                **binary_metrics(
                    target.target_label, np.zeros(len(target), dtype=int), np.zeros(len(target))
                ),
            }
        )
    domain = RandomForestClassifier(
        n_estimators=100, max_depth=4, min_samples_leaf=3, random_state=protocol["seed"], n_jobs=1
    )
    domain.fit(
        train[names], (train.source_id == "kaist").astype(int), sample_weight=source_weights(train)
    )
    source_accuracy = float(
        np.mean(domain.predict(validation[names]) == (validation.source_id == "kaist").astype(int))
    )
    report = {
        "purpose": "fixed feasibility comparisons; no final model artifact",
        "comparisons": comparisons,
        "source_classifier_validation_accuracy": source_accuracy,
        "pseudo_labels_accepted": 0,
        "pseudo_label_policy": (
            "RWTH/ULT lack independent minute/condition-level target reference "
            "for a proposed transfer; remain indeterminate"
        ),
        "label_target_limitation": (
            "SMART appliance maintenance versus KAIST induced bearing condition, "
            "conditional broad abnormality mapping only"
        ),
        "test_used": False,
        "external_data_read": False,
    }
    return report, pd.DataFrame(predictions)


def run_public_research(dataset_version: str, root: Path = Path(".")) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folder = root / "reports/research" / dataset_version
    protocol = json.loads((folder / "public-protocol.json").read_text(encoding="utf-8"))
    partitions = pd.read_csv(folder / "partitions.csv")
    validate_partition(partitions)
    snapshot = json.loads((folder / "partitions.json").read_text(encoding="utf-8"))
    if (
        hashlib.sha256((folder / "label-policy.json").read_bytes()).hexdigest()
        != snapshot["inputs"]["label_policy_sha256"]
    ):
        raise DataValidationError("Frozen public label policy changed.")
    if (
        hashlib.sha256((folder / "partitions.csv").read_bytes()).hexdigest()
        != snapshot["partitions_sha256"]
    ):
        raise DataValidationError("Frozen public partitions changed.")
    if (
        hashlib.sha256((folder / "public-protocol.json").read_bytes()).hexdigest()
        != snapshot["inputs"]["protocol_sha256"]
    ):
        raise DataValidationError("Frozen public protocol changed.")
    engine = create_engine_for_url(Settings.from_env().database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    fingerprint = hashlib.sha256(
        Path(__file__).read_bytes()
        + Path(__file__).with_name("public_study.py").read_bytes()
        + Path(__file__).with_name("database").joinpath("research_repository.py").read_bytes()
        + document_bytes(snapshot)
    ).hexdigest()
    run_id = dataset_version + "-eda-" + fingerprint[:8]
    output = folder / run_id
    try:
        repository = ResearchRepository(engine)
        datasets = repository.tables["study_datasets"]
        with engine.connect() as connection:
            frozen_manifest = connection.execute(
                select(datasets.c.manifest_json).where(
                    datasets.c.dataset_version == dataset_version
                )
            ).scalar_one()
        members_hash = hashlib.sha256(
            document_bytes(
                partitions[["observation_id", "dependency_group_id", "partition_name", "label_id"]]
                .sort_values("observation_id")
                .to_dict(orient="records")
            )
        ).hexdigest()
        if members_hash != frozen_manifest["partition_members_sha256"]:
            raise DataValidationError("Partition members differ from the registered snapshot.")
        frame, long = load_public(repository, protocol["allowed_sources"])
        if set(frame.observation_id) != set(partitions.observation_id):
            raise DataValidationError(
                "Prepared source membership changed after the frozen snapshot."
            )
        frame = frame.drop(columns="dependency_group_id").merge(
            partitions[["observation_id", "dependency_group_id", "partition_name"]],
            on="observation_id",
            validate="one_to_one",
        )
        if (output / "feasibility.json").exists():
            runs = repository.tables["study_runs"]
            with engine.connect() as connection:
                status = connection.execute(
                    select(runs.c.status).where(runs.c.run_id == run_id)
                ).scalar_one_or_none()
            if status != "completed":
                raise DataValidationError(
                    "Incomplete research run; inspect before creating a new revision."
                )
            return json.loads((output / "feasibility.json").read_text(encoding="utf-8"))
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_eda_and_feasibility",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {
                            "dataset_version": dataset_version,
                            "snapshot": snapshot,
                        },
                        "code_fingerprint": fingerprint,
                    }
                ]
            },
            scope="public",
        )
        output.mkdir(parents=True, exist_ok=False)
        development = frame.loc[frame.partition_name == "train"]
        dev_long = long.loc[long.observation_id.isin(development.observation_id)].merge(
            development[["observation_id", "source_id", "dependency_group_id", "target_label"]],
            on="observation_id",
            validate="many_to_one",
        )
        if not np.isfinite(dev_long.loc[dev_long.value_status != "missing", "numeric_value"]).all():
            raise DataValidationError("Nonfinite value in public source preparation.")
        quality = {
            "canonical_contract": (
                "study_observations + study_feature_values; one source-namespaced "
                "observation, explicit signal definition per value"
            ),
            "observations": len(frame),
            "source_counts": frame.source_id.value_counts().to_dict(),
            "missing_values": int(long.numeric_value.isna().sum()),
            "missing_values_scope": (
                "prepared scalar features; raw declared empty channels are "
                "reported separately, never imputed"
            ),
            "kaist_raw_declared_empty_channels": int(
                frame.loc[frame.source_id == "kaist", "condition_json"].iloc[0][
                    "raw_tdms_empty_channels_total"
                ]
            ),
            "nonfinite_values": int((~np.isfinite(long.numeric_value.dropna())).sum()),
            "duplicate_observation_ids": int(frame.observation_id.duplicated().sum()),
            "parse_invalid": 0,
            "treatments": [
                {
                    "rule": "strict parser/schema failures reject a source run; no silent deletion",
                    "before": len(frame),
                    "after": len(frame),
                    "removed": 0,
                },
                {
                    "rule": "RWTH exact session/charge association",
                    "before": 200,
                    "after": 195,
                    "unmatched": 5,
                },
            ],
            "extremes": (
                "train IQR flags below are descriptive; retained as possible "
                "operational/fault evidence"
            ),
            "unknowns": {
                "smart_pdm": ["physical device ID", "vibration calibration/unit", "bandwidth"],
                "kaist": ["thermal/vibration simultaneity", "transfer to refrigerating compressor"],
                "rwth_r290": ["binary fault reference"],
                "ult_freezers": [
                    "fault onset",
                    "timezone",
                    "controller/header identity discrepancies",
                ],
            },
            "external_data_read": False,
        }
        summary_rows, statistics, correlations = [], [], []

        def statistic(source, name, value, n, groups, feature=None, other=None, dimensions=None):
            key = hashlib.sha256(
                document_bytes([source, name, feature, other, dimensions])
            ).hexdigest()
            statistics.append(
                {
                    "run_id": run_id,
                    "statistic_key": key,
                    "source_id": source,
                    "source_version": frame.loc[frame.source_id == source, "source_version"].iloc[
                        0
                    ],
                    "statistic_name": name,
                    "feature_name": feature,
                    "other_feature_name": other,
                    "numeric_value": None
                    if value is None or not np.isfinite(value)
                    else float(value),
                    "sample_count": int(n),
                    "group_count": int(groups),
                    "dimensions_json": dimensions or {"partition": "train"},
                }
            )

        for (source, feature), subset in dev_long.groupby(["source_id", "feature_name"]):
            values = subset.numeric_value.dropna()
            q = values.quantile([0, 0.25, 0.5, 0.75, 1])
            iqr = q.loc[0.75] - q.loc[0.25]
            extreme = int(
                ((values < q.loc[0.25] - 1.5 * iqr) | (values > q.loc[0.75] + 1.5 * iqr)).sum()
            )
            summary = {
                "source_id": source,
                "feature": feature,
                "n": len(values),
                "missing": int(subset.numeric_value.isna().sum()),
                "groups": subset.dependency_group_id.nunique(),
                "unit": subset.unit.iloc[0],
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
                "min": float(q.loc[0]),
                "q25": float(q.loc[0.25]),
                "median": float(q.loc[0.5]),
                "q75": float(q.loc[0.75]),
                "max": float(q.loc[1]),
                "iqr_extremes_retained": extreme,
            }
            summary_rows.append(summary)
            for name in [
                "mean",
                "std",
                "min",
                "q25",
                "median",
                "q75",
                "max",
                "missing",
                "iqr_extremes_retained",
            ]:
                statistic(source, name, summary[name], len(values), summary["groups"], feature)
        pd.DataFrame(summary_rows).to_csv(output / "descriptive.csv", index=False)
        dev_long.groupby(
            ["source_id", "target_label", "feature_name"], dropna=False
        ).numeric_value.agg(["count", "mean", "std", "median", "min", "max"]).to_csv(
            output / "descriptive-by-reference.csv"
        )
        dev_long.groupby(["source_id", "dependency_group_id", "feature_name"]).numeric_value.agg(
            ["count", "mean", "std", "median"]
        ).to_csv(output / "descriptive-by-group.csv")
        pd.DataFrame(summary_rows).groupby("source_id").iqr_extremes_retained.sum().to_csv(
            output / "extremes-retained.csv"
        )
        for source, subset in dev_long.groupby("source_id"):
            wide = subset.pivot(
                index="observation_id", columns="feature_name", values="numeric_value"
            )
            if source == "smart_pdm":
                chosen = [name for name in wide if name.startswith("Vibration__")]
            elif source == "rwth_r290":
                chosen = [
                    name
                    for name in wide
                    if name.startswith("compressor_rms_")
                    or name.startswith("T_com_")
                    or name in {"refrigerant_charge_g", "f_comp_set_Hz"}
                ]
            else:
                chosen = list(wide)
            for method in ["pearson", "spearman"]:
                matrix = wide[chosen].corr(method=method)
                for index, first in enumerate(chosen):
                    for second in chosen[index + 1 :]:
                        paired = wide[[first, second]].dropna()
                        value = matrix.loc[first, second]
                        if np.isfinite(value):
                            correlations.append(
                                {
                                    "source_id": source,
                                    "method": method,
                                    "first": first,
                                    "second": second,
                                    "correlation": float(value),
                                    "n": len(paired),
                                    "groups": subset.dependency_group_id.nunique(),
                                }
                            )
                            statistic(
                                source,
                                method,
                                value,
                                len(paired),
                                subset.dependency_group_id.nunique(),
                                first,
                                second,
                            )
            selected = [name for name in chosen if "fft" not in name][:4]
            fig, axes = plt.subplots(
                1, len(selected), figsize=(4 * len(selected), 3.5), squeeze=False
            )
            source_frame = development.loc[development.source_id == source].set_index(
                "observation_id"
            )
            for axis, feature in zip(axes[0], selected, strict=True):
                for label, ids in source_frame.groupby(
                    source_frame.target_label.fillna(-1)
                ).groups.items():
                    axis.hist(
                        wide.loc[ids, feature].dropna(),
                        bins=20,
                        alpha=0.6,
                        label="indeterminate" if label == -1 else f"reference {int(label)}",
                    )
                unit = subset.loc[subset.feature_name == feature, "unit"].iloc[0]
                axis.set_xlabel(feature + " [" + unit_label(unit) + "]", fontsize=8)
                axis.set_ylabel("observations (dependent within group)")
                axis.legend(fontsize=7)
            fig.suptitle(source + ": public train only")
            fig.tight_layout()
            fig.savefig(output / (source + "-distributions.png"), dpi=150)
            plt.close(fig)
            time_feature = {
                "smart_pdm": "Vibration__standard_deviation",
                "kaist": "kurtosis",
                "rwth_r290": "compressor_rms_x",
                "ult_freezers": "TC9",
            }[source]
            fig, axis = plt.subplots(figsize=(9, 3.5))
            for group, group_frame in source_frame.groupby("dependency_group_id"):
                if source == "smart_pdm":
                    times = pd.to_datetime(group_frame.started_at)
                elif source == "ult_freezers":
                    times = pd.to_datetime(
                        group_frame.condition_json.map(lambda value: value["local_timestamp"])
                    )
                elif source == "kaist":
                    times = group_frame.condition_json.map(
                        lambda value: value["sample_start"] / value["sampling_hz"]
                    )
                else:
                    times = wide.loc[group_frame.index, "refrigerant_charge_g"]
                axis.plot(
                    times, wide.loc[group_frame.index, time_feature], ".", markersize=2, label=group
                )
            axis.set_xlabel(
                "capture time (ULT local timezone unknown)"
                if source in {"smart_pdm", "ult_freezers"}
                else "seconds within each source recording (not joined)"
                if source == "kaist"
                else "refrigerant charge [g], separate source sessions"
            )
            unit = subset.loc[subset.feature_name == time_feature, "unit"].iloc[0]
            axis.set_ylabel(time_feature + " [" + unit_label(unit) + "]")
            axis.set_title(source + ": development evolution / dependency groups")
            axis.legend(fontsize=6)
            fig.autofmt_xdate()
            fig.tight_layout()
            fig.savefig(output / (source + "-evolution.png"), dpi=150)
            plt.close(fig)
        pd.DataFrame(correlations).to_csv(output / "correlations.csv", index=False)
        save_immutable(output / "quality.json", document_bytes(quality))
        dev_long.groupby(["source_id", "feature_name"]).size().unstack("source_id").fillna(
            0
        ).to_csv(output / "source-feature-availability.csv")
        frame[
            [
                "observation_id",
                "source_id",
                "label_id",
                "label_version",
                "label_status",
                "target_label",
                "dependency_group_id",
                "partition_name",
            ]
        ].to_csv(output / "labels.csv", index=False)
        candidate = candidate_matrix(frame.loc[frame.partition_name != "test"], long)
        candidate.loc[
            candidate.partition_name == "train", ["source_id", *protocol["candidate_features"]]
        ].to_csv(output / "candidate-train.csv")
        cluster_report = cluster_experiments(
            repository, development, dev_long, candidate, protocol, run_id, now
        )
        save_immutable(output / "clusters.json", document_bytes(cluster_report))
        integration, predictions = transfer_experiments(candidate, protocol)
        smart_marginal = candidate.loc[
            (candidate.source_id == "smart_pdm") & (candidate.partition_name == "train"), "kurtosis"
        ]
        ult_marginal = dev_long.loc[
            (dev_long.source_id == "ult_freezers") & (dev_long.feature_name == "TC9"),
            "numeric_value",
        ]
        integration["coupling_sensitivity"] = coupling_sensitivity(
            smart_marginal, ult_marginal, protocol["seed"]
        )
        integration["row_fusion_created"] = False
        for scenario, coefficients in integration["coupling_sensitivity"]["scenarios"].items():
            for method, value in coefficients.items():
                statistic(
                    "smart_pdm",
                    "hypothetical_coupling_" + method,
                    value,
                    0,
                    0,
                    dimensions={
                        "empirical_joint_correlation": False,
                        "second_source": "ult_freezers",
                        "scenario": scenario,
                        "quantile_grid": 128,
                        "purpose": "nonidentifiability counterexample; no paired training row",
                    },
                )
        integration["derived_label_comparison"] = {
            "status": "not_applicable_no_admissible_derived_labels",
            "reason": (
                "No independent target reference supports RWTH/ULT pseudo-labels; "
                "a reference-plus-pseudo-label score would not evaluate real fault detection."
            ),
        }
        integration["environment"] = {
            "python": sys.version,
            **{
                name: version(name)
                for name in [
                    "numpy",
                    "pandas",
                    "scipy",
                    "scikit-learn",
                    "SQLAlchemy",
                    "npTDMS",
                    "matplotlib",
                ]
            },
        }
        predictions.to_csv(output / "transfer-predictions.csv", index=False)
        save_immutable(output / "integration.json", document_bytes(integration))
        prediction_values = []
        for prediction in predictions.to_dict(orient="records"):
            for name, value in [
                ("class", prediction["prediction"]),
                ("score", prediction["score"]),
            ]:
                prediction_values.append(
                    {
                        "observation_id": prediction["observation_id"],
                        "feature_contract_version": run_id,
                        "feature_name": prediction["experiment"] + "__" + name,
                        "numeric_value": value,
                        "unit": "1",
                        "value_status": "derived",
                        "definition_json": {
                            "purpose": "public feasibility prediction, never training input",
                            "experiment": prediction["experiment"],
                        },
                        "run_id": run_id,
                    }
                )
        for comparison in integration["comparisons"]:
            for metric in [
                "balanced_accuracy",
                "recall",
                "precision",
                "f1",
                "average_precision",
                "tn",
                "fp",
                "fn",
                "tp",
            ]:
                statistic(
                    comparison["validation_source"],
                    metric,
                    comparison[metric],
                    comparison["n"],
                    comparison["validation_groups"],
                    dimensions={
                        "partition": "validation",
                        "training": comparison["training"],
                        "experimental_only": True,
                    },
                )
        compatibility = compatibility_decision()
        save_immutable(output / "compatibility.json", document_bytes(compatibility))
        feasibility = {
            "run_id": run_id,
            "dataset_version": dataset_version,
            "decision": "unsupported_for_current_application",
            "public_integration": "conditional",
            "release_final_training": False,
            "evidence": [
                "descriptive.csv",
                "correlations.csv",
                "clusters.json",
                "integration.json",
                "compatibility.json",
            ],
            "candidate_counts": frame.groupby(["source_id", "label_status"], dropna=False)
            .size()
            .reset_index(name="n")
            .to_dict(orient="records"),
            "public_comparisons": integration["comparisons"],
            "source_classifier_validation_accuracy": integration[
                "source_classifier_validation_accuracy"
            ],
            "pseudo_labels_accepted": 0,
            "blocking_reasons": compatibility["blocking_reasons"],
            "public_validation_bar": [
                {
                    "source": comparison["validation_source"],
                    "balanced_accuracy_met": comparison["balanced_accuracy"] is not None
                    and comparison["balanced_accuracy"]
                    >= protocol["prototype_public_minima"][
                        "balanced_accuracy_each_reference_source"
                    ],
                    "recall_met": comparison["recall"] is not None
                    and comparison["recall"]
                    >= protocol["prototype_public_minima"]["recall_anomaly_each_reference_source"],
                    "precision_met": comparison["precision"] is not None
                    and comparison["precision"]
                    >= protocol["prototype_public_minima"][
                        "precision_anomaly_each_reference_source"
                    ],
                    "groups": comparison["validation_groups"],
                }
                for comparison in integration["comparisons"]
                if comparison["training"] == "combined_references"
            ],
            "next_decision": (
                "The team must choose a public-only research deliverable with a "
                "reduced claim, or provide a demonstrably compatible "
                "acquisition/independent target reference. Do not silently replace "
                "the agreed multibase local objective."
            ),
            "external_data_read": False,
            "final_model_trained": False,
            "external_accuracy_measured": False,
        }
        save_immutable(output / "feasibility.json", document_bytes(feasibility))
        sources = json.loads((root / "config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        first_source = next(row for row in sources if row["source_id"] == "smart_pdm")
        report_files = [
            {
                "relative_path": str(path),
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "byte_size": path.stat().st_size,
            }
            for path in sorted(output.iterdir())
            if path.is_file()
        ]
        manifest_file = save_immutable(
            output / "report-manifest.json",
            document_bytes({"run_id": run_id, "files": report_files}),
        )
        report_files.append(manifest_file)
        for offset in range(0, len(statistics), 500):
            repository.persist(
                {"study_statistics": statistics[offset : offset + 500]}, scope="public"
            )
        for offset in range(0, len(prediction_values), 500):
            repository.persist(
                {"study_feature_values": prediction_values[offset : offset + 500]}, scope="public"
            )
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(
                        first_source,
                        file,
                        "report",
                        {
                            "run_id": run_id,
                            "scope": "multisource",
                            "source_ids": protocol["allowed_sources"],
                        },
                        now,
                    )
                    for file in report_files
                ]
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        return feasibility
    except Exception as error:
        if "repository" in locals():
            runs = repository.tables["study_runs"]
            with engine.connect() as connection:
                status = connection.execute(
                    select(runs.c.status).where(runs.c.run_id == run_id)
                ).scalar_one_or_none()
            if status == "running":
                repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


def cluster_experiments(repository, development, dev_long, candidate, protocol, parent_id, now):
    report = []
    for source, subset in development.groupby("source_id"):
        wide = dev_long.loc[dev_long.source_id == source].pivot(
            index="observation_id", columns="feature_name", values="numeric_value"
        )
        if source in {"smart_pdm", "kaist"}:
            wide = candidate.loc[
                (candidate.source_id == source) & (candidate.partition_name == "train"),
                protocol["candidate_features"],
            ]
        elif source == "rwth_r290":
            wide = wide[
                [
                    "compressor_rms_x",
                    "compressor_rms_y",
                    "compressor_rms_z",
                    "T_com_in_C",
                    "T_com_out_C",
                ]
            ]
        else:
            wide = wide[["RTD", "TC1", "TC6", "TC9"]]
        if wide.isna().any().any():
            raise DataValidationError(
                "Clustering requires explicit handling of missing source values."
            )
        scaler = RobustScaler().fit(wide)
        scaled = scaler.transform(wide)
        groups = subset.set_index("observation_id").loc[wide.index, "dependency_group_id"]
        labels = subset.set_index("observation_id").loc[wide.index, "target_label"]
        for k in protocol["unsupervised"]["kmeans_clusters"]:
            model = KMeans(n_clusters=k, n_init=10, random_state=protocol["seed"])
            assignments = model.fit_predict(scaled)
            stability = []
            for group in sorted(groups.unique()):
                mask = (groups != group).to_numpy()
                if mask.sum() > k:
                    subset_scaled = RobustScaler().fit_transform(wide.loc[mask])
                    refit = KMeans(
                        n_clusters=k, n_init=10, random_state=protocol["seed"]
                    ).fit_predict(subset_scaled)
                    stability.append(float(adjusted_rand_score(assignments[mask], refit)))
            detail = {
                "parent_run_id": parent_id,
                "seed": protocol["seed"],
                "n_init": 10,
                "scale": "RobustScaler, source train only",
                "scaler_center": scaler.center_.tolist(),
                "scaler_scale": scaler.scale_.tolist(),
                "source": source,
                "method": "KMeans",
                "k": k,
                "n": len(wide),
                "groups": groups.nunique(),
                "features": list(wide.columns),
                "silhouette": float(
                    silhouette_score(
                        scaled,
                        assignments,
                        sample_size=min(1000, len(wide)),
                        random_state=protocol["seed"],
                    )
                ),
                "leave_group_out_ari": stability,
                "reference_ari_descriptive_only": float(adjusted_rand_score(labels, assignments))
                if labels.notna().all()
                else None,
                "sizes": {
                    str(key): int(value)
                    for key, value in pd.Series(assignments).value_counts().items()
                },
                "profiles": [
                    {
                        "cluster": str(cluster),
                        "n": int((assignments == cluster).sum()),
                        "dependency_groups": sorted(
                            groups.loc[assignments == cluster].unique().tolist()
                        ),
                        "reference_anomalies": int(labels.loc[assignments == cluster].sum())
                        if labels.notna().all()
                        else None,
                        "feature_means": {
                            str(key): float(value)
                            for key, value in wide.loc[assignments == cluster].mean().items()
                        },
                    }
                    for cluster in sorted(set(assignments))
                ],
                "stability_status": "leave-group-out measured"
                if stability
                else "not estimable with one training group",
                "clusters_are_fault_labels": False,
            }
            child = (
                parent_id.removesuffix(parent_id[-8:])
                + hashlib.sha256(f"{source}:k{k}:{parent_id}".encode()).hexdigest()[:8]
            )
            persist_clusters(
                repository,
                child,
                source,
                wide.index,
                assignments,
                np.zeros(len(wide), dtype=bool),
                None,
                detail,
                now,
            )
            report.append(detail)
        for contamination in protocol["unsupervised"]["isolation_forest_contamination"]:
            model = IsolationForest(
                contamination=contamination,
                n_estimators=100,
                random_state=protocol["seed"],
                n_jobs=1,
            ).fit(scaled)
            score, noise = -model.score_samples(scaled), model.predict(scaled) == -1
            detail = {
                "parent_run_id": parent_id,
                "seed": protocol["seed"],
                "n_estimators": 100,
                "scale": "RobustScaler, source train only",
                "scaler_center": scaler.center_.tolist(),
                "scaler_scale": scaler.scale_.tolist(),
                "source": source,
                "method": "IsolationForest",
                "contamination": contamination,
                "n": len(wide),
                "groups": groups.nunique(),
                "features": list(wide.columns),
                "flagged": int(noise.sum()),
                "flags_are_fault_labels": False,
            }
            child = (
                parent_id.removesuffix(parent_id[-8:])
                + hashlib.sha256(f"{source}:if{contamination}:{parent_id}".encode()).hexdigest()[:8]
            )
            persist_clusters(repository, child, source, wide.index, None, noise, score, detail, now)
            report.append(detail)
    return report


def persist_clusters(repository, run_id, source, ids, assignments, noise, scores, detail, now):
    repository.persist(
        {
            "study_runs": [
                {
                    "run_id": run_id,
                    "stage": "public_unsupervised",
                    "data_scope": "public",
                    "status": "running",
                    "started_at": now,
                    "configuration_json": detail,
                    "input_manifest_json": {
                        "source": source,
                        "partition": "train",
                        "parent_run_id": detail["parent_run_id"],
                    },
                }
            ]
        },
        scope="public",
    )
    repository.persist(
        {
            "study_clusters": [
                {
                    "run_id": run_id,
                    "observation_id": key,
                    "cluster_label": str(int(assignments[index]))
                    if assignments is not None
                    else None,
                    "is_noise": bool(noise[index]),
                    "outlier_score": float(scores[index]) if scores is not None else None,
                    "metadata_json": {
                        "source": source,
                        "method": detail["method"],
                        "not_a_fault_label": True,
                    },
                }
                for index, key in enumerate(ids)
            ]
        },
        scope="public",
    )
    repository.finish_run(run_id, "completed")


def compatibility_decision():
    return {
        "candidate": {
            "features": ["skewness", "kurtosis", "range_over_std"],
            "unit": "1",
            "definition": (
                "adjusted Fisher-Pearson skewness, unbiased Fisher excess kurtosis, "
                "peak-to-peak divided by population standard deviation"
            ),
            "time_support": (
                "SMART full appliance cycle versus KAIST nonoverlapping 5 s channel window"
            ),
            "constant_signal": "undefined, refuse; never impute normal",
        },
        "matrix": [
            {
                "relation": "SMART-KAIST vibration shape",
                "status": "conditional",
                "reason": (
                    "numerically shared dimensionless moments; different "
                    "sampling/bandwidth, positions, window durations, devices and target "
                    "diagnoses"
                ),
            },
            {
                "relation": "RWTH inlet/outlet temperature and triaxial RMS",
                "status": "supported",
                "scope": "within-source paired operating-condition research only",
                "reason": (
                    "exact session/charge keys, 195 genuine paired conditions; no binary "
                    "fault truth"
                ),
            },
            {
                "relation": "ULT thermal channels and repair events",
                "status": "conditional",
                "reason": (
                    "known freezer models and thermal locations, but service date is not "
                    "precise onset; no negative minute-level reference inferred"
                ),
            },
            {
                "relation": "SMART labels transferred to RWTH/ULT",
                "status": "unsupported",
                "reason": (
                    "no verified shared representation/independent target labels for this "
                    "transfer; marginal matching or clusters do not validate health "
                    "labels"
                ),
            },
            {
                "relation": "final public features from existing Ulisses API",
                "status": "unsupported",
                "reason": (
                    "schema exposes temperature and one instantaneous calibrated XYZ "
                    "tuple per reading; no rate/bandwidth/window contract to reproduce "
                    "public temporal shape statistics"
                ),
            },
        ],
        "api_contract": {
            "allowed_inspection": "source code/schema only, no external observations",
            "temperature": (
                "measurement location not confirmed; cannot equate to "
                "refrigerant/sump/bearing temperature"
            ),
            "rms": "sqrt((x^2+y^2+z^2)/3), instantaneous spatial combination, not temporal RMS",
            "preprocessing": "API already subtracts offsets and applies noise floor; never repeat",
            "unsupported_inputs": [
                "electrical signals absent from API",
                "FFT or fast-signal moments without captured waveform",
                "a guessed 15-second measurement",
                "a cross-source correlation coefficient inferred from unpaired rows",
            ],
        },
        "blocking_reasons": [
            (
                "The public temporal vibration representation cannot currently be "
                "reproduced from the documented acquisition contract."
            ),
            (
                "SMART and KAIST reference labels describe different failure scopes; "
                "a broad abnormality mapping remains conditional."
            ),
            (
                "RWTH and sampled ULT provide no independently validated binary "
                "labels at the proposed analysis units; no pseudo-labels were "
                "accepted."
            ),
            (
                "Only four SMART positive connected week blocks and two sampled KAIST "
                "loads limit validation; no independent field accuracy exists."
            ),
        ],
    }


if __name__ == "__main__":
    import sys

    result = run_public_research(sys.argv[1])
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "decision": result["decision"],
                "final_model_trained": result["final_model_trained"],
            }
        )
    )
