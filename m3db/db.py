"""Open .duckdb files for loading, and run SQL with TRACE logging."""

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path

import duckdb
from loguru import logger

DUCKDB_SCHEMA = files("m3db") / "ddl_duckdb.sql"

# Each tag type ID with its tag type name and the SQL that turns a JSON value `j` into
# the type of the value column in the table {name}_tags
TAG_TYPES = {
    1: ("alphanumerical", "j->>'$'"),
    2: ("timestamp", "CAST(j->>'$' AS TIMESTAMP)"),
    3: ("time", "CAST(j->>'$' AS TIME)"),
    4: ("date", "CAST(j->>'$' AS DATE)"),
    5: ("numerical_int", "CAST(j->>'$' AS BIGINT)"),
    6: ("numerical_dec", "CAST(j->>'$' AS DECIMAL(10,5))"),
    7: ("json", "j->>'$'"),
}
TAG_TYPE_NAMES = ", ".join(name for name, _ in TAG_TYPES.values())


def connect(
    db_file: Path, memory_limit: str = "1GB", threads: int | None = None
) -> duckdb.DuckDBPyConnection:
    """Open DB_FILE with MEMORY_LIMIT and THREADS (default all cores).

    Work that does not fit in MEMORY_LIMIT spills to the folder DB_FILE.tmp.
    """
    connection = duckdb.connect(db_file)
    execute(connection, f"SET memory_limit = '{memory_limit}'")
    # The loaders number rows by file position, so DuckDB need not keep row order
    execute(connection, "SET preserve_insertion_order = false")
    if threads:
        execute(connection, f"SET threads = {int(threads)}")
    return connection


def execute(
    connection: duckdb.DuckDBPyConnection, sql: str, parameters: list | None = None
) -> duckdb.DuckDBPyConnection:
    """Log SQL at TRACE level, then run it on CONNECTION with PARAMETERS."""
    logger.trace("SQL\n{}", sql)
    return connection.execute(sql, parameters)


@contextmanager
def transaction(connection: duckdb.DuckDBPyConnection) -> Iterator[None]:
    """Run the with-block in one transaction on CONNECTION. Any error rolls back the whole block."""
    execute(connection, "BEGIN")
    try:
        yield
    except BaseException:
        execute(connection, "ROLLBACK")
        raise
    execute(connection, "COMMIT")


def create_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Drop and create every table of ddl_duckdb.sql."""
    execute(connection, DUCKDB_SCHEMA.read_text())
