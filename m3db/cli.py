"""The m3db command and its subcommands."""

import sys
from pathlib import Path
from time import perf_counter

import click
import duckdb
from loguru import logger

from m3db import M3DBError, db
from m3db.logs import LEVELS, counted, setup_logging
from m3db.medias import add_medias
from m3db.taggings import add_taggings
from m3db.tagsets import add_tags, add_tagsets

EXISTING_FILE = click.Path(exists=True, dir_okay=False, path_type=Path)


class M3DBGroup(click.Group):
    """A click group that prints an M3DBError or DuckDB error as one ERROR line and exits with 1."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except (M3DBError, duckdb.Error) as error:
            logger.error(str(error))
            logger.opt(exception=error).debug("Traceback of the error above")
            sys.exit(1)


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


@cli.command()
@click.argument("db_file", type=click.Path(dir_okay=False, path_type=Path))
def init(db_file: Path):
    """Create DB_FILE with every table of the M3 schema.

    On an existing DB_FILE, init asks before it drops and recreates every table.
    """
    if db_file.exists():
        logger.warning(
            f"{db_file} exists. init drops and recreates every table, so all its data is lost."
        )
        if not click.confirm("Continue?", default=False, err=True):
            logger.info(f"Stopped. {db_file} is unchanged.")
            sys.exit(1)

    with db.connect(db_file) as connection:
        db.create_schema(connection)
    logger.info(f"Created {db_file}")


def duckdb_options(command):
    """Add --memory-limit and --threads to a command that loads data into a .duckdb file."""
    command = click.option(
        "--threads",
        type=click.IntRange(min=1),
        help="Threads DuckDB may use. Fewer threads use less memory.  [default: all cores]",
    )(command)
    command = click.option(
        "--memory-limit",
        default="1GB",
        show_default=True,
        help="Memory DuckDB may use for data. Work over it spills to the folder DB_FILE.tmp.",
    )(command)
    return command


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
    [{"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Bo"]}]

    The tagtype is one of alphanumerical, timestamp, time, date, numerical_int, numerical_dec, json.
    """
    logger.info(f"Reading {tagsets_json}")
    start = perf_counter()
    with db.connect(db_file, memory_limit, threads) as connection:
        tagsets_added, tags_added = add_tagsets(connection, tagsets_json, ignore_existing)
    logger.info(
        f"Added {counted(tagsets_added, 'tagset')} and {counted(tags_added, 'tag')} "
        f"in {perf_counter() - start:.1f} s"
    )


@cli.command("add-tags")
@click.argument("db_file", type=EXISTING_FILE)
@click.argument("tags_json", type=EXISTING_FILE)
@duckdb_options
def add_tags_command(db_file: Path, tags_json: Path, memory_limit: str, threads: int | None):
    """Add the tags in TAGS_JSON to tagsets that exist in DB_FILE.

    \b
    TAGS_JSON is a list of tag lists, for example
    [{"tagset_name": "People", "tags": ["Cy", "Dee"]}]

    A tagset may have several entries. Its new tags take IDs in file order.
    """
    logger.info(f"Reading {tags_json}")
    start = perf_counter()
    with db.connect(db_file, memory_limit, threads) as connection:
        tags_added = add_tags(connection, tags_json)
    logger.info(f"Added {counted(tags_added, 'tag')} in {perf_counter() - start:.1f} s")


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
    [{"source": "v1.mp4", "source_type": "video", "thumbnail": "v1.jpg"},
     {"source": "v1_001.jpg", "source_type": "image", "group": "v1.mp4"}]

    The source_type is one of image, video, audio, text, other. The thumbnail and group are
    optional. A group names the source of another media, in MEDIAS_JSON or in DB_FILE.
    """
    logger.info(f"Reading {medias_json}")
    start = perf_counter()
    with db.connect(db_file, memory_limit, threads) as connection:
        medias_added, medias_skipped = add_medias(connection, medias_json, ignore_existing)
    if medias_skipped:
        logger.info(f"Skipped {counted(medias_skipped, 'media', 'medias')} that exist")
    logger.info(
        f"Added {counted(medias_added, 'media', 'medias')} in {perf_counter() - start:.1f} s"
    )


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
    [{"media_source": "v1.mp4", "tagsets": {"People": ["Anna", "Bo"], "Year": [2019]}}]

    Each media must exist in DB_FILE. A tagging for an unknown tagset, or for a value
    that is not a tag of its tagset, is skipped with a WARNING. Add missing values with
    m3db add-tags first.
    """
    logger.info(f"Reading {taggings_json}")
    start = perf_counter()
    with db.connect(db_file, memory_limit, threads) as connection:
        taggings_added = add_taggings(connection, taggings_json)
    logger.info(f"Added {counted(taggings_added, 'tagging')} in {perf_counter() - start:.1f} s")
