"""Read the M3 JSON and JSONL files with DuckDB, keeping the position of each row in the file."""

from pathlib import Path

from m3db import M3DBError

# The DuckDB read_json format for each file extension: a JSON list, or one object per line
JSON_FORMATS = {".json": "array", ".jsonl": "newline_delimited"}


def read_json(path: Path, columns: dict[str, str]) -> str:
    """Return SQL that reads the .json or .jsonl file PATH as rows with COLUMNS (name to type).

    Each row also gets `ordinality`, its position in the file starting at 1.
    A key missing from an object reads as NULL.
    """
    if path.suffix not in JSON_FORMATS:
        raise M3DBError(f"{path.name} is not a .json or .jsonl file.")
    quoted_path = str(path).replace("'", "''")
    column_types = ", ".join(f"'{name}': '{sql_type}'" for name, sql_type in columns.items())
    return (
        f"read_json('{quoted_path}', format = '{JSON_FORMATS[path.suffix]}', "
        f"columns = {{{column_types}}}) WITH ORDINALITY"
    )
