"""The m3db command and its subcommands."""
import sys
from pathlib import Path

import click
import duckdb
from loguru import logger

from m3db import M3DBError, db
from m3db.logs import LEVELS, setup_logging


class M3DBGroup(click.Group):
    """A click group that prints an M3DBError or DuckDB error as one ERROR line and exits with code 1."""

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
    help="Show messages at this level and above. DEBUG adds phase timings, TRACE adds every SQL statement.",
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
        logger.warning(f"{db_file} exists. init drops and recreates every table, so all its data is lost.")
        if not click.confirm("Continue?", default=False, err=True):
            logger.info(f"Stopped. {db_file} is unchanged.")
            sys.exit(1)

    with db.connect(db_file) as connection:
        db.create_schema(connection)
    logger.info(f"Created {db_file}")
