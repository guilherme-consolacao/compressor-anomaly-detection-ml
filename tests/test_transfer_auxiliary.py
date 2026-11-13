import pandas as pd
import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_auxiliary import auxiliary_comparison, washer_tables


def test_washer_import_quarantines_conflicting_identities_and_preserves_provider_references(
    tmp_path,
):
    metadata = [
        ["cycle-a", 1, 2, "brand", "model", "p", 20, 800, "empty", "Working", None],
        ["cycle-b", 3, 4, "brand", "model", "p", 20, 800, "empty", "Motor", None],
        ["cycle-c", 5, 6, "brand", "model", "p", 20, 800, "empty", "Heating", None],
        ["cycle-c", 5, 6, "brand", "model", "p", 20, 800, "empty", "Working", None],
        ["cycle-d", 7, 8, "brand", "model", "p", 20, 800, "empty", "Bearings", None],
    ]
    pd.DataFrame(metadata).to_csv(
        tmp_path / "washing_machine_metadata.csv", header=False, index=False
    )
    names = [
        prefix + "__f" + str(i) for prefix in ("ActP", "Current", "Vibration") for i in range(25)
    ]
    values = pd.DataFrame([[1.0] * 75] * 5, columns=names)
    values.insert(0, "Id", ["cycle-a", "cycle-b", "cycle-c", "cycle-d", "cycle-d"])
    values.loc[4, names[0]] = 2.0
    values.to_csv(tmp_path / "WM_ExtractedFeatures.csv", index=False)
    frame, _, audit = washer_tables(tmp_path)
    assert frame.original_id.tolist() == ["cycle-a", "cycle-b"]
    assert frame.target_label.tolist() == [0, 1]
    assert audit["conflicting_metadata_ids"] == ["cycle-c"]
    assert audit["conflicting_feature_ids"] == ["cycle-d"]
    assert audit["compressor_failure_labels"] is False


def test_auxiliary_comparison_refuses_reserved_or_external_anchor_before_training():
    smart = pd.DataFrame({"source_id": ["smart_pdm"], "partition_name": ["test"]})
    auxiliary = pd.DataFrame({"source_id": ["smart_pdm_washers"]})
    with pytest.raises(DataValidationError):
        auxiliary_comparison(smart, auxiliary, {})
