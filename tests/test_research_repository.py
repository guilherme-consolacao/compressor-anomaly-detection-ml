import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import URL
from test_local_mysql import isolated_research_database as isolated_research_database

from compressor_anomaly_detection_ml.database import create_engine_for_url
from compressor_anomaly_detection_ml.database.research_repository import ResearchRepository
from compressor_anomaly_detection_ml.domain import DataValidationError

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.getenv("LOCAL_MYSQL_INTEGRATION") != "1", reason="Local MariaDB opt-in not supplied."
    ),
]


@pytest.fixture
def repository(isolated_research_database):
    with isolated_research_database.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        database = cursor.fetchone()[0]
    engine = create_engine_for_url(
        URL.create(
            "mysql+pymysql",
            username=os.getenv("LOCAL_MYSQL_ADMIN_USER", "root"),
            password=os.getenv("LOCAL_MYSQL_ADMIN_PASSWORD", ""),
            host="127.0.0.1",
            port=3306,
            database=database,
        )
    )
    try:
        yield ResearchRepository(engine)
    finally:
        engine.dispose()


def source(source_id="public", origin="public_measured"):
    return {
        "source_id": source_id,
        "source_version": "v1",
        "data_origin": origin,
        "title": "Artificial software fixture",
        "primary_url": "https://example.invalid",
        "license_name": "CC BY 4.0",
        "inspection_status": "inspected",
        "metadata_json": {"resource_kind": "dataset"},
        "created_at": datetime(2026, 1, 1),
    }


def observation(source_id="public", origin="public_measured"):
    return {
        "observation_id": "obs",
        "source_id": source_id,
        "source_version": "v1",
        "original_id": "source-row",
        "analysis_unit": "reading",
        "dependency_group_id": "group",
        "quality_status": "valid",
        "condition_json": {},
        "provenance_json": {
            "provenance_nodes": [
                {
                    "node_id": "root",
                    "source_id": source_id,
                    "source_version": "v1",
                    "data_origin": origin,
                    "parent_ids": [],
                }
            ]
        },
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }


def test_roundtrip_idempotence_and_conflict(repository):
    records = {"study_sources": [source()], "study_observations": [observation()]}
    assert repository.persist(records, scope="public")["created"] == 2
    assert repository.persist(records, scope="public")["unchanged"] == 2
    with pytest.raises(DataValidationError, match="Immutable"):
        repository.persist(
            {"study_observations": [{**observation(), "analysis_unit": "cycle"}]}, scope="public"
        )
    with repository.engine.connect() as connection:
        assert (
            connection.execute(
                select(repository.tables["study_observations"].c.analysis_unit)
            ).scalar_one()
            == "reading"
        )


def test_double_roundtrip_preserves_small_values_and_idempotence(repository):
    repository.persist(
        {
            "study_sources": [source()],
            "study_observations": [observation()],
            "study_runs": [
                {
                    "run_id": "double-test",
                    "stage": "test",
                    "data_scope": "public",
                    "status": "running",
                    "started_at": datetime(2026, 1, 1),
                    "configuration_json": {},
                    "input_manifest_json": {},
                }
            ],
        },
        scope="public",
    )
    expected = [1 / 3, 1e-14]
    records = {
        "study_feature_values": [
            {
                "observation_id": "obs",
                "feature_contract_version": "float-v1",
                "feature_name": str(i),
                "numeric_value": value,
                "unit": "1",
                "value_status": "derived",
                "definition_json": {},
                "run_id": "double-test",
            }
            for i, value in enumerate(expected)
        ]
    }
    assert repository.persist(records, scope="public")["created"] == 2
    assert repository.persist(records, scope="public")["unchanged"] == 2
    table = repository.tables["study_feature_values"]
    with repository.engine.connect() as connection:
        actual = list(
            connection.execute(
                select(table.c.numeric_value).order_by(table.c.feature_name)
            ).scalars()
        )
    assert actual == expected and all(isinstance(value, float) for value in actual)


def test_transaction_rolls_back_registered_source_when_child_is_invalid(repository):
    with pytest.raises(DataValidationError):
        repository.persist(
            {"study_sources": [source()], "study_observations": [observation("missing")]},
            scope="public",
        )
    with repository.engine.connect() as connection:
        assert connection.execute(select(repository.tables["study_sources"])).first() is None


def test_reserved_local_data_and_its_ancestry_are_rejected(repository):
    repository.persist(
        {"study_sources": [source(), source("ulisses", "ulisses_external")]}, scope="public"
    )
    with pytest.raises(DataValidationError, match="External"):
        repository.persist(
            {"study_observations": [observation("ulisses", "ulisses_external")]}, scope="public"
        )
    forged = observation()
    forged["provenance_json"] = observation("ulisses", "ulisses_external")["provenance_json"]
    with pytest.raises(DataValidationError):
        repository.persist({"study_observations": [forged]}, scope="public")
    assert (
        repository.persist(
            {"study_observations": [observation("ulisses", "ulisses_external")]}, scope="external"
        )["created"]
        == 1
    )


def test_dataset_requires_full_public_provenance_and_run_scope(repository):
    now = datetime(2026, 1, 1)
    repository.persist(
        {
            "study_runs": [
                {
                    "run_id": "run",
                    "stage": "research",
                    "data_scope": "public",
                    "status": "running",
                    "started_at": now,
                    "configuration_json": {},
                    "input_manifest_json": {},
                }
            ]
        },
        scope="public",
    )
    with pytest.raises(DataValidationError):
        repository.persist(
            {
                "study_datasets": [
                    {
                        "dataset_version": "bad",
                        "status": "research",
                        "manifest_sha256": "a" * 64,
                        "feature_contract_json": {},
                        "manifest_json": {},
                        "run_id": "run",
                        "created_at": now,
                    }
                ]
            },
            scope="public",
        )
    repository.finish_run("run", "completed")
    with pytest.raises(DataValidationError, match="running"):
        repository.finish_run("run", "completed")


def test_unknown_tables_and_nonfinite_values_are_rejected(repository):
    with pytest.raises(DataValidationError, match="restricted"):
        repository.persist({"readings": []}, scope="public")
    with pytest.raises(DataValidationError, match="finite"):
        repository.persist({"study_statistics": [{"numeric_value": float("nan")}]}, scope="public")
