"""Copy an M3 database between DuckDB and SQLite (m3db to-sqlite and m3db to-duckdb)."""

import sqlite3
from contextlib import closing
from importlib.resources import files
from pathlib import Path

import duckdb

from m3db import M3DBError, db
from m3db.checks import run_checks
from m3db.db import TAG_TYPES, execute, transaction
from m3db.logs import phase

SQLITE_SCHEMA = files("m3db") / "ddl.sql"
SQLITE_PAGE_SIZE = 16384

# The tables to copy, each with the columns that order it.
# source_types and tag_types are not copied, since ddl.sql fills them.
COPIED_TABLES = {
    "tagsets": "id",
    "medias": "id",
    "tags": "id",
    **{f"{type_name}_tags": "id" for type_name, _ in TAG_TYPES.values()},
    "taggings": "media_id, tag_id",
}


def to_sqlite(
    duckdb_file: Path,
    sqlite_file: Path,
    memory_limit: str = "8GB",
    threads: int | None = None,
    cache_mb: int = 1024,
) -> None:
    """Write the M3 database DUCKDB_FILE to the new SQLite file SQLITE_FILE.

    Any problem stops the copy and deletes SQLITE_FILE.
    """
    if sqlite_file.exists():
        raise M3DBError(f"{sqlite_file} exists. Choose a new file name, or delete it first.")
    tables_sql, indexes_sql = split_schema()
    try:
        with phase("Create the SQLite tables"):
            with closing(sqlite3.connect(sqlite_file)) as sqlite:
                sqlite.execute(f"PRAGMA page_size = {SQLITE_PAGE_SIZE}")
                sqlite.executescript(tables_sql)
        copy_rows(duckdb_file, sqlite_file, memory_limit, threads)
        finish_sqlite(sqlite_file, indexes_sql, cache_mb)
    except BaseException:
        sqlite_file.unlink(missing_ok=True)
        raise


def split_schema() -> tuple[str, str]:
    """Split ddl.sql into the statements that create the tables and the CREATE INDEX statements."""
    lines = SQLITE_SCHEMA.read_text().splitlines()
    tables = [line for line in lines if not line.startswith("CREATE INDEX")]
    indexes = [line for line in lines if line.startswith("CREATE INDEX")]
    return "\n".join(tables), "\n".join(indexes)


def copy_rows(duckdb_file: Path, sqlite_file: Path, memory_limit: str, threads: int | None) -> None:
    """Check DUCKDB_FILE, then copy each table of COPIED_TABLES into SQLITE_FILE in key order."""
    with duckdb.connect() as connection:
        execute(connection, f"SET memory_limit = '{memory_limit}'")
        execute(connection, f"SET temp_directory = '{sqlite_file}.tmp'")
        if threads:
            execute(connection, f"SET threads = {int(threads)}")
        execute(connection, f"ATTACH '{duckdb_file}' AS m3 (READ_ONLY)")
        execute(connection, "USE m3")
        run_checks(connection)

        execute(connection, f"ATTACH '{sqlite_file}' AS sqlite_file (TYPE sqlite)")
        execute(connection, "BEGIN")
        for table, key in COPIED_TABLES.items():
            with phase(f"Copy {table}"):
                # DuckDB treats a SQLite TIME column as TIMESTAMP, so time values go in as text
                execute(connection, f"SET sqlite_all_varchar = {table == 'time_tags'}")
                execute(
                    connection,
                    f"INSERT INTO sqlite_file.{table} BY NAME SELECT * FROM {table} ORDER BY {key}",
                )
        execute(connection, "COMMIT")


def finish_sqlite(sqlite_file: Path, indexes_sql: str, cache_mb: int) -> None:
    """Build the indexes of SQLITE_FILE, run ANALYZE, and raise an M3DBError if
    quick_check finds a problem in the written file."""
    with closing(sqlite3.connect(sqlite_file)) as sqlite:
        sqlite.execute(f"PRAGMA cache_size = -{cache_mb * 1024}")
        with phase("Build the SQLite indexes"):
            sqlite.executescript(indexes_sql)
        with phase("ANALYZE"):
            sqlite.execute("ANALYZE")
            sqlite.commit()
        with phase("Check the SQLite file"):
            result = sqlite.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise M3DBError(
                    f'SQLite quick_check reports "{result}". {sqlite_file} was deleted.'
                )


def to_duckdb(
    sqlite_file: Path, duckdb_file: Path, memory_limit: str = "8GB", threads: int | None = None
) -> None:
    """Write the M3 database SQLITE_FILE to the new DuckDB file DUCKDB_FILE, with native types.

    Any problem stops the copy and deletes DUCKDB_FILE.
    """
    if duckdb_file.exists():
        raise M3DBError(f"{duckdb_file} exists. Choose a new file name, or delete it first.")
    try:
        with db.connect(duckdb_file, memory_limit, threads) as connection:
            db.create_schema(connection)
            # Read every SQLite value as text, then cast it to the DuckDB column type
            execute(connection, "SET sqlite_all_varchar = true")
            execute(connection, f"ATTACH '{sqlite_file}' AS sqlite_file (TYPE sqlite, READ_ONLY)")
            with transaction(connection):
                for table, key in COPIED_TABLES.items():
                    with phase(f"Copy {table}"):
                        copy_from_sqlite(connection, sqlite_file, table, key)
                run_checks(connection)
    except BaseException:
        duckdb_file.unlink(missing_ok=True)
        Path(f"{duckdb_file}.wal").unlink(missing_ok=True)
        raise


def copy_from_sqlite(
    connection: duckdb.DuckDBPyConnection, sqlite_file: Path, table: str, key: str
) -> None:
    """Copy TABLE from the attached sqlite_file into DuckDB, casting each column to its type.

    Reads through sqlite_query, since DuckDB cannot scan a WITHOUT ROWID table directly.
    """
    columns = execute(
        connection,
        """
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_catalog = current_database() AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table],
    ).fetchall()
    casts = ", ".join(f"CAST({name} AS {data_type}) AS {name}" for name, data_type in columns)
    try:
        execute(
            connection,
            f"""
            INSERT INTO {table} BY NAME
            SELECT {casts}
            FROM sqlite_query('sqlite_file', 'SELECT * FROM {table}')
            ORDER BY {key}
            """,
        )
    except duckdb.ConversionException as error:
        raise M3DBError(
            f"A value in {table} of {sqlite_file.name} does not convert to its DuckDB type. {error}"
        ) from error
