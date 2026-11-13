"""Measured public bridges and thermal reference ablation for the revised SDD."""

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
from compressor_anomaly_detection_ml.nist_refrigeration import nist_table
from compressor_anomaly_detection_ml.public_acquisition import artifact_row
from compressor_anomaly_detection_ml.public_study import document_bytes
from compressor_anomaly_detection_ml.transfer_analysis import paired_bridge, refrigeration_ablation
from compressor_anomaly_detection_ml.transfer_bridges import (
    file_manifest,
    refrigeration_common,
    rwth_spectral_table,
)
from compressor_anomaly_detection_ml.transfer_inputs import tri_hp_main


def main():
    protocol_path = Path("config/transfer-round2-bridges.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["external_data_allowed"] or protocol["public_test_opened"]:
        raise DataValidationError("This stage excludes external and reserved test data.")
    rwth_root = Path("data/public/raw/rwth_r290/22097811")
    tri_path = Path(
        "data/public/raw/tri_hp_faults/5155136.v1/H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
    )
    nist_path = Path("data/public/raw/nist_hvac/nist-fdd-14-16seer.xlsx")
    inputs = file_manifest(
        [
            *list((rwth_root / "psd-audit/vibration_psd").glob("**/*.csv")),
            rwth_root / "thermodynamic/thermodynamic_averaged_with_uncertainty.csv",
            rwth_root / "vibration_rms/rms_by_charge.csv",
            tri_path,
            nist_path,
        ]
    )
    code = b"".join(
        Path(name).read_bytes()
        for name in [
            __file__,
            "src/compressor_anomaly_detection_ml/transfer_analysis.py",
            "src/compressor_anomaly_detection_ml/transfer_bridges.py",
            "src/compressor_anomaly_detection_ml/transfer_inputs.py",
            "src/compressor_anomaly_detection_ml/nist_refrigeration.py",
        ]
    )
    digest = hashlib.sha256(code + protocol_path.read_bytes() + document_bytes(inputs)).hexdigest()
    run_id = "bridge-round2-" + digest[:20]
    output = Path("reports/research") / run_id
    engine = create_engine_for_url(Settings.from_env().database_url)
    started = False
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        repository = ResearchRepository(engine)
        with engine.connect() as connection:
            previous = connection.execute(
                select(repository.tables["study_runs"].c.status).where(
                    repository.tables["study_runs"].c.run_id == run_id
                )
            ).scalar_one_or_none()
        if previous:
            if previous != "completed":
                raise DataValidationError("Inspect incomplete bridge analysis before retrying.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        registry = json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
            "sources"
        ]
        sources = {row["source_id"]: row for row in registry}
        input_artifacts = []
        for file in inputs:
            source_id = (
                "rwth_r290"
                if "/rwth_r290/" in file["relative_path"]
                else "tri_hp_faults"
                if "/tri_hp_faults/" in file["relative_path"]
                else "nist_hvac"
            )
            input_artifacts.append(
                artifact_row(
                    sources[source_id],
                    file,
                    "raw",
                    {
                        "hypotheses": ["H03", "H04", "H05"],
                        "full_archive_checksum_verified": False
                        if source_id == "rwth_r290"
                        else None,
                        "range_members_crc_verified": source_id == "rwth_r290",
                    },
                    now,
                )
            )
        with engine.connect() as connection:
            table = repository.tables["study_artifacts"]
            registered = {
                row["artifact_id"]: dict(row)
                for row in connection.execute(
                    select(table).where(
                        table.c.artifact_id.in_([row["artifact_id"] for row in input_artifacts])
                    )
                ).mappings()
            }
        # Reuse the immutable acquisition record instead of rewriting its audit metadata.
        input_artifacts = [registered.get(row["artifact_id"], row) for row in input_artifacts]
        repository.persist(
            {
                "study_artifacts": input_artifacts,
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_measured_bridge",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {
                            "artifacts": [row["artifact_id"] for row in input_artifacts],
                            "external_data_read": False,
                        },
                        "code_fingerprint": hashlib.sha256(code).hexdigest(),
                    }
                ],
            },
            scope="public",
        )
        started = True
        output.mkdir(parents=True, exist_ok=False)
        save_immutable(output / "protocol.json", protocol_path.read_bytes())
        rwth, audit = rwth_spectral_table(rwth_root)
        rwth, _ = refrigeration_common(rwth, "rwth_r290")
        tri, tri_audit = tri_hp_main(tri_path)
        tri, _ = refrigeration_common(tri, "tri_hp_faults")
        tri["observation_id"] = (
            "tri_hp_faults:5155136.v1:" + tri.sheet + ":" + tri.provider_row.astype(str)
        )
        tri["experiment_id"] = tri["Test code"]
        nist, _, nist_audit = nist_table(nist_path)
        nist["experiment_id"] = nist.Filename
        tri["partition_name"] = np.where(
            tri.sheet.str.startswith("OC"),
            "test",
            np.where(tri.load_kw.eq(10), "train", "validation"),
        )
        nist["partition_name"] = np.where(
            nist.equipment_stratum.eq("14-SEER"),
            "train",
            np.where(nist.equipment_stratum.eq("16-SEER"), "validation", "discovery"),
        )
        members = pd.concat(
            [
                tri[["observation_id", "source_id", "group_id", "partition_name", "target_label"]],
                nist[["observation_id", "source_id", "group_id", "partition_name", "target_label"]],
            ],
            ignore_index=True,
        )
        save_immutable(
            output / "partitions.csv", members.to_csv(index=False, lineterminator="\n").encode()
        )
        for _source, group in members.groupby("source_id"):
            if group.groupby("group_id").partition_name.nunique().gt(1).any():
                raise DataValidationError("A new public source group crosses partitions.")
        # These reservations are written before any fit; OC values do not enter EDA or metrics.
        development = pd.concat(
            [tri[tri.partition_name.ne("test")], nist[nist.target_label.notna()]], ignore_index=True
        )
        features = protocol["shared_thermal_features"]
        development[
            ["observation_id", "source_id", "group_id", "partition_name", *features]
        ].to_csv(output / "shared-thermal-development.csv", index=False)
        fits = []
        for name, predictors in (
            ("measured_thermal_electrical", protocol["bridge_predictors"]),
            ("operating_regime_control", protocol["bridge_control"]),
            ("shared_thermal_only", features),
        ):
            result = paired_bridge(
                rwth, predictors, protocol["bridge_targets"], "measurement_id", name=name
            )
            fits.append(result)
            print(json.dumps({"bridge_completed": name}), flush=True)
        training = development[development.partition_name.eq("train")]
        validation = development[development.partition_name.eq("validation")]
        comparisons, predictions = refrigeration_ablation(training, validation, features)
        summary = {
            "run_id": run_id,
            "external_data_read": False,
            "reserved_smart_test_used": False,
            "tri_oc_test_used_for_analysis": False,
            "rwth": audit,
            "tri_hp": tri_audit,
            "nist": nist_audit,
            "bridge_validation": fits,
            "thermal_reference_comparisons": comparisons,
            "probability_status": (
                "uncalibrated reference-state scores, "
                "not validated local compressor failure probabilities"
            ),
            "local_release": False,
        }
        relations = {
            "run_id": run_id,
            "edges": [
                {
                    "from": "rwth thermal/electrical",
                    "to": "rwth triaxial vibration PSD",
                    "relation": "measured paired",
                    "joint_support": 195,
                    "groups": 9,
                    "validation": "leave one session out plus operating-regime control",
                    "report": "summary.json",
                },
                {
                    "from": "SMART scalar vibration",
                    "to": "RWTH three-axis spectral shape",
                    "relation": "conditional representation hypothesis",
                    "joint_support": 0,
                    "assumptions": [
                        "linear sensor gain",
                        "common frequency band",
                        "axis aggregation sensitivity",
                    ],
                    "labels_transferred": 0,
                },
                {
                    "from": "TRI-HP thermal reference",
                    "to": "RWTH thermal covariates",
                    "relation": "physically analogous measured quantities, different equipment",
                    "joint_support": 0,
                    "status": "requires transfer and support testing",
                },
                {
                    "from": "NIST thermal reference",
                    "to": "TRI-HP thermal reference",
                    "relation": "shared temperatures/mass flow with held-equipment comparison",
                    "power_excluded": "outdoor power is not compressor power",
                    "status": "comparison reported, no arbitrary row pairing",
                },
                {
                    "from": "ULT sump temperature",
                    "to": "refrigerant line temperatures",
                    "relation": "not direct physical equivalence",
                    "status": "do not relabel repair episodes or pair unrelated timestamps",
                },
                {
                    "from": "KAIST bearing faults",
                    "to": "refrigerator compressor",
                    "relation": "auxiliary mechanical control, different target domain",
                    "status": "not independent refrigerator fault validation",
                },
            ],
            "fictitious_joint_rows_created": 0,
        }
        files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(output / "source-relations.json", document_bytes(relations)),
            save_immutable(
                output / "predictions.csv",
                predictions.to_csv(index=False, lineterminator="\n").encode(),
            ),
        ]
        statistic_rows = []
        for comparison in comparisons:
            for metric in (
                "balanced_accuracy",
                "recall",
                "false_positive_rate",
                "average_precision",
                "brier",
                "log_loss",
            ):
                statistic_rows.append(
                    {
                        "run_id": run_id,
                        "statistic_key": comparison["model_id"]
                        + ":"
                        + comparison["evaluation_source"]
                        + ":"
                        + metric,
                        "source_id": comparison["evaluation_source"],
                        "source_version": sources[comparison["evaluation_source"]][
                            "source_version"
                        ],
                        "statistic_name": "thermal_transfer_ablation",
                        "feature_name": metric,
                        "numeric_value": comparison[metric],
                        "sample_count": comparison["n"],
                        "group_count": comparison["validation_groups"],
                        "dimensions_json": {
                            "model_id": comparison["model_id"],
                            "training_sources": comparison["training_sources"],
                            "experiments": comparison["validation_experiments"],
                        },
                    }
                )
        for bridge in fits:
            for row in bridge["results"]:
                for metric in ("mae", "r2", "mean_group_mae"):
                    statistic_rows.append(
                        {
                            "run_id": run_id,
                            "statistic_key": bridge["name"]
                            + ":"
                            + row["target"]
                            + ":"
                            + row["model"]
                            + ":"
                            + metric,
                            "source_id": "rwth_r290",
                            "source_version": "22097811",
                            "statistic_name": "measured_bridge_validation",
                            "feature_name": row["target"],
                            "numeric_value": row[metric],
                            "sample_count": row["n"],
                            "group_count": row["groups"],
                            "dimensions_json": {
                                "bridge": bridge["name"],
                                "model": row["model"],
                                "metric": metric,
                                "predictors": bridge["predictors"],
                            },
                        }
                    )
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(sources["rwth_r290"], file, "report", {"run_id": run_id}, now)
                    for file in files
                ],
                "study_statistics": statistic_rows,
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        started = False
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "bridges": len(fits),
                    "thermal_evaluations": len(comparisons),
                    "reports": output.as_posix(),
                },
                indent=2,
            )
        )
    except Exception as error:
        if started:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
