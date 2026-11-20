"""Tests for opening .duckdb files in m3db.db."""

from m3db import db


def setting(connection, name: str) -> str:
    return connection.execute("SELECT current_setting(?)", [name]).fetchone()[0]


def test_connect_sets_the_memory_limit_and_threads(db_file):
    with db.connect(db_file, memory_limit="512MB", threads=2) as connection:
        assert setting(connection, "memory_limit") == "488.2 MiB"
        assert setting(connection, "threads") == 2
        assert setting(connection, "preserve_insertion_order") is False


def test_connect_defaults_to_an_8gb_memory_limit(db_file):
    with db.connect(db_file) as connection:
        assert setting(connection, "memory_limit") == "7.4 GiB"
