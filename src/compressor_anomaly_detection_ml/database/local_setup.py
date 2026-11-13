"""Explicit administration of a new loopback-only development database.

This is separate from application startup. It never initializes an existing
database and never connects to the shared acquisition server.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

ROOT = Path(__file__).resolve().parents[3]
SQL_ROOT = ROOT / "database"
APP_USER = "compressor_ml_app"
READER_USER = "compressor_ml_metabase"
SCHEMA_VERSION = "002-reference-sources"


def validate_target(host: str, database: str) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Local setup requires an explicit loopback host.")
    if not re.fullmatch(r"compressor_ml_(?:dev|schema_verify_[0-9a-f]{8})", database):
        raise ValueError("Local setup accepts only project development/verification databases.")


def admin_connection(host: str, port: int, database: str | None = None):
    validate_target(host, database or "compressor_ml_dev")
    connection = pymysql.connect(
        host=host,
        port=port,
        user=os.getenv("LOCAL_MYSQL_ADMIN_USER", "root"),
        password=os.getenv("LOCAL_MYSQL_ADMIN_PASSWORD", ""),
        database=database,
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=30,
        write_timeout=30,
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")
    return connection


def execute_script(connection, sql: str) -> None:
    """Execute only this project's trusted SQL; no ad-hoc SQL splitting."""
    with connection.cursor() as cursor:
        cursor.execute(sql)
        while cursor.nextset():
            pass


def initialize(host: str, port: int, database: str, env_file: Path) -> dict:
    validate_target(host, database)
    if database != "compressor_ml_dev":
        raise ValueError("Initialization is restricted to compressor_ml_dev.")
    if env_file.exists():
        raise FileExistsError("Refusing to replace an existing environment file.")
    scripts = [
        SQL_ROOT / "local/001_acquisition.sql",
        SQL_ROOT / "001_ml_sidecars_proposal.sql",
        SQL_ROOT / "local/002_research.sql",
        SQL_ROOT / "local/003_metabase_views.sql",
    ]
    sql = [path.read_text(encoding="utf-8") for path in scripts]
    with admin_connection(host, port) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s",
                (database,),
            )
            if cursor.fetchone():
                raise ValueError("Refusing to initialize an existing database.")
            cursor.execute(
                "SELECT User FROM mysql.user WHERE User IN (%s,%s)",
                (APP_USER, READER_USER),
            )
            if cursor.fetchone():
                raise ValueError("Project accounts already exist; passwords will not be reset.")
            app_password, reader_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            # Save generated credentials before nontransactional DDL for recovery after failure.
            with env_file.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "# Local project database; generated secrets, never commit.\n"
                    f"DB_HOST={host}\nDB_PORT={port}\nDB_NAME={database}\n"
                    f"DB_USER={APP_USER}\nDB_PASSWORD={app_password}\n"
                    "# Metabase DATA SOURCE credentials, not its application metadata database.\n"
                    f"METABASE_SOURCE_HOST={host}\nMETABASE_SOURCE_PORT={port}\n"
                    f"METABASE_SOURCE_DATABASE={database}\n"
                    f"METABASE_SOURCE_USER={READER_USER}\n"
                    f"METABASE_SOURCE_PASSWORD={reader_password}\n"
                )
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{database}`")
        for statement in sql:
            execute_script(connection, statement)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO study_schema_versions VALUES (%s,%s,%s)",
                (
                    SCHEMA_VERSION,
                    hashlib.sha256("\n".join(sql).encode()).hexdigest(),
                    datetime.now(UTC).replace(tzinfo=None),
                ),
            )
            for user, password in ((APP_USER, app_password), (READER_USER, reader_password)):
                cursor.execute("CREATE USER %s@'localhost' IDENTIFIED BY %s", (user, password))
                cursor.execute(f"GRANT SELECT ON `{database}`.* TO %s@'localhost'", (user,))
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'",
                (database,),
            )
            for (table,) in cursor.fetchall():
                if table not in {"readings", "study_schema_versions"}:
                    cursor.execute(
                        f"GRANT INSERT, UPDATE ON `{database}`.`{table}` TO %s@'localhost'",
                        (APP_USER,),
                    )
    return {"database": database, "created": True, "credentials_file": str(env_file)}


def portable_dump(sql: str, database: str) -> str:
    validate_target("127.0.0.1", database)
    forbidden = (
        r"\b(?:INSERT\s+INTO|REPLACE\s+INTO|CREATE\s+USER|GRANT\s+|"
        r"(?:CREATE|DROP)\s+DATABASE|USE\s+|DELETE\s+FROM|UPDATE\s+`|TRUNCATE\s+)\b"
    )
    if re.search(forbidden, sql, re.I):
        raise ValueError("Schema-only export contains data or accounts.")
    sql = re.sub(r"\bDEFINER=`[^`]+`@`[^`]+`\s*", "", sql)
    # mysqldump qualifies view bodies with the original database name.
    sql = sql.replace(f"`{database}`.", "")
    return "-- Schema only; restore into a NEW EMPTY database. No users or data.\n" + sql


