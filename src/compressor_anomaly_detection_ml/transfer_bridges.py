"""Exact measured modality joins and refrigeration-domain bridge features."""

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .domain import DataValidationError
from .public_importers import rwth_tables
from .transfer_inputs import spectral_shape


def rwth_spectral_table(folder: Path) -> tuple[pd.DataFrame, dict]:
    base, _, _ = rwth_tables(folder)
    psd_root = folder / "psd-audit/vibration_psd"
    manifest = pd.read_csv(psd_root / "manifest.csv")
    records = {}
    rms_errors = []
    for session in sorted(base.measurement_id.unique()):
        for axis in "xyz":
            match = manifest[
                (manifest.measurement_id == session)
                & (manifest.sensor_raw_channel == "comp_down_tri_" + axis)
            ]
            if len(match) != 1:
                raise DataValidationError(
                    "PSD channel mapping must be unique and provider documented."
                )
            file = Path(match.iloc[0]["file"])
            if file.is_absolute() or ".." in file.parts:
                raise DataValidationError("Unsafe provider PSD path.")
            frame = pd.read_csv(psd_root / file)
            if frame.columns[0] != "frequency_hz" or len(frame) != int(
                match.iloc[0].n_frequency_bins
            ):
                raise DataValidationError("RWTH PSD frequency schema changed.")
            if len(frame.columns) - 1 != int(match.iloc[0].n_charge_levels):
                raise DataValidationError("RWTH PSD condition support differs from its manifest.")
            frequency = frame.frequency_hz.to_numpy(float)
            for charge_name in frame.columns[1:]:
                if not re.fullmatch(r"[0-9]+g", charge_name):
                    raise DataValidationError("RWTH PSD charge identity is malformed.")
                charge = int(charge_name[:-1])
                density = frame[charge_name].to_numpy(float)
                features = spectral_shape(frequency, density)
                row = records.setdefault(
                    (session, charge), {"measurement_id": session, "refrigerant_charge_g": charge}
                )
                row.update({"psd_" + axis + "_" + key: value for key, value in features.items()})
                band = (frequency >= 10) & (frequency <= 1000)
                row["psd_integrated_rms_" + axis] = float(
                    np.sqrt(np.trapezoid(density[band], frequency[band]))
                )
    spectral = pd.DataFrame(records.values())
    joined = base.merge(
        spectral, on=["measurement_id", "refrigerant_charge_g"], how="left", validate="one_to_one"
    )
    spectral_names = [
        name for name in spectral if name not in {"measurement_id", "refrigerant_charge_g"}
    ]
    if not np.isfinite(joined[spectral_names].to_numpy(float)).all():
        raise DataValidationError("A paired RWTH thermal condition lacks a compressor spectrum.")
    shape_names = list(spectral_shape(np.arange(1025), np.ones(1025)))
    for name in shape_names:
        joined["vibration_" + name] = joined[["psd_" + axis + "_" + name for axis in "xyz"]].mean(
            axis=1
        )
    joined["compressor_rms_spatial"] = np.sqrt(
        (joined[["compressor_rms_" + axis for axis in "xyz"]] ** 2).mean(axis=1)
    )
    for axis in "xyz":
        relative = joined["psd_integrated_rms_" + axis] / joined["compressor_rms_" + axis] - 1
        rms_errors.append(
            {
                "axis": axis,
                "median_relative_difference": float(relative.median()),
                "maximum_absolute_relative_difference": float(relative.abs().max()),
            }
        )
    return joined, {
        "exact_paired_conditions": len(joined),
        "spectral_conditions": len(spectral),
        "group_count": int(joined.measurement_id.nunique()),
        "compressor_channels": ["comp_down_tri_" + axis for axis in "xyz"],
        "join_keys": ["measurement_id", "refrigerant_charge_g"],
        "rms_integration_comparison": rms_errors,
        "band_hz": [10, 1000],
        "full_archive_checksum_verified": False,
        "archive_member_integrity": (
            "ZIP CRC plus local SHA-256; complete archive was not downloaded"
        ),
    }


def refrigeration_common(frame: pd.DataFrame, source: str) -> tuple[pd.DataFrame, list[str]]:
    """Only physically corresponding measurements, with explicit location semantics."""
    if source == "rwth_r290":
        names = {
            "power_kw": "P_el_com_kW",
            "evaporating_c": "T_e_C",
            "condensing_c": "T_c_C",
            "discharge_c": "T_com_out_C",
            "liquid_line_c": "T_con_out_C",
            "mass_flow_gs": "m_flow_ref_gs",
            "heat_duty_kw": "Q_flow_con_ref_kW",
            "cop": "COP_ref",
        }
    elif source == "tri_hp_faults":
        names = {
            "power_kw": "Compressor_power_consumption",
            "evaporating_c": "Evaporator_saturation_temperature",
            "condensing_c": "Condenser_saturation_temperature",
            "discharge_c": "Compressor_outlet_temperature",
            "liquid_line_c": "Liquid_line_refrigerant_temperature",
            "mass_flow_gs": "Refrigerant_Mass_flow",
            "heat_duty_kw": "Condenser_heat_duty",
            "cop": "COP",
        }
    else:
        raise DataValidationError("No verified thermal/electrical mapping for this source.")
    result = frame.rename(columns={value: key for key, value in names.items()}).copy()
    if not np.isfinite(result[list(names)].to_numpy(float)).all():
        raise DataValidationError("Common refrigeration measurements must be finite.")
    result["temperature_lift_c"] = result.condensing_c - result.evaporating_c
    result["discharge_above_condensing_c"] = result.discharge_c - result.condensing_c
    result["subcooling_c"] = result.condensing_c - result.liquid_line_c
    result["source_id"] = source
    return result, list(names) + [
        "temperature_lift_c",
        "discharge_above_condensing_c",
        "subcooling_c",
    ]


def file_manifest(paths: list[Path]) -> list[dict]:
    return [
        {
            "relative_path": path.as_posix(),
            "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size,
        }
        for path in sorted(paths)
    ]
