"""
Tests for sql/03_validate.sql.

These tests do NOT run 02_clean.sql. Instead each test builds its own clean_data
table (a faithful copy of "Raw Data"), optionally breaks it on purpose, and then
checks that the 7 validation queries notice the problem.

Result order (one per SELECT in the file):
  0 row count   1 totals   2 answered+abandoned=incoming   3 answer rate
  4 keys/nulls  5 row 1 time conversion   6 ranges
"""
import pytest

from conftest import RAW_NAMES

CLEAN_COLUMNS = [
    "row_id", "incoming_calls", "answered_calls", "abandoned_calls", "answer_rate",
    "avg_answer_speed_sec", "avg_talk_duration_sec", "avg_waiting_time_sec",
    "service_level_20s",
]


def to_seconds(hms):
    h, m, s = (int(p) for p in hms.split(":"))
    return h * 3600 + m * 60 + s


def clean_rows_from_raw(raw_rows):
    """Straight copy of raw rows into the clean_data shape (times -> seconds)."""
    return [
        {
            "row_id": r["Index"],
            "incoming_calls": r["Incoming Calls"],
            "answered_calls": r["Answered Calls"],
            "abandoned_calls": r["Abandoned Calls"],
            "answer_rate": r["Answer Rate"],
            "avg_answer_speed_sec": to_seconds(r["Answer Speed _AVG_"]),
            "avg_talk_duration_sec": to_seconds(r["Talk Duration _AVG_"]),
            "avg_waiting_time_sec": to_seconds(r["Waiting Time _AVG_"]),
            "service_level_20s": r["Service Level _20 Seconds_"],
        }
        for r in raw_rows
    ]


def build_clean(con, rows):
    """Create clean_data in `con` and fill it with `rows` (list of dicts)."""
    con.execute(
        "CREATE TABLE clean_data (row_id INTEGER, incoming_calls INTEGER, "
        "answered_calls INTEGER, abandoned_calls INTEGER, answer_rate REAL, "
        "avg_answer_speed_sec INTEGER, avg_talk_duration_sec INTEGER, "
        "avg_waiting_time_sec INTEGER, service_level_20s REAL)"
    )
    con.executemany(
        f"INSERT INTO clean_data VALUES ({', '.join('?' for _ in CLEAN_COLUMNS)})",
        [tuple(r[c] for c in CLEAN_COLUMNS) for r in rows],
    )
    return con


def raw_row(index, incoming=100, answered=90, abandoned=10, rate=None):
    """One small, internally consistent raw row (rate defaults to answered/incoming)."""
    if rate is None:
        rate = answered / incoming if incoming else 0.0
    return {
        "Index": index,
        "Incoming Calls": incoming,
        "Answered Calls": answered,
        "Answer Rate": rate,
        "Abandoned Calls": abandoned,
        "Answer Speed _AVG_": "00:00:17",
        "Talk Duration _AVG_": "00:02:14",
        "Waiting Time _AVG_": "00:02:45",
        "Service Level _20 Seconds_": 0.75,
    }


@pytest.fixture
def small(make_raw_db):
    """A 3-row raw table plus a faithful clean copy you can edit before building."""
    raws = [raw_row(1), raw_row(2, 200, 150, 50), raw_row(3, 50, 40, 10)]
    con = make_raw_db(raws)
    return con, clean_rows_from_raw(raws)


# ---------- happy path on the real data ----------

def test_real_data_all_checks_pass(raw_db, csv_rows, run_sql):
    """With a faithful clean_data, every check on the real CSV returns its 'expected' value."""
    build_clean(raw_db, clean_rows_from_raw(csv_rows))
    res = run_sql(raw_db, "03_validate.sql")
    assert len(res) == 7

    assert res[0][0]["rows_dropped"] == 0
    assert res[0][0]["raw_rows"] == res[0][0]["clean_rows"] == 1251

    t = res[1][0]
    assert (t["raw_incoming"], t["raw_answered"], t["raw_abandoned"]) == (248373, 221234, 27139)
    assert (t["clean_incoming"], t["clean_answered"], t["clean_abandoned"]) == (248373, 221234, 27139)

    assert res[2][0]["mismatched_rows"] == 0
    assert res[3][0]["off_rate_rows"] == 0

    k = res[4][0]
    assert k["total_rows"] == k["distinct_ids"] == 1251
    assert k["rows_with_nulls"] == 0

    r1 = res[5][0]
    assert (r1["avg_answer_speed_sec"], r1["avg_talk_duration_sec"], r1["avg_waiting_time_sec"]) == (17, 134, 165)

    rng = res[6][0]
    assert rng["min_incoming"] >= 0 and rng["min_waiting_sec"] >= 0
    assert 0 <= rng["min_answer_rate"] <= rng["max_answer_rate"] <= 1
    assert 0 <= rng["min_service_level"] <= rng["max_service_level"] <= 1


