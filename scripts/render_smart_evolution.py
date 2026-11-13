"""Render correction only; preserve the original experiment and all model outputs."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import matplotlib
import pandas as pd
from sqlalchemy import select

from compressor_anomaly_detection_ml.config import Settings
from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.datasets import save_immutable
from compressor_anomaly_detection_ml.public_acquisition import artifact_row

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

dataset_version, parent_run = sys.argv[1:3]
folder = Path("reports/research") / dataset_version / "figures-v2"
if folder.exists():
    raise SystemExit("Render revision exists; original artifacts are never overwritten.")
engine = create_engine_for_url(Settings.from_env().database_url)
try:
    repository = ResearchRepository(engine)
    observations = repository.tables["study_observations"]
    values = repository.tables["study_feature_values"]
    members = repository.tables["study_dataset_members"]
    runs = repository.tables["study_runs"]
    with engine.connect() as connection:
        frame = pd.DataFrame(
            connection.execute(
                select(
                    observations.c.observation_id,
                    observations.c.started_at,
                    members.c.dependency_group_id,
                    values.c.numeric_value,
                )
                .join(members, observations.c.observation_id == members.c.observation_id)
                .join(values, values.c.observation_id == observations.c.observation_id)
                .join(runs, runs.c.run_id == values.c.run_id)
                .where(
                    observations.c.source_id == "smart_pdm",
                    members.c.dataset_version == dataset_version,
                    members.c.partition_name == "train",
                    values.c.feature_name == "Vibration__standard_deviation",
                    runs.c.stage == "public_source_preparation",
                )
            ).mappings()
        )
    expected = pd.read_csv(Path("reports/research") / dataset_version / "partitions.csv")
    expected = expected.loc[
        (expected.source_id == "smart_pdm") & (expected.partition_name == "train")
    ]
    assert not frame.empty and not frame.observation_id.duplicated().any()
    assert set(frame.observation_id) == set(expected.observation_id)
    fig, axis = plt.subplots(figsize=(10, 4))
    for group, subset in frame.groupby("dependency_group_id"):
        axis.plot(subset.started_at, subset.numeric_value, ".", markersize=2, label=group)
    axis.set_ylabel("Vibration standard deviation\n[native unit unconfirmed]")
    axis.set_xlabel("Capture time [UTC]")
    axis.set_title("SMART-PDM: public development groups")
    axis.legend(fontsize=6)
    fig.autofmt_xdate()
    fig.tight_layout()
    image = BytesIO()
    fig.savefig(image, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    folder.mkdir(parents=True)
    file = save_immutable(folder / "smart_pdm-evolution.png", image.getvalue())
    now = datetime.now(UTC).replace(tzinfo=None)
    run_id = dataset_version + "-render-v2"
    metadata = {
        "parent_run_id": parent_run,
        "dataset_version": dataset_version,
        "scientific_values_changed": False,
        "reason": "shorten clipped y-axis label; show UTC only on SMART time axis",
    }
    source = next(
        row
        for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        if row["source_id"] == "smart_pdm"
    )
    repository.persist(
        {
            "study_runs": [
                {
                    "run_id": run_id,
                    "stage": "public_render_correction",
                    "data_scope": "public",
                    "status": "running",
                    "started_at": now,
                    "configuration_json": metadata,
                    "input_manifest_json": {
                        "dataset_version": dataset_version,
                        "parent_run_id": parent_run,
                    },
                    "code_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                }
            ],
            "study_artifacts": [artifact_row(source, file, "report", metadata, now)],
        },
        scope="public",
    )
    repository.finish_run(run_id, "completed")
    save_immutable(folder / "render.json", json.dumps({**metadata, **file}, indent=2).encode())
    print(json.dumps(file))
finally:
    engine.dispose()
