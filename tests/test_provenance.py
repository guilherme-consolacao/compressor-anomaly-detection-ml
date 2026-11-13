import json
from copy import deepcopy

import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.provenance import (
    load_registry,
    validate_public_file,
    validate_public_provenance,
)


@pytest.fixture
def registry():
    return {
        ("public", "v1"): {
            "data_origin": "public_measured",
            "resource_kind": "dataset",
            "license_name": "CC BY 4.0",
        },
        ("ulisses", "v1"): {
            "data_origin": "ulisses_external",
            "resource_kind": "reserved_external",
        },
    }


def root(origin="public_measured", source="public"):
    return {
        "node_id": "raw",
        "source_id": source,
        "source_version": "v1",
        "data_origin": origin,
        "parent_ids": [],
    }


def test_public_ancestry_accepts_derived_nodes_in_any_order(registry):
    nodes = [{"node_id": "features", "data_origin": "derived", "parent_ids": ["raw"]}, root()]
    assert validate_public_provenance(nodes, registry)["node_count"] == 2


@pytest.mark.parametrize("origin", [None, "", "unknown", "ulisses_external", "public_synthetic"])
def test_nonpublic_or_missing_origin_is_rejected(origin, registry):
    with pytest.raises(DataValidationError):
        validate_public_provenance([root(origin)], registry)


def test_external_ancestor_is_rejected_even_under_public_directory(tmp_path, registry):
    public = tmp_path / "data/public/renamed.json"
    public.parent.mkdir(parents=True)
    nodes = [
        root("ulisses_external", "ulisses"),
        {"node_id": "normalized", "data_origin": "derived", "parent_ids": ["raw"]},
    ]
    public.write_text(json.dumps({"provenance_nodes": nodes}), encoding="utf-8")
    source_file = tmp_path / "sources.json"
    source_file.write_text(
        json.dumps(
            {
                "sources": [
                    {"source_id": source, "source_version": version, **entry}
                    for (source, version), entry in registry.items()
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError):
        validate_public_file(public, source_file)


def test_changing_declared_origin_does_not_bypass_registered_external_source(registry):
    with pytest.raises(DataValidationError, match="registry"):
        validate_public_provenance([root(source="ulisses")], registry)


@pytest.mark.parametrize(
    "nodes",
    [
        [],
        [root(), root()],
        [None],
        [{"node_id": "x", "data_origin": "derived", "parent_ids": []}],
        [{"node_id": "x", "data_origin": "derived", "parent_ids": ["missing"]}],
        [
            {"node_id": "x", "data_origin": "derived", "parent_ids": ["y"]},
            {"node_id": "y", "data_origin": "derived", "parent_ids": ["x"]},
        ],
    ],
)
def test_incomplete_or_cyclic_ancestry_is_rejected(nodes, registry):
    with pytest.raises(DataValidationError):
        validate_public_provenance(nodes, registry)


def test_registry_requires_license(registry):
    sources = deepcopy(registry)
    sources[("public", "v1")]["license_name"] = None
    with pytest.raises(DataValidationError, match="licensed"):
        validate_public_provenance([root()], sources)


def test_duplicate_source_version_is_rejected(tmp_path):
    path = tmp_path / "registry.json"
    row = {"source_id": "x", "source_version": "1"}
    path.write_text(json.dumps({"sources": [row, row]}), encoding="utf-8")
    with pytest.raises(DataValidationError):
        load_registry(path)