# ---------- does each check catch a real problem? ----------

def test_dropped_row_is_caught(small, run_sql):
    """Losing one row during cleaning shows up as rows_dropped = 1 and mismatched totals."""
    con, clean = small
    build_clean(con, clean[:-1])  # drop row 3 (50 incoming)
    res = run_sql(con, "03_validate.sql")
    assert res[0][0]["rows_dropped"] == 1
    t = res[1][0]
    assert t["raw_incoming"] - t["clean_incoming"] == 50
    assert t["raw_answered"] != t["clean_answered"]


def test_changed_value_breaks_totals(small, run_sql):
    """Even with no rows lost, a changed number makes the totals check disagree."""
    con, clean = small
    clean[0]["abandoned_calls"] += 5
    build_clean(con, clean)
    t = run_sql(con, "03_validate.sql")[1][0]
    assert t["clean_abandoned"] == t["raw_abandoned"] + 5


def test_answered_plus_abandoned_mismatch_is_caught(small, run_sql):
    """A row where answered + abandoned != incoming is counted in mismatched_rows."""
    con, clean = small
    clean[1]["abandoned_calls"] = 49  # 150 + 49 != 200
    build_clean(con, clean)
    assert run_sql(con, "03_validate.sql")[2][0]["mismatched_rows"] == 1


def test_answer_rate_off_by_one_hundredth_is_flagged(small, run_sql):
    """answer_rate 0.01 away from answered/incoming is outside the 0.001 tolerance."""
    con, clean = small
    clean[0]["answer_rate"] = 0.91  # true ratio is 90/100 = 0.90
    build_clean(con, clean)
    assert run_sql(con, "03_validate.sql")[3][0]["off_rate_rows"] == 1


def test_answer_rate_small_rounding_is_tolerated(small, run_sql):
    """answer_rate only 0.0005 away (source rounding) is inside the tolerance, so not flagged."""
    con, clean = small
    clean[0]["answer_rate"] = 0.9005
    build_clean(con, clean)
    assert run_sql(con, "03_validate.sql")[3][0]["off_rate_rows"] == 0


def test_zero_incoming_does_not_crash_answer_rate_check(make_raw_db, run_sql):
    """incoming_calls = 0 is handled by SAFE_DIVIDE: no divide-by-zero, row not flagged.

    Note: because SAFE_DIVIDE returns NULL, the comparison is NULL and COUNTIF skips
    the row. So a zero-incoming row is never checked at all -- even a nonsense
    answer_rate like 0.5 would pass check 4. Check 3 still covers the call counts.
    """
    raws = [raw_row(1), raw_row(2, incoming=0, answered=0, abandoned=0, rate=0.0)]
    con = make_raw_db(raws)
    clean = clean_rows_from_raw(raws)
    clean[1]["answer_rate"] = 0.5  # nonsense, but the check cannot see it
    build_clean(con, clean)
    res = run_sql(con, "03_validate.sql")
    assert res[3][0]["off_rate_rows"] == 0
    assert res[2][0]["mismatched_rows"] == 0


def test_duplicate_row_id_is_caught(small, run_sql):
    """Two rows sharing a row_id make distinct_ids smaller than total_rows."""
    con, clean = small
    clean[2]["row_id"] = 2
    build_clean(con, clean)
    k = run_sql(con, "03_validate.sql")[4][0]
    assert k["total_rows"] == 3
    assert k["distinct_ids"] == 2


@pytest.mark.parametrize("column", CLEAN_COLUMNS)
def test_null_in_any_column_is_counted(small, run_sql, column):
    """A NULL in any single clean_data column is counted once in rows_with_nulls."""
    con, clean = small
    clean[1][column] = None
    build_clean(con, clean)
    assert run_sql(con, "03_validate.sql")[4][0]["rows_with_nulls"] == 1


def test_wrong_time_conversion_is_visible(small, run_sql):
    """If the TIME -> seconds step were wrong (e.g. minutes kept as 2 instead of 134 sec), check 6 shows it."""
    con, clean = small
    clean[0]["avg_talk_duration_sec"] = 2
    build_clean(con, clean)
    r1 = run_sql(con, "03_validate.sql")[5][0]
    assert r1["avg_talk_duration_sec"] != 134


def test_out_of_range_values_show_in_ranges_check(small, run_sql):
    """A negative waiting time or a rate above 1 shows up in the min/max range check."""
    con, clean = small
    clean[0]["avg_waiting_time_sec"] = -5
    clean[1]["service_level_20s"] = 1.2
    build_clean(con, clean)
    rng = run_sql(con, "03_validate.sql")[6][0]
    assert rng["min_waiting_sec"] < 0
    assert rng["max_service_level"] > 1
