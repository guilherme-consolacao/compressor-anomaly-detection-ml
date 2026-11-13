"""Representative public samples, not a claim to import complete source archives."""

import json
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .database import create_engine_for_url
from .database.research_repository import ResearchRepository
from .datasets import extract_remote_members
from .public_acquisition import artifact_row


def sample_public(source_id: str, root: Path = Path(".")) -> dict:
    registry = json.loads((root / "config/dataset-sources.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == source_id)
    if source_id not in {"kaist", "ult_freezers"}:
        raise ValueError("Only explicitly selected public sources are sampled.")
    folder = root / "data/public/raw" / source_id / source["source_version"]
    provider = json.loads((folder / "provider-metadata.json").read_text(encoding="utf-8"))
    listings = json.loads((folder / "archive-listings.json").read_text(encoding="utf-8"))
    now = datetime.now(UTC).replace(tzinfo=None)
    run_id = source_id + "-samples-" + now.strftime("%Y%m%dT%H%M%S%f")
    report = {
        "run_id": run_id,
        "source_id": source_id,
        "representative_subset": True,
        "external_data_read": False,
        "archives": [],
    }
    engine = create_engine_for_url(Settings.from_env().database_url)
    try:
        repository = ResearchRepository(engine)
        repository.persist(
            {
                "study_runs": [
                    {
                        "run_id": run_id,
                        "stage": "raw_sample_audit",
                        "data_scope": "public",
                        "status": "running",
                        "started_at": now,
                        "configuration_json": {
                            "selection": "two loads (2/4 Nm); normal and outer-bearing fault"
                            if source_id == "kaist"
                            else "documentation, event summary and three small thermal logs",
                            "maximum_download_bytes": 384_000_000,
                        },
                        "input_manifest_json": {
                            "source_id": source_id,
                            "version": source["source_version"],
                        },
                    }
                ]
            },
            scope="public",
        )
        try:
            for listing in listings:
                if "members" not in listing:
                    raise ValueError("Archive listing unavailable.")
                if source_id == "kaist":
                    extension = ".mat" if listing["archive"] == "vibration.zip" else ".tdms"
                    names = [
                        f"{load}Nm_{condition}{extension}"
                        for load in [2, 4]
                        for condition in ["Normal", "BPFO_03"]
                    ]
                    item = next(
                        row for row in provider["files"] if row["filename"] == listing["archive"]
                    )
                    url, size = item["content_details"]["download_url"], item["size"]
                    destination = folder / "sample" / listing["archive"].removesuffix(".zip")
                else:
                    item = provider["files"][0]
                    url, size = item["download_url"], item["size"]
                    names = [
                        m["name"]
                        for m in listing["members"]
                        if m["name"].lower().endswith("readme.md") and m["size"] < 100_000
                    ]
                    names += [
                        "data/dataset/fault_summary_R1.xlsx",
                        "data/raw_data/other_data/freezers_model_data.csv",
                    ]
                    candidates = sorted(
                        [
                            m
                            for m in listing["members"]
                            if "/temp/" in m["name"]
                            and m["name"].endswith(".dat")
                            and 10_000 < m["size"] < 1_000_000
                        ],
                        key=lambda x: x["size"],
                    )
                    devices = set()
                    for member in candidates:
                        device = member["name"].split("/")[3]
                        if device not in devices:
                            names.append(member["name"])
                            devices.add(device)
                        if len(devices) == 3:
                            break
                    destination = folder / "sample"
                result = extract_remote_members(
                    url, size, names, destination, member_limit=160_000_000
                )
                report["archives"].append({"archive": listing["archive"], **result})
                repository.persist(
                    {
                        "study_artifacts": [
                            artifact_row(
                                source,
                                file,
                                "raw",
                                {
                                    "provider_url": url,
                                    "archive_member": file["archive_member"],
                                    "zip_crc32": file["zip_crc32"],
                                    "full_archive_checksum_verified": False,
                                },
                                now,
                            )
                            for file in result["files"]
                        ]
                    },
                    scope="public",
                )
            repository.finish_run(run_id, "completed")
        except Exception as error:
            repository.finish_run(run_id, "failed", error_message=type(error).__name__)
            raise
    finally:
        engine.dispose()
    output = root / "reports/research" / run_id
    output.mkdir(parents=True, exist_ok=False)
    (output / "samples.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"run_id": run_id, "report": str(output / "samples.json")}), flush=True)
    return report


if __name__ == "__main__":
    import sys

    sample_public(sys.argv[1])
