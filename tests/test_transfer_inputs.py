import numpy as np
import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_inputs import (
    TRI_COLUMNS,
    TRI_SHEETS,
    TRI_UNITS,
    smart_wave,
    spectral_shape,
    tri_hp_main,
)


def workbook(path, *, wrong_code=False, missing_main=False):
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"description": ["fixture, not real measurements"]}).to_excel(
            writer, sheet_name="Information", index=False
        )
        for name in TRI_SHEETS:
            code = name if name.startswith("NF") else name + ".1"
            row = [
                pd.Timestamp("2020-11-19 10:00:00"),
                "UNKNOWN" if wrong_code else code,
                0.1,
                *([1.0] * 10),
            ]
            if missing_main:
                row[0] = None
            frame = pd.DataFrame([TRI_UNITS, row, [None] * 13], columns=TRI_COLUMNS)
            frame["Date "] = [
                None,
                pd.Timestamp("2020-11-19 11:30:00"),
                pd.Timestamp("2020-11-19 11:31:00"),
            ]
            frame["Superheating"] = ["ºC", 12.0, 13.0]
            frame.to_excel(writer, sheet_name=name, index=False)


def test_tri_hp_keeps_asynchronous_logger_separate_and_label_metadata_out_of_features(tmp_path):
    path = tmp_path / "fixture.xlsx"
    workbook(path)
    frame, audit = tri_hp_main(path)
    assert len(frame) == 10
    assert frame.target_label.value_counts().to_dict() == {1: 8, 0: 2}
    assert "Superheating" not in frame
    assert audit["sheets"]["NF10"]["padding_rows_excluded"] == 1
    assert "Fault intensity" in audit["excluded_predictors"]
    assert frame.group_id.nunique() == 1


@pytest.mark.parametrize("change", ["wrong_code", "missing_main"])
def test_tri_hp_refuses_unidentified_labels_or_missing_main_timestamps(tmp_path, change):
    path = tmp_path / "invalid.xlsx"
    workbook(path, **{change: True})
    with pytest.raises(DataValidationError):
        tri_hp_main(path)


def test_spectral_shape_is_gain_invariant_and_separates_frequency_bands():
    frequency = np.arange(1025)
    density = np.exp(-(((frequency - 200) / 5.0) ** 2))
    expected = spectral_shape(frequency, density)
    amplified = spectral_shape(frequency, 100 * density)
    assert expected == pytest.approx(amplified)
    assert expected["band_fraction_100_300"] > 0.99
    assert sum(
        value for name, value in expected.items() if name.startswith("band_fraction")
    ) == pytest.approx(1.0)


@pytest.mark.parametrize("problem", ["negative", "zero", "coverage", "order"])
def test_spectral_shape_rejects_invalid_or_incompatible_spectra(problem):
    frequency = np.arange(1025, dtype=float)
    density = np.ones(1025)
    if problem == "negative":
        density[50] = -1
    elif problem == "zero":
        density[:] = 0
    elif problem == "coverage":
        frequency /= 2
    else:
        frequency[50] = frequency[49]
    with pytest.raises(DataValidationError):
        spectral_shape(frequency, density)


def test_smart_fast_audit_validates_timestamps_and_preserves_one_minute_support(tmp_path):
    timestamp = np.floor(np.arange(122880) * 1e6 / 2048).astype(int)
    wave = np.sin(2 * np.pi * 200 * timestamp / 1e6)
    frame = pd.DataFrame(
        {"UnixTimestamp (us)": timestamp, "Current": wave, "Vibration": 1800 + wave}
    )
    path = tmp_path / "fast.csv"
    frame.to_csv(path, index=False)
    values, audit = smart_wave(path)
    assert audit["duration_seconds"] == pytest.approx(60.0, abs=1e-5)
    assert audit["whole_cycle_waveform"] is False
    assert values["vibration_band_fraction_100_300"] > 0.99
    frame.loc[5, "UnixTimestamp (us)"] = 0
    frame.to_csv(path, index=False)
    with pytest.raises(DataValidationError):
        smart_wave(path)
