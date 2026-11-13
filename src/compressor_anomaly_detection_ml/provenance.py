"""Fail-closed origin checks for the public development path (SDD RF-02)."""

import json
from collections import deque
from collections.abc import Mapping
from pathlib import Path

from .domain import DataValidationError


def load_registry(path: Path) -> dict[tuple[str, str], dict]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        rows = document["sources"]
        if not isinstance(rows, list):
            raise ValueError
        registry = {}
        for row in rows:
            key = (row["source_id"], row["source_version"])
            if not all(isinstance(value, str) and value.strip() for value in key):
                raise ValueError
            if key in registry:
                raise ValueError
            registry[key] = row
        return registry
    except (OSError, ValueError, KeyError, TypeError):
        raise DataValidationError("Invalid or unavailable public source registry.") from None


def validate_public_provenance(nodes: list[dict], registry: Mapping) -> dict:
    """Validate the complete ancestry, not the directory containing the file.

    Declared lineage is verified against the source registry. File-content hashes
    must also be verified by ingestion; this is not a forensic origin classifier.
    """
    if not isinstance(nodes, list) or not nodes:
        raise DataValidationError("Public development requires explicit nonempty provenance.")
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise DataValidationError("Every provenance node must be an object.")
        node_id = node.get("node_id")
        if not isinstance(node_id, str) or not node_id.strip() or node_id in by_id:
            raise DataValidationError("Provenance IDs must be nonempty and unique.")
        origin, parents = node.get("data_origin"), node.get("parent_ids")
        if not isinstance(parents, list) or any(not isinstance(p, str) for p in parents):
            raise DataValidationError("Explicit parent_ids are required for every node.")
        if len(set(parents)) != len(parents):
            raise DataValidationError("Repeated provenance parents are invalid.")
        if origin == "derived":
            if not parents:
                raise DataValidationError("Derived records require complete ancestry.")
        elif origin == "public_measured":
            key = (node.get("source_id"), node.get("source_version"))
            if not all(isinstance(value, str) and value.strip() for value in key):
                raise DataValidationError("Public source identity is required.")
            source = registry.get(key)
            if not source or source.get("data_origin") != "public_measured":
                raise DataValidationError("Public origin does not match the source registry.")
            if source.get("resource_kind") != "dataset" or not source.get("license_name"):
                raise DataValidationError("Public observations require a licensed dataset source.")
            if parents:
                raise DataValidationError("Transformed nodes must declare derived origin.")
        else:
            raise DataValidationError(
                "External, synthetic or missing origins are not public training data."
            )
        by_id[node_id] = node
    children = {node_id: [] for node_id in by_id}
    pending = {}
    for node_id, node in by_id.items():
        pending[node_id] = len(node["parent_ids"])
        for parent in node["parent_ids"]:
            if parent not in by_id:
                raise DataValidationError("A provenance ancestor is missing.")
            children[parent].append(node_id)
    ready = deque(node_id for node_id, count in pending.items() if not count)
    visited = 0
    while ready:
        node_id = ready.popleft()
        visited += 1
        for child in children[node_id]:
            pending[child] -= 1
            if pending[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        raise DataValidationError("Cyclic provenance is invalid.")
    return {
        "eligible_public_origin": True,
        "node_count": visited,
        "root_count": sum(node["data_origin"] == "public_measured" for node in nodes),
    }


def validate_public_file(path: Path, registry_path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        nodes = document["provenance_nodes"]
    except (OSError, ValueError, KeyError, TypeError):
        raise DataValidationError("Invalid provenance manifest.") from None
    return validate_public_provenance(nodes, load_registry(registry_path))
