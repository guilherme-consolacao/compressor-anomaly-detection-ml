import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.nist_refrigeration import NIST_TEMPERATURES, nist_common


def fixture():
    return pd.DataFrame(
        {
            "Filename": ["normal.txt", "fault.txt", "unknown.txt"],
            "NF(NO=0,Yes=1)": [1.0, 0.0, None],
            "Rated_SEER": [14.0, 16.0, None],
            "Long/Short (0/1)": [0.0, 1.0, None],
            **{name: [100.0, 80.0, None] for name in ["EF", "CF", "LL", "UC/OC"]},
            **{name: [32.0, 212.0, 50.0] for name in NIST_TEMPERATURES.values()},
            "1712_RotoMass_Massflow_lb/min": [1.0, 2.0, 3.0],
            "OD_Xitron_Watts": [1000.0, 2000.0, 3000.0],
        }
    )


def test_nist_converts_units_inverts_reference_and_preserves_unknown_truth():
    frame, names, audit = nist_common(fixture())
    assert frame.discharge_c.tolist() == pytest.approx([0.0, 100.0, 10.0])
    assert frame.mass_flow_gs.iloc[0] == pytest.approx(453.59237 / 60)
    assert frame.target_label.iloc[:2].tolist() == [0, 1]
    assert pd.isna(frame.target_label.iloc[2])
    assert "power_kw" not in names
    assert "NF(NO=0,Yes=1)" not in names
    assert audit["indeterminate_rows"] == 1


def test_nist_does_not_coerce_unknown_label_or_invent_physical_values():
    raw = fixture()
    raw.loc[0, "NF(NO=0,Yes=1)"] = 2
    with pytest.raises(DataValidationError):
        nist_common(raw)
    raw = fixture()
    raw.loc[0, "1712_RotoMass_Massflow_lb/min"] = None
    with pytest.raises(DataValidationError):
        nist_common(raw)
