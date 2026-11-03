"""
Shared test harness: runs the BigQuery SQL files in sql/ locally on SQLite.

BigQuery isn't available in a test run, so this file:
  1. Loads data into an in-memory SQLite table named "Raw Data", shaped the way
     BigQuery loaded it (snake-ish column names, Answer Rate as a decimal,
     time columns as HH:MM:SS).
  2. Translates the few BigQuery-only bits the SQL files use
     (COUNTIF, TIME_DIFF, SAFE_DIVIDE, CREATE OR REPLACE, project-qualified names,
     INFORMATION_SCHEMA) into SQLite equivalents.
  3. Runs each statement in a file and returns its results, in order.

Fixtures:
  raw_db        - connection with the real "Call Center Data.csv" loaded
  make_raw_db   - factory: make_raw_db(rows) -> connection with your own rows
  run_sql       - run_sql(con, "02_clean.sql") -> list of results (one per statement)
"""
import csv
import re
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SQL_DIR = REPO / "sql"
CSV_PATH = REPO / "Call Center Data.csv"

RAW_COLUMNS = [
    ("Index", "INTEGER"),
    ("Incoming Calls", "INTEGER"),
    ("Answered Calls", "INTEGER"),
    ("Answer Rate", "REAL"),
    ("Abandoned Calls", "INTEGER"),
    ("Answer Speed _AVG_", "TIME"),
    ("Talk Duration _AVG_", "TIME"),
    ("Waiting Time _AVG_", "TIME"),
    ("Service Level _20 Seconds_", "REAL"),
]
RAW_NAMES = [name for name, _ in RAW_COLUMNS]


# ---------- SQLite stand-ins for BigQuery functions ----------

class _CountIf:
    def __init__(self):
        self.n = 0

    def step(self, value):
        if value:
            self.n += 1

    def finalize(self):
        return self.n


def _to_seconds(t):
    if t is None:
        return None
    h, m, s = (int(p) for p in str(t).split(":"))
    return h * 3600 + m * 60 + s


def _time_diff(a, b, unit):
    if a is None or b is None:
        return None
    if str(unit).upper() != "SECOND":
        raise ValueError(f"time_diff unit {unit} not supported in tests")
    return _to_seconds(a) - _to_seconds(b)


def _safe_divide(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def new_connection():
    con = sqlite3.connect(":memory:")
    con.create_aggregate("count_if", 1, _CountIf)
    con.create_function("time_diff", 3, _time_diff)
    con.create_function("safe_divide", 2, _safe_divide)
    return con


# ---------- loading data ----------

def _pct(value):
    """'94.01%' -> 0.9401 (BigQuery stored rates as decimals)."""
    return float(value.strip().rstrip("%")) / 100


def _normalize_time(value):
    """'0:00:17' -> '00:00:17'."""
    h, m, s = value.strip().split(":")
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def read_csv_rows():
    """The real CSV, converted to the BigQuery shape, as a list of dicts keyed by RAW_NAMES."""
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "Index": int(r["Index"]),
                "Incoming Calls": int(r["Incoming Calls"]),
                "Answered Calls": int(r["Answered Calls"]),
                "Answer Rate": _pct(r["Answer Rate"]),
                "Abandoned Calls": int(r["Abandoned Calls"]),
                "Answer Speed _AVG_": _normalize_time(r["Answer Speed (AVG)"]),
                "Talk Duration _AVG_": _normalize_time(r["Talk Duration (AVG)"]),
                "Waiting Time _AVG_": _normalize_time(r["Waiting Time (AVG)"]),
                "Service Level _20 Seconds_": _pct(r["Service Level (20 Seconds)"]),
            })
    return rows


def load_raw(con, rows):
    cols = ", ".join(f'"{n}" {t}' for n, t in RAW_COLUMNS)
    con.execute(f'CREATE TABLE "Raw Data" ({cols})')
    placeholders = ", ".join("?" for _ in RAW_NAMES)
    con.executemany(
        f'INSERT INTO "Raw Data" VALUES ({placeholders})',
        [tuple(r.get(n) for n in RAW_NAMES) for r in rows],
    )
    return con


# ---------- translating BigQuery SQL ----------

def _info_schema_subquery(con):
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()]
    parts = [
        f"SELECT '{t}' AS table_name, name AS column_name, type AS data_type, "
        f"cid + 1 AS ordinal_position FROM pragma_table_info('{t}')"
        for t in tables
    ]
    return "(" + " UNION ALL ".join(parts) + ")"


def translate(sql, con):
    sql = re.sub(r"`[^`]*\.INFORMATION_SCHEMA\.COLUMNS`",
                 lambda _: _info_schema_subquery(con), sql)
    sql = re.sub(r"`call-center-analysis-cb\.call_center\.([^`]+)`", r'"\1"', sql)
    sql = re.sub(r"`([^`]+)`", r'"\1"', sql)
    sql = re.sub(r"\bCOUNTIF\s*\(", "count_if(", sql, flags=re.I)
    sql = re.sub(r"\bTIME\s+'([^']*)'", r"'\1'", sql)
    sql = re.sub(r",\s*SECOND\s*\)", ", 'SECOND')", sql)
    sql = re.sub(r'CREATE\s+OR\s+REPLACE\s+TABLE\s+("[^"]+"|\w+)',
                 r"DROP TABLE IF EXISTS \1;\nCREATE TABLE \1", sql, count=1, flags=re.I)
    return sql


def split_statements(text):
    """Split a .sql file on ';' and drop chunks that are only comments/blank."""
    out = []
    for chunk in text.split(";"):
        code = "\n".join(l for l in chunk.splitlines() if not l.strip().startswith("--"))
        if code.strip():
            out.append(chunk)
    return out


class Result:
    """Columns + rows for one statement. result[0]['col'] gives a value."""

    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = [dict(zip(columns, r)) for r in rows]

    def __getitem__(self, i):
        return self.rows[i]

    def __len__(self):
        return len(self.rows)


def run_sql_file(con, filename):
    text = (SQL_DIR / filename).read_text(encoding="utf-8")
    results = []
    for stmt in split_statements(text):
        sql = translate(stmt, con)
        if "DROP TABLE IF EXISTS" in sql:
            con.executescript(sql)  # CREATE OR REPLACE became two statements
            results.append(Result([], []))
            continue
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        results.append(Result(cols, cur.fetchall() if cols else []))
    return results


# ---------- fixtures ----------

@pytest.fixture
def csv_rows():
    return read_csv_rows()


@pytest.fixture
def raw_db(csv_rows):
    con = load_raw(new_connection(), csv_rows)
    yield con
    con.close()


@pytest.fixture
def make_raw_db():
    cons = []

    def _make(rows):
        con = load_raw(new_connection(), rows)
        cons.append(con)
        return con

    yield _make
    for c in cons:
        c.close()


@pytest.fixture
def run_sql():
    return run_sql_file