def client_environment() -> dict[str, str]:
    environment = dict(os.environ)
    password = os.getenv("LOCAL_MYSQL_ADMIN_PASSWORD")
    if password:
        environment["MYSQL_PWD"] = password
    else:
        environment.pop("MYSQL_PWD", None)
    return environment


def export_schema(host: str, port: int, database: str, dump_exe: Path, output: Path) -> dict:
    validate_target(host, database)
    if output.exists():
        raise FileExistsError("Choose a new schema export path; existing exports are preserved.")
    command = [
        str(dump_exe),
        "--no-defaults",
        f"--host={host}",
        f"--port={port}",
        f"--user={os.getenv('LOCAL_MYSQL_ADMIN_USER', 'root')}",
        "--no-data",
        "--skip-comments",
        "--skip-dump-date",
        "--skip-add-drop-table",
        "--skip-lock-tables",
        "--skip-add-locks",
        "--skip-triggers",
        "--default-character-set=utf8mb4",
        database,
    ]
    result = subprocess.run(command, capture_output=True, env=client_environment(), timeout=60)
    if result.returncode:
        raise RuntimeError("Schema export failed; credentials and driver output are not logged.")
    document = portable_dump(result.stdout.decode("utf-8"), database)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(document)
    return {"schema_file": str(output), "sha256": hashlib.sha256(document.encode()).hexdigest()}


def schema_signature(connection, database: str) -> dict:
    queries = {
        "tables": "SELECT TABLE_NAME,TABLE_TYPE,ENGINE FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",
        "columns": "SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA "
        "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s "
        "ORDER BY TABLE_NAME,ORDINAL_POSITION",
        "indexes": "SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=%s "
        "ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX",
        "foreign_keys": "SELECT TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,"
        "REFERENCED_COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION",
        "checks": "SELECT TABLE_NAME,CONSTRAINT_NAME,CHECK_CLAUSE "
        "FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=%s "
        "ORDER BY TABLE_NAME,CONSTRAINT_NAME",
        "views": "SELECT TABLE_NAME,VIEW_DEFINITION,SECURITY_TYPE "
        "FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",
    }
    signature = {}
    with connection.cursor() as cursor:
        for name, query in queries.items():
            cursor.execute(query, (database,))
            signature[name] = [
                [v.replace(f"`{database}`.", "") if isinstance(v, str) else v for v in row]
                for row in cursor.fetchall()
            ]
    return signature


def verify_restore(host: str, port: int, database: str, client_exe: Path, schema: Path) -> dict:
    validate_target(host, database)
    sql = schema.read_text(encoding="utf-8")
    portable_dump(sql, database)
    if re.search(r"\b(?:CREATE\s+DATABASE|USE\s+|DEFINER=)", sql, re.I):
        raise ValueError("Export must not select a database or embed a definer.")
    target = "compressor_ml_schema_verify_" + secrets.token_hex(4)
    created = False
    with admin_connection(host, port) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (target,),
                )
                if cursor.fetchone():
                    raise ValueError("Verification target must be new.")
                cursor.execute(
                    f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                created = True
            result = subprocess.run(
                [
                    str(client_exe),
                    "--no-defaults",
                    f"--host={host}",
                    f"--port={port}",
                    f"--user={os.getenv('LOCAL_MYSQL_ADMIN_USER', 'root')}",
                    "--default-character-set=utf8mb4",
                    target,
                ],
                input=sql.encode("utf-8"),
                capture_output=True,
                env=client_environment(),
                timeout=60,
            )
            if result.returncode:
                raise RuntimeError("Schema restoration failed; client output is not logged.")
            expected = schema_signature(connection, database)
            restored = schema_signature(connection, target)
            mismatches = [key for key in expected if expected[key] != restored[key]]
            if mismatches:
                raise ValueError("Restored schema differs: " + ", ".join(mismatches))
            with connection.cursor() as cursor:
                for name, table_type, _engine in restored["tables"]:
                    cursor.execute(f"SELECT COUNT(*) FROM `{target}`.`{name}`")
                    if cursor.fetchone()[0] != 0:
                        raise ValueError("Schema-only restore unexpectedly contains records.")
                    if table_type == "VIEW":
                        cursor.execute(f"SELECT * FROM `{target}`.`{name}` LIMIT 0")
            return {
                "schema_restored": True,
                "base_tables": sum(row[1] == "BASE TABLE" for row in restored["tables"]),
                "views": len(restored["views"]),
                "compared": list(expected),
                "all_restored_tables_empty": True,
                "verification_database_removed": True,
            }
        finally:
            if created:
                validate_target(host, target)
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE `{target}`")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--database", default="compressor_ml_dev")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--env-file", type=Path, default=ROOT / ".env")
    dump = sub.add_parser("export")
    dump.add_argument("--dump-exe", type=Path, required=True)
    dump.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--client-exe", type=Path, required=True)
    verify.add_argument("--schema-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            report = initialize(args.host, args.port, args.database, args.env_file)
        elif args.command == "export":
            report = export_schema(args.host, args.port, args.database, args.dump_exe, args.output)
        else:
            report = verify_restore(
                args.host, args.port, args.database, args.client_exe, args.schema_file
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except pymysql.MySQLError as exc:
        print(json.dumps({"error": "LocalDatabaseOperationFailed", "code": exc.args[0]}))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
