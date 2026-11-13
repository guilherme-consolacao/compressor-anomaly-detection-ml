import copy
import json
from pathlib import Path

import pytest

from compressor_anomaly_detection_ml.domain import DataValidationError
from compressor_anomaly_detection_ml.transfer_protocol import validate_transfer_protocol


def fixture():
    protocol = json.loads(Path("config/transfer-protocol-v2.json").read_text())
    parent = {
        "dataset_version": protocol["parent_dataset_version"],
        "partitions_sha256": protocol["parent_partitions_sha256"],
    }
    return protocol, parent


def test_protocol_keeps_reference_anchor_and_separate_release_gates():
    protocol, parent = fixture()
    validate_transfer_protocol(protocol, parent)
    assert protocol["prior_validation_status"].startswith("known")


@pytest.mark.parametrize("problem", ["external", "hash", "duplicate", "anchor", "gate"])
def test_protocol_refuses_external_leakage_or_unregistered_changes(problem):
    protocol, parent = fixture()
    if problem == "external":
        protocol["external_data_allowed"] = True
    elif problem == "hash":
        parent["partitions_sha256"] = "changed"
    elif problem == "duplicate":
        protocol["hypotheses"].append(copy.deepcopy(protocol["hypotheses"][0]))
    elif problem == "anchor":
        protocol["primary_anchor"] = "ulisses"
    else:
        protocol["release_decisions"].pop()
    with pytest.raises(DataValidationError):
        validate_transfer_protocol(protocol, parent)
