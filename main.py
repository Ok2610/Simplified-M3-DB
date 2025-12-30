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


# TODO: Add CLI command for adding media and taggings from JSON
@cli.command()
@click.argument("db_file", type=Path)
@click.argument("medias_file", type=Path)
@click.option("--ignore-existing", is_flag=True, help="Ignore existing media groups.")
@click.option("--no-groups", is_flag=True, help="There are no media groups.")
def add_medias_from_json(db_file: Path, medias_file: Path, ignore_existing: bool = False, no_groups: bool = False):
    """
    Add media objects from a JSON file.
    
    Parameters:
    - db_file: Path to the DuckDB database file.
    - medias_file: Path to the JSON file containing media objects.
    - ignore_existing: Whether to ignore existing media entries.
    - no_groups: Whether there are no media groups.

    Example JSON format:
    [
        {
            "source": "media_src_path.mp4/jpg/text",
            "source_type": "image|video|audio|text|other", 
            "thumbnail": "thumnail_src_path.jpg",
            "group": "media_src_path.mp4"
        },
    ]

    Note that the thumbnail and group fields are optional
    """
    if not db_file.exists():
        raise FileNotFoundError(f"Database file not found: {db_file}")

    if not medias_file.exists():
        raise FileNotFoundError(f"Medias file not found: {medias_file}")

    try:
        with open(medias_file, 'r') as f:
            medias_data : List[sdl.MediaObject] = []
            for mo in json.load(f):
                medias_data.append(
                    sdl.MediaObject(
                        mo['source'], 
                        mo['source_type'],
                        mo.get('thumbnail', None),
                        mo.get('group', None)
                    )
                )
            with duckdb.connect(db_file) as connection:
                sdl.add_media_objects(connection, medias_data, ignore_existing, no_groups)
    except Exception as e:
        print("Error loading media objects from JSON:", e)


if __name__ == "__main__":
    cli()