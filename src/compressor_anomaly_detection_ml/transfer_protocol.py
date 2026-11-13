"""Register a new research protocol without opening reserved signal values."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import save_immutable
from .domain import DataValidationError
from .public_acquisition import artifact_row
from .public_study import document_bytes


def validate_transfer_protocol(protocol: dict, parent: dict) -> None:
    if protocol.get("external_data_allowed") is not False:
        raise DataValidationError("Transfer development must exclude external observations.")
    if protocol.get("primary_anchor") != "smart_pdm":
        raise DataValidationError("The agreed reference anchor must remain explicit.")
    if protocol.get("parent_dataset_version") != parent.get("dataset_version") or protocol.get(
        "parent_partitions_sha256"
    ) != parent.get("partitions_sha256"):
        raise DataValidationError("Reserved parent membership/hash must remain unchanged.")
    hypotheses = protocol.get("hypotheses", [])
    ids = [row.get("id") for row in hypotheses]
    if not ids or not all(ids) or len(set(ids)) != len(ids):
        raise DataValidationError("A nonempty uniquely identified hypothesis matrix is required.")
    if "sealed" not in protocol.get("public_test_access", ""):
        raise DataValidationError("The public test remains sealed before candidate selection.")
    if set(protocol.get("release_decisions", [])) != {
        "public_integration_decision",
        "public_probability_support",
        "local_portability_status",
        "external_release_decision",
    }:
        raise DataValidationError("Public feasibility and external release are separate decisions.")


def register_protocol(path: Path = Path("config/transfer-protocol-v2.json")) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    parent_path = Path("reports/research") / protocol["parent_dataset_version"] / "partitions.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    validate_transfer_protocol(protocol, parent)
    partition_path = parent_path.with_name("partitions.csv")
    if hashlib.sha256(partition_path.read_bytes()).hexdigest() != parent["partitions_sha256"]:
        raise DataValidationError("Parent partition file changed.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    run_id = "transfer-protocol-" + digest[:20]
    output = Path("reports/research") / run_id
    now = datetime.now(UTC).replace(tzinfo=None)
    engine = create_engine_for_url(Settings.from_env().database_url)
    started = False
    try:
        repository = ResearchRepository(engine)
        datasets, runs = repository.tables["study_datasets"], repository.tables["study_runs"]
        with engine.connect() as connection:
            manifest = connection.execute(
                select(datasets.c.manifest_json).where(
                    datasets.c.dataset_version == protocol["parent_dataset_version"]
                )
            ).scalar_one()
            previous = connection.execute(
                select(runs.c.status).where(runs.c.run_id == run_id)
            ).scalar_one_or_none()
        if previous:
            if previous != "completed" or not (output / "registration.json").exists():
                raise DataValidationError("Incomplete protocol registration requires inspection.")
            return json.loads((output / "registration.json").read_text(encoding="utf-8"))
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_transfer_protocol",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": protocol,
                        "input_manifest_json": manifest,
                        "code_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    }
                ]
            },
            scope="public",
        )
        started = True
        output.mkdir(parents=True, exist_ok=False)
        file = save_immutable(output / "transfer-protocol.json", path.read_bytes())
        source = next(
            row
            for row in json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            if row["source_id"] == "smart_pdm"
        )
        repository.persist(
            {
                "study_artifacts": [
                    artifact_row(
                        source,
                        file,
                        "protocol",
                        {
                            "run_id": run_id,
                            "parent_dataset_version": protocol["parent_dataset_version"],
                        },
                        now,
                    )
                ]
            },
            scope="public",
        )
        report = {
            "run_id": run_id,
            "protocol_sha256": digest,
            "parent_dataset_version": protocol["parent_dataset_version"],
            "hypotheses": len(protocol["hypotheses"]),
            "reserved_test_opened": False,
            "external_data_read": False,
            "protocol_path": file["relative_path"],
        }
        save_immutable(output / "registration.json", document_bytes(report))
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
    print(json.dumps(register_protocol(), indent=2))
