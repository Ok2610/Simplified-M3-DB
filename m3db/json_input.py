"""Read the M3 JSON files with DuckDB, keeping the position of each row in the file."""

from pathlib import Path


def read_json(path: Path, columns: dict[str, str]) -> str:
    """Return SQL that reads the JSON array in PATH as rows with COLUMNS (name to DuckDB type).

    Each row also gets `ordinality`, its position in the file starting at 1.
    A key missing from an object reads as NULL.
    """
    quoted_path = str(path).replace("'", "''")
    column_types = ", ".join(f"'{name}': '{sql_type}'" for name, sql_type in columns.items())
    return (
        f"read_json('{quoted_path}', format = 'array', columns = {{{column_types}}})"
        " WITH ORDINALITY"
    )
