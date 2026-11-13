"""Install the PI IV result tables and dashboard on the local instance."""

import csv
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pymysql
from dotenv import dotenv_values

PRIVATE = Path("reports/private")
RUNTIME = PRIVATE / "metabase-runtime"
URL = "http://127.0.0.1:3000"
SCHEMA = "compressor_ml_delivery_pi4"
READER = "compressor_pi4_reader"
DATABASE_NAME = "PI IV - Resultados de validação"
DASHBOARD_NAME = "PI IV | Detecção de anomalias em refrigeração"
METHODS = {
    "persistence_c": "Última temperatura",
    "trend_c": "Tendência recente",
    "public_c": "Random Forest pública TRI-HP",
    "adapted_c": "Modelo ajustado ao protótipo",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def credentials():
    path = RUNTIME / "credentials.json"
    if not path.exists():
        data = {
            "email": "entrega@compressor.local",
            "password": secrets.token_urlsafe(30) + "Aa1!",
            "database_reader_password": secrets.token_urlsafe(32),
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return read_json(path)


def result_tables():
    run = PRIVATE / "ulisses-temperature-v2"
    thermal = read_json(run / "summary.json")["historical_test"]
    gaps = read_json(PRIVATE / "ulisses-time-gap-20261008/sensitivity.json")["results"]
    test_path = Path("reports/research/cycle-freeze-8af6bb44817d037a836c/public-test/summary.json")
    public = read_json(test_path)["by_source"]
    with (run / "predictions.csv").open(encoding="utf-8", newline="") as file:
        series = [
            (
                datetime.fromisoformat(row["observed_at"]).replace(tzinfo=None),
                *[float(row[key]) for key in ("observed_c", "adapted_c", "lower_c", "upper_c")],
                int(row["outside_band"] == "True"),
            )
            for row in csv.DictReader(file)
        ]
    assert len(series) == thermal["cases"] == 432 and sum(row[-1] for row in series) == 41
    assert len(gaps) == 18
    return {
        "temperature_forecasts": (
            "observed_at DATETIME PRIMARY KEY, observed_c DOUBLE, predicted_c DOUBLE, "
            "lower_c DOUBLE, upper_c DOUBLE, outside_band TINYINT",
            series,
        ),
        "temperature_errors": (
            "method VARCHAR(80) PRIMARY KEY, cases INT, mae_c DOUBLE, rmse_c DOUBLE",
            [
                (
                    label,
                    thermal["cases"],
                    thermal["metrics"][key]["mae_c"],
                    thermal["metrics"][key]["rmse_c"],
                )
                for key, label in METHODS.items()
            ],
        ),
        "telemetry_gaps": (
            "gap_seconds INT PRIMARY KEY, measurements INT, scored INT, alerts INT",
            [
                tuple(row[key] for key in ("gap_seconds", "measurements", "scored", "alerts"))
                for row in gaps
            ],
        ),
        "public_cycle_test": (
            "source VARCHAR(40) PRIMARY KEY, tp INT, fn INT, fp INT, tn INT",
            [
                (label, *[public[key][field] for field in ("tp", "fn", "fp", "tn")])
                for key, label in (("smart_pdm", "SMART-PDM"), ("tri_hp_faults", "TRI-HP"))
            ],
        ),
    }


def load_mariadb(secret):
    tables = result_tables()
    env = {**dotenv_values(), **os.environ}
    local = {"host": "127.0.0.1", "port": 3306, "charset": "utf8mb4", "connect_timeout": 5}
    with pymysql.connect(
        **local,
        user=env.get("LOCAL_MYSQL_ADMIN_USER", "root"),
        password=env.get("LOCAL_MYSQL_ADMIN_PASSWORD", ""),
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{SCHEMA}` CHARACTER SET utf8mb4")
            cursor.execute(f"USE `{SCHEMA}`")
            cursor.execute("SHOW TABLES")
            if set(row[0] for row in cursor.fetchall()) - tables.keys():
                raise RuntimeError("Unexpected tables found in the reserved delivery schema.")
            for table, (ddl, rows) in tables.items():
                cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table}` ({ddl}) ENGINE=InnoDB")
                placeholders = ", ".join(["%s"] * len(rows[0]))
                cursor.executemany(f"REPLACE INTO `{table}` VALUES ({placeholders})", rows)
            connection.commit()
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{READER}'@'127.0.0.1' IDENTIFIED BY %s", (secret,)
            )
            cursor.execute(f"GRANT SELECT ON `{SCHEMA}`.* TO '{READER}'@'127.0.0.1'")
    with pymysql.connect(**local, user=READER, password=secret, database=SCHEMA) as connection:
        with connection.cursor() as cursor:
            for table, (_, rows) in tables.items():
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                assert cursor.fetchone()[0] == len(rows)
    print("MariaDB: 432 previsões, 4 métodos, 18 cortes e 2 fontes públicas.", flush=True)


def api(method, path, data=None, session=None):
    headers = {"Content-Type": "application/json"}
    if session:
        headers["X-Metabase-Session"] = session
    request = Request(
        URL + path,
        method=method,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        with urlopen(request, timeout=35) as response:
            return json.loads(response.read() or b"null")
    except HTTPError as error:
        raise RuntimeError(f"Metabase {method} {path}: HTTP {error.code}") from None


def setup(secret):
    for _ in range(36):
        try:
            if api("GET", "/api/health")["status"] == "ok":
                break
        except (URLError, RuntimeError):
            pass
        time.sleep(5)
    else:
        raise RuntimeError("Metabase did not become ready. Check the local logs.")
    props = api("GET", "/api/session/properties")
    if props.get("has-user-setup"):
        auth = api(
            "POST", "/api/session", {"username": secret["email"], "password": secret["password"]}
        )
    else:
        auth = api(
            "POST",
            "/api/setup",
            {
                "token": props["setup-token"],
                "user": {
                    "email": secret["email"],
                    "password": secret["password"],
                    "first_name": "Projeto",
                    "last_name": "Integrador IV",
                },
                "prefs": {
                    "site_name": "Projeto Integrador IV",
                    "site_locale": "pt_BR",
                    "allow_tracking": False,
                },
            },
        )
    return auth["id"], props.get("version", {}).get("tag")


def dashboard(secret, session, version):
    databases = api("GET", "/api/database", session=session)["data"]
    database = next((row for row in databases if row["name"] == DATABASE_NAME), None)
    if database is None:
        database = api(
            "POST",
            "/api/database",
            {
                "name": DATABASE_NAME,
                "engine": "mysql",
                "details": {
                    "host": "127.0.0.1",
                    "port": 3306,
                    "dbname": SCHEMA,
                    "user": READER,
                    "password": secret,
                    "ssl": False,
                },
            },
            session,
        )
    boards = api("GET", "/api/dashboard", session=session)
    board = next((row for row in boards if row["name"] == DASHBOARD_NAME), None)
    if board is None:
        board = api(
            "POST",
            "/api/dashboard",
            {
                "name": DASHBOARD_NAME,
                "description": "Teste público de ciclos e ensaios com registros do protótipo. "
                "A faixa térmica sinaliza desvios de previsão para revisão.",
            },
            session,
        )
    cards = {row["name"]: row for row in api("GET", "/api/card", session=session)}
    definitions = [
        (
            "Erro de previsão térmica (°C)",
            "bar",
            "Método",
            ["Erro médio (°C)"],
            "SELECT method AS `Método`, mae_c AS `Erro médio (°C)` "
            "FROM temperature_errors ORDER BY mae_c",
            4,
        ),
        (
            "Alertas por limite de pausa",
            "line",
            "Limite (s)",
            ["Medições pontuadas", "Alertas"],
            "SELECT gap_seconds AS `Limite (s)`, scored AS `Medições pontuadas`, alerts AS Alertas "
            "FROM telemetry_gaps ORDER BY gap_seconds",
            18,
        ),
        (
            "Temperatura medida e prevista (UTC)",
            "line",
            "Horário (UTC)",
            ["Medida (°C)", "Prevista (°C)"],
            "SELECT observed_at AS `Horário (UTC)`, observed_c AS `Medida (°C)`, "
            "predicted_c AS `Prevista (°C)` FROM temperature_forecasts ORDER BY observed_at",
            432,
        ),
        (
            "Teste público da Random Forest por ciclos",
            "table",
            None,
            [],
            "SELECT source AS Base, tp AS Detectados, fn AS Perdidos, fp AS Falsos_alertas, "
            "tn AS Normais_corretos FROM public_cycle_test ORDER BY source",
            2,
        ),
        (
            "Leituras fora da faixa prevista",
            "scalar",
            None,
            [],
            "SELECT SUM(outside_band) AS fora_da_faixa FROM temperature_forecasts",
            1,
        ),
    ]
    checks = []
    current = api("GET", f"/api/dashboard/{board['id']}", session=session)["dashcards"]
    on_board = {row.get("card_id") for row in current}
    layout = [(0, 0, 12, 6), (0, 12, 12, 6), (6, 0, 24, 7), (13, 0, 16, 5), (13, 16, 8, 5)]
    for index, (name, display, dimension, series, sql, expected_rows) in enumerate(definitions):
        card = cards.get(name)
        if card is None and display == "scalar":
            card = cards.get("Previsões térmicas fora da faixa")
        options = {"graph.dimensions": [dimension], "graph.metrics": series} if dimension else {}
        payload = {
            "name": name,
            "type": "question",
            "display": display,
            "visualization_settings": options,
            "dataset_query": {
                "database": database["id"],
                "type": "native",
                "native": {"query": sql},
            },
        }
        card = (
            api("POST", "/api/card", payload, session)
            if card is None
            else api("PUT", f"/api/card/{card['id']}", payload, session)
        )
        result = api("POST", f"/api/card/{card['id']}/query", {}, session)
        assert result["status"] == "completed" and len(result["data"]["rows"]) == expected_rows, (
            name
        )
        checks.append({"name": name, "card_id": card["id"], "rows_verified": expected_rows})
        if card["id"] not in on_board:
            row, col, width, height = layout[index]
            current.append(
                {
                    "id": -index - 1,
                    "card_id": card["id"],
                    "row": row,
                    "col": col,
                    "size_x": width,
                    "size_y": height,
                }
            )
    api("PUT", f"/api/dashboard/{board['id']}", {"dashcards": current}, session)
    verified = api("GET", f"/api/dashboard/{board['id']}", session=session)
    assert {check["card_id"] for check in checks} <= {r["card_id"] for r in verified["dashcards"]}
    return {
        "url": f"{URL}/dashboard/{board['id']}",
        "metabase_version": version,
        "database_schema": SCHEMA,
        "cards": checks,
    }


def main():
    secret = credentials()
    load_mariadb(secret["database_reader_password"])
    session, version = setup(secret)
    result = dashboard(secret["database_reader_password"], session, version)
    (RUNTIME / "dashboard.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
