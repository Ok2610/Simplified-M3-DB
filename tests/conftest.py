"""Fixtures shared by the m3db tests."""
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from m3db.cli import cli


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    """Path of a .duckdb file that does not exist yet."""
    return tmp_path / "test.duckdb"


@pytest.fixture
def m3db():
    """Run the m3db command with a list of arguments and return the click Result."""
    def run(*args: str | Path, input: str | None = None) -> Result:
        return CliRunner().invoke(cli, [str(arg) for arg in args], input=input)
    return run
