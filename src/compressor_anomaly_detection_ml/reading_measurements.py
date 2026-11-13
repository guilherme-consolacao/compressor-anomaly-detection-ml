"""Experimental grouping of telemetry by time gaps, separate from confirmed cycles."""

import hashlib
import json
from datetime import UTC, datetime
from itertools import groupby

import pandas as pd

from .cycle_candidate import score_ratios
from .domain import DataValidationError
from .transfer_temporal import completed_cycle_context


def predict_reading_measurements(artifact, readings, *, gap_seconds: int):
    if type(gap_seconds) is not int or gap_seconds <= 0:
        raise DataValidationError("The grouping gap must be a positive number of seconds.")
    if not isinstance(readings, list) or not readings:
        raise DataValidationError("Provide a nonempty list of timestamped readings.")

    now = datetime.now(UTC)
    samples = []
    seen = set()
    for reading in readings:
        try:
            equipment = reading["equipment_id"]
            reading_id = reading["reading_id"]
            if not isinstance(equipment, str) or not equipment.strip():
                raise ValueError
            if type(reading_id) not in (str, int) or not str(reading_id).strip():
                raise ValueError
            reading_id = str(reading_id)
            timestamp = datetime.fromisoformat(reading["timestamp"])
            if timestamp.tzinfo is None or timestamp > now:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise DataValidationError(
                "Readings require equipment_id, reading_id and a past ISO timestamp with timezone."
            ) from None
        identity = (equipment, reading_id)
        if identity in seen:
            raise DataValidationError("Reading identities must be unique within each equipment.")
        seen.add(identity)
        samples.append((equipment, timestamp.astimezone(UTC), reading_id))

    measurements = []
    for equipment, stream in groupby(sorted(samples), key=lambda sample: sample[0]):
        groups = []
        for _, timestamp, reading_id in stream:
            if not groups or (timestamp - groups[-1][-1][0]).total_seconds() > gap_seconds:
                groups.append([])
            groups[-1].append((timestamp, reading_id))

        for index, group in enumerate(groups):
            first_at, first_id = group[0]
            last_at, _ = group[-1]
            observed_span = (last_at - first_at).total_seconds()
            identity = json.dumps(
                ["time-gap-v1", equipment, gap_seconds, first_at.isoformat(), first_id]
            )
            # The same first reading and rule identify the group as later readings arrive.
            measurement_id = hashlib.sha256(identity.encode()).hexdigest()
            if index == 0 or index == len(groups) - 1:
                status = "snapshot_boundary"
            elif observed_span == 0:
                status = "no_observed_span"
            else:
                status = "insufficient_context"
            measurements.append(
                {
                    "measurement_id": measurement_id,
                    "equipment_id": equipment,
                    "first_reading_at": first_at.isoformat(),
                    "last_reading_at": last_at.isoformat(),
                    "reading_ids": [reading_id for _, reading_id in group],
                    "observed_span_seconds": observed_span,
                    "status": status,
                }
            )

    eligible = [m for m in measurements if m["status"] == "insufficient_context"]
    if not eligible:
        return measurements

    context = completed_cycle_context(
        pd.DataFrame(
            {
                "observation_id": [m["measurement_id"] for m in eligible],
                "dependency_group_id": [m["equipment_id"] for m in eligible],
                "started_at": pd.to_datetime(
                    [m["first_reading_at"] for m in eligible], format="ISO8601"
                ),
                "ended_at": pd.to_datetime(
                    [m["last_reading_at"] for m in eligible], format="ISO8601"
                ),
            }
        ),
        **artifact["cycle_context"],
    )
    for measurement, row in zip(eligible, context.itertuples(), strict=True):
        measurement["prior_measurements"] = int(row.history_cycles_support)
        if pd.notna(row.duration_relative_history):
            raw, _ = score_ratios(artifact, [row.duration_relative_history])
            measurement.update(
                status="exploratory_scored",
                duration_relative_history=float(row.duration_relative_history),
                exploratory_score=float(raw[0]),
                exploratory_alert=bool(raw[0] >= artifact["threshold"]),
            )
    return measurements
