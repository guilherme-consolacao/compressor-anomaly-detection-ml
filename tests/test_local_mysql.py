"""Opt-in checks on loopback MariaDB; fixtures use a freshly created database.

LOCAL_MYSQL_INTEGRATION=1 enables creation/removal only of a unique project
verification database. The development database is consulted for permissions,
never populated by these tests.
"""

import json
import os
import secrets
from datetime import UTC, datetime

import pymysql
import pytest
from dotenv import dotenv_values

from compressor_anomaly_detection_ml.database.local_setup import (
    ROOT,
    admin_connection,
    execute_script,
    validate_target,
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.getenv("LOCAL_MYSQL_INTEGRATION") != "1", reason="Local MariaDB opt-in not supplied."
    ),
]


@pytest.fixture
def isolated_research_database():
    database = "compressor_ml_schema_verify_" + secrets.token_hex(4)
    validate_target("127.0.0.1", database)
    with admin_connection("127.0.0.1", 3306) as connection:
        created = False
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (database,),
                )
                assert cursor.fetchone() is None
                cursor.execute(
                    f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                created = True
                cursor.execute(f"USE `{database}`")
            execute_script(
                connection, (ROOT / "database/local/schema.sql").read_text(encoding="utf-8")
            )
            yield connection
        finally:
            if created:
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE `{database}`")


def test_research_constraints_views_and_external_denominators(isolated_research_database):
    connection = isolated_research_database
    now = datetime.now(UTC).replace(tzinfo=None)
    with connection.cursor() as cursor:
        for source, origin in (
            ("public_fixture", "public_measured"),
            ("local_fixture", "ulisses_external"),
        ):
            cursor.execute(
                "INSERT INTO study_sources VALUES (%s,'v1',%s,'Artificial fixture',"
                "'https://example.invalid',NULL,'inspected','{}',%s)",
                (source, origin, now),
            )
        cursor.execute(
            "INSERT INTO study_runs (run_id,stage,data_scope,status,started_at,"
            "configuration_json,input_manifest_json) VALUES "
            "('fixture-run','software_test','synthetic_test','completed',%s,'{}','[]')",
            (now,),
        )
        for index in range(8):
            source = "public_fixture" if index < 2 else "local_fixture"
            cursor.execute(
                "INSERT INTO study_observations (observation_id,source_id,source_version,"
                "original_id,analysis_unit,dependency_group_id,quality_status,condition_json,"
                "provenance_json,created_at) VALUES "
                "(%s,%s,'v1',%s,'reading',%s,'valid','{}','{}',%s)",
                (f"obs-{index}", source, str(index), f"group-{index}", now),
            )
        for index in range(2):
            cursor.execute(
                "INSERT INTO study_labels (observation_id,label_version,target_label,"
                "label_status,method,evidence_json,recorded_at) VALUES "
                "(%s,'label-v1',%s,'reference','artificial test fixture','{}',%s)",
                (f"obs-{index}", index, now),
            )
        cursor.execute("SELECT label_id FROM study_labels WHERE observation_id='obs-0'")
        label_zero = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO study_datasets VALUES "
            "('dataset-v1','research',%s,'{}','{}','fixture-run',%s)",
            ("a" * 64, now),
        )
        cursor.execute(
            "INSERT INTO study_dataset_members VALUES ('dataset-v1','obs-0',%s,'train','group-0')",
            (label_zero,),
        )
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute(
                "INSERT INTO study_dataset_members VALUES "
                "('dataset-v1','obs-1',%s,'test','group-1')",
                (label_zero,),
            )
        with pytest.raises(pymysql.MySQLError):
            cursor.execute(
                "INSERT INTO study_feature_values VALUES "
                "('obs-0','contract-v1','invalid',1,'g','missing','{}','fixture-run')"
            )
        cursor.execute(
            "INSERT INTO study_feature_values VALUES "
            "('obs-0','contract-v1','temperature',25,'degC','observed','{}','fixture-run')"
        )
        cursor.execute(
            "INSERT INTO study_statistics (run_id,statistic_key,source_id,source_version,"
            "statistic_name,feature_name,numeric_value,sample_count,group_count,dimensions_json) "
            "VALUES ('fixture-run','temp-mean','public_fixture','v1',"
            "'mean','temperature',25,1,1,'{}')"
        )
        cursor.execute("INSERT INTO study_clusters VALUES ('fixture-run','obs-0','-1',1,0.7,'{}')")
        document = {"metrics": {"accuracy": None, "precision": None, "recall": None, "f1": None}}
        cursor.execute(
            "INSERT INTO ml_models (name,version,processing_version,document) "
            "VALUES ('artificial-fixture','v1','fixture-contract',%s)",
            (json.dumps(document),),
        )
        model_id = cursor.lastrowid
        cursor.execute("SELECT accuracy,`precision`,recall,f1 FROM mb_ml_models")
        assert cursor.fetchone() == (None, None, None, None)
        examples = [
            (1, 1, "classified"),
            (0, 0, "classified"),
            (0, 1, "classified"),
            (1, 0, "classified"),
            (0, None, "invalid_input"),
            (None, 1, "classified"),
        ]
        for offset, (truth, predicted, status) in enumerate(examples, 2):
            case = f"case-{offset}"
            cursor.execute(
                "INSERT INTO study_external_cases VALUES (%s,%s,'campaign-fixture',%s,'{}')",
                (case, f"obs-{offset}", "b" * 64),
            )
            cursor.execute(
                "INSERT INTO study_external_ground_truth VALUES (%s,'v1',%s,%s,'fixture',%s,'{}')",
                (case, truth, "confirmed" if truth is not None else "indeterminate", now),
            )
            cursor.execute(
                "INSERT INTO study_external_predictions VALUES "
                "(%s,%s,'fixture-run','v1',%s,%s,%s,%s,%s,%s)",
                (
                    case,
                    model_id,
                    status,
                    predicted,
                    None if predicted is None else 0.6,
                    "c" * 64,
                    now,
                    "fixture rejection" if predicted is None else None,
                ),
            )
        # A later reference revision must not change the pinned evaluation.
        cursor.execute(
            "INSERT INTO study_external_ground_truth VALUES "
            "('case-2','v2',0,'confirmed','fixture',%s,'{}')",
            (now,),
        )
        cursor.execute("SELECT COUNT(*) FROM mb_external_predictions")
        assert cursor.fetchone()[0] == 6
        cursor.execute(
            "SELECT processed_count,classified_count,evaluated_count,tp,tn,fp,fn,accuracy,"
            "classification_coverage FROM mb_external_metrics"
        )
        result = cursor.fetchone()
        assert tuple(map(int, result[:7])) == (6, 5, 4, 1, 1, 1, 1)
        assert float(result[7]) == pytest.approx(0.5)
        assert float(result[8]) == pytest.approx(5 / 6, abs=1e-4)
        for view in (
            "mb_study_inventory",
            "mb_study_feature_values",
            "mb_study_labels",
            "mb_study_statistics",
            "mb_study_clusters",
            "mb_study_dataset_members",
        ):
            cursor.execute(f"SELECT COUNT(*) FROM `{view}`")
            assert cursor.fetchone()[0] > 0
        cursor.execute("SELECT COUNT(*) FROM readings")
        assert cursor.fetchone()[0] == 0


