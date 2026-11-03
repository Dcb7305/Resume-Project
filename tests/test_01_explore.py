"""
Tests for sql/01_explore.sql (the profiling queries run BEFORE cleaning).

The file has 7 SELECT statements. run_sql returns one result per statement, in order:
  [0] column names/types   [1] row count + distinct ids   [2] null counts
  [3] numeric ranges       [4] time ranges                [5] logic checks
  [6] the problem rows themselves (max 25, ordered by Index)

Two kinds of tests live here:
  * real-data tests: lock in the findings from the actual CSV
  * synthetic tests: tiny hand-made tables that prove each check really
    catches the problem it is meant to catch
"""

SQL = "01_explore.sql"

NULL_COLUMNS = {
    "Index": "null_index",
    "Incoming Calls": "null_incoming",
    "Answered Calls": "null_answered",
    "Abandoned Calls": "null_abandoned",
    "Answer Rate": "null_answer_rate",
    "Answer Speed _AVG_": "null_answer_speed",
    "Talk Duration _AVG_": "null_talk_duration",
    "Waiting Time _AVG_": "null_waiting_time",
    "Service Level _20 Seconds_": "null_service_level",
}


def good_row(index, incoming=100, answered=90, abandoned=10):
    """A clean row: answered + abandoned == incoming, all columns filled."""
    return {
        "Index": index,
        "Incoming Calls": incoming,
        "Answered Calls": answered,
        "Answer Rate": answered / incoming,
        "Abandoned Calls": abandoned,
        "Answer Speed _AVG_": "00:00:15",
        "Talk Duration _AVG_": "00:02:30",
        "Waiting Time _AVG_": "00:00:40",
        "Service Level _20 Seconds_": 0.8,
    }


# ---------------- real data ----------------

def test_file_has_seven_statements(raw_db, run_sql):
    """The file runs end to end and produces one result per SELECT (7 total)."""
    assert len(run_sql(raw_db, SQL)) == 7


def test_schema_lists_nine_columns_in_order(raw_db, run_sql):
    """Statement 1 lists all 9 raw columns, in table order, starting with Index."""
    schema = run_sql(raw_db, SQL)[0]
    names = [row["column_name"] for row in schema.rows]
    assert len(names) == 9
    assert names[0] == "Index"
    assert names == [
        "Index", "Incoming Calls", "Answered Calls", "Answer Rate", "Abandoned Calls",
        "Answer Speed _AVG_", "Talk Duration _AVG_", "Waiting Time _AVG_",
        "Service Level _20 Seconds_",
    ]


def test_real_data_index_is_unique(raw_db, run_sql):
    """All 1,251 rows have a different Index, so Index is a safe unique key."""
    r = run_sql(raw_db, SQL)[1][0]
    assert r["total_rows"] == 1251
    assert r["distinct_ids"] == 1251


def test_real_data_has_no_nulls(raw_db, run_sql):
    """Every null_* count is 0 on the real data, so cleaning needs no NULL handling."""
    r = run_sql(raw_db, SQL)[2][0]
    for col in NULL_COLUMNS.values():
        assert r[col] == 0, col


def test_real_data_incoming_range(raw_db, run_sql):
    """Incoming Calls runs from 5 to 1,575 with an average of 198.5."""
    r = run_sql(raw_db, SQL)[3][0]
    assert r["min_incoming"] == 5
    assert r["max_incoming"] == 1575
    assert r["avg_incoming"] == 198.5


def test_real_data_passes_logic_checks(raw_db, run_sql):
    """No impossible or mismatched rows in the real data, so statement 7 is empty."""
    results = run_sql(raw_db, SQL)
    assert results[5][0]["impossible_rows"] == 0
    assert results[5][0]["mismatched_totals"] == 0
    assert len(results[6]) == 0


# ---------------- synthetic data ----------------

def test_duplicate_index_is_detected(make_raw_db, run_sql):
    """If two rows share an Index, distinct_ids drops below total_rows."""
    con = make_raw_db([good_row(1), good_row(2), good_row(2)])
    r = run_sql(con, SQL)[1][0]
    assert r["total_rows"] == 3
    assert r["distinct_ids"] == 2


