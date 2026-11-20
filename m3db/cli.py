"""The m3db command and its subcommands."""

import re
import sqlite3
import sys
from pathlib import Path
from time import perf_counter

import click
import duckdb
from loguru import logger

from m3db import M3DBError, db
from m3db.convert import to_duckdb, to_sqlite
from m3db.json_input import JSON_FORMATS
from m3db.logs import LEVELS, counted, setup_logging
from m3db.medias import add_medias
from m3db.taggings import add_taggings
from m3db.tagsets import add_tags, add_tagsets

EXISTING_FILE = click.Path(exists=True, dir_okay=False, path_type=Path)


class M3DBGroup(click.Group):
    """A click group that prints an M3DBError, DuckDB error or SQLite error as one ERROR line,
    then exits with code 1."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except (M3DBError, duckdb.Error, sqlite3.Error) as error:
            logger.error(explain(error))
            logger.opt(exception=error).debug("Traceback of the error above")
            sys.exit(1)


def explain(error: Exception) -> str:
    """Return the message for ERROR, reworded for the DuckDB errors that have a known fix."""
    message = str(error)
    too_long = re.search(r'"maximum_object_size" .* reading file "([^"]+)"', message)
    if too_long:
        return (
            f"{Path(too_long[1]).name} has a line too long to read as JSONL. "
            "Split its list over several lines of under 16 MB, or use a .json file."
        )
    return message


@click.group(cls=M3DBGroup)
@click.option(
    "--log-level",
    type=click.Choice(LEVELS, case_sensitive=False),
    default="INFO",
    show_default=True,
    help="Show messages at this level and above. "
    "DEBUG adds phase timings, TRACE adds every SQL statement.",
)
@click.version_option(package_name="simplified-m3-db")
def cli(log_level: str):
    """Build a Simplified M3 database in DuckDB from JSON files."""
    setup_logging(log_level.upper())


# Loading steps shared by the add commands and build


def reset_database(db_file: Path) -> None:
    """Create DB_FILE with every table of the M3 schema, asking first when DB_FILE exists."""
    if db_file.exists():
        logger.warning(
            f"{db_file} exists. Continuing drops and recreates every table, so its data is lost."
        )
        if not click.confirm("Continue?", default=False, err=True):
            logger.info(f"Stopped. {db_file} is unchanged.")
            sys.exit(1)
    with db.connect(db_file) as connection:
        db.create_schema(connection)
    logger.info(f"Created {db_file}")


def load_tagsets(connection, tagsets_json: Path, ignore_existing: bool = False) -> None:
    """Add the tagsets in TAGSETS_JSON and log what was added."""
    logger.info(f"Reading {tagsets_json}")
    start = perf_counter()
    tagsets_added, tags_added = add_tagsets(connection, tagsets_json, ignore_existing)
    logger.info(
        f"Added {counted(tagsets_added, 'tagset')} and {counted(tags_added, 'tag')} "
        f"in {perf_counter() - start:.1f} s"
    )


def load_tags(connection, tags_json: Path) -> None:
    """Add the tags in TAGS_JSON and log what was added."""
    logger.info(f"Reading {tags_json}")
    start = perf_counter()
    tags_added = add_tags(connection, tags_json)
    logger.info(f"Added {counted(tags_added, 'tag')} in {perf_counter() - start:.1f} s")


def load_medias(connection, medias_json: Path, ignore_existing: bool = False) -> None:
    """Add the medias in MEDIAS_JSON and log what was added."""
    logger.info(f"Reading {medias_json}")
    start = perf_counter()
    medias_added, medias_skipped = add_medias(connection, medias_json, ignore_existing)
    if medias_skipped:
        logger.info(f"Skipped {counted(medias_skipped, 'media', 'medias')} that exist")
    logger.info(
        f"Added {counted(medias_added, 'media', 'medias')} in {perf_counter() - start:.1f} s"
    )


def load_taggings(connection, taggings_json: Path) -> None:
    """Add the taggings in TAGGINGS_JSON and log what was added."""
    logger.info(f"Reading {taggings_json}")
    start = perf_counter()
    taggings_added = add_taggings(connection, taggings_json)
    logger.info(f"Added {counted(taggings_added, 'tagging')} in {perf_counter() - start:.1f} s")


def duckdb_options(command):
    """Add --memory-limit and --threads to a command that loads data into a .duckdb file."""
    command = click.option(
        "--threads",
        type=click.IntRange(min=1),
        help="Threads DuckDB may use. Fewer threads use less memory.  [default: all cores]",
    )(command)
    command = click.option(
        "--memory-limit",
        default="8GB",
        show_default=True,
        help="Memory DuckDB may use for data. Work over it spills to a .tmp folder by the output.",
    )(command)
    return command


# Commands


@cli.command()
@click.argument("db_file", type=click.Path(dir_okay=False, path_type=Path))
def init(db_file: Path):
    """Create DB_FILE with every table of the M3 schema.

    On an existing DB_FILE, init asks before it drops and recreates every table.
    """
    reset_database(db_file)


@cli.command()
@click.argument("db_file", type=click.Path(dir_okay=False, path_type=Path))
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@duckdb_options
def build(db_file: Path, folder: Path, memory_limit: str, threads: int | None):
    """Create DB_FILE and load the M3 files in FOLDER.

    \b
    A file's kind is the end of its name, and the kinds load in this order:
    1. tagsets.json, for example v3c_tagsets.json
    2. tags.json
    3. medias.json
    4. taggings.json

    Files of one kind load one at a time in name order, so a collection too big for memory
    can be split, for example into people_tags.json and year_tags.json. Each file may also
    be JSONL, one object per line, with the extension .jsonl.

    A file that fails stops the build, and the files before it stay loaded.
    On an existing DB_FILE, build asks before it drops and recreates every table.
    """
    files = build_files(folder)
    if not any(files.values()):
        raise M3DBError(f"No tagsets, tags, medias or taggings files in {folder}.")
    start = perf_counter()
    reset_database(db_file)
    with db.connect(db_file, memory_limit, threads) as connection:
        for path in files["tagsets"]:
            load_tagsets(connection, path)
        for path in files["tags"]:
            load_tags(connection, path)
        for path in files["medias"]:
            load_medias(connection, path)
        for path in files["taggings"]:
            load_taggings(connection, path)
    logger.info(f"Built {db_file} in {perf_counter() - start:.1f} s")


# The kinds of M3 file, in the order build loads them
KINDS = ("tagsets", "tags", "medias", "taggings")


def build_files(folder: Path) -> dict[str, list[Path]]:
    """Find the M3 files in FOLDER for build, per kind and in name order.

    A file's kind is the end of its name, as in v3c_medias.json or part2_taggings.jsonl.
    Logs an INFO line for each kind with no file and a WARNING for each other JSON file.
    """
    files = {
        kind: sorted(
            (path for suffix in JSON_FORMATS for path in folder.glob(f"*{kind}{suffix}")),
            key=lambda path: path.name,
        )
        for kind in KINDS
    }
    for kind, paths in files.items():
        if not paths:
            logger.info(f"No {kind} file in {folder}, so build adds no {kind}")
        stems = [path.stem for path in paths]
        twice = next((stem for stem in stems if stems.count(stem) > 1), None)
        if twice:
            raise M3DBError(f"{folder} has both {twice}.json and {twice}.jsonl. Keep one.")

    known = {path for paths in files.values() for path in paths}
    for path in sorted(folder.iterdir()):
        if path.suffix in JSON_FORMATS and path not in known:
            logger.warning(f"Ignored {path.name}, whose name does not end in an M3 file kind")
    return files


@cli.command("add-tagsets")
@click.argument("db_file", type=EXISTING_FILE)
@click.argument("tagsets_json", type=EXISTING_FILE)
@click.option(
    "--ignore-existing",
    is_flag=True,
    help="Skip tagsets that already exist, and add only their new tags.",
)
@duckdb_options
def add_tagsets_command(
    db_file: Path, tagsets_json: Path, ignore_existing: bool, memory_limit: str, threads: int | None
):
    """Add the tagsets in TAGSETS_JSON and the tags listed with them to DB_FILE.

    \b
    TAGSETS_JSON is a list of tagsets, for example
    [
        {
            "name": "People",
            "tagtype": "alphanumerical",
            "tags": ["Anna", "Bo"]
        },
        {
            "name": "Year",
            "tagtype": "numerical_int",
            "tags": [2019, 2020]
        }
    ]

    The tagtype is one of alphanumerical, timestamp, time, date, numerical_int, numerical_dec, json.
    """
    with db.connect(db_file, memory_limit, threads) as connection:
        load_tagsets(connection, tagsets_json, ignore_existing)


@cli.command("add-tags")
@click.argument("db_file", type=EXISTING_FILE)
@click.argument("tags_json", type=EXISTING_FILE)
@duckdb_options
def add_tags_command(db_file: Path, tags_json: Path, memory_limit: str, threads: int | None):
    """Add the tags in TAGS_JSON to tagsets that exist in DB_FILE.

    \b
    TAGS_JSON is a list of tag lists, for example
    [
        {
            "tagset_name": "People",
            "tags": ["Cy", "Dee"]
        }
    ]

    A tagset may have several entries. Its new tags take IDs in file order.
    """
    with db.connect(db_file, memory_limit, threads) as connection:
        load_tags(connection, tags_json)


@cli.command("add-medias")
@click.argument("db_file", type=EXISTING_FILE)
@click.argument("medias_json", type=EXISTING_FILE)
@click.option("--ignore-existing", is_flag=True, help="Skip medias whose source already exists.")
@duckdb_options
def add_medias_command(
    db_file: Path, medias_json: Path, ignore_existing: bool, memory_limit: str, threads: int | None
):
    """Add the medias in MEDIAS_JSON to DB_FILE.

    \b
    MEDIAS_JSON is a list of medias, for example
    [
        {
            "source": "v1.mp4",
            "source_type": "video",
            "thumbnail": "v1.jpg"
        },
        {
            "source": "v1_001.jpg",
            "source_type": "image",
            "group": "v1.mp4"
        }
    ]

    The source_type is one of image, video, audio, text, other. The thumbnail and group are
    optional. A group names the source of another media, in MEDIAS_JSON or in DB_FILE.
    """
    with db.connect(db_file, memory_limit, threads) as connection:
        load_medias(connection, medias_json, ignore_existing)


@cli.command("add-taggings")
@click.argument("db_file", type=EXISTING_FILE)
@click.argument("taggings_json", type=EXISTING_FILE)
@duckdb_options
def add_taggings_command(
    db_file: Path, taggings_json: Path, memory_limit: str, threads: int | None
):
    """Add the taggings in TAGGINGS_JSON to DB_FILE.

    \b
    TAGGINGS_JSON is a list of medias with their tags per tagset, for example
    [
        {
            "media_source": "v1.mp4",
            "tagsets": {
                "People": ["Anna", "Bo"],
                "Year": [2019]
            }
        }
    ]

    Each media must exist in DB_FILE. A tagging for an unknown tagset, or for a value
    that is not a tag of its tagset, is skipped with a WARNING. Add missing values with
    m3db add-tags first.
    """
    with db.connect(db_file, memory_limit, threads) as connection:
        load_taggings(connection, taggings_json)


@cli.command("to-sqlite")
@click.argument("duckdb_file", type=EXISTING_FILE)
@click.argument("sqlite_file", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--cache-mb",
    type=click.IntRange(min=1),
    default=1024,
    show_default=True,
    help="SQLite page cache in MB while the indexes are built.",
)
@duckdb_options
def to_sqlite_command(
    duckdb_file: Path, sqlite_file: Path, cache_mb: int, memory_limit: str, threads: int | None
):
    """Write the M3 database DUCKDB_FILE to the new SQLite file SQLITE_FILE.

    SQLITE_FILE gets the schema of m3db/ddl.sql with 16 KB pages. DUCKDB_FILE is checked
    before the copy and SQLITE_FILE after it. On any problem SQLITE_FILE is deleted.
    """
    logger.info(f"Copying {duckdb_file} to {sqlite_file}")
    start = perf_counter()
    to_sqlite(duckdb_file, sqlite_file, memory_limit, threads, cache_mb)
    size_mb = sqlite_file.stat().st_size / 1e6
    logger.info(f"Wrote {sqlite_file} ({size_mb:,.0f} MB) in {perf_counter() - start:.1f} s")


@cli.command("to-duckdb")
@click.argument("sqlite_file", type=EXISTING_FILE)
@click.argument("duckdb_file", type=click.Path(dir_okay=False, path_type=Path))
@duckdb_options
def to_duckdb_command(sqlite_file: Path, duckdb_file: Path, memory_limit: str, threads: int | None):
    """Write the M3 database SQLITE_FILE to the new DuckDB file DUCKDB_FILE.

    SQLITE_FILE may use the old schema or the one of m3db/ddl.sql. Each value is cast to
    its DuckDB type, and DUCKDB_FILE is checked before it is committed. On any problem
    DUCKDB_FILE is deleted.
    """
    logger.info(f"Copying {sqlite_file} to {duckdb_file}")
    start = perf_counter()
    to_duckdb(sqlite_file, duckdb_file, memory_limit, threads)
    size_mb = duckdb_file.stat().st_size / 1e6
    logger.info(f"Wrote {duckdb_file} ({size_mb:,.0f} MB) in {perf_counter() - start:.1f} s")
