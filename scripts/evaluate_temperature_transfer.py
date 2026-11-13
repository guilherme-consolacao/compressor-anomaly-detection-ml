"""Train on public TRI-HP sessions and test against recorded prototype temperatures."""

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut

from compressor_anomaly_detection_ml.transfer_inputs import tri_hp_main

TRI_SHA = "3c141b558273aa70bc8d94cff7346dae39d91861e07b4e3d6f5f5ae0c0e5e7b4"
BACKUP_SHA = "a0817427315910d34aeafe66d8b20d2a73813c3a6300a00ba01d0df07d2ed789"
HORIZON = 60
GAP = 60
LAGS = (20, 40, 60, 120, 180)
FEATURES = [f"trend_{seconds}s" for seconds in LAGS]
CHANNELS = [
    "Compressor_outlet_temperature",
    "Liquid_line_refrigerant_temperature",
    "Evaporator_saturation_temperature",
    "Condenser_saturation_temperature",
]


def verify(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Unexpected input hash for {path.name}.")
    return actual


def temperature_cases(series):
    """Features use only observed past values. Targets are actual future samples."""
    times = (series.timestamp - series.timestamp.iloc[0]).dt.total_seconds().to_numpy()
    values = series.temperature.to_numpy(dtype=float)
    if np.any(np.diff(times) <= 0) or not np.isfinite(values).all():
        raise ValueError("Temperature series must be finite and strictly ordered.")
    segment = np.cumsum(np.r_[False, np.diff(times) > GAP])
    rows = []
    for i, now in enumerate(times):
        past = np.searchsorted(times, now - np.asarray(LAGS), side="right") - 1
        future = np.searchsorted(times, now + HORIZON)
        if (
            past.min() < 0
            or future >= len(times)
            or times[future] > now + HORIZON + 20
            or (now - times[past] - LAGS > 35).any()
            or segment[past[-1]] != segment[future]
        ):
            continue
        row = dict(
            zip(FEATURES, (values[i] - values[past]) * HORIZON / (now - times[past]), strict=True)
        )
        rows.append(
            {
                **row,
                "issued_at": series.timestamp.iloc[i],
                "observed_at": series.timestamp.iloc[future],
                "current_c": values[i],
                "observed_c": values[future],
                "delta_c": values[future] - values[i],
            }
        )
    return pd.DataFrame(
        rows, columns=[*FEATURES, "issued_at", "observed_at", "current_c", "observed_c", "delta_c"]
    )


def public_windows(path):
    frame, _ = tri_hp_main(path)
    oc_days = frame.loc[frame.fault_type.eq("OC"), "group_id"]
    frame = frame.loc[~frame.group_id.isin(oc_days)]
    windows = []
    for (session, _, _), run in frame.groupby(["group_id", "sheet", "Test code"]):
        for channel in CHANNELS:
            signal = run[["Date", channel]].set_axis(["timestamp", "temperature"], axis=1)
            windows.append(temperature_cases(signal).assign(session=session, channel=channel))
    return pd.concat(windows, ignore_index=True)


def local_backup(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        raw = stream.read()
    matches = re.findall(
        r"\((\d+),(-?\d+(?:\.\d+)?),(?:-?\d+(?:\.\d+)?,){3}(-?\d+(?:\.\d+)?),\s*"
        r"'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)'\)",
        raw,
    )
    if len(matches) != 3701 or len({row[0] for row in matches}) != 3701:
        raise ValueError("Unexpected number of readings in the audited backup.")
    rows = pd.DataFrame(matches, columns=["reading_id", "temperature", "rms", "timestamp"])
    rows["temperature"] = rows.temperature.astype(float)
    rows["rms"] = rows.rms.astype(float)
    rows["timestamp"] = pd.to_datetime(rows.timestamp, utc=True)
    return rows.sort_values("timestamp").reset_index(drop=True)


def fresh_model(name):
    if name == "ridge":
        return Ridge(alpha=5, fit_intercept=False)
    return RandomForestRegressor(
        n_estimators=80, max_depth=6, min_samples_leaf=16, random_state=2026, n_jobs=1
    )


def metric(observed, predicted):
    residual = np.asarray(predicted) - np.asarray(observed)
    return {
        "mae_c": float(np.mean(abs(residual))),
        "rmse_c": float(np.sqrt(np.mean(residual**2))),
        "bias_c": float(np.mean(residual)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tri", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tri_sha = verify(args.tri, TRI_SHA)
    public = public_windows(args.tri)
    discharge = public[public.channel.eq(CHANNELS[0])].reset_index(drop=True)
    assert discharge.session.nunique() >= 4
    print(f"Public cases: {len(public)} pooled, {len(discharge)} discharge", flush=True)

    leaderboard = []
    for family in ("ridge", "forest"):
        for channels in ("discharge", "pooled"):
            errors = []
            for _, held in LeaveOneGroupOut().split(discharge, groups=discharge.session):
                test = discharge.iloc[held]
                cohort = discharge if channels == "discharge" else public
                train = cohort[~cohort.session.isin(test.session)]
                model = fresh_model(family).fit(train[FEATURES], train.delta_c)
                errors.append(metric(test.delta_c, model.predict(test[FEATURES]))["mae_c"])
            leaderboard.append(
                {
                    "model": family,
                    "training_channels": channels,
                    "public_equal_session_mae_c": float(np.mean(errors)),
                }
            )
    choice = min(leaderboard, key=lambda row: row["public_equal_session_mae_c"])
    cohort = discharge if choice["training_channels"] == "discharge" else public
    model = fresh_model(choice["model"]).fit(cohort[FEATURES], cohort.delta_c)
    print(json.dumps({"public_selection": choice, "leaderboard": leaderboard}), flush=True)

    # Freeze the public choice and model before evaluating the local readings.
    args.output.mkdir(parents=True, exist_ok=False)
    artifact = args.output / "temperature-transfer.joblib"
    joblib.dump(model, artifact)
    summary = {
        "model": choice,
        "model_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "tri_sha256": tri_sha,
        "public_models": leaderboard,
        "public_sessions": int(cohort.session.nunique()),
        "public_training_rows": len(cohort),
        "history_seconds": list(LAGS),
        "features": FEATURES,
        "horizon_seconds": HORIZON,
        "target_tolerance_seconds": 20,
        "gap_seconds": GAP,
    }
    (args.output / "public-freeze.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary["backup_sha256"] = verify(args.backup, BACKUP_SHA)
    local = local_backup(args.backup)
    cut = local.timestamp.iloc[0] + (local.timestamp.iloc[-1] - local.timestamp.iloc[0]) / 2
    candidates = temperature_cases(local)
    candidates = candidates.loc[candidates.issued_at.ge(cut)].reset_index(drop=True)
    # Keep disjoint future intervals and use the same cases for every comparator.
    chosen = []
    for index, row in candidates.iterrows():
        if not chosen or row.issued_at >= candidates.loc[chosen[-1], "observed_at"]:
            chosen.append(index)
    test = candidates.loc[chosen].copy()
    assert len(test) >= 100 and (test.observed_at > test.issued_at).all()
    test["persistence_c"] = test.current_c
    test["trend_c"] = test.current_c + test.trend_60s
    test["predicted_c"] = test.current_c + model.predict(test[FEATURES])
    methods = ("persistence_c", "trend_c", "predicted_c")
    summary["historical_test"] = {
        "cases": len(test),
        "cut_utc": cut.isoformat(),
        "first_issued_at": test.issued_at.min().isoformat(),
        "last_observed_at": test.observed_at.max().isoformat(),
        "metrics": {name: metric(test.observed_c, test[name]) for name in methods},
        "by_time_block": [
            {
                "started_at": part.issued_at.iloc[0].isoformat(),
                "cases": len(part),
                "mae_c": {name: metric(part.observed_c, part[name])["mae_c"] for name in methods},
            }
            for part in (test.iloc[indices] for indices in np.array_split(np.arange(len(test)), 4))
        ],
        "reference": "actual future sensor temperature; no physical malfunction labels",
    }
    test.to_csv(args.output / "predictions.csv", index=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["historical_test"], indent=2), flush=True)


if __name__ == "__main__":
    main()
