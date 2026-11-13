import hashlib
import io
import zipfile

import pytest

from compressor_anomaly_detection_ml import datasets
from compressor_anomaly_detection_ml.domain import DataValidationError


def test_immutable_files_reject_changed_version_and_checksum(tmp_path):
    path = tmp_path / "raw/source.csv"
    first = datasets.save_immutable(path, b"one", expected_md5=hashlib.md5(b"one").hexdigest())
    assert datasets.save_immutable(path, b"one") == first
    with pytest.raises(DataValidationError, match="overwrite"):
        datasets.save_immutable(path, b"two")
    with pytest.raises(DataValidationError, match="checksum"):
        datasets.save_immutable(tmp_path / "wrong", b"one", expected_md5="0" * 32)
    assert path.read_bytes() == b"one"
    assert not (tmp_path / "wrong").exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "a/../../b", "..\\escape"])
def test_unsafe_archive_paths_are_rejected(name):
    with pytest.raises(DataValidationError):
        datasets.safe_member(name)


def archive(name, content):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as handle:
        handle.writestr(name, content)
    return buffer.getvalue()


def test_small_zip_and_expansion_limit():
    content = archive("safe/data.csv", b"column\n1\n")
    assert datasets.zip_members(content) == {"safe/data.csv": b"column\n1\n"}
    with pytest.raises(DataValidationError, match="budget"):
        datasets.zip_members(content, expanded_limit=2)
    with pytest.raises(zipfile.BadZipFile):
        datasets.zip_members(b"not a zip")
    with pytest.raises(DataValidationError):
        datasets.zip_members(archive("../escape", b"x"))


class Response(io.BytesIO):
    def __init__(self, content, status=200, headers=None):
        super().__init__(content)
        self.status, self.headers = status, headers or {}


def test_range_requires_exact_status_bounds_and_length(monkeypatch):
    reader = datasets.RemoteZip("https://example.invalid/archive", 100)
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        lambda *_a, **_k: Response(b"abc", 206, {"Content-Range": "bytes 0-2/100"}),
    )
    assert reader.read(3) == b"abc"
    for response in [
        Response(b"abc", 200),
        Response(b"abc", 206, {"Content-Range": "bytes 3-5/99"}),
        Response(b"a", 206, {"Content-Range": "bytes 3-5/100"}),
    ]:
        monkeypatch.setattr(
            datasets.urllib.request, "urlopen", lambda *_a, _response=response, **_k: _response
        )
        with pytest.raises(DataValidationError):
            reader.read(3)


def test_budget_timeout_and_no_credentials_in_urls(monkeypatch):
    with pytest.raises(DataValidationError, match="budget"):
        datasets.RemoteZip("https://example.invalid/x", 100, budget=2).read(3)
    monkeypatch.setattr(
        datasets.urllib.request, "urlopen", lambda *_a, **_k: Response(b"too large")
    )
    with pytest.raises(DataValidationError, match="budget"):
        datasets.fetch_bytes("https://example.invalid/x", limit=2)

    def timeout(*_a, **_k):
        raise TimeoutError("fixture timeout")

    monkeypatch.setattr(datasets.urllib.request, "urlopen", timeout)
    with pytest.raises(TimeoutError):
        datasets.fetch_bytes("https://example.invalid/x")
    with pytest.raises(DataValidationError):
        datasets.fetch_bytes("https://user:password@example.invalid/x")


def test_remote_member_extraction_is_complete_and_cached_crc_is_checked(monkeypatch, tmp_path):
    payload = archive("sample/data.csv", b"column\n1\n")

    def response(request, **_kwargs):
        start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
        return Response(
            payload[start : end + 1], 206, {"Content-Range": f"bytes {start}-{end}/{len(payload)}"}
        )

    monkeypatch.setattr(datasets.urllib.request, "urlopen", response)
    result = datasets.extract_remote_members(
        "https://example.invalid/archive", len(payload), ["sample/data.csv"], tmp_path
    )
    assert result["files"][0]["byte_size"] == 9
    (tmp_path / "sample/data.csv").write_bytes(b"changed")
    with pytest.raises(DataValidationError, match="integrity"):
        datasets.extract_remote_members(
            "https://example.invalid/archive", len(payload), ["sample/data.csv"], tmp_path
        )
