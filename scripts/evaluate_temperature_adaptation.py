"""Adapt temperature forecasts on early readings and evaluate a later time block."""

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from evaluate_temperature_transfer import (
    BACKUP_SHA,
    FEATURES,
    local_backup,
    metric,
    temperature_cases,
    verify,
)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def blocked_sample(cases):
    selected, last_target = [], None
    for row in cases.itertuples():
        if last_target is None or row.issued_at >= last_target:
            selected.append(row.Index)
            last_target = row.observed_at
    return cases.loc[selected].copy()


def fit_correction(kind, strength, features, rows):
    if kind == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=strength))
    else:
        model = HistGradientBoostingRegressor(
            max_iter=80,
            max_leaf_nodes=strength,
            min_samples_leaf=25,
            l2_regularization=2,
            random_state=2026,
            early_stopping=False,
        )
    return model.fit(rows[features], rows.delta_c - rows.trend_60s)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--public-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    backup_sha = verify(args.backup, BACKUP_SHA)
    public_manifest = json.loads(
        (args.public_run / "public-freeze.json").read_text(encoding="utf-8")
    )
    public_path = args.public_run / "temperature-transfer.joblib"
    verify(public_path, public_manifest["model_sha256"])
    public_model = joblib.load(public_path)

    local = local_backup(args.backup)
    assert len(local) == 3701 and np.isfinite(local.rms).all()
    origin, end = local.timestamp.iloc[[0, -1]]
    cut = origin + (end - origin) / 2
    fit_cut = origin + (cut - origin) * 0.75
    segments = local.timestamp.diff().dt.total_seconds().gt(60).cumsum()
    local["rms_mean_60s"] = local.groupby(segments, group_keys=False).apply(
        lambda rows: rows.set_index("timestamp").rms.rolling("60s").mean().set_axis(rows.index),
        include_groups=False,
    )
    cases = temperature_cases(local).merge(
        local[["timestamp", "rms", "rms_mean_60s"]],
        left_on="issued_at",
        right_on="timestamp",
        validate="one_to_one",
    )
    cases["public_delta_c"] = public_model.predict(cases[FEATURES])
    candidate_features = {
        "tendencia": FEATURES,
        "temperatura_vibracao": [*FEATURES, "current_c", "rms", "rms_mean_60s"],
        "temperatura_vibracao_publica": [
            *FEATURES,
            "current_c",
            "rms",
            "rms_mean_60s",
            "public_delta_c",
        ],
    }
    fit_rows = cases.loc[cases.observed_at.lt(fit_cut)]
    calibration = blocked_sample(cases.loc[cases.issued_at.ge(fit_cut) & cases.observed_at.lt(cut)])
    train_folds = []
    edges = [origin + (fit_cut - origin) * fraction for fraction in (0.4, 0.6, 0.8, 1)]
    for start, stop in zip(edges, edges[1:], strict=False):
        train = fit_rows.loc[fit_rows.observed_at.lt(start)]
        validation = blocked_sample(
            fit_rows.loc[fit_rows.issued_at.ge(start) & fit_rows.observed_at.lt(stop)]
        )
        assert (
            len(train) and len(validation) and train.observed_at.max() < validation.issued_at.min()
        )
        train_folds.append((train, validation))

    leaderboard = []
    for name, features in candidate_features.items():
        for kind, strengths in (("ridge", (0.5, 5, 50)), ("boosting", (5, 12))):
            for strength in strengths:
                errors = []
                for train, validation in train_folds:
                    model = fit_correction(kind, strength, features, train)
                    delta = validation.trend_60s + model.predict(validation[features])
                    errors.append(metric(validation.delta_c, delta)["mae_c"])
                leaderboard.append(
                    {
                        "features": name,
                        "model": kind,
                        "strength": strength,
                        "fold_mae_c": errors,
                        "validation_mae_c": float(np.mean(errors)),
                    }
                )
    choice = min(leaderboard, key=lambda row: row["validation_mae_c"])
    features = candidate_features[choice["features"]]
    model = fit_correction(choice["model"], choice["strength"], features, fit_rows)
    cal_errors = abs(
        calibration.delta_c - calibration.trend_60s - model.predict(calibration[features])
    )
    assert len(cal_errors) >= 50 and calibration.observed_at.max() < cut
    half_width = float(np.quantile(cal_errors, 0.95, method="higher"))

    args.output.mkdir(parents=True, exist_ok=False)
    artifact = args.output / "temperature-adapted.joblib"
    joblib.dump(model, artifact)
    summary = {
        "backup_sha256": backup_sha,
        "model_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "public_prior_sha256": public_manifest["model_sha256"],
        "choice": choice,
        "features": features,
        "selection": leaderboard,
        "fitting_cases": len(fit_rows),
        "calibration_cases": len(calibration),
        "half_width_c": half_width,
        "fit_cut_utc": fit_cut.isoformat(),
        "test_cut_utc": cut.isoformat(),
    }
    (args.output / "adaptation-freeze.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    test = blocked_sample(cases.loc[cases.issued_at.ge(cut)])
    assert len(test) == 432 and test.observed_at.min() > cut
    test["persistence_c"] = test.current_c
    test["trend_c"] = test.current_c + test.trend_60s
    test["public_c"] = test.current_c + test.public_delta_c
    test["adapted_c"] = test.trend_c + model.predict(test[features])
    test["lower_c"], test["upper_c"] = test.adapted_c - half_width, test.adapted_c + half_width
    test["outside_band"] = ~test.observed_c.between(test.lower_c, test.upper_c)
    methods = ("persistence_c", "trend_c", "public_c", "adapted_c")
    summary["historical_test"] = {
        "cases": len(test),
        "outside_band": int(test.outside_band.sum()),
        "metrics": {name: metric(test.observed_c, test[name]) for name in methods},
        "by_time_block": [
            {
                "started_at": part.issued_at.iloc[0].isoformat(),
                "cases": len(part),
                "mae_c": {name: metric(part.observed_c, part[name])["mae_c"] for name in methods},
            }
            for part in (test.iloc[indices] for indices in np.array_split(np.arange(len(test)), 4))
        ],
    }
    test.to_csv(args.output / "predictions.csv", index=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"choice": choice, "half_width_c": half_width, **summary["historical_test"]}, indent=2
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