def test_each_null_lands_in_its_own_column(make_raw_db, run_sql):
    """A NULL in one column is counted in that column's null_* field and nowhere else."""
    for raw_col, null_col in NULL_COLUMNS.items():
        bad = good_row(99)
        bad[raw_col] = None
        con = make_raw_db([good_row(1), bad])
        r = run_sql(con, SQL)[2][0]
        for other in NULL_COLUMNS.values():
            expected = 1 if other == null_col else 0
            assert r[other] == expected, f"NULL in {raw_col}: {other}={r[other]}"


def test_numeric_and_time_ranges_on_small_data(make_raw_db, run_sql):
    """Statements 4 and 5 report the true min/max/avg of a known tiny table."""
    a = good_row(1, incoming=10, answered=8, abandoned=2)
    b = good_row(2, incoming=30, answered=25, abandoned=5)
    b["Talk Duration _AVG_"] = "00:10:00"
    con = make_raw_db([a, b])
    results = run_sql(con, SQL)
    nums, times = results[3][0], results[4][0]
    assert (nums["min_incoming"], nums["max_incoming"], nums["avg_incoming"]) == (10, 30, 20.0)
    assert (nums["min_answered"], nums["max_answered"], nums["avg_answered"]) == (8, 25, 16.5)
    assert (nums["min_abandoned"], nums["max_abandoned"], nums["avg_abandoned"]) == (2, 5, 3.5)
    assert times["min_talk_duration"] == "00:02:30"
    assert times["max_talk_duration"] == "00:10:00"


def test_answered_more_than_incoming_is_flagged(make_raw_db, run_sql):
    """A row with answered > incoming counts as impossible AND shows up in statement 7."""
    # 50 answered out of 40 incoming. abandoned=-10 keeps the totals adding up,
    # so this row is impossible but NOT mismatched -- isolating the first check.
    bad = good_row(7, incoming=40, answered=50, abandoned=-10)
    con = make_raw_db([good_row(1), bad, good_row(3)])
    results = run_sql(con, SQL)
    assert results[5][0]["impossible_rows"] == 1
    assert results[5][0]["mismatched_totals"] == 0
    assert [row["Index"] for row in results[6].rows] == [7]


def test_totals_that_dont_add_up_are_flagged(make_raw_db, run_sql):
    """answered + abandoned != incoming counts as mismatched (not impossible) and is listed."""
    bad = good_row(5, incoming=100, answered=90, abandoned=5)  # 95 != 100
    con = make_raw_db([good_row(1), bad])
    results = run_sql(con, SQL)
    assert results[5][0]["impossible_rows"] == 0
    assert results[5][0]["mismatched_totals"] == 1
    assert [row["Index"] for row in results[6].rows] == [5]


def test_problem_rows_capped_at_25_and_sorted_by_index(make_raw_db, run_sql):
    """Statement 7 returns at most 25 rows, lowest Index first, even if inserted out of order."""
    # 30 mismatched rows inserted in reverse order (Index 30 down to 1), plus a clean row.
    rows = [good_row(i, incoming=100, answered=90, abandoned=1) for i in range(30, 0, -1)]
    rows.append(good_row(100))
    con = make_raw_db(rows)
    results = run_sql(con, SQL)
    assert results[5][0]["mismatched_totals"] == 30  # the count is NOT capped
    problem = results[6]
    assert len(problem) == 25
    assert [row["Index"] for row in problem.rows] == list(range(1, 26))
    assert len(problem.columns) == 9  # SELECT * keeps every column for inspection


def test_null_call_count_slips_past_logic_checks(make_raw_db, run_sql):
    """FINDING: a row with a NULL call count is not flagged by statement 6 or 7.

    `NULL + 10 != 100` is NULL (unknown), not TRUE, so COUNTIF skips it and the
    WHERE in statement 7 drops it. That's standard SQL (BigQuery behaves the same),
    so statement 3's null counts are the only place such a row is caught.
    """
    bad = good_row(4)
    bad["Answered Calls"] = None
    con = make_raw_db([good_row(1), bad])
    results = run_sql(con, SQL)
    assert results[2][0]["null_answered"] == 1
    assert results[5][0]["impossible_rows"] == 0
    assert results[5][0]["mismatched_totals"] == 0
    assert len(results[6]) == 0
