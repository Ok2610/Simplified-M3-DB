"""Load Simplified M3 JSON files into DuckDB and copy them to SQLite."""

from importlib.metadata import version

__version__ = version("simplified-m3-db")


class M3DBError(Exception):
    """A problem in the input files or the database that stops an m3db command."""
