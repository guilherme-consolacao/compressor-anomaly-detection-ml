"""Decode the bounded public samples, preserving recording and sensor identities."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat, whosmat
from scipy.stats import kurtosis, skew

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import save_immutable
from .domain import DataValidationError
from .public_acquisition import artifact_row


def signal_features(values) -> dict:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 8 or not np.isfinite(values).all():
        raise DataValidationError("A signal must contain at least eight finite samples.")
    std = float(values.std())
    return {
        "mean": float(values.mean()),
        "std": std,
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "rms": float(np.sqrt(np.mean(values**2))),
        "skewness": float(skew(values, bias=False)) if std else None,
        "kurtosis": float(kurtosis(values, fisher=True, bias=False)) if std else None,
        "range_over_std": float(np.ptp(values) / std) if std else None,
    }


def fault_summary(path: Path) -> pd.DataFrame:
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        props = workbook.find("s:workbookPr", ns)
        epoch = (
            datetime(1904, 1, 1)
            if props is not None and props.get("date1904") == "1"
            else datetime(1899, 12, 30)
        )
        strings = [
            "".join(item.itertext())
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", ns)
        ]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//s:row", ns):
            cells = {}
            for cell in row.findall("s:c", ns):
                value = cell.find("s:v", ns)
                if value is not None:
                    cells[re.sub(r"\d", "", cell.attrib["r"])] = (
                        strings[int(value.text)] if cell.get("t") == "s" else value.text
                    )
            rows.append([cells.get(letter) for letter in "ABCD"])
    if not rows or rows[0][:3] != ["freezer_id", "registered_date", "main_fault"]:
        raise DataValidationError("ULT service summary schema changed.")
    frame = pd.DataFrame(rows[1:], columns=rows[0])
    frame["registered_date"] = frame.registered_date.map(
        lambda value: epoch + timedelta(days=float(value))
    )
    if frame.duplicated().any() or frame.isna().any().any():
        raise DataValidationError("ULT service summary contains duplicate/incomplete events.")
    return frame


def ult_log(path: Path) -> tuple[pd.DataFrame, dict]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    offset = next(
        (i for i, line in enumerate(lines) if line.startswith("Start\tDate\tTime\t")), None
    )
    if offset is None:
        raise DataValidationError("ULT thermal header is missing.")
    frame = pd.read_csv(StringIO("\n".join(lines[offset:])), sep="\t")
    required = {"Date", "Time", "Temperature Units", "RTD", "TC1", "TC9", "SetPoint"}
    if not required <= set(frame) or frame.empty:
        raise DataValidationError("ULT thermal schema changed.")
    if not frame["Temperature Units"].astype(str).str.strip().eq("C").all():
        raise DataValidationError("ULT sample temperature unit is not Celsius.")
    frame["local_time"] = pd.to_datetime(frame.Date + " " + frame.Time, format="%m/%d/%Y %H:%M:%S")
    numeric = [
        name
        for name in frame
        if name.startswith("TC") or name in {"RTD", "SetPoint", "Mains Voltage"}
    ]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame[numeric].to_numpy()).all() or frame.local_time.duplicated().any():
        raise DataValidationError("ULT sample contains nonfinite values or duplicate timestamps.")
    return frame, {
        "rows": len(frame),
        "channels": numeric,
        "temperature_unit": "degC",
        "timezone": "unknown; local timestamps retained as strings, not asserted UTC",
        "median_interval_seconds": float(
            frame.local_time.sort_values().diff().dt.total_seconds().median()
        ),
        "header": lines[:offset],
        "identity": "provider freezer folder; controller header preserved",
    }


def kaist_vibration(path: Path) -> tuple[list[dict], dict]:
    variables = whosmat(path)
    if variables != [("Signal", (1, 1), "struct")]:
        raise DataValidationError("KAIST vibration requires the audited Test.Lab Signal struct.")
    try:
        signal = loadmat(path, variable_names=["Signal"], squeeze_me=True, struct_as_record=False)[
            "Signal"
        ]
        matrix = np.asarray(signal.y_values.values, dtype=float)
        increment = float(signal.x_values.increment)
        start_time = float(signal.x_values.start_value)
        declared_count = int(signal.x_values.number_of_values)
        quantity = signal.y_values.quantity
        unit_metadata = {
            "label": str(quantity.label),
            "info": str(quantity.info),
            "factor": float(quantity.unit_transformation.factor),
            "offset": float(quantity.unit_transformation.offset),
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        raise DataValidationError("KAIST Signal struct is incomplete.") from None
    if matrix.ndim != 2 or matrix.shape[1] != 4 or len(matrix) != declared_count:
        raise DataValidationError("KAIST Signal sample count/channels differ from metadata.")
    if not np.isfinite(matrix).all():
        raise DataValidationError("KAIST vibration contains nonfinite samples.")
    if not np.isfinite([increment, start_time]).all() or increment <= 0:
        raise DataValidationError("KAIST vibration time axis is not regular/increasing.")
    load, condition = path.stem.split("Nm_", 1)
    if load not in {"2", "4"} or condition not in {"Normal", "BPFO_03"}:
        raise DataValidationError("KAIST condition is outside the selected label policy.")
    width = round(5 / increment)
    if width < 8 or width > len(matrix):
        raise DataValidationError("KAIST recording cannot support the declared research window.")
    rows = []
    for start in range(0, len(matrix) - width + 1, width):
        for index, position in enumerate(
            ["housing_A_x", "housing_A_y", "housing_B_x", "housing_B_y"]
        ):
            rows.append(
                {
                    "original_id": f"{path.name}:{position}:samples:{start}:{start + width}",
                    "group": f"kaist:load:{load}Nm",
                    "target": int(condition != "Normal"),
                    "condition": {
                        "load_nm": int(load),
                        "provider_diagnosis": condition,
                        "recording": path.name,
                        "position": position,
                        "sample_start": start,
                        "sample_stop": start + width,
                        "window_seconds": width * increment,
                        "sampling_hz": 1 / increment,
                        "unit_metadata": unit_metadata,
                    },
                    "features": signal_features(matrix[start : start + width, index]),
                    "unit": None,
                }
            )
    return rows, {
        "path": str(path),
        "variables": variables,
        "samples": len(matrix),
        "sampling_hz": 1 / increment,
        "duration_seconds": (len(matrix) - 1) * increment,
        "unit_metadata": unit_metadata,
        "native_values": (
            "MKS export with g display label/factor; no absolute-scale conversion assumed"
        ),
        "windows_channels": len(rows),
        "analysis_unit": "nonoverlapping five-second channel window; not independent equipment",
    }


def kaist_thermal(path: Path) -> dict:
    from nptdms import TdmsFile

    with TdmsFile.open(path) as recording:
        channels = []
        for group in recording.groups():
            for channel in group.channels():
                values = channel[:]
                channels.append(
                    {
                        "name": channel.name,
                        "samples": len(values),
                        "unit_as_stored": channel.properties.get("unit_string"),
                        "channel_type": channel.properties.get("DAC~Channel~Type"),
                        "increment_seconds": channel.properties.get("wf_increment"),
                        "start_as_stored": str(channel.properties.get("wf_start_time")),
                        "status": "missing" if len(values) == 0 else "observed",
                        "features": None if len(values) == 0 else signal_features(values),
                    }
                )
    if len(channels) != 5:
        raise DataValidationError("KAIST TDMS expected two temperatures and three currents.")
    return {
        "path": str(path),
        "channels": channels,
        "pairing": "same load/diagnosis is not proof of simultaneous thermal/vibration recording",
    }


def audit_samples(source_id: str, revision: str = "v1", root: Path = Path(".")) -> dict:
    if source_id not in {"kaist", "ult_freezers"}:
        raise DataValidationError("Only the two bounded sample sources are accepted.")
    source = next(
        row
        for row in json.loads((root / "config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        if row["source_id"] == source_id
    )
    folder = root / "data/public/raw" / source_id / source["source_version"] / "sample"
    engine = create_engine_for_url(Settings.from_env().database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    run_id = source_id + "-audit-" + now.strftime("%Y%m%dT%H%M%S%f")
    report = {
        "run_id": run_id,
        "source_id": source_id,
        "external_data_read": False,
        "representative_subset": True,
    }
    try:
        repository = ResearchRepository(engine)
        table = repository.tables["study_artifacts"]
        from sqlalchemy import select

        with engine.connect() as connection:
            artifacts = [
                dict(row)
                for row in connection.execute(
                    select(table).where(
                        table.c.source_id == source_id, table.c.artifact_kind == "raw"
                    )
                ).mappings()
                if "sample" in Path(row["relative_path"]).parts
            ]
        if not artifacts:
            raise DataValidationError("Registered source samples are required.")
        for item in artifacts:
            if (
                hashlib.sha256(Path(item["relative_path"]).read_bytes()).hexdigest()
                != item["content_sha256"]
            ):
                raise DataValidationError("Sample checksum differs from registered acquisition.")
        roots = [
            {
                "node_id": item["artifact_id"],
                "data_origin": "public_measured",
                "source_id": source_id,
                "source_version": source["source_version"],
                "parent_ids": [],
                "content_sha256": item["content_sha256"],
            }
            for item in artifacts
        ]
        runs = repository.tables["study_runs"]
        with engine.connect() as connection:
            previous = list(
                connection.execute(
                    select(runs).where(
                        runs.c.stage == "sample_canonical_audit", runs.c.status == "completed"
                    )
                ).mappings()
            )
        for row in previous:
            prior_roots = row["input_manifest_json"].get("provenance_nodes", [])
            if not prior_roots or prior_roots[0].get("source_id") != source_id:
                continue
            if row["configuration_json"].get("revision", "v1") == revision:
                if sorted(r["content_sha256"] for r in prior_roots) != sorted(
                    r["content_sha256"] for r in roots
                ):
                    raise DataValidationError(
                        "Sample inputs changed; a new semantic revision is required."
                    )
                prior_report = root / "reports/research" / row["run_id"] / "audit.json"
                if not prior_report.exists():
                    raise DataValidationError("Completed sample audit report is unavailable.")
                return json.loads(prior_report.read_text(encoding="utf-8"))
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "sample_canonical_audit",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {"subset": True, "revision": revision},
                        "input_manifest_json": {"provenance_nodes": roots},
                        "code_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    }
                ]
            },
            scope="public",
        )
        records = []
        if source_id == "kaist":
            report["vibration"] = []
            for path in sorted(folder.rglob("*.mat")):
                rows, audit = kaist_vibration(path)
                records.extend(rows)
                report["vibration"].append(audit)
            report["thermal_electrical"] = [
                kaist_thermal(path) for path in sorted(folder.rglob("*.tdms"))
            ]
            report["declared_empty_tdms_channels"] = sum(
                channel["status"] == "missing"
                for file in report["thermal_electrical"]
                for channel in file["channels"]
            )
            for record in records:
                record["condition"]["raw_tdms_empty_channels_total"] = report[
                    "declared_empty_tdms_channels"
                ]
            if len(report["vibration"]) != 4 or len(report["thermal_electrical"]) != 4:
                raise DataValidationError(
                    "The four selected recordings per modality must be complete."
                )
            report["eligibility"] = (
                "conditional research only: bearing test bench; "
                "no refrigeration equivalence assumed"
            )
        else:
            summary = fault_summary(folder / "data/dataset/fault_summary_R1.xlsx")
            report["fault_events"] = len(summary)
            report["fault_categories"] = summary.iloc[:, 3].value_counts().to_dict()
            report["compressor_models"] = (
                pd.read_csv(folder / "data/raw_data/other_data/freezers_model_data.csv")
                .fillna("")
                .to_dict(orient="records")
            )
            report["logs"] = []
            for path in sorted(folder.rglob("*.dat")):
                frame, audit = ult_log(path)
                device = path.parts[-3]
                report["logs"].append({"path": str(path), "freezer_id": device, **audit})
                for row in frame.to_dict(orient="records"):
                    records.append(
                        {
                            "original_id": f"{device}:{path.name}:{row['local_time'].isoformat()}",
                            "group": f"ult:freezer:{device}",
                            "target": None,
                            "condition": {
                                "freezer_id": device,
                                "local_timestamp": row["local_time"].isoformat(),
                                "timezone": "unknown",
                                "reference": "unassigned: service request date is not fault onset",
                            },
                            "features": {name: float(row[name]) for name in audit["channels"]},
                            "unit": "degC",
                        }
                    )
            report["events"] = [
                {**row, "registered_date": row["registered_date"].isoformat()}
                for row in summary.to_dict(orient="records")
            ]
            report["eligibility"] = (
                "thermal research; temporal fault-onset labels indeterminate; no vibration"
            )
        observations, labels, values = [], [], []
        for record in records:
            obs_id = (
                source_id
                + ":"
                + source["source_version"]
                + ":"
                + hashlib.sha256(record["original_id"].encode()).hexdigest()[:32]
            )
            observations.append(
                {
                    "observation_id": obs_id,
                    "source_id": source_id,
                    "source_version": source["source_version"],
                    "original_id": record["original_id"],
                    "analysis_unit": "channel_window" if source_id == "kaist" else "thermal_sample",
                    "dependency_group_id": record["group"],
                    "equipment_id": record["condition"].get("freezer_id"),
                    "quality_status": "valid",
                    "condition_json": record["condition"],
                    "provenance_json": {
                        "provenance_nodes": roots
                        + [
                            {
                                "node_id": obs_id,
                                "data_origin": "derived",
                                "parent_ids": [r["node_id"] for r in roots],
                            }
                        ]
                    },
                    "created_at": now,
                }
            )
            labels.append(
                {
                    "observation_id": obs_id,
                    "label_version": "sample-reference-v1",
                    "original_label": record["condition"].get("provider_diagnosis"),
                    "target_label": record["target"],
                    "label_status": "reference"
                    if record["target"] is not None
                    else "indeterminate",
                    "method": "provider recording diagnosis"
                    if source_id == "kaist"
                    else "no minute-level fault onset reference",
                    "evidence_json": record["condition"],
                    "recorded_at": now,
                }
            )
            for name, value in record["features"].items():
                values.append(
                    {
                        "observation_id": obs_id,
                        "feature_contract_version": source_id + "-sample-" + revision,
                        "feature_name": name,
                        "numeric_value": value,
                        "unit": "1"
                        if name in {"skewness", "kurtosis", "range_over_std"}
                        else "V"
                        if name == "Mains Voltage"
                        else record["unit"],
                        "value_status": "missing" if value is None else "derived",
                        "definition_json": {
                            "position": record["condition"].get("position", name),
                            "ddof_std": 0,
                            "skew_kurtosis_bias": False,
                            "kurtosis_fisher": True,
                            "calibration": "provider; no additional calibration fitted",
                        },
                        "run_id": run_id,
                    }
                )
        repository.persist(
            {"study_observations": observations, "study_labels": labels}, scope="public"
        )
        for offset in range(0, len(values), 2500):
            repository.persist(
                {"study_feature_values": values[offset : offset + 2500]}, scope="public"
            )
        report.update(
            observations=len(observations),
            feature_values=len(values),
            target_counts={str(k): sum(r["target"] == k for r in records) for k in [0, 1, None]},
        )
        output = root / "reports/research" / run_id / "audit.json"
        output.parent.mkdir(parents=True, exist_ok=False)
        file = save_immutable(
            output, json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False).encode()
        )
        repository.persist(
            {"study_artifacts": [artifact_row(source, file, "report", {"run_id": run_id}, now)]},
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        return report
    except Exception as error:
        if "repository" in locals():
            try:
                repository.finish_run(run_id, "failed", error_message=type(error).__name__)
            except DataValidationError:
                pass
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    import sys

    result = audit_samples(sys.argv[1])
    print(json.dumps({key: result[key] for key in ["run_id", "observations", "feature_values"]}))
