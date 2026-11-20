"""Tests for m3db to-sqlite and m3db to-duckdb."""

import datetime
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

TAGSETS = [
    {"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Bo"]},
    {"name": "Moment", "tagtype": "timestamp", "tags": ["2019-01-02 10:11:12"]},
    {"name": "Clock", "tagtype": "time", "tags": ["10:11:12"]},
    {"name": "Day", "tagtype": "date", "tags": ["2019-01-02"]},
    {"name": "Year", "tagtype": "numerical_int", "tags": [2019]},
    {"name": "Score", "tagtype": "numerical_dec", "tags": [0.5]},
    {"name": "Box", "tagtype": "json", "tags": [{"x": 1}]},
]
MEDIAS = [
    {"source": "v1.mp4", "source_type": "video", "thumbnail": "v1.jpg"},
    {"source": "a.jpg", "source_type": "image", "group": "v1.mp4"},
]
TAGGINGS = [
    {"media_source": "v1.mp4", "tagsets": {"Moment": ["2019-01-02 10:11:12"], "Year": [2019]}},
    {"media_source": "a.jpg", "tagsets": {"People": ["Anna", "Bo"], "Clock": ["10:11:12"]}},
]
COPIED_TABLES = [
    "source_types",
    "tag_types",
    "tagsets",
    "medias",
    "tags",
    "alphanumerical_tags",
    "numerical_int_tags",
    "taggings",
]


@pytest.fixture
def loaded_db(m3db, new_db, write_json):
    """A test database with one tagset of each tag type, 2 medias and 6 taggings."""
    m3db("add-tagsets", new_db, write_json("tagsets.json", TAGSETS))
    m3db("add-medias", new_db, write_json("medias.json", MEDIAS))
    m3db("add-taggings", new_db, write_json("taggings.json", TAGGINGS))
    return new_db


def sqlite_rows(sqlite_file, sql: str) -> list[tuple]:
    with sqlite3.connect(sqlite_file) as connection:
        return connection.execute(sql).fetchall()


def test_every_row_is_copied(m3db, loaded_db, tmp_path):
    sqlite_file = tmp_path / "test.db"

    result = m3db("to-sqlite", loaded_db, sqlite_file)

    assert result.exit_code == 0, result.output
    assert f"Wrote {sqlite_file}" in result.stderr
    with duckdb.connect(loaded_db, read_only=True) as connection:
        for table in COPIED_TABLES:
            expected = connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            assert sqlite_rows(sqlite_file, f"SELECT * FROM {table} ORDER BY 1, 2") == expected


def test_dates_and_times_are_stored_as_text(m3db, loaded_db, tmp_path):
    sqlite_file = tmp_path / "test.db"

    m3db("to-sqlite", loaded_db, sqlite_file)

    for table, value in [
        ("timestamp_tags", "2019-01-02 10:11:12"),
        ("time_tags", "10:11:12"),
        ("date_tags", "2019-01-02"),
        ("json_tags", '{"x":1}'),
    ]:
        assert sqlite_rows(sqlite_file, f"SELECT value, typeof(value) FROM {table}") == [
            (value, "text")
        ], table
    assert sqlite_rows(sqlite_file, "SELECT value FROM numerical_dec_tags") == [(0.5,)]


def test_the_sqlite_file_uses_16_kb_pages_indexes_and_statistics(m3db, loaded_db, tmp_path):
    sqlite_file = tmp_path / "test.db"

    m3db("to-sqlite", loaded_db, sqlite_file)

    assert sqlite_rows(sqlite_file, "PRAGMA page_size") == [(16384,)]
    index_names = sqlite_rows(sqlite_file, "SELECT name FROM sqlite_master WHERE type = 'index'")
    assert ("idx_taggings_tag_id",) in index_names
    assert ("idx_medias_group_id",) in index_names
    assert sqlite_rows(sqlite_file, "SELECT count(*) FROM sqlite_stat1")[0][0] > 0


def test_an_existing_sqlite_file_is_refused_and_unchanged(m3db, loaded_db, tmp_path):
    sqlite_file = tmp_path / "test.db"
    sqlite_file.write_text("keep me")

    result = m3db("to-sqlite", loaded_db, sqlite_file)

    assert result.exit_code == 1
    assert "test.db exists" in result.stderr
    assert sqlite_file.read_text() == "keep me"


@pytest.mark.parametrize(
    "break_sql, message",
    [
        ("INSERT INTO taggings VALUES (9, 1)", "taggings.media_id with no media"),
        ("UPDATE medias SET source_type = 9 WHERE id = 1", "foreign key"),
    ],
)
def test_a_broken_database_is_refused_and_leaves_no_sqlite_file(
    m3db, loaded_db, tmp_path, break_sql, message
):
    with duckdb.connect(loaded_db) as connection:
        connection.execute(break_sql)
    sqlite_file = tmp_path / "test.db"

    result = m3db("to-sqlite", loaded_db, sqlite_file)

    assert result.exit_code == 1
    assert message in result.stderr
    assert not sqlite_file.exists()


