import zipfile
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.sample_audit import (
    fault_summary,
    kaist_thermal,
    kaist_vibration,
    signal_features,
    ult_log,
)


def test_dimensionless_statistics_are_invariant_to_positive_scale_and_offset():
    signal = np.random.default_rng(7).normal(size=500)
    first, second = signal_features(signal), signal_features(30 + signal * 12)
    for name in ["skewness", "kurtosis", "range_over_std"]:
        assert first[name] == pytest.approx(second[name])
    assert signal_features(np.ones(10))["skewness"] is None


@pytest.mark.parametrize("values", [[1, 2], [0] * 9 + [np.inf]])
def test_signal_refuses_invalid_samples(values):
    with pytest.raises(DataValidationError):
        signal_features(values)


def test_kaist_preserves_positions_and_load_group(tmp_path):
    time = np.arange(100) / 10
    matrix = np.column_stack([np.sin(time + i) for i in range(4)])
    signal = {
        "x_values": {"start_value": 0, "increment": 0.1, "number_of_values": 100},
        "y_values": {
            "values": matrix,
            "quantity": {
                "label": "g",
                "info": "MKS",
                "unit_transformation": {"factor": 0.1019716, "offset": 0},
            },
        },
    }
    path = tmp_path / "2Nm_BPFO_03.mat"
    savemat(path, {"Signal": signal})
    rows, report = kaist_vibration(path)
    assert len(rows) == 8 and report["sampling_hz"] == pytest.approx(10)
    assert {r["group"] for r in rows} == {"kaist:load:2Nm"}
    assert {r["target"] for r in rows} == {1}
    assert rows[0]["condition"]["position"] == "housing_A_x"
    assert rows[0]["unit"] is None
    signal["x_values"]["increment"] = -0.1
    savemat(path, {"Signal": signal})
    with pytest.raises(DataValidationError, match="regular"):
        kaist_vibration(path)
    signal["x_values"]["increment"] = 0.1
    unknown = tmp_path / "2Nm_Unknown.mat"
    savemat(unknown, {"Signal": signal})
    with pytest.raises(DataValidationError, match="label policy"):
        kaist_vibration(unknown)


def test_kaist_refuses_invented_matrix_layout(tmp_path):
    path = tmp_path / "2Nm_Normal.mat"
    savemat(path, {"recording": np.zeros((100, 5))})
    with pytest.raises(DataValidationError, match="Signal struct"):
        kaist_vibration(path)


def test_kaist_thermal_preserves_declared_empty_current_channels(tmp_path):
    from nptdms import ChannelObject, TdmsWriter

    path = tmp_path / "sample.tdms"
    with TdmsWriter(path) as writer:
        writer.write_segment(
            [
                ChannelObject(
                    "Log",
                    f"channel{i}",
                    np.arange(10, dtype=float) if i < 3 else np.array([], dtype=float),
                    properties={"DAC~Channel~Type": "Temperature" if i < 2 else "Current"},
                )
                for i in range(5)
            ]
        )
    report = kaist_thermal(path)
    assert len(report["channels"]) == 5
    assert sum(c["status"] == "missing" for c in report["channels"]) == 2
    assert report["channels"][-1]["features"] is None


def test_ult_keeps_naive_time_and_legitimate_extreme(tmp_path):
    path = tmp_path / "sample.dat"
    path.write_text(
        "UnitID\t99\nStart\tDate\tTime\tRTD\tTC1\tTC9\tSetPoint\tTemperature Units\n"
        "SX\t01/01/2020\t00:00:00\t-80\t10\t200\t-80\tC\n"
        "SX\t01/01/2020\t00:01:00\t-81\t11\t20\t-80\tC\n"
    )
    frame, audit = ult_log(path)
    assert frame.TC9.iloc[0] == 200
    assert frame.local_time.dt.tz is None
    assert audit["median_interval_seconds"] == 60
    path.write_text(path.read_text().replace("\tC\n", "\tF\n"))
    with pytest.raises(DataValidationError, match="Celsius"):
        ult_log(path)


def test_fault_summary_preserves_service_date_without_inventing_onset(tmp_path):
    path = tmp_path / "summary.xlsx"
    namespace = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    strings = [
        "freezer_id",
        "registered_date",
        "main_fault",
        "Fault categories",
        "compressor",
        "stage2",
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f"<workbook {namespace}><workbookPr/></workbook>")
        archive.writestr(
            "xl/sharedStrings.xml",
            f"<sst {namespace}>" + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"<worksheet {namespace}><sheetData><row>"
            + "".join(f'<c r="{letter}1" t="s"><v>{i}</v></c>' for i, letter in enumerate("ABCD"))
            + '</row><row><c r="A2"><v>123</v></c><c r="B2"><v>43831</v></c>'
            '<c r="C2" t="s"><v>4</v></c><c r="D2" t="s"><v>5</v></c>'
            "</row></sheetData></worksheet>",
        )
    frame = fault_summary(Path(path))
    assert frame.registered_date.iloc[0].isoformat() == "2020-01-01T00:00:00"
    assert "target_label" not in frame
