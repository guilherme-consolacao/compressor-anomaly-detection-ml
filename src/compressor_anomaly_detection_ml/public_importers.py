"""Source-specific public tables; no invented units, cycles or binary labels."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .domain import DataValidationError


def read_table(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=None, engine="python")
    if frame.empty or frame.columns.duplicated().any():
        raise DataValidationError("Public table is empty or has repeated columns.")
    return frame.copy()


def smart_pdm_tables(folder: Path) -> tuple[pd.DataFrame, list[str], dict]:
    metadata = read_table(folder / "fridge_metadata.csv")
    features = read_table(folder / "F_ExtractedFeatures.csv")
    required = {"begin_end", "timestamp_begin", "timestamp_end", "brand", "model", "failure"}
    if not required <= set(metadata) or "Id" not in features:
        raise DataValidationError("SMART-PDM table schema differs from the verified version.")
    if metadata.begin_end.duplicated().any() or features.Id.duplicated().any():
        raise DataValidationError("SMART-PDM cycle keys are not unique.")
    frame = features.merge(
        metadata,
        how="outer",
        left_on="Id",
        right_on="begin_end",
        validate="one_to_one",
        indicator=True,
    )
    if not (frame["_merge"] == "both").all():
        raise DataValidationError("SMART-PDM has cycles without matching metadata/features.")
    names = [column for column in features if column != "Id"]
    if len(names) != 100:
        raise DataValidationError(
            "SMART-PDM published feature count changed; inspect a new version."
        )
    values = frame[names].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values.to_numpy()).all():
        raise DataValidationError("SMART-PDM published features contain missing/nonfinite values.")
    if not set(frame.failure) <= {"Normal", "Malfunction"}:
        raise DataValidationError("Unknown SMART-PDM label.")
    frame[names] = values
    frame = frame.copy()
    frame["started_at"] = pd.to_datetime(frame.timestamp_begin, unit="s", utc=True)
    frame["ended_at"] = pd.to_datetime(frame.timestamp_end, unit="s", utc=True)
    if frame.started_at.isna().any() or frame.ended_at.isna().any():
        raise DataValidationError("SMART-PDM cycle capture limits are missing.")
    if (frame.ended_at < frame.started_at).any():
        raise DataValidationError("SMART-PDM cycle ends before it begins.")
    frame["original_id"] = frame.begin_end
    frame["target_label"] = frame.failure.map({"Normal": 0, "Malfunction": 1})
    frame["observation_id"] = frame.begin_end.map(
        lambda x: "smart_pdm:7245198:" + hashlib.sha256(x.encode()).hexdigest()[:32]
    )
    frame["candidate_group"] = "smart_pdm:utc-day:" + frame.started_at.dt.strftime("%Y-%m-%d")
    frame = frame.sort_values("original_id").reset_index(drop=True)
    return (
        frame,
        names,
        {
            "rows": len(frame),
            "feature_count": len(names),
            "labels": {str(k): int(v) for k, v in frame.failure.value_counts().items()},
            "join": "features.Id == metadata.begin_end; one-to-one; no orphan keys",
            "original_row_order_equal": features.Id.tolist() == metadata.begin_end.tolist(),
            "missing_numeric_cells": int(values.isna().sum().sum()),
            "candidate_temporal_groups": int(frame.candidate_group.nunique()),
            "physical_equipment_identity_known": False,
            "vibration_physical_unit_confirmed": False,
            "raw_waveforms_downloaded": False,
        },
    )


def rwth_tables(folder: Path) -> tuple[pd.DataFrame, list[str], dict]:
    thermal = read_table(folder / "thermodynamic/thermodynamic_averaged_with_uncertainty.csv")
    rms = read_table(folder / "vibration_rms/rms_by_charge.csv")
    keys = ["measurement_id", "refrigerant_charge_g"]
    if not set(keys) <= set(thermal) or not {
        "measurement_id",
        "charge_g",
        "sensor_raw_channel",
        "frequency_band_hz",
        "rms_ms2",
    } <= set(rms):
        raise DataValidationError("RWTH source schema changed.")
    if thermal.duplicated(keys).any():
        raise DataValidationError("RWTH thermal keys are not unique.")
    channels = {
        "comp_down_tri_x": "compressor_rms_x",
        "comp_down_tri_y": "compressor_rms_y",
        "comp_down_tri_z": "compressor_rms_z",
    }
    selected = rms.loc[rms.sensor_raw_channel.isin(channels)].copy()
    if selected.duplicated(["measurement_id", "charge_g", "sensor_raw_channel"]).any():
        raise DataValidationError("RWTH contains duplicated compressor axes.")
    count = selected.groupby(["measurement_id", "charge_g"]).sensor_raw_channel.nunique()
    if not (count == 3).all():
        raise DataValidationError("RWTH compressor condition is missing an axis.")
    if not (selected.frequency_band_hz.astype(str) == "10-1000").all():
        raise DataValidationError("RWTH RMS integration band changed.")
    if not np.isfinite(selected.rms_ms2).all() or (selected.rms_ms2 < 0).any():
        raise DataValidationError("Invalid RWTH compressor RMS.")
    selected["feature"] = selected.sensor_raw_channel.map(channels)
    pivot = selected.pivot(
        index=["measurement_id", "charge_g"], columns="feature", values="rms_ms2"
    )
    pivot = pivot.reset_index().rename(columns={"charge_g": "refrigerant_charge_g"})
    frame = thermal.merge(pivot, how="outer", on=keys, validate="one_to_one", indicator=True)
    unmatched = frame.loc[frame["_merge"] != "both", keys].to_dict(orient="records")
    frame = frame.loc[frame["_merge"] == "both"].copy()
    names = [
        column for column in frame.select_dtypes(include="number") if not column.startswith("U_")
    ]
    if not np.isfinite(frame[names].to_numpy()).all():
        raise DataValidationError("RWTH paired conditions have nonfinite feature values.")
    frame["original_id"] = (
        frame.measurement_id + ":charge:" + frame.refrigerant_charge_g.astype(str)
    )
    frame["observation_id"] = frame.original_id.map(
        lambda x: "rwth_r290:22097811:" + hashlib.sha256(x.encode()).hexdigest()[:32]
    )
    frame["candidate_group"] = "rwth_r290:session:" + frame.measurement_id
    frame = frame.sort_values("original_id").reset_index(drop=True)
    return (
        frame,
        names,
        {
            "thermal_conditions": len(thermal),
            "triaxial_rms_conditions": len(pivot),
            "paired_conditions": len(frame),
            "unmatched_conditions": unmatched,
            "rms_rows_all_sensors": len(rms),
            "sessions": int(frame.measurement_id.nunique()),
            "binary_labels_available": False,
            "compressor_rms_unit": "m/s²",
            "rms_band_hz": [10, 1000],
            "temperature_locations": [
                "compressor refrigerant inlet",
                "compressor refrigerant outlet",
            ],
            "raw_waveforms_downloaded": False,
        },
    )
