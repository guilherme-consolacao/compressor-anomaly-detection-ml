"""Verified supplementary signals for the second public transfer cycle."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import welch
from sqlalchemy import select

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import save_immutable
from .domain import DataValidationError
from .public_acquisition import artifact_row, source_row
from .public_study import document_bytes

TRI_COLUMNS = [
    "Date",
    "Test code",
    "Fault intensity",
    "COP",
    "Compressor_power_consumption",
    "Condenser_heat_duty",
    "Subcooling",
    "Evaporator_saturation_temperature",
    "Condenser_saturation_temperature",
    "Compressor_outlet_temperature",
    "Liquid_line_refrigerant_temperature",
    "Refrigerant_Mass_flow",
    "Compressor_speed",
]
TRI_UNITS = [None, None, None, "-", "kW", "kW", "ºC", "ºC", "ºC", "ºC", "ºC", "g/s", "rps"]
TRI_SHEETS = [kind + load for kind in ("NF", "EF", "CVL", "LL", "OC") for load in ("10", "12")]


def tri_hp_main(path: Path) -> tuple[pd.DataFrame, dict]:
    """Keep the main logger separate from the asynchronous superheat table."""
    sheets = pd.read_excel(path, sheet_name=None)
    if set(sheets) != {"Information", *TRI_SHEETS}:
        raise DataValidationError("TRI-HP workbook sheets differ from the inspected contract.")
    frames, audit = [], {}
    for name in TRI_SHEETS:
        raw = sheets[name]
        if list(raw.columns[:13]) != TRI_COLUMNS:
            raise DataValidationError("TRI-HP main logger header changed.")
        units = [None if pd.isna(value) else str(value) for value in raw.iloc[0, :13]]
        if units != TRI_UNITS:
            raise DataValidationError("TRI-HP physical units changed.")
        # The second Date column belongs to another logger; row numbers are not pairs.
        main = raw.iloc[1:, :13].copy()
        padding = main["Date"].isna()
        if main.loc[padding].notna().any().any():
            raise DataValidationError("Missing main timestamp with nonempty physical readings.")
        main = main.loc[~padding].copy()
        main["Date"] = pd.to_datetime(main["Date"], errors="raise")
        if (
            main.empty
            or main["Date"].duplicated().any()
            or not main["Date"].is_monotonic_increasing
        ):
            raise DataValidationError("Empty, duplicated or unordered TRI-HP main timestamps.")
        pattern = name if name.startswith("NF") else re.escape(name) + r"\.[1-9][0-9]*"
        if not main["Test code"].astype(str).str.fullmatch(pattern).all():
            raise DataValidationError("Fault code does not match the documented experiment.")
        numeric = main[TRI_COLUMNS[3:]].apply(pd.to_numeric, errors="raise").astype(float)
        if not np.isfinite(numeric.to_numpy()).all():
            raise DataValidationError("TRI-HP contains missing or nonfinite physical values.")
        main[TRI_COLUMNS[3:]] = numeric
        main["sheet"] = name
        main["target_label"] = 0 if name.startswith("NF") else 1
        main["fault_type"] = re.sub(r"[0-9]+$", "", name)
        main["load_kw"] = int(re.search(r"[0-9]+$", name).group())
        main["group_id"] = "tri-hp-session:" + main["Date"].dt.strftime("%Y-%m-%d")
        main["provider_row"] = main.index + 2
        audit[name] = {
            "main_rows": len(main),
            "padding_rows_excluded": int(padding.sum()),
            "test_codes": main["Test code"].value_counts().to_dict(),
            "timestamp_step_seconds": main["Date"]
            .diff()
            .dt.total_seconds()
            .value_counts()
            .to_dict(),
            "fault_intensity_unique": int(main["Fault intensity"].nunique()),
            "asynchronous_superheat_joined": False,
        }
        frames.append(main)
    frame = pd.concat(frames, ignore_index=True)
    return frame, {
        "sheets": audit,
        "main_rows": len(frame),
        "groups": int(frame.group_id.nunique()),
        "normal_rows": int((frame.target_label == 0).sum()),
        "fault_rows": int((frame.target_label == 1).sum()),
        "test_conditions": int(frame["Test code"].nunique()),
        "timezone": "provider local/unspecified; not converted to UTC",
        "excluded_predictors": [
            "Date",
            "Test code",
            "Fault intensity",
            "sheet",
            "fault_type",
            "load_kw",
            "group_id",
            "provider_row",
        ],
        "label_scope": "controlled heat-pump fault, not every fault is a compressor defect",
        "sample_rows_are_not_independent_experiments": True,
    }


def spectral_shape(frequency, density, low=10.0, high=1000.0) -> dict:
    """Dimensionless band shape; invariance is conditional on linear sensor gain."""
    frequency, density = np.asarray(frequency, float), np.asarray(density, float)
    if (
        frequency.ndim != 1
        or density.shape != frequency.shape
        or len(frequency) < 4
        or not np.isfinite(frequency).all()
        or not np.isfinite(density).all()
        or (np.diff(frequency) <= 0).any()
        or (density < 0).any()
        or frequency[0] > low
        or frequency[-1] < high
    ):
        raise DataValidationError("A finite increasing PSD covering the common band is required.")
    mask = (frequency >= low) & (frequency <= high)
    f, p = frequency[mask], density[mask]
    mass = p * np.gradient(f)
    total = float(mass.sum())
    if len(f) < 4 or total <= 0:
        raise DataValidationError("The common frequency band has no usable energy.")
    probability = mass / total
    centroid = float(np.sum(f * probability))
    # Fixed bins prevent FFT resolution alone from changing the entropy scale.
    entropy_mass, _ = np.histogram(f, bins=np.linspace(low, high, 65), weights=probability)
    positive = entropy_mass > 0
    result = {
        "spectral_centroid_relative": (centroid - low) / (high - low),
        "spectral_spread_relative": float(
            np.sqrt(np.sum((f - centroid) ** 2 * probability)) / (high - low)
        ),
        "spectral_entropy": float(
            -np.sum(entropy_mass[positive] * np.log(entropy_mass[positive])) / np.log(64)
        ),
        "spectral_peak_relative": float((f[np.argmax(p)] - low) / (high - low)),
    }
    for begin, end in ((10, 100), (100, 300), (300, 600), (600, 1000)):
        selected = (f >= begin) & ((f < end) if end < high else (f <= end))
        result[f"band_fraction_{begin}_{end}"] = float(probability[selected].sum())
    return result


def smart_wave(path: Path) -> tuple[dict, dict]:
    frame = pd.read_csv(path)
    if list(frame.columns) != ["UnixTimestamp (us)", "Current", "Vibration"]:
        raise DataValidationError("SMART fast signal header changed.")
    data = frame.to_numpy(dtype=float)
    if len(data) < 4096 or not np.isfinite(data).all():
        raise DataValidationError("Insufficient or nonfinite SMART fast samples.")
    delta = np.diff(data[:, 0])
    if not np.all((delta >= 487) & (delta <= 490)):
        raise DataValidationError("SMART fast timestamps do not support the declared 2048 Hz rate.")
    result = {}
    for index, channel in ((1, "current"), (2, "vibration")):
        f, p = welch(data[:, index], fs=2048, nperseg=2048, detrend="constant")
        result.update({channel + "_" + key: value for key, value in spectral_shape(f, p).items()})
    return result, {
        "samples": len(frame),
        "sampling_hz": 2048,
        "duration_seconds": float((data[-1, 0] - data[0, 0]) / 1e6 + 1 / 2048),
        "timestamp_is_relative": True,
        "whole_cycle_waveform": False,
        "vibration_physical_unit": "unconfirmed",
        "feature_band_hz": [10, 1000],
    }


def prepare_tri_hp(revision="v1") -> dict:
    source = next(
        row
        for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        if row["source_id"] == "tri_hp_faults"
    )
    folder = Path("data/public/raw/tri_hp_faults/5155136.v1")
    path = folder / "H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
    content = path.read_bytes()
    if (
        hashlib.md5(content, usedforsecurity=False).hexdigest()
        != "ffc895d65a88550793ad6a210ae0a7fd"
    ):
        raise DataValidationError("TRI-HP workbook differs from the provider checksum.")
    frame, quality = tri_hp_main(path)
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    run_id = (
        "tri-hp-prepare-"
        + hashlib.sha256((digest + code_hash + revision).encode()).hexdigest()[:20]
    )
    output = Path("reports/research") / run_id
    now = datetime.now(UTC).replace(tzinfo=None)
    engine = create_engine_for_url(Settings.from_env().database_url)
    started = False
    try:
        repository = ResearchRepository(engine)
        with engine.connect() as connection:
            previous = connection.execute(
                select(repository.tables["study_runs"].c.status).where(
                    repository.tables["study_runs"].c.run_id == run_id
                )
            ).scalar_one_or_none()
        if previous:
            if previous == "completed":
                return json.loads((output / "import.json").read_text(encoding="utf-8"))
            raise DataValidationError("Inspect the incomplete TRI-HP preparation before retrying.")
        artifact = artifact_row(
            source,
            {
                "relative_path": path.as_posix(),
                "content_sha256": digest,
                "byte_size": path.stat().st_size,
            },
            "raw",
            {"provider_md5_verified": True, "hypotheses": ["H03", "H05"]},
            now,
        )
        root = {
            "node_id": artifact["artifact_id"],
            "source_id": source["source_id"],
            "source_version": source["source_version"],
            "data_origin": "public_measured",
            "parent_ids": [],
            "content_sha256": digest,
        }
        repository.persist(
            {
                "study_sources": [source_row(source, now)],
                "study_artifacts": [artifact],
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_transfer_input",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "revision": revision,
                            "analysis_unit": "controlled logger sample",
                            "labels_from": "provider test code",
                            "UTC_conversion": False,
                        },
                        "input_manifest_json": {"provenance_nodes": [root]},
                        "code_fingerprint": code_hash,
                    }
                ],
            },
            scope="public",
        )
        started = True
        observations, labels, values = [], [], []
        for row in frame.to_dict("records"):
            original = row["sheet"] + ":" + str(row["provider_row"])
            obs_id = "tri_hp_faults:5155136.v1:" + original
            observations.append(
                {
                    "observation_id": obs_id,
                    "source_id": source["source_id"],
                    "source_version": source["source_version"],
                    "original_id": original,
                    "analysis_unit": "controlled_logger_sample",
                    "dependency_group_id": row["group_id"],
                    "equipment_id": "tri-hp:single-R290-scroll-test-bench",
                    "started_at": None,
                    "ended_at": None,
                    "quality_status": "valid",
                    "condition_json": {
                        "test_code": row["Test code"],
                        "sheet": row["sheet"],
                        "fault_type": row["fault_type"],
                        "load_kw": row["load_kw"],
                        "provider_local_time": row["Date"].isoformat(),
                        "provider_row": row["provider_row"],
                        "fault_intensity_original": float(row["Fault intensity"]),
                    },
                    "provenance_json": {
                        "provenance_nodes": [
                            root,
                            {
                                "node_id": obs_id,
                                "data_origin": "derived",
                                "parent_ids": [root["node_id"]],
                            },
                        ]
                    },
                    "created_at": now,
                }
            )
            labels.append(
                {
                    "observation_id": obs_id,
                    "label_version": "tri-hp-provider-code-v1",
                    "original_label": row["Test code"],
                    "target_label": int(row["target_label"]),
                    "label_status": "reference",
                    "method": "documented physically imposed fault or no-fault test code",
                    "confidence": None,
                    "evidence_artifact_id": artifact["artifact_id"],
                    "evidence_json": {
                        "scope": quality["label_scope"],
                        "not_independent_per_sample": True,
                    },
                    "recorded_at": now,
                }
            )
            for name, unit in zip(TRI_COLUMNS[3:], TRI_UNITS[3:], strict=True):
                values.append(
                    {
                        "observation_id": obs_id,
                        "feature_contract_version": "tri-hp-main-v1",
                        "feature_name": name,
                        "numeric_value": float(row[name]),
                        "unit": "degC" if unit == "ºC" else unit,
                        "value_status": "observed",
                        "definition_json": {
                            "provider_feature_name": name,
                            "logger": "main",
                            "superheating_row_join": False,
                        },
                        "run_id": run_id,
                    }
                )
        for offset in range(0, len(observations), 500):
            repository.persist(
                {
                    "study_observations": observations[offset : offset + 500],
                    "study_labels": labels[offset : offset + 500],
                },
                scope="public",
            )
        for offset in range(0, len(values), 2500):
            repository.persist(
                {"study_feature_values": values[offset : offset + 2500]}, scope="public"
            )
        output.mkdir(parents=True, exist_ok=False)
        report = {
            "run_id": run_id,
            "source_id": source["source_id"],
            "observations": len(observations),
            "feature_values": len(values),
            "quality": quality,
            "input_sha256": digest,
            "external_data_read": False,
        }
        file = save_immutable(output / "import.json", document_bytes(report))
        repository.persist(
            {"study_artifacts": [artifact_row(source, file, "report", {"run_id": run_id}, now)]},
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        started = False
        return report
    except Exception as error:
        if started:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(json.dumps(prepare_tri_hp(), indent=2, ensure_ascii=False))
