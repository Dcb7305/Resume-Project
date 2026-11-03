"""
Tests for sql/02_clean.sql (builds clean_data from "Raw Data").

Each test runs the real SQL file on a local SQLite copy of the data
(see tests/conftest.py), then checks clean_data.
"""
from conftest import RAW_NAMES

EXPECTED_COLUMNS = [
    "row_id",
    "incoming_calls",
    "answered_calls",
    "abandoned_calls",
    "answer_rate",
    "avg_answer_speed_sec",
    "avg_talk_duration_sec",
    "avg_waiting_time_sec",
    "service_level_20s",
]


def raw(index=1, incoming=100, answered=90, **extra):
    """A valid raw row (keyed by RAW_NAMES). Change Index/counts via arguments;
    pass other raw columns by name with **{"Column Name": value}."""
    row = {
        "Index": index,
        "Incoming Calls": incoming,
        "Answered Calls": answered,
        "Answer Rate": 0.90,
        "Abandoned Calls": 10,
        "Answer Speed _AVG_": "00:00:17",
        "Talk Duration _AVG_": "00:02:14",
        "Waiting Time _AVG_": "00:02:45",
        "Service Level _20 Seconds_": 0.75,
    }
    for name in extra:
        assert name in RAW_NAMES, f"unknown raw column: {name}"
    row.update(extra)
    return row


def clean_rows(con):
    """All rows of clean_data as dicts, ordered by row_id."""
    cur = con.execute("SELECT * FROM clean_data ORDER BY row_id")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------- shape ----------

def test_output_columns_names_and_order(raw_db, run_sql):
    """clean_data has exactly the 9 snake_case columns, in the documented order."""
    run_sql(raw_db, "02_clean.sql")
    cur = raw_db.execute("SELECT * FROM clean_data LIMIT 0")
    assert [d[0] for d in cur.description] == EXPECTED_COLUMNS


def test_no_rows_dropped_on_real_data(raw_db, run_sql):
    """The real data has no bad rows, so all 1,251 rows survive cleaning."""
    run_sql(raw_db, "02_clean.sql")
    assert raw_db.execute("SELECT COUNT(*) FROM clean_data").fetchone()[0] == 1251


def test_row_ids_are_unique_and_match_raw(raw_db, run_sql):
    """Every raw Index shows up exactly once as row_id (nothing duplicated or lost)."""
    run_sql(raw_db, "02_clean.sql")
    raw_ids = {r[0] for r in raw_db.execute('SELECT "Index" FROM "Raw Data"')}
    clean_ids = [r[0] for r in raw_db.execute("SELECT row_id FROM clean_data")]
    assert len(clean_ids) == len(set(clean_ids))
    assert set(clean_ids) == raw_ids


# ---------- time -> seconds ----------

def test_known_seconds_for_row_1(raw_db, run_sql):
    """Row 1's HH:MM:SS times convert to the known second values (17, 134, 165)."""
    run_sql(raw_db, "02_clean.sql")
    row = raw_db.execute(
        "SELECT avg_answer_speed_sec, avg_talk_duration_sec, avg_waiting_time_sec "
        "FROM clean_data WHERE row_id = 1"
    ).fetchone()
    assert row == (17, 134, 165)


def test_time_conversion_includes_hours(make_raw_db, run_sql):
    """Hours and minutes count too: '01:02:03' -> 3723 seconds, '00:00:00' -> 0."""
    con = make_raw_db([raw(**{
        "Answer Speed _AVG_": "01:02:03",
        "Talk Duration _AVG_": "00:00:00",
        "Waiting Time _AVG_": "23:59:59",
    })])
    run_sql(con, "02_clean.sql")
    row = clean_rows(con)[0]
    assert row["avg_answer_speed_sec"] == 3723
    assert row["avg_talk_duration_sec"] == 0
    assert row["avg_waiting_time_sec"] == 86399


# ---------- values pass through ----------

def test_values_pass_through_unchanged(raw_db, run_sql, csv_rows):
    """Counts, answer_rate and service level are copied as-is for every real row."""
    run_sql(raw_db, "02_clean.sql")
    by_id = {r["row_id"]: r for r in clean_rows(raw_db)}
    for src in csv_rows:
        out = by_id[src["Index"]]
        assert out["incoming_calls"] == src["Incoming Calls"]
        assert out["answered_calls"] == src["Answered Calls"]
        assert out["abandoned_calls"] == src["Abandoned Calls"]
        assert out["answer_rate"] == src["Answer Rate"]
        assert out["service_level_20s"] == src["Service Level _20 Seconds_"]


# ---------- row filters ----------

def test_answered_greater_than_incoming_is_dropped(make_raw_db, run_sql):
    """A row claiming more answered calls than incoming calls is impossible and is removed."""
    con = make_raw_db([
        raw(index=1, incoming=100, answered=90),   # good
        raw(index=2, incoming=50, answered=51),    # bad: 51 > 50
    ])
    run_sql(con, "02_clean.sql")
    assert [r["row_id"] for r in clean_rows(con)] == [1]


def test_answered_equal_to_incoming_is_kept(make_raw_db, run_sql):
    """Boundary: answering every call (answered == incoming) is valid and kept (<=, not <)."""
    con = make_raw_db([raw(index=7, incoming=40, answered=40)])
    run_sql(con, "02_clean.sql")
    rows = clean_rows(con)
    assert len(rows) == 1
    assert rows[0]["row_id"] == 7


def test_null_index_is_dropped(make_raw_db, run_sql):
    """A row with no Index can't be identified, so it is removed."""
    con = make_raw_db([
        raw(index=1),
        raw(index=None),
    ])
    run_sql(con, "02_clean.sql")
    rows = clean_rows(con)
    assert [r["row_id"] for r in rows] == [1]


def test_only_bad_rows_are_dropped_from_a_mix(make_raw_db, run_sql):
    """With good and bad rows mixed together, exactly the bad ones disappear."""
    con = make_raw_db([
        raw(index=1, incoming=10, answered=5),
        raw(index=None, incoming=10, answered=5),   # NULL Index
        raw(index=3, incoming=10, answered=11),     # answered > incoming
        raw(index=4, incoming=0, answered=0),       # boundary, kept
        raw(index=5, incoming=10, answered=10),     # boundary, kept
    ])
    run_sql(con, "02_clean.sql")
    assert [r["row_id"] for r in clean_rows(con)] == [1, 4, 5]


# ---------- re-running ----------

def test_running_twice_does_not_duplicate_rows(raw_db, run_sql):
    """CREATE OR REPLACE rebuilds the table, so a second run still gives 1,251 rows."""
    run_sql(raw_db, "02_clean.sql")
    run_sql(raw_db, "02_clean.sql")
    assert raw_db.execute("SELECT COUNT(*) FROM clean_data").fetchone()[0] == 1251
