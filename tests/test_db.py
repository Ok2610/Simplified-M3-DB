"""Tests for opening .duckdb files in m3db.db."""

from m3db import db


def setting(connection, name: str) -> str:
    return connection.execute("SELECT current_setting(?)", [name]).fetchone()[0]


def test_connect_sets_the_memory_limit_and_threads(db_file):
    with db.connect(db_file, memory_limit="512MB", threads=2) as connection:
        assert setting(connection, "memory_limit") == "488.2 MiB"
        assert setting(connection, "threads") == 2
        assert setting(connection, "preserve_insertion_order") is False


def test_connect_keeps_duckdb_threads_when_none_are_given(db_file):
    with db.connect(db_file) as connection:
        assert setting(connection, "threads") >= 1
        assert setting(connection, "memory_limit") == "7.4 GiB"
