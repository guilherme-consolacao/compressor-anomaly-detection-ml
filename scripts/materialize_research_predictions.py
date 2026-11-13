"""Expose canonical experimental scores as relational values for downstream charts."""

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
from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_study import document_bytes

RUNS = [
    "anchor-round2-e66c9eee5ccc1f261841",
    "bridge-round2-9154a7b7f7ac5737b9e7",
    "spectral-round2-bf2cffa52330d761890f",
    "spectral-round3-c61d2d3fdf5e9f3a0d50",
    "spectral-round4-proxy-bb432419f779fc881bbe",
    "auxiliary-round5-b2db3eab72fa67abc96f",
    "novelty-round6-a0cdfdba68ec937811c1",
    "temporal-round7-c2f700026e1cc1c77edd",
    "temporal-round8-9492770bdefcfd8c0fcd",
]


def canonical_scores(frame):
    frame = frame.copy()
    if "model_id" in frame:
        frame = frame[frame.model_id.str.endswith(":depth=5:leaf=3")].copy()
    else:
        frame = frame[frame["mode"].eq("raw_fixed")].copy()
        frame["model_id"] = (
            frame.variant + ":shuffle=" + frame.shuffle_seed.astype(str) + ":" + frame["mode"]
        )
    if (
        frame.empty
        or frame.duplicated(["model_id", "observation_id"]).any()
        or not np.isfinite(frame.score).all()
        or not frame.score.between(0, 1).all()
    ):
        raise DataValidationError(
            "Research scores require unique identities and finite [0,1] scores."
        )
    return frame


def main():
    now = datetime.now(UTC).replace(tzinfo=None)
    engine = create_engine_for_url(Settings.from_env().database_url)
    repository = ResearchRepository(engine)
    try:
        for parent in RUNS:
            path = Path("reports/research") / parent / "predictions.csv"
            content_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            runs = repository.tables["study_runs"]
            artifacts = repository.tables["study_artifacts"]
            with engine.connect() as connection:
                status = connection.execute(
                    select(runs.c.status).where(runs.c.run_id == parent)
                ).scalar_one()
                hashes = (
                    connection.execute(
                        select(artifacts.c.content_sha256).where(
                            artifacts.c.relative_path == path.as_posix()
                        )
                    )
                    .scalars()
                    .all()
                )
            if status != "completed" or content_sha not in hashes:
                raise DataValidationError(
                    "Only completed registered public predictions may be exposed."
                )
            code = Path(__file__).read_bytes()
            digest = hashlib.sha256(code + parent.encode() + content_sha.encode()).hexdigest()
            run_id = "score-materialize-" + digest[:20]
            contract = "research-score-" + digest[:20]
            with engine.connect() as connection:
                previous = connection.execute(
                    select(runs.c.status).where(runs.c.run_id == run_id)
                ).scalar_one_or_none()
            if previous:
                if previous != "completed":
                    raise DataValidationError("Inspect incomplete score materialization first.")
                print(json.dumps({"run_id": run_id, "status": "already_completed"}), flush=True)
                continue
            frame = canonical_scores(pd.read_csv(path))
            repository.persist(
                {
                    "study_runs": [
                        {
                            "run_id": run_id,
                            "stage": "public_research_scores",
                            "data_scope": "public",
                            "status": "running",
                            "started_at": now,
                            "configuration_json": {
                                "parent": parent,
                                "selection": "depth5 leaf3; round8 raw_fixed, all controls",
                                "output_role": "diagnostic output; never a measured training input",
                            },
                            "input_manifest_json": {"path": path.as_posix(), "sha256": content_sha},
                            "code_fingerprint": hashlib.sha256(code).hexdigest(),
                        }
                    ]
                },
                scope="public",
            )
            try:
                for model_id, selected in frame.groupby("model_id", sort=True):
                    feature = (
                        "uncalibrated_reference_score_"
                        + hashlib.sha256(model_id.encode()).hexdigest()[:16]
                    )
                    definition = {
                        "model_id": model_id,
                        "parent_run": parent,
                        "threshold": 0.5,
                        "probability_status": "uncalibrated reference score",
                        "evaluation": "known public development; not external validation",
                        "not_a_training_input": True,
                    }
                    rows = [
                        {
                            "observation_id": row.observation_id,
                            "feature_contract_version": contract,
                            "feature_name": feature,
                            "numeric_value": float(row.score),
                            "unit": "1",
                            "value_status": "derived",
                            "definition_json": definition,
                            "run_id": run_id,
                        }
                        for row in selected.itertuples()
                    ]
                    repository.persist({"study_feature_values": rows}, scope="public")
                output = Path("reports/research") / run_id / "summary.json"
                file = save_immutable(
                    output,
                    document_bytes(
                        {
                            "run_id": run_id,
                            "parent_run": parent,
                            "scores": len(frame),
                            "observations": int(frame.observation_id.nunique()),
                            "comparisons": int(frame.model_id.nunique()),
                            "feature_contract_version": contract,
                        }
                    ),
                )
                source = next(
                    row
                    for row in json.loads(Path("config/dataset-sources.json").read_text())[
                        "sources"
                    ]
                    if row["source_id"] == "smart_pdm"
                )
                repository.persist(
                    {
                        "study_artifacts": [
                            artifact_row(source, file, "report", {"run_id": run_id}, now)
                        ]
                    },
                    scope="public",
                )
                repository.finish_run(run_id, "completed")
                print(json.dumps({"run_id": run_id, "scores": len(frame)}), flush=True)
            except Exception as error:
                repository.finish_run(run_id, "failed", error_message=type(error).__name__)
                raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
