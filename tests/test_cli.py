"""Tests for the m3db command group: help, log levels and errors."""


def test_info_prints_a_status_line_and_no_sql(m3db, db_file):
    result = m3db("init", db_file)

    assert f"Created {db_file}" in result.stderr
    assert "CREATE TABLE" not in result.stderr


def test_trace_prints_every_sql_statement(m3db, db_file):
    result = m3db("--log-level", "TRACE", "init", db_file)

    assert "CREATE TABLE tagsets" in result.stderr


def test_an_error_prints_one_line_and_exits_with_code_1(m3db, tmp_path):
    result = m3db("init", tmp_path / "missing_folder" / "test.duckdb", exit_code=1)

    error_lines = [line for line in result.stderr.splitlines() if "ERROR" in line]
    assert len(error_lines) == 1
    assert "Traceback" not in result.stderr


def test_memory_options_reach_duckdb(m3db, new_db, write_json):
    tagsets_json = write_json("tagsets.json", [{"name": "People", "tagtype": "alphanumerical"}])

    result = m3db(
        "--log-level",
        "TRACE",
        "add-tagsets",
        new_db,
        tagsets_json,
        "--memory-limit",
        "256MB",
        "--threads",
        "1",
    )

    assert "SET memory_limit = '256MB'" in result.stderr
    assert "SET threads = 1" in result.stderr
