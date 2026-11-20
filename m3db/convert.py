"""Copy an M3 database from DuckDB to a new SQLite file (m3db to-sqlite)."""

import sqlite3
from contextlib import closing
from importlib.resources import files
from pathlib import Path

import duckdb

from m3db import M3DBError
from m3db.checks import run_checks
from m3db.db import TAG_TYPES, execute
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
    """Build the indexes of SQLITE_FILE, run ANALYZE, and raise an M3DBError for a broken
    foreign key or a failed quick_check."""
    with closing(sqlite3.connect(sqlite_file)) as sqlite:
        sqlite.execute(f"PRAGMA cache_size = -{cache_mb * 1024}")
        with phase("Build the SQLite indexes"):
            sqlite.executescript(indexes_sql)
        with phase("ANALYZE"):
            sqlite.execute("ANALYZE")
            sqlite.commit()

        with phase("Check the SQLite file"):
            broken = sqlite.execute("SELECT count(*) FROM pragma_foreign_key_check").fetchone()[0]
            if broken:
                table, _, parent, _ = sqlite.execute(
                    "SELECT * FROM pragma_foreign_key_check LIMIT 1"
                ).fetchone()
                raise M3DBError(
                    f"{broken:,} rows of the SQLite file break a foreign key, for example "
                    f"a row of {table} with no {parent} row. {sqlite_file} was deleted."
                )
            result = sqlite.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise M3DBError(
                    f'SQLite quick_check reports "{result}". {sqlite_file} was deleted.'
                )
