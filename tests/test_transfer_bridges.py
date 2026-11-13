import numpy as np
import pandas as pd
import pytest

import compressor_anomaly_detection_ml.transfer_bridges as bridges
from compressor_anomaly_detection_ml.domain import DataValidationError


def test_rwth_pairs_only_exact_session_charge_and_documented_axis(tmp_path, monkeypatch):
    root = tmp_path / "psd-audit/vibration_psd"
    (root / "M01").mkdir(parents=True)
    frequency = np.arange(1025, dtype=float)
    density = np.ones(len(frequency))
    rms = float(np.sqrt(np.trapezoid(density[10:1001], frequency[10:1001])))
    base = pd.DataFrame(
        {
            "measurement_id": ["M01"],
            "refrigerant_charge_g": [500],
            **{"compressor_rms_" + axis: [rms] for axis in "xyz"},
        }
    )
    monkeypatch.setattr(bridges, "rwth_tables", lambda folder: (base, [], {}))
    rows = []
    for axis in "xyz":
        file = "M01/psd_compressor_" + axis + ".csv"
        pd.DataFrame({"frequency_hz": frequency, "500g": density, "600g": density * 2}).to_csv(
            root / file, index=False
        )
        rows.append(
            {
                "measurement_id": "M01",
                "sensor_raw_channel": "comp_down_tri_" + axis,
                "file": file,
                "n_frequency_bins": len(frequency),
                "n_charge_levels": 2,
            }
        )
    pd.DataFrame(rows).to_csv(root / "manifest.csv", index=False)
    frame, audit = bridges.rwth_spectral_table(tmp_path)
    assert len(frame) == 1
    assert audit["spectral_conditions"] == 2
    assert audit["exact_paired_conditions"] == 1
    assert audit["rms_integration_comparison"][0][
        "maximum_absolute_relative_difference"
    ] == pytest.approx(0.0)
    rows[0]["sensor_raw_channel"] = "wrong_sensor"
    pd.DataFrame(rows).to_csv(root / "manifest.csv", index=False)
    with pytest.raises(DataValidationError):
        bridges.rwth_spectral_table(tmp_path)
