import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.public_importers import rwth_tables, smart_pdm_tables


def smart_fixture(folder):
    folder.mkdir(parents=True, exist_ok=True)
    metadata = pd.DataFrame(
        {
            "begin_end": ["a", "b"],
            "timestamp_begin": [100, 200],
            "timestamp_end": [150, 250],
            "brand": ["fixture"] * 2,
            "model": ["fixture"] * 2,
            "failure": ["Normal", "Malfunction"],
        }
    )
    features = pd.DataFrame({"Id": ["b", "a"], **{f"feature_{i}": [2.0, 1.0] for i in range(100)}})
    metadata.to_csv(folder / "fridge_metadata.csv", index=False)
    features.to_csv(folder / "F_ExtractedFeatures.csv", index=False)
    return metadata, features


def test_smart_matches_keys_not_positions(tmp_path):
    smart_fixture(tmp_path)
    frame, names, report = smart_pdm_tables(tmp_path)
    assert len(names) == 100 and report["original_row_order_equal"] is False
    assert frame.loc[frame.original_id == "a", "target_label"].item() == 0
    assert frame.loc[frame.original_id == "a", "feature_0"].item() == 1
    assert frame.loc[frame.original_id == "b", "target_label"].item() == 1


@pytest.mark.parametrize("problem", ["duplicate", "orphan", "nonfinite", "label"])
def test_smart_rejects_inconsistent_input(tmp_path, problem):
    metadata, features = smart_fixture(tmp_path)
    if problem == "duplicate":
        features["Id"] = ["a", "a"]
    if problem == "orphan":
        features.loc[0, "Id"] = "missing"
    if problem == "nonfinite":
        features.loc[0, "feature_0"] = float("inf")
    if problem == "label":
        metadata.loc[0, "failure"] = "unknown"
    metadata.to_csv(tmp_path / "fridge_metadata.csv", index=False)
    features.to_csv(tmp_path / "F_ExtractedFeatures.csv", index=False)
    with pytest.raises(DataValidationError):
        smart_pdm_tables(tmp_path)


def rwth_fixture(folder):
    (folder / "thermodynamic").mkdir()
    (folder / "vibration_rms").mkdir()
    thermal = pd.DataFrame(
        {
            "measurement_id": ["M01"],
            "refrigerant_charge_g": [500],
            "T_com_in_C": [10.0],
            "T_com_out_C": [70.0],
        }
    )
    rms = pd.DataFrame(
        [
            {
                "measurement_id": "M01",
                "charge_g": charge,
                "sensor_raw_channel": "comp_down_tri_" + axis,
                "frequency_band_hz": "10-1000",
                "rms_ms2": 1.0,
            }
            for charge in [500, 600]
            for axis in ["x", "y", "z"]
        ]
    )
    thermal.to_csv(
        folder / "thermodynamic/thermodynamic_averaged_with_uncertainty.csv", index=False
    )
    rms.to_csv(folder / "vibration_rms/rms_by_charge.csv", index=False)
    return rms


def test_rwth_keeps_unmatched_conditions_visible(tmp_path):
    rwth_fixture(tmp_path)
    frame, names, report = rwth_tables(tmp_path)
    assert len(frame) == 1 and "compressor_rms_x" in names
    assert report["unmatched_conditions"] == [
        {"measurement_id": "M01", "refrigerant_charge_g": 600}
    ]
    assert report["binary_labels_available"] is False


@pytest.mark.parametrize("problem", ["duplicate", "missing_axis", "band"])
def test_rwth_rejects_invalid_axis_or_definition(tmp_path, problem):
    rms = rwth_fixture(tmp_path)
    if problem == "duplicate":
        rms = pd.concat([rms, rms.iloc[:1]], ignore_index=True)
    if problem == "missing_axis":
        rms = rms.iloc[1:]
    if problem == "band":
        rms["frequency_band_hz"] = "0-10"
    rms.to_csv(tmp_path / "vibration_rms/rms_by_charge.csv", index=False)
    with pytest.raises(DataValidationError):
        rwth_tables(tmp_path)
