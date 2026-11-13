"""Evaluate a measured RWTH bridge and projected refrigeration references on SMART."""

import hashlib
import json
import sys
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
from compressor_anomaly_detection_ml.transfer_bridges import (
    file_manifest,
    refrigeration_common,
    rwth_spectral_table,
)
from compressor_anomaly_detection_ml.transfer_inputs import tri_hp_main
from compressor_anomaly_detection_ml.transfer_projection import (
    select_measured_bridge,
    specific_refrigeration_state,
    spectral_reference_comparison,
)
from compressor_anomaly_detection_ml.transfer_spectra import rwth_signatures, smart_signature


def main(protocol_path=Path("config/transfer-round2-spectral.json")):
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    folder = Path("data/public/raw/smart_pdm/7245198")
    acquisition_path = Path(
        "reports/research/transfer-protocol-2b941b65972c76bd9371/smart-wave-round2-acquisition.json"
    )
    if (
        protocol["external_data_allowed"]
        or protocol["public_test_opened"]
        or not acquisition_path.exists()
    ):
        raise DataValidationError("A completed public-only acquisition is required first.")
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    selection = json.loads((folder / "round2-wave-selection.json").read_text(encoding="utf-8"))
    selected = pd.DataFrame(selection["rows"])
    if selected.partition_name.eq("test").any() or selected.observation_id.duplicated().any():
        raise DataValidationError("The selected cohort contains a reserved or repeated cycle.")
    parent_partition = Path("reports/research/public-study-87d04baa2e265aeb/partitions.csv")
    parent_policy = json.loads(Path("config/transfer-protocol-v2.json").read_text(encoding="utf-8"))
    if (
        hashlib.sha256(parent_partition.read_bytes()).hexdigest()
        != parent_policy["parent_partitions_sha256"]
    ):
        raise DataValidationError("Parent reservations changed.")
    files = []
    by_member = {row["archive_member"]: row for row in acquisition["files"]}
    for member in selection["members"]:
        row = by_member[member]
        path = Path(row["relative_path"])
        if (
            path.parent.name not in set(selected.original_id)
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["content_sha256"]
        ):
            raise DataValidationError("Selected waveform identity or checksum changed.")
        files.append(row)
    rwth_root = Path("data/public/raw/rwth_r290/22097811")
    tri_path = Path(
        "data/public/raw/tri_hp_faults/5155136.v1/H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
    )
    supplement_inputs = file_manifest(
        [
            *list((rwth_root / "psd-audit/vibration_psd").glob("**/*.csv")),
            rwth_root / "thermodynamic/thermodynamic_averaged_with_uncertainty.csv",
            rwth_root / "vibration_rms/rms_by_charge.csv",
            tri_path,
        ]
    )
    code_paths = [
        __file__,
        "src/compressor_anomaly_detection_ml/transfer_projection.py",
        "src/compressor_anomaly_detection_ml/transfer_spectra.py",
        "src/compressor_anomaly_detection_ml/transfer_inputs.py",
        "src/compressor_anomaly_detection_ml/transfer_bridges.py",
        "src/compressor_anomaly_detection_ml/public_importers.py",
    ]
    code = b"".join(Path(path).read_bytes() for path in code_paths)
    digest = hashlib.sha256(
        code + protocol_path.read_bytes() + document_bytes(files + supplement_inputs)
    ).hexdigest()
    run_id = "spectral-" + protocol.get("round_name", "round2") + "-" + digest[:20]
    output = Path("reports/research") / run_id
    engine = create_engine_for_url(Settings.from_env().database_url)
    started = False
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        repository = ResearchRepository(engine)
        with engine.connect() as connection:
            runs = repository.tables["study_runs"]
            previous = connection.execute(
                select(runs.c.status).where(runs.c.run_id == run_id)
            ).scalar_one_or_none()
            table = repository.tables["study_artifacts"]
            registered = {
                row["artifact_id"]: dict(row)
                for row in connection.execute(
                    select(table).where(
                        table.c.source_id.in_(["smart_pdm", "rwth_r290", "tri_hp_faults"])
                    )
                ).mappings()
            }
        if previous:
            if previous != "completed":
                raise DataValidationError("Inspect incomplete spectral analysis before retrying.")
            print((output / "summary.json").read_text(encoding="utf-8"))
            return
        sources = {
            row["source_id"]: row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
        }
        artifacts = [
            artifact_row(
                sources["smart_pdm"],
                file,
                "raw",
                {
                    "archive_member": file["archive_member"],
                    "zip_crc32": file["zip_crc32"],
                    "full_archive_checksum_verified": False,
                    "cohort": "predeclared development-only",
                    "hypotheses": ["H02", "H03", "H05"],
                },
                now,
            )
            for file in files
        ]
        artifacts = [registered.get(row["artifact_id"], row) for row in artifacts]
        for file in supplement_inputs:
            source_id = (
                "tri_hp_faults" if "/tri_hp_faults/" in file["relative_path"] else "rwth_r290"
            )
            candidate = artifact_row(sources[source_id], file, "raw", {}, now)
            if candidate["artifact_id"] not in registered:
                raise DataValidationError(
                    "Supplementary bridge inputs must be acquired and registered first."
                )
            artifacts.append(registered[candidate["artifact_id"]])
        repository.persist(
            {
                "study_artifacts": artifacts,
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_spectral_transfer",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": {
                            "raw_artifacts": [row["artifact_id"] for row in artifacts],
                            "cohort_sha256": hashlib.sha256(
                                (folder / "round2-wave-selection.json").read_bytes()
                            ).hexdigest(),
                            "parent_partition_sha256": parent_policy["parent_partitions_sha256"],
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
        save_immutable(output / "executed-code.txt", code)
        data, audit, rejected = [], [], []
        file_by_original = {Path(row["relative_path"]).parent.name: row for row in files}
        artifact_by_path = {row["relative_path"]: row["artifact_id"] for row in artifacts}
        for index, row in enumerate(selected.to_dict("records")):
            file = file_by_original[row["original_id"]]
            try:
                values, detail = smart_signature(Path(file["relative_path"]))
                data.append({**row, "source_id": "smart_pdm", **values})
                audit.append({"observation_id": row["observation_id"], **detail})
            except DataValidationError as error:
                rejected.append({"observation_id": row["observation_id"], "reason": str(error)})
            if index % 30 == 0:
                print(
                    json.dumps({"waveforms_audited": index + 1, "total": len(selected)}), flush=True
                )
        smart = pd.DataFrame(data)
        if len(smart) != len(selected):
            save_immutable(output / "waveform-quality-rejections.json", document_bytes(rejected))
            raise DataValidationError(
                "Resolve or predeclare the effect of waveform-quality exclusions before fitting."
            )
        rwth_root = Path("data/public/raw/rwth_r290/22097811")
        rwth, rwth_audit = rwth_spectral_table(rwth_root)
        rwth = rwth.drop(columns=[name for name in rwth if name.startswith("vibration_")])
        rich = rwth_signatures(rwth_root / "psd-audit/vibration_psd")
        rwth = rwth.merge(
            rich, on=["measurement_id", "refrigerant_charge_g"], validate="one_to_one"
        )
        rwth, _ = refrigeration_common(rwth, "rwth_r290")
        if protocol["bridge"].get("specific_work_normalization"):
            rwth = specific_refrigeration_state(rwth)
        partitions = pd.read_csv(parent_partition)
        rwth = rwth.merge(
            partitions[["observation_id", "partition_name"]],
            on="observation_id",
            validate="one_to_one",
        )
        if protocol["bridge"].get("rwth_known_development"):
            rwth_train = rwth.loc[rwth.partition_name.ne("test")].copy()
            rwth_train["parent_partition_name"] = rwth_train.partition_name
            rwth_train["partition_name"] = "train"
        else:
            rwth_train = rwth[rwth.partition_name.eq("train")]
        targets = sorted(name for name in rwth if name.startswith("vibration_"))
        predictors = protocol["bridge"]["predictors"]
        control = [
            "f_comp_set_Hz",
            "water_supply_temperature_setpoint_C",
            "water_return_temperature_setpoint_C",
            "ambient_temperature_setpoint_C",
        ]
        model, shared, bridge_report = select_measured_bridge(
            rwth_train, predictors, control, targets, protocol["bridge"]
        )
        tri_path = Path(
            "data/public/raw/tri_hp_faults/5155136.v1/H2020_TRI-HP_T6.2_PropaneIceFaultTests_v1.xlsx"
        )
        tri, _ = tri_hp_main(tri_path)
        tri = tri[~tri.sheet.str.startswith("OC")].copy()
        tri, _ = refrigeration_common(tri, "tri_hp_faults")
        if protocol["bridge"].get("specific_work_normalization"):
            tri = specific_refrigeration_state(tri)
        median = tri.groupby("Test code", sort=True)[predictors].median()
        metadata = tri.groupby("Test code", sort=True)[
            ["target_label", "group_id", "load_kw"]
        ].first()
        if tri.groupby("Test code").target_label.nunique().gt(1).any():
            raise DataValidationError("A projected condition contains conflicting references.")
        projected = median.join(metadata).reset_index()
        projected["observation_id"] = "tri_hp_faults:5155136.v1:condition:" + projected["Test code"]
        projected["source_id"] = "tri_hp_faults"
        projected["partition_name"] = np.where(projected.load_kw.eq(10), "train", "validation")
        inside = (
            ((median >= rwth_train[predictors].min()) & (median <= rwth_train[predictors].max()))
            .all(axis=1)
            .to_numpy()
        )
        projected["inside_training_box"] = inside
        if model is not None:
            projected[shared] = np.asarray(model.predict(projected[predictors])).reshape(
                len(projected), len(shared)
            )
        projected_training = (
            projected[projected.partition_name.eq("train") & projected.inside_training_box].copy()
            if model is not None
            else pd.DataFrame()
        )
        print(
            json.dumps(
                {
                    "bridge_selected_features": len(shared),
                    "projected_training_conditions_in_support": len(projected_training),
                }
            ),
            flush=True,
        )
        comparisons, predictions = spectral_reference_comparison(
            smart, projected_training, shared, protocol
        )
        summary = {
            "run_id": run_id,
            "external_data_read": False,
            "reserved_smart_test_opened": False,
            "tri_oc_test_opened": False,
            "cohort": {
                "cycles": len(smart),
                "positives": int(smart.target_label.sum()),
                "groups": int(smart.dependency_group_id.nunique()),
                "waveform_support_seconds": sorted(
                    {round(row["duration_seconds"], 5) for row in audit}
                ),
                "prevalence_is_not_deployment_prevalence": True,
            },
            "rwth": rwth_audit,
            "bridge": bridge_report,
            "shared_projection_features": shared,
            "projected_reference_conditions": len(projected),
            "projected_training_conditions_in_box": len(projected_training),
            "projected_training_has_both_classes": set(projected_training.target_label.astype(int))
            == {0, 1}
            if not projected_training.empty
            else False,
            "results": comparisons,
            "derived_binary_labels_accepted": 0,
            "local_release": False,
            "projection_scope": (
                "estimated vibration descriptors, independently measured fault labels; "
                "not observed TRI vibration"
            ),
            "probability_status": (
                "uncalibrated public reference scores on selected development cohort"
            ),
        }
        report_files = [
            save_immutable(output / "summary.json", document_bytes(summary)),
            save_immutable(output / "waveform-audit.json", document_bytes(audit)),
            save_immutable(
                output / "smart-spectral-development.csv",
                smart.to_csv(index=False, lineterminator="\n").encode(),
            ),
            save_immutable(
                output / "projected-tri-conditions.csv",
                projected.to_csv(index=False, lineterminator="\n").encode(),
            ),
            save_immutable(
                output / "predictions.csv",
                predictions.to_csv(index=False, lineterminator="\n").encode(),
            ),
        ]
        features = sorted(name for name in smart if name.startswith(("vibration_", "current_")))
        feature_rows = []
        for row in smart.to_dict("records"):
            raw = file_by_original[row["original_id"]]
            for name in features:
                feature_rows.append(
                    {
                        "observation_id": row["observation_id"],
                        "feature_contract_version": "smart-spectral-v2-" + digest[:12],
                        "feature_name": name,
                        "numeric_value": float(row[name]),
                        "unit": "1",
                        "value_status": "derived",
                        "definition_json": {
                            "raw_artifact_id": artifact_by_path[raw["relative_path"]],
                            "sampling_hz": 2048,
                            "band_hz": [10, 1000],
                            "one_cycle_is_one_observation": True,
                        },
                        "run_id": run_id,
                    }
                )
        for offset in range(0, len(feature_rows), 2500):
            repository.persist(
                {"study_feature_values": feature_rows[offset : offset + 2500]}, scope="public"
            )
        stats = []
        for report in comparisons:
            for metric in (
                "balanced_accuracy",
                "recall",
                "false_positive_rate",
                "f1",
                "average_precision",
                "brier",
            ):
                stats.append(
                    {
                        "run_id": run_id,
                        "statistic_key": report["model_id"] + ":" + metric,
                        "source_id": "smart_pdm",
                        "source_version": "7245198",
                        "statistic_name": "spectral_bridge_ablation",
                        "feature_name": metric,
                        "numeric_value": report[metric],
                        "sample_count": len(smart),
                        "group_count": int(smart.dependency_group_id.nunique()),
                        "dimensions_json": {
                            "model_id": report["model_id"],
                            "features": report["features"],
                            "alignment": report["alignment"],
                            "projected_mass": report["projected_mass"],
                            "evaluation": report["evaluation"],
                        },
                    }
                )
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(sources["smart_pdm"], file, "report", {"run_id": run_id}, now)
                    for file in report_files
                ],
                "study_statistics": stats,
            },
            scope="public",
        )
        repository.finish_run(run_id, "completed")
        started = False
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "comparisons": len(comparisons),
                    "bridge_features": len(shared),
                    "best_development_f1": max(row["f1"] for row in comparisons),
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
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/transfer-round2-spectral.json"))
