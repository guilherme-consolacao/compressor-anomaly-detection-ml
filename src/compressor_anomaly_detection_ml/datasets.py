"""Bounded public acquisition and deterministic small archive extraction."""

import hashlib
import io
import json
import os
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .domain import DataValidationError

HEADERS = {"User-Agent": "CompressorML-public-research/1.0"}


def _public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DataValidationError("Public acquisition requires an HTTPS URL without credentials.")


def fetch_bytes(url: str, limit: int = 2_000_000, timeout: int = 30) -> bytes:
    _public_url(url)
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=HEADERS), timeout=timeout
    ) as response:
        if response.status != 200:
            raise DataValidationError("Unexpected public download status.")
        content = response.read(limit + 1)
    if len(content) > limit:
        raise DataValidationError("Public download exceeded its declared budget.")
    return content


def save_immutable(path: Path, content: bytes, *, expected_md5: str | None = None) -> dict:
    digest = hashlib.sha256(content).hexdigest()
    if expected_md5 and hashlib.md5(content).hexdigest() != expected_md5.lower():
        raise DataValidationError("Public file checksum mismatch.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if (
            path.stat().st_size != len(content)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise DataValidationError("Existing public file/version differs; refusing overwrite.")
    else:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        try:
            if os.name == "nt":
                os.rename(temporary, path)  # Windows rename refuses an existing destination.
            else:
                os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return {"relative_path": path.as_posix(), "content_sha256": digest, "byte_size": len(content)}


def safe_member(name: str) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in normalized or "\x00" in normalized:
        raise DataValidationError("Unsafe ZIP member path.")


def zip_members(content: bytes, *, expanded_limit: int = 5_000_000) -> dict[str, bytes]:
    result = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > expanded_limit:
            raise DataValidationError("Expanded archive exceeds the extraction budget.")
        for item in archive.infolist():
            safe_member(item.filename)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise DataValidationError("Archive symlinks are not supported.")
            if item.is_dir():
                continue
            if item.filename in result:
                raise DataValidationError("Duplicate ZIP member name.")
            with archive.open(item) as handle:
                data = handle.read(expanded_limit + 1)
            if len(data) != item.file_size or len(data) > expanded_limit:
                raise DataValidationError("Expanded member size differs.")
            result[item.filename] = data
    return result


class RemoteZip(io.RawIOBase):
    """Seekable HTTPS reader with exact range validation and a cumulative budget."""

    def __init__(self, url: str, size: int, budget: int = 12_000_000):
        _public_url(url)
        if size <= 0 or budget <= 0:
            raise DataValidationError("Invalid remote archive size/budget.")
        self.url, self.size, self.budget = url, size, budget
        self.position = self.transferred = 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError("Invalid seek mode.")
        position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        if position < 0:
            raise ValueError("Negative seek.")
        self.position = position
        return position

    def read(self, size=-1):
        count = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if count <= 0:
            return b""
        if count > 4_000_000 or self.transferred + count > self.budget:
            raise DataValidationError("Remote ZIP range budget exceeded.")
        start, end = self.position, self.position + count - 1
        request = urllib.request.Request(
            self.url, headers={**HEADERS, "Range": f"bytes={start}-{end}"}
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            expected = f"bytes {start}-{end}/{self.size}"
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise DataValidationError("Server ignored the exact byte range; download stopped.")
            content = response.read(count + 1)
        if len(content) != count:
            raise DataValidationError("Truncated or oversized range response.")
        self.position += count
        self.transferred += count
        return content


def inspect_smart_archive(record: dict, destination: Path) -> dict:
    entry = next(file for file in record["files"] if file["key"] == "SMART-PDM-Dataset.zip")
    stream = RemoteZip(entry["links"]["self"], entry["size"])
    files = []
    with zipfile.ZipFile(stream) as archive:
        for item in archive.infolist():
            if not re.search(r"fridge.*metadata|F_ExtractedFeatures", item.filename, re.I):
                continue
            safe_member(item.filename)
            if item.file_size > 3_000_000 or item.compress_size > 2_000_000:
                raise DataValidationError("Selected SMART-PDM member exceeds budget.")
            with archive.open(item) as handle:
                data = handle.read(3_000_001)
            if len(data) != item.file_size:
                raise DataValidationError("Selected SMART-PDM member is incomplete.")
            file = save_immutable(destination / PurePosixPath(item.filename).name, data)
            files.append({**file, "archive_member": item.filename, "zip_crc32": f"{item.CRC:08x}"})
        if len(files) != 2:
            raise DataValidationError(
                "Expected exactly two refrigerator metadata/features members."
            )
        candidates = [
            item.filename for item in archive.infolist() if "/3-fridges/" in item.filename
        ]
    return {
        "files": files,
        "bytes_transferred": stream.transferred,
        "declared_archive_checksum": entry["checksum"],
        "full_archive_checksum_verified": False,
        "refrigerator_member_names": candidates,
    }


def fetch_json(url: str) -> tuple[dict | list, bytes]:
    content = fetch_bytes(url)
    try:
        return json.loads(content), content
    except (UnicodeError, ValueError):
        raise DataValidationError("Public metadata is not valid JSON.") from None


def extract_remote_members(
    url: str,
    archive_size: int,
    names: list[str],
    destination: Path,
    *,
    budget: int = 384_000_000,
    member_limit: int = 80_000_000,
) -> dict:
    stream = RemoteZip(url, archive_size, budget=budget)
    files = []
    with zipfile.ZipFile(stream) as archive:
        for name in names:
            safe_member(name)
            info = archive.getinfo(name)
            if info.file_size > member_limit:
                raise DataValidationError("Selected raw member exceeds its explicit budget.")
            target = destination / name
            if target.exists():
                import zlib

                content = target.read_bytes()
                if len(content) != info.file_size or zlib.crc32(content) != info.CRC:
                    raise DataValidationError("Cached public member integrity differs.")
            else:
                chunks, size = [], 0
                with archive.open(info) as handle:
                    while block := handle.read(1_000_000):
                        size += len(block)
                        if size > member_limit:
                            raise DataValidationError("Expanded raw member exceeds its budget.")
                        chunks.append(block)
                content = b"".join(chunks)
            file = save_immutable(target, content)
            files.append(
                {
                    **file,
                    "archive_member": name,
                    "zip_crc32": f"{info.CRC:08x}",
                    "full_archive_checksum_verified": False,
                }
            )
            print(json.dumps({"downloaded_member": name, "bytes": len(content)}), flush=True)
    return {
        "files": files,
        "bytes_transferred": stream.transferred,
        "full_archive_checksum_verified": False,
    }
