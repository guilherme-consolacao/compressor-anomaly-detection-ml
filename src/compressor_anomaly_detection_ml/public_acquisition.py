"""Reproducible public inventory; deliberately never reads the external dataset."""

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import (
    RemoteZip,
    fetch_bytes,
    fetch_json,
    inspect_smart_archive,
    save_immutable,
    zip_members,
)
from .domain import DataValidationError

METADATA = {
    "smart_pdm": ("https://zenodo.org/api/records/7245198", "7245198"),
    "rwth_r290": ("https://zenodo.org/api/records/22097811", "22097811"),
    "kaist": ("https://data.mendeley.com/public-api/datasets/ztmf3m7h5x", "ztmf3m7h5x"),
    "ult_freezers": ("https://api.figshare.com/v2/articles/24033324", "24033324"),
}


def source_row(source: dict, now: datetime) -> dict:
    columns = {
        key: source[key]
        for key in (
            "source_id",
            "source_version",
            "data_origin",
            "title",
            "primary_url",
            "license_name",
            "inspection_status",
        )
    }
    return {**columns, "metadata_json": dict(source), "created_at": now}


def artifact_row(source: dict, file: dict, kind: str, metadata: dict, now: datetime) -> dict:
    identity = "|".join(
        (
            source["source_id"],
            source["source_version"],
            file["relative_path"],
            file["content_sha256"],
        )
    )
    return {
        "artifact_id": hashlib.sha256(identity.encode()).hexdigest(),
        "source_id": source["source_id"],
        "source_version": source["source_version"],
        "artifact_kind": kind,
        **{key: file[key] for key in ("relative_path", "content_sha256", "byte_size")},
        "metadata_json": metadata,
        "created_at": now,
    }


