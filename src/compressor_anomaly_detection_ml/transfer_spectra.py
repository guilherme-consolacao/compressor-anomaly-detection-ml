"""Richer scale-free signatures for the public mechanical transfer experiment."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import welch

from .datasets import safe_member
from .domain import DataValidationError
from .transfer_inputs import smart_wave, spectral_shape


def spectrum_signature(frequency, density):
    result = spectral_shape(frequency, density)
    frequency, density = np.asarray(frequency, float), np.asarray(density, float)
    selected = (frequency >= 10) & (frequency <= 1000)
    f, p = frequency[selected], density[selected]
    mass = p * np.gradient(f)
    mass /= mass.sum()
    bins, _ = np.histogram(f, bins=np.linspace(10, 1000, 33), weights=mass)
    result.update(
        {"spectral_bin_" + str(index).zfill(2): float(value) for index, value in enumerate(bins)}
    )
    fundamental = (f >= 20) & (f <= 120)
    if not fundamental.any():
        raise DataValidationError("A resolved low-frequency peak band is required.")
    base = float(f[fundamental][np.argmax(p[fundamental])])
    result["dominant_low_frequency_relative"] = (base - 20) / 100
    # This is a statistical spectral peak, not an identified shaft speed.
    for order in (1, 2, 3, 4, 6):
        result["harmonic_energy_" + str(order)] = float(
            mass[np.abs(f - base * order) <= max(5, base * 0.05)].sum()
        )
    return result


def smart_signature(path: Path):
    _, audit = smart_wave(path)
    raw = pd.read_csv(path)
    result = {}
    for channel in ("Vibration", "Current"):
        f, p = welch(raw[channel].to_numpy(float), fs=2048, nperseg=2048, detrend="constant")
        result.update(
            {
                channel.lower() + "_" + name: value
                for name, value in spectrum_signature(f, p).items()
            }
        )
    return result, audit


def rwth_signatures(folder: Path):
    manifest = pd.read_csv(folder / "manifest.csv")
    by_condition = {}
    for row in manifest.itertuples():
        if row.sensor_raw_channel not in {"comp_down_tri_" + axis for axis in "xyz"}:
            continue
        safe_member(row.file)
        frame = pd.read_csv(folder / row.file)
        axis = row.sensor_raw_channel[-1]
        for column in frame.columns[1:]:
            key = (row.measurement_id, int(column[:-1]))
            values = by_condition.setdefault(key, {})
            values[axis] = spectrum_signature(frame.frequency_hz, frame[column])
    rows = []
    for (session, charge), axes in sorted(by_condition.items()):
        if set(axes) != {"x", "y", "z"}:
            raise DataValidationError("All documented compressor axes are required.")
        shared = {
            "vibration_" + name: float(np.mean([axes[axis][name] for axis in "xyz"]))
            for name in axes["x"]
        }
        rows.append({"measurement_id": session, "refrigerant_charge_g": charge, **shared})
    return pd.DataFrame(rows)
