"""NIST measured fault summaries: preserve references and convert verified units."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .domain import DataValidationError

NIST_FILE_SHA256 = "db807bb9486717c275a2fc3cf45d04042aa1bae2668a592bf050be88f2bdfc2c"
NIST_TEMPERATURES = {
    "evaporating_c": "CompSuct_Tsat_F",
    "condensing_c": "CompDisch_Tsat_F",
    "discharge_c": "1617_CompDisch_TempF",
    "liquid_line_c": "1500_ODLiqSV_TempF",
    "suction_c": "1608_CompSuct_TempF",
    "outdoor_air_c": "OD Air AVG DB (F)",
}


def nist_common(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict]:
    labels = "NF(NO=0,Yes=1)"
    metadata = ["Filename", labels, "Rated_SEER", "Long/Short (0/1)", "EF", "CF", "LL", "UC/OC"]
    required = [
        *metadata,
        *NIST_TEMPERATURES.values(),
        "1712_RotoMass_Massflow_lb/min",
        "OD_Xitron_Watts",
    ]
    if not set(required) <= set(raw) or raw.Filename.isna().any():
        raise DataValidationError("NIST summary schema or original identity changed.")
    known = raw[labels].notna()
    if not raw.loc[known, labels].isin([0, 1]).all():
        raise DataValidationError("NIST reference is not the documented no-fault flag.")
    if raw.loc[known, ["Rated_SEER", "Long/Short (0/1)"]].isna().any().any():
        raise DataValidationError("NIST labelled observation lacks its equipment stratum.")
    if (
        not raw.loc[known, "Rated_SEER"].isin([14, 16]).all()
        or not raw.loc[known, "Long/Short (0/1)"].isin([0, 1]).all()
    ):
        raise DataValidationError("NIST equipment strata changed from the inspected contract.")
    frame = raw[metadata].copy()
    for name, original in NIST_TEMPERATURES.items():
        frame[name] = (pd.to_numeric(raw[original], errors="raise") - 32) * 5 / 9
    frame["mass_flow_gs"] = (
        pd.to_numeric(raw["1712_RotoMass_Massflow_lb/min"], errors="raise") * 453.59237 / 60
    )
    # Outdoor-unit power includes fan consumption; it is not compressor-only power.
    frame["outdoor_unit_power_kw"] = pd.to_numeric(raw["OD_Xitron_Watts"], errors="raise") / 1000
    frame["temperature_lift_c"] = frame.condensing_c - frame.evaporating_c
    frame["discharge_above_condensing_c"] = frame.discharge_c - frame.condensing_c
    frame["subcooling_c"] = frame.condensing_c - frame.liquid_line_c
    names = [
        *NIST_TEMPERATURES,
        "mass_flow_gs",
        "outdoor_unit_power_kw",
        "temperature_lift_c",
        "discharge_above_condensing_c",
        "subcooling_c",
    ]
    if not np.isfinite(frame[names].to_numpy(float)).all():
        raise DataValidationError("NIST physical summaries have missing or nonfinite values.")
    frame["target_label"] = (1 - raw[labels]).astype("Int64")
    frame["label_status"] = np.where(known, "reference", "indeterminate")
    frame["source_id"] = "nist_hvac"
    frame["provider_row"] = np.arange(len(frame)) + 2
    frame["observation_id"] = "nist_hvac:2019:" + frame.provider_row.astype(str)
    # Entire equipment stratum remains together for the first cross-equipment holdout.
    frame["equipment_stratum"] = (
        raw["Rated_SEER"].map({14: "14-SEER", 16: "16-SEER"}).fillna("unknown")
    )
    frame["group_id"] = "nist:equipment-stratum:" + frame.equipment_stratum
    frame["source_file_group"] = frame.Filename
    return (
        frame,
        names,
        {
            "rows": len(frame),
            "known_reference_rows": int(known.sum()),
            "indeterminate_rows": int((~known).sum()),
            "files": int(frame.Filename.nunique()),
            "normal_rows": int(frame.target_label.eq(0).sum()),
            "fault_rows": int(frame.target_label.eq(1).sum()),
            "grouping": "SEER equipment strata, not independently identified serial numbers",
            "no_fault_encoding": "provider 1=normal; project target 1=fault",
            "outdoor_power_not_compressor_power": True,
            "excluded_predictors": metadata,
            "time_axis": "steady-state summary order, no acquisition timestamp supplied here",
            "temperature_locations": (
                "refrigerant line surface and pressure-derived saturation, not carcass"
            ),
        },
    )


def nist_table(path: Path) -> tuple[pd.DataFrame, list[str], dict]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != NIST_FILE_SHA256:
        raise DataValidationError("NIST workbook changed from the inspected public artifact.")
    return nist_common(pd.read_excel(path))