def test_local_reader_and_application_privileges():
    values = dotenv_values(ROOT / ".env")
    for reader in (True, False):
        user_key = "METABASE_SOURCE_USER" if reader else "DB_USER"
        password_key = "METABASE_SOURCE_PASSWORD" if reader else "DB_PASSWORD"
        with pymysql.connect(
            host="127.0.0.1",
            port=3306,
            user=values[user_key],
            password=values[password_key],
            database="compressor_ml_dev",
            connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM mb_study_inventory")
                # Ingestion grows the inventory; this checks SELECT permission.
                assert cursor.fetchone()[0] >= 0
                with pytest.raises(pymysql.MySQLError) as denied:
                    cursor.execute("UPDATE readings SET temperature=temperature WHERE id=0")
                assert denied.value.args[0] in (1142, 1143)
                with pytest.raises(pymysql.MySQLError) as denied:
                    cursor.execute("CREATE TEMPORARY TABLE permission_probe (id INTEGER)")
                assert denied.value.args[0] in (1044, 1142, 1143)
                if reader:
                    with pytest.raises(pymysql.MySQLError) as denied:
                        cursor.execute("DELETE FROM study_runs WHERE 1=0")
                    assert denied.value.args[0] in (1142, 1143)
                cursor.execute("SHOW GRANTS")
                # Never print grant text: MariaDB can include password hashes in it.
                privileges = [
                    row[0].split(" ON ", 1)[0].removeprefix("GRANT ") for row in cursor.fetchall()
                ]
                assert all(p in {"USAGE", "SELECT", "INSERT, UPDATE"} for p in privileges)
