"""Load Simplified M3 JSON files into DuckDB and copy them to SQLite."""

__version__ = "0.1.0"


class M3DBError(Exception):
    """A problem in the input files or the database that stops an m3db command."""