def acquire_public(root: Path = Path(".")) -> dict:
    now = datetime.now(UTC).replace(tzinfo=None)
    registry = json.loads((root / "config/dataset-sources.json").read_text(encoding="utf-8"))
    run_id = "public-acquisition-" + now.strftime("%Y%m%dT%H%M%S%f")
    report = {"run_id": run_id, "sources": {}, "external_data_read": False}
    records = {}
    for source in registry["sources"]:
        if source["source_id"] not in METADATA:
            continue
        url, expected = METADATA[source["source_id"]]
        try:
            record, raw = fetch_json(url)
            if not isinstance(record, dict) or str(record.get("id")) != expected:
                raise DataValidationError("Provider returned a different dataset identity.")
            if source["source_id"] == "kaist" and record.get("version") != 6:
                raise DataValidationError("KAIST provider version differs from the registry.")
            if source["source_id"] == "ult_freezers":
                source["license_name"] = record["license"]["name"]
            records[source["source_id"]] = (record, raw, url)
            report["sources"][source["source_id"]] = {"metadata_verified": True}
        except (OSError, ValueError, KeyError, DataValidationError) as error:
            report["sources"][source["source_id"]] = {
                "metadata_verified": False,
                "error_type": type(error).__name__,
                "message": str(error)[:300],
            }
    engine = create_engine_for_url(Settings.from_env().database_url)
    try:
        repository = ResearchRepository(engine)
        repository.persist(
            {
                "study_sources": [source_row(source, now) for source in registry["sources"]],
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "public_acquisition",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "max_metadata_bytes": 2_000_000,
                            "range_budget_per_archive": 12_000_000,
                        },
                        "input_manifest_json": {"registry_version": registry["registry_version"]},
                    }
                ],
            },
            scope="public",
        )
        for source in registry["sources"]:
            source_id = source["source_id"]
            if source_id not in records:
                continue
            print(json.dumps({"stage": "public_acquisition", "source": source_id}), flush=True)
            record, raw, url = records[source_id]
            folder = root / "data/public/raw" / source_id / source["source_version"]
            artifacts = []

            def save(
                name,
                content,
                kind="raw",
                metadata=None,
                md5=None,
                _folder=folder,
                _artifacts=artifacts,
                _source=source,
                _url=url,
            ):
                file = save_immutable(_folder / name, content, expected_md5=md5)
                _artifacts.append(
                    artifact_row(_source, file, kind, metadata or {"provider_url": _url}, now)
                )
                return file

            metadata_name = "provider-metadata.json"
            if (folder / metadata_name).exists() and (folder / metadata_name).read_bytes() != raw:
                metadata_name = (
                    "provider-metadata-" + hashlib.sha256(raw).hexdigest()[:16] + ".json"
                )
            save(metadata_name, raw, "metadata", {"provider_url": url})
            try:
                if source_id == "smart_pdm":
                    details = inspect_smart_archive(record, folder)
                    for file in details["files"]:
                        artifacts.append(
                            artifact_row(
                                source,
                                file,
                                "raw",
                                {
                                    "provider_url": url,
                                    "zip_crc32": file["zip_crc32"],
                                    "archive_member": file["archive_member"],
                                    "full_archive_checksum_verified": False,
                                },
                                now,
                            )
                        )
                    report["sources"][source_id].update(details)
                elif source_id == "rwth_r290":
                    for file in record["files"]:
                        if file["key"] not in {
                            "thermodynamic.zip",
                            "vibration_rms.zip",
                            "README.md",
                            "data_mapping.csv",
                            "operating_points.csv",
                        }:
                            continue
                        if file["size"] > 1_000_000:
                            raise DataValidationError(
                                "Processed RWTH file exceeds its expected budget."
                            )
                        content = fetch_bytes(file["links"]["self"], 1_000_000)
                        checksum = file["checksum"]
                        if not checksum.startswith("md5:"):
                            raise DataValidationError("Unsupported provider checksum declaration.")
                        save(
                            file["key"],
                            content,
                            metadata={
                                "provider_url": file["links"]["self"],
                                "provider_checksum": checksum,
                            },
                            md5=checksum[4:],
                        )
                        if file["key"].endswith(".zip"):
                            for member, data in zip_members(content).items():
                                save(
                                    member,
                                    data,
                                    metadata={
                                        "parent_archive": file["key"],
                                        "zip_crc_verified": True,
                                    },
                                )
                    report["sources"][source_id]["small_files_downloaded"] = True
                elif source_id in {"kaist", "ult_freezers"}:
                    files = []
                    for file in record["files"]:
                        name = file.get("filename", file.get("name"))
                        if source_id == "kaist":
                            info = file["content_details"]
                            files.append(
                                {
                                    "name": name,
                                    "size": info["size"],
                                    "url": info["download_url"],
                                    "declared_sha256": info["sha256_hash"],
                                }
                            )
                        else:
                            files.append(
                                {
                                    "name": name,
                                    "size": file["size"],
                                    "url": file["download_url"],
                                    "declared_md5": file["computed_md5"],
                                }
                            )
                    report["sources"][source_id]["files"] = files
                    listings = []
                    for file in files:
                        if source_id == "kaist" and file["name"] == "acoustic.zip":
                            continue
                        stream = RemoteZip(file["url"], file["size"])
                        try:
                            with zipfile.ZipFile(stream) as archive:
                                members = [
                                    {
                                        "name": item.filename,
                                        "size": item.file_size,
                                        "compressed_size": item.compress_size,
                                        "crc32": f"{item.CRC:08x}",
                                    }
                                    for item in archive.infolist()
                                    if not item.is_dir()
                                ]
                            listings.append(
                                {
                                    "archive": file["name"],
                                    "members": members,
                                    "bytes_transferred": stream.transferred,
                                }
                            )
                        except (
                            OSError,
                            ValueError,
                            zipfile.BadZipFile,
                            DataValidationError,
                        ) as error:
                            listings.append(
                                {
                                    "archive": file["name"],
                                    "error_type": type(error).__name__,
                                    "message": str(error)[:200],
                                }
                            )
                    report["sources"][source_id]["archive_listings"] = listings
                    save(
                        "archive-listings.json", json.dumps(listings, indent=2).encode(), "metadata"
                    )
            except (
                OSError,
                ValueError,
                KeyError,
                zipfile.BadZipFile,
                DataValidationError,
            ) as error:
                report["sources"][source_id]["acquisition_error"] = {
                    "type": type(error).__name__,
                    "message": str(error)[:300],
                }
            repository.persist({"study_artifacts": artifacts}, scope="public")
        persist_acquisition_summary(report, repository)
        repository.finish_run(run_id, "completed")
    finally:
        engine.dispose()
    destination = root / "reports/research" / run_id
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "acquisition.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps({"run_id": run_id, "report": str(destination / "acquisition.json")}), flush=True
    )
    return report


def persist_acquisition_summary(report: dict, repository: ResearchRepository) -> None:
    rows = []
    registry = json.loads(Path("config/dataset-sources.json").read_text(encoding="utf-8"))
    versions = {row["source_id"]: row["source_version"] for row in registry["sources"]}
    for source_id, details in report["sources"].items():
        rows.append(
            {
                "run_id": report["run_id"],
                "statistic_key": source_id + ":metadata_verified",
                "source_id": source_id,
                "source_version": versions[source_id],
                "statistic_name": "acquisition_metadata_verified",
                "numeric_value": int(details["metadata_verified"]),
                "sample_count": 0,
                "group_count": 0,
                "dimensions_json": {
                    "external_data_read": False,
                    "acquisition_error": details.get("acquisition_error"),
                    "archive_count": len(details.get("archive_listings", [])),
                    "range_bytes_transferred": details.get("bytes_transferred"),
                    "full_archive_checksum_verified": details.get("full_archive_checksum_verified"),
                },
            }
        )
    repository.persist({"study_statistics": rows}, scope="public")


if __name__ == "__main__":
    try:
        acquire_public()
    except (OSError, DataValidationError) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}))
        sys.exit(1)
