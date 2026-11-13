"""Supplementary descriptive audit of known public inputs, without model selection."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from compressor_anomaly_detection_ml.config import Settings
from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.datasets import save_immutable
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_study import document_bytes


def main():
    thermal_path = Path(
        "reports/research/bridge-round2-9154a7b7f7ac5737b9e7/shared-thermal-development.csv"
    )
    cycle_path = Path("reports/research/cycle-freeze-8af6bb44817d037a836c/training-inputs.csv")
    thermal = pd.read_csv(thermal_path)
    cycles = pd.read_csv(cycle_path)
    cycles = cycles[cycles.source_id.eq("smart_pdm")].copy()
    assert len(cycles) == 782 and int(cycles.target_label.sum()) == 13
    assert not thermal.observation_id.duplicated().any()
    contract = json.loads(Path("config/transfer-round7-temporal.json").read_text())
    files = [thermal_path, cycle_path]
    inputs = [
        {"path": p.as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files
    ]
    code = Path(__file__).read_bytes()
    digest = hashlib.sha256(code + document_bytes(inputs)).hexdigest()
    run_id = "transfer-description-" + digest[:20]
    now = datetime.now(UTC).replace(tzinfo=None)
    engine = create_engine_for_url(Settings.from_env().database_url)
    repository = ResearchRepository(engine)
    running = False
    try:
        with engine.connect() as connection:
            runs = repository.tables["study_runs"]
            previous = connection.execute(
                select(runs.c.status).where(runs.c.run_id == run_id)
            ).scalar_one_or_none()
        if previous:
            assert previous == "completed", "Inspect incomplete descriptive audit"
            print(json.dumps({"run_id": run_id, "status": "already_completed"}))
            return
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_descriptive_handoff",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "role": "known development description; frozen model unchanged",
                            "external_data_read": False,
                        },
                        "input_manifest_json": {"files": inputs},
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ]
            },
            scope="public",
        )
        running = True
        rows = []
        for source, frame in thermal.groupby("source_id"):
            groups = int(frame.group_id.nunique())
            for name in contract["auxiliary_features"]:
                values = frame[name]
                assert np.isfinite(values).all()
                for statistic, value in {
                    "minimum": values.min(),
                    "q05": values.quantile(0.05),
                    "q25": values.quantile(0.25),
                    "median": values.median(),
                    "q75": values.quantile(0.75),
                    "q95": values.quantile(0.95),
                    "maximum": values.max(),
                    "std": values.std(),
                }.items():
                    rows.append(
                        (source, "all", statistic, name, None, float(value), len(frame), groups)
                    )
            names = contract["auxiliary_features"]
            for method in ("pearson", "spearman"):
                correlation = frame[names].corr(method=method)
                for i, first in enumerate(names):
                    for second in names[i + 1 :]:
                        value = correlation.loc[first, second]
                        rows.append(
                            (
                                source,
                                "all",
                                method,
                                first,
                                second,
                                float(value) if np.isfinite(value) else None,
                                len(frame),
                                groups,
                            )
                        )
        for label, frame in cycles.groupby("target_label"):
            values = frame.duration_relative_history
            for statistic, value in {
                "minimum": values.min(),
                "q05": values.quantile(0.05),
                "median": values.median(),
                "q95": values.quantile(0.95),
                "maximum": values.max(),
                "std": values.std(),
            }.items():
                rows.append(
                    (
                        "smart_pdm",
                        str(int(label)),
                        statistic,
                        "duration_relative_history",
                        None,
                        float(value),
                        len(frame),
                        int(frame.dependency_group_id.nunique()),
                    )
                )
        registry = {
            r["source_id"]: r
            for r in json.loads(Path("config/dataset-sources.json").read_text())["sources"]
        }
        stats = [
            {
                "run_id": run_id,
                "statistic_key": ":".join(str(v) for v in row[:5]),
                "source_id": row[0],
                "source_version": registry[row[0]]["source_version"],
                "statistic_name": row[2],
                "feature_name": row[3],
                "other_feature_name": row[4],
                "numeric_value": row[5],
                "sample_count": row[6],
                "group_count": row[7],
                "dimensions_json": {
                    "reference_class": row[1],
                    "paired_within_source": True,
                    "role": "known input audit; correlated rows are not independent experiments",
                },
            }
            for row in rows
        ]
        output = Path("reports/research") / run_id
        table = pd.DataFrame(
            rows,
            columns=[
                "source",
                "reference_class",
                "statistic",
                "feature",
                "other_feature",
                "value",
                "n",
                "groups",
            ],
        )
        file = save_immutable(output / "statistics.csv", table.to_csv(index=False).encode())
        repository.persist(
            {
                "study_statistics": stats,
                "study_artifacts": [
                    artifact_row(registry["smart_pdm"], file, "report", {"run_id": run_id}, now)
                ],
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        running = False
        print(json.dumps({"run_id": run_id, "statistics": len(stats), "external_data_read": False}))
    except Exception as error:
        if running:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
