"""Fixtures shared by the m3db tests."""

import json
from pathlib import Path

import duckdb
import pytest
from click.testing import CliRunner, Result

from m3db.cli import cli


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    """Path of a .duckdb file that does not exist yet."""
    return tmp_path / "test.duckdb"


@pytest.fixture
def m3db():
    """Run the m3db command with a list of arguments, check its exit code, and return the Result.

    The exit code must be EXIT_CODE, 0 unless a test expects the command to fail.
    """

    def run(*args: str | Path, input: str | None = None, exit_code: int = 0) -> Result:
        result = CliRunner().invoke(cli, [str(arg) for arg in args], input=input)
        assert result.exit_code == exit_code, result.output
        return result

    return run


@pytest.fixture
def new_db(db_file: Path, m3db) -> Path:
    """Path of a .duckdb file made by m3db init."""
    m3db("init", db_file)
    return db_file


@pytest.fixture
def write_json(tmp_path: Path):
    """Write DATA as JSON to the file NAME in the test folder and return its path."""

    def write(name: str, data) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(data))
        return path

    return write


@pytest.fixture
def query(db_file: Path):
    """Run SQL on the test .duckdb file and return every row."""

    def run(sql: str) -> list[tuple]:
        with duckdb.connect(db_file, read_only=True) as connection:
            return connection.execute(sql).fetchall()

    return run
