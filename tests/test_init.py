"""Tests for m3db init."""

import duckdb


def column_types(db_file, table: str) -> dict[str, str]:
    """Map each column of TABLE in DB_FILE to its DuckDB type."""
    with duckdb.connect(db_file, read_only=True) as connection:
        rows = connection.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ?",
            [table],
        ).fetchall()
    return dict(rows)


def test_init_uses_native_types_for_tag_values(m3db, db_file):
    m3db("init", db_file)

    expected = {
        "alphanumerical_tags": "VARCHAR",
        "timestamp_tags": "TIMESTAMP",
        "time_tags": "TIME",
        "date_tags": "DATE",
        "numerical_int_tags": "BIGINT",
        "numerical_dec_tags": "DECIMAL(10,5)",
        "json_tags": "VARCHAR",
    }
    for table, value_type in expected.items():
        assert column_types(db_file, table)["value"] == value_type, table


def test_init_fills_source_types_and_tag_types(m3db, db_file):
    m3db("init", db_file)

    with duckdb.connect(db_file, read_only=True) as connection:
        source_types = connection.execute("SELECT name FROM source_types ORDER BY id").fetchall()
        tag_types = connection.execute("SELECT description FROM tag_types ORDER BY id").fetchall()
    assert [name for (name,) in source_types] == ["Image", "Video", "Audio", "Text", "Other"]
    assert [description for (description,) in tag_types] == [
        "alphanumerical",
        "timestamp",
        "time",
        "date",
        "numerical_int",
        "numerical_dec",
        "json",
    ]


def add_one_tagset(db_file) -> None:
    """Insert one tagset into DB_FILE so a reset can be seen."""
    with duckdb.connect(db_file) as connection:
        connection.execute("INSERT INTO tagsets VALUES (1, 'People', 1)")


def count_tagsets(db_file) -> int:
    with duckdb.connect(db_file, read_only=True) as connection:
        return connection.execute("SELECT count(*) FROM tagsets").fetchone()[0]


def test_init_on_an_existing_file_warns_and_stops_when_declined(m3db, db_file):
    m3db("init", db_file)
    add_one_tagset(db_file)

    result = m3db("init", db_file, input="n\n", exit_code=1)

    assert "every table" in result.output
    assert count_tagsets(db_file) == 1


def test_init_on_an_existing_file_resets_the_tables_when_confirmed(m3db, db_file):
    m3db("init", db_file)
    add_one_tagset(db_file)

    m3db("init", db_file, input="y\n")

    assert count_tagsets(db_file) == 0
