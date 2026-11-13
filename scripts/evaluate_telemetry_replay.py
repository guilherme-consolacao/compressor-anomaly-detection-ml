"""Exercise the frozen cycle detector with the historical telemetry cadence."""

import argparse
import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from compressor_anomaly_detection_ml.cycle_candidate import load_cycle_candidate, score_ratios
from compressor_anomaly_detection_ml.reading_measurements import predict_reading_measurements

LIMITS = (30, 33, 39, 45, 50, 55, 59, 60, 64, 65, 66, 70, 72, 75, 79, 80, 99, 120)


def replay(artifact, readings):
    groups = predict_reading_measurements(artifact, readings, gap_seconds=60)
    scored = {
        (row["reading_ids"][0], row["reading_ids"][-1]): (
            row["exploratory_alert"],
            row["exploratory_score"],
        )
        for row in groups
        if row["status"] == "exploratory_scored"
    }
    return groups, scored


def shifted(reading, seconds):
    timestamp = datetime.fromisoformat(reading["timestamp"]) + timedelta(seconds=seconds)
    return {**reading, "timestamp": timestamp.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--readings", type=Path)
    source.add_argument("--backup", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.backup:
        from evaluate_temperature_transfer import BACKUP_SHA, local_backup, verify

        verify(args.backup, BACKUP_SHA)
        readings = [
            {
                "equipment_id": "historical-ulisses-stream",
                "reading_id": row.reading_id,
                "timestamp": row.timestamp.isoformat(),
            }
            for row in local_backup(args.backup).itertuples()
        ]
        raw = (json.dumps(readings, indent=2) + "\n").encode()
    else:
        raw = args.readings.read_bytes()
        readings = json.loads(raw)
    model, manifest = load_cycle_candidate(args.manifest, Path("models"))
    groups, baseline = replay(model, readings)
    assert len(readings) == 3701 and len(groups) == 11 and len(baseline) == 6
    assert all(alert for alert, _ in baseline.values())

    _, shift_scores = replay(model, [shifted(row, -3600) for row in reversed(readings)])
    assert shift_scores == baseline
    by_id = {str(row["reading_id"]): datetime.fromisoformat(row["timestamp"]) for row in readings}
    dropped = set()
    for group in groups:
        ids = group["reading_ids"]
        for before, current, after in zip(ids, ids[1:], ids[2:], strict=False):
            if (by_id[after] - by_id[before]).total_seconds() <= 60:
                dropped.add(current)
                break
    _, sparse = replay(model, [row for row in readings if str(row["reading_id"]) not in dropped])
    assert sparse == baseline

    jitter = []
    for seed in range(2026, 2046):
        rng = random.Random(seed)
        perturbed, scores = replay(model, [shifted(row, rng.randint(-1, 1)) for row in readings])
        alerts = sum(value[0] for value in scores.values())
        common = baseline.keys() & scores.keys()
        jitter.append(
            {
                "seed": seed,
                "groups": len(perturbed),
                "scored": len(scores),
                "alerts": alerts,
                "matched_alerts": sum(scores[key][0] for key in common),
                "same_alerts": {key for key, val in scores.items() if val[0]} == baseline.keys(),
            }
        )

    # One model input per designed ratio, since the normalized input repeats across contexts.
    ratios = [0.5, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 2]
    raw_scores, _ = score_ratios(model, ratios)
    comparisons = [
        {"ratio": ratio, "score": float(score), "alert": bool(score >= model["threshold"])}
        for ratio, score in zip(ratios, raw_scores, strict=True)
    ]
    output = {
        "model_version": manifest["version"],
        "gap_seconds": 60,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "input_readings": len(readings),
        "groups": len(groups),
        "observed_alerts": len(baseline),
        "shift_and_reverse_preserved_all_scores": True,
        "one_safe_interior_removal_per_group_preserved_all_scores": len(dropped),
        "jitter_trials": jitter,
        "jitter_same_alerts": sum(row["same_alerts"] for row in jitter),
        "controlled_duration_ratios": comparisons,
        "reference": "observed telemetry replay and artificial duration inputs, no fault labels",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sensitivity = args.output.with_name("sensitivity.json")
    if args.backup and not sensitivity.exists():
        results = []
        for limit in LIMITS:
            trial = predict_reading_measurements(model, readings, gap_seconds=limit)
            assert sum(len(row["reading_ids"]) for row in trial) == len(readings)
            results.append(
                {
                    "gap_seconds": limit,
                    "measurements": len(trial),
                    "scored": sum(r["status"] == "exploratory_scored" for r in trial),
                    "alerts": sum(r.get("exploratory_alert", False) for r in trial),
                }
            )
        sensitivity.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: val for key, val in output.items() if key != "jitter_trials"}, indent=2))


if __name__ == "__main__":
    main()