# to-duckdb

OLD_SCHEMA = Path(__file__).parent / "data" / "old_ddl.sql"
OLD_ROWS = """
INSERT INTO tagsets VALUES (1, 'People', 1), (2, 'Clock', 3), (3, 'Moment', 2), (4, 'Score', 6);
INSERT INTO tags VALUES (1, 1, 1), (2, 1, 1), (3, 3, 2), (4, 2, 3), (5, 6, 4);
INSERT INTO alphanumerical_tags VALUES (1, 'Anna', 1), (2, 'Bo', 1);
INSERT INTO time_tags VALUES (3, '08:00:00', 2);
INSERT INTO timestamp_tags VALUES (4, '2019-01-02 10:11:12', 3);
INSERT INTO numerical_dec_tags VALUES (5, 0.5, 4);
INSERT INTO medias VALUES (1, 'v1.mp4', 2, 'v1.jpg', NULL), (2, 'a.jpg', 1, NULL, 1);
INSERT INTO taggings VALUES (1, 4), (2, 1), (2, 2), (2, 3), (2, 5);
"""


def old_sqlite_file(path: Path, extra_sql: str = "") -> Path:
    """Write a SQLite file in the schema of the old loader, with a few rows of each kind."""
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(OLD_SCHEMA.read_text() + OLD_ROWS + extra_sql)
    return path


def test_a_sqlite_file_in_the_old_schema_converts_with_native_types(m3db, tmp_path):
    duckdb_file = tmp_path / "test.duckdb"

    result = m3db("to-duckdb", old_sqlite_file(tmp_path / "old.db"), duckdb_file)

    assert result.exit_code == 0, result.output
    assert f"Wrote {duckdb_file}" in result.stderr
    with duckdb.connect(duckdb_file, read_only=True) as connection:
        assert connection.execute("SELECT value FROM time_tags").fetchall() == [
            (datetime.time(8, 0),)
        ]
        assert connection.execute("SELECT value FROM timestamp_tags").fetchall() == [
            (datetime.datetime(2019, 1, 2, 10, 11, 12),)
        ]
        assert connection.execute("SELECT value FROM numerical_dec_tags").fetchall() == [
            (Decimal("0.50000"),)
        ]
        assert connection.execute("SELECT * FROM medias ORDER BY id").fetchall() == [
            (1, "v1.mp4", 2, "v1.jpg", None),
            (2, "a.jpg", 1, None, 1),
        ]
        assert connection.execute("SELECT count(*) FROM taggings").fetchone() == (5,)


def test_a_round_trip_through_to_sqlite_keeps_every_row(m3db, loaded_db, tmp_path):
    m3db("to-sqlite", loaded_db, tmp_path / "test.db")

    result = m3db("to-duckdb", tmp_path / "test.db", tmp_path / "back.duckdb")

    assert result.exit_code == 0, result.output
    tables = COPIED_TABLES + ["timestamp_tags", "time_tags", "date_tags", "json_tags"]
    with duckdb.connect(loaded_db, read_only=True) as original:
        with duckdb.connect(tmp_path / "back.duckdb", read_only=True) as back:
            for table in tables + ["numerical_dec_tags"]:
                sql = f"SELECT * FROM {table} ORDER BY ALL"
                assert back.execute(sql).fetchall() == original.execute(sql).fetchall(), table


def test_a_malformed_time_stops_the_copy_and_leaves_no_duckdb_file(m3db, tmp_path):
    sqlite_file = old_sqlite_file(
        tmp_path / "old.db",
        "INSERT INTO tags VALUES (6, 3, 2); INSERT INTO time_tags VALUES (6, '25:99', 2);",
    )

    result = m3db("to-duckdb", sqlite_file, tmp_path / "test.duckdb")

    assert result.exit_code == 1
    assert "time_tags" in result.stderr
    assert "25:99" in result.stderr
    assert not (tmp_path / "test.duckdb").exists()


def test_a_sqlite_file_that_fails_the_checks_leaves_no_duckdb_file(m3db, tmp_path):
    sqlite_file = old_sqlite_file(tmp_path / "old.db", "INSERT INTO taggings VALUES (9, 1);")

    result = m3db("to-duckdb", sqlite_file, tmp_path / "test.duckdb")

    assert result.exit_code == 1
    assert "1 taggings.media_id with no media" in result.stderr
    assert not (tmp_path / "test.duckdb").exists()


def test_an_existing_duckdb_file_is_refused_and_unchanged(m3db, loaded_db, tmp_path):
    sqlite_file = old_sqlite_file(tmp_path / "old.db")

    result = m3db("to-duckdb", sqlite_file, loaded_db)

    assert result.exit_code == 1
    assert "test.duckdb exists" in result.stderr
    with duckdb.connect(loaded_db, read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM tagsets").fetchone() == (7,)
