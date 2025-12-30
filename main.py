import click
import json
import duckdb
from typing import List
from pathlib import Path

from SimpleDataLoader import Tagset, Tags, TagType
import SimpleDataLoader as sdl

@click.group()
def cli():
    pass

@cli.command()
@click.argument("dbname", type=str)
def initdb(dbname: str):
    """Initializa the database with the given name in the current directory."""
    import os
    os.system(f"duckdb {dbname}.db -f ddl.sql")

@cli.command()
@click.argument("db_file", type=Path)
@click.argument("tagsets_f", type=Path)
@click.option("--ignore-existing", is_flag=True, help="Ignore existing tagsets.")
def add_tagsets_from_json(db_file: Path, tagsets_f: Path, ignore_existing: bool = False):
    """
    Add tagsets from a JSON file.
    
    Parameters:
    - db_file: Path to the DuckDB database file.
    - tagsets_f: Path to the JSON file containing tagsets.

    Example JSON format:
    [
        {"name": "Tagset1", "tagtype": "alphanumerical", "tags": []},
    ]
    """
    if not db_file.exists():
        raise FileNotFoundError(f"Database file not found: {db_file}")

    if not tagsets_f.exists():
        raise FileNotFoundError(f"Tagsets file not found: {tagsets_f}")

    try:
        with open(tagsets_f, 'r') as f:
            tagsets_data : List[Tagset] = []
            for ts in json.load(f):
                if ts['tagtype'].upper() not in TagType.__members__:
                    raise ValueError(f"Invalid tag type: ({ts['name'], ts['tagtype']})")
                tagsets_data.append(
                    Tagset(
                        ts['name'], 
                        TagType[ts['tagtype'].upper()],
                        Tags(ts['name'], ts['tags'])
                    )
                )
            with duckdb.connect(db_file) as connection:
                sdl.add_tagsets(connection, tagsets_data, ignore_existing)
    except Exception as e:
        print("Error loading tagsets from JSON:", e)


@cli.command()
@click.argument("db_file", type=Path)
@click.argument("tags_file", type=Path)
def add_tags_from_json(db_file: Path, tags_file: Path):
    """
    Add tags from a JSON file.
    
    Parameters:
    - db_file: Path to the DuckDB database file.
    - tags_file: Path to the JSON file containing tags.

    Example JSON format:
    [
        {"tagset_name": "Tagset1", "tags": []},
    ]
    """
    if not db_file.exists():
        raise FileNotFoundError(f"Database file not found: {db_file}")

    if not tags_file.exists():
        raise FileNotFoundError(f"Tags file not found: {tags_file}")

    try:
        with open(tags_file, 'r') as f:
            tags_data : List[Tags] = []
            for tg in json.load(f):
                tags_data.append(
                    Tags(
                        tg['tagset_name'], 
                        tg['tags']
                    )
                )
            with duckdb.connect(db_file) as connection:
                for tags in tags_data:
                    sdl.add_tags(connection, tags)
    except Exception as e:
        print("Error loading tags from JSON:", e)



if __name__ == "__main__":
    cli()