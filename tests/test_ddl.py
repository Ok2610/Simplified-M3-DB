"""Tests for the SQLite schema m3db/ddl.sql, run in SQLite."""

import sqlite3
from importlib.resources import files

import duckdb
import pytest

TAG_VALUE_TABLES = [
    "alphanumerical_tags",
    "timestamp_tags",
    "time_tags",
    "date_tags",
    "numerical_int_tags",
    "numerical_dec_tags",
    "json_tags",
]


@pytest.fixture
def sqlite_db(tmp_path):
    """A SQLite connection to a file made from m3db/ddl.sql."""
    connection = sqlite3.connect(tmp_path / "test.db")
    connection.executescript((files("m3db") / "ddl.sql").read_text())
    yield connection
    connection.close()


def indexes(sqlite_db, table: str) -> dict[str, tuple[bool, list[str]]]:
    """Each index of TABLE as name to (unique, columns)."""
    result = {}
    for _, name, unique, _, _ in sqlite_db.execute(f"PRAGMA index_list({table})"):
        columns = [row[2] for row in sqlite_db.execute(f"PRAGMA index_info({name})")]
        result[name] = (bool(unique), columns)
    return result


def test_sqlite_and_duckdb_schemas_have_the_same_tables_and_columns(sqlite_db, tmp_path):
    with duckdb.connect(tmp_path / "test.duckdb") as connection:
        connection.execute((files("m3db") / "ddl_duckdb.sql").read_text())
        duckdb_columns = set(
            connection.execute(
                "SELECT table_name, column_name FROM information_schema.columns"
            ).fetchall()
        )
    sqlite_columns = {
        (table, column[1])
        for (table,) in sqlite_db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        for column in sqlite_db.execute(f"PRAGMA table_info({table})")
    }

    assert sqlite_columns == duckdb_columns


def test_taggings_is_stored_by_its_key_without_rowid(sqlite_db):
    sql = sqlite_db.execute("SELECT sql FROM sqlite_master WHERE name = 'taggings'").fetchone()[0]

    assert "WITHOUT ROWID" in sql
    assert "PRIMARY KEY (media_id, tag_id)" in sql
    assert sorted(indexes(sqlite_db, "taggings").values()) == [
        (False, ["tag_id"]),
        (True, ["media_id", "tag_id"]),
    ]


@pytest.mark.parametrize("table", TAG_VALUE_TABLES)
def test_each_value_table_has_one_unique_index_on_tagset_id_and_value(sqlite_db, table):
    assert list(indexes(sqlite_db, table).values()) == [(True, ["tagset_id", "value"])]


def test_medias_has_an_index_on_group_id(sqlite_db):
    assert (False, ["group_id"]) in indexes(sqlite_db, "medias").values()


def test_foreign_keys_reject_a_tagging_for_a_missing_media(sqlite_db):
    sqlite_db.execute("PRAGMA foreign_keys = ON")

    with pytest.raises(sqlite3.IntegrityError):
        sqlite_db.execute("INSERT INTO taggings VALUES (1, 1)")
