from pathlib import Path

import pytest

from compressor_anomaly_detection_ml.database.local_setup import (
    initialize,
    portable_dump,
    validate_target,
)


@pytest.mark.parametrize("host", ["srv.example.org", "0.0.0.0", "127.0.0.1.example.org"])
def test_setup_refuses_nonlocal_server(host):
    with pytest.raises(ValueError, match="loopback"):
        validate_target(host, "compressor_ml_dev")


@pytest.mark.parametrize(
    "database", ["mysql", "compressor", "compressor_ml_dev; DROP DATABASE mysql"]
)
def test_setup_refuses_unrelated_or_injected_database(database):
    with pytest.raises(ValueError, match="project"):
        validate_target("127.0.0.1", database)


def test_setup_preserves_existing_credentials_before_connecting(tmp_path):
    environment = tmp_path / ".env"
    environment.write_text("existing configuration", encoding="utf-8")
    with pytest.raises(FileExistsError):
        initialize("127.0.0.1", 3306, "compressor_ml_dev", environment)
    assert environment.read_text(encoding="utf-8") == "existing configuration"


def test_export_removes_owner_and_original_database_from_views():
    sql = (
        "CREATE DEFINER=`root`@`localhost` SQL SECURITY INVOKER VIEW mb_test AS "
        "SELECT * FROM `compressor_ml_dev`.`readings`;"
    )
    result = portable_dump(sql, "compressor_ml_dev")
    assert "DEFINER=" not in result
    assert "`compressor_ml_dev`." not in result
    assert "SQL SECURITY INVOKER" in result


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO readings VALUES (1)",
        "REPLACE INTO readings VALUES (1)",
        "CREATE USER 'someone'",
        "GRANT SELECT ON x.* TO 'someone'",
        "DROP DATABASE mysql",
        "CREATE DATABASE another",
        "USE mysql",
        "DELETE FROM readings",
    ],
)
def test_export_rejects_data_and_accounts(sql):
    with pytest.raises(ValueError, match="data or accounts"):
        portable_dump(sql, "compressor_ml_dev")


def test_research_schema_retains_external_and_public_contracts():
    root = Path(__file__).resolve().parents[1]
    document = (root / "database/local/002_research.sql").read_text(encoding="utf-8")
    assert "ulisses_external" in document
    assert "FOREIGN KEY (observation_id,label_id)" in document
    assert "FOREIGN KEY (external_case_id,truth_version)" in document
    assert "study_external_ground_truth" in document
