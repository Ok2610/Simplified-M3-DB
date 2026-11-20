# Simplified Multi-dimensional Media Model (M<sup>3</sup>)

A structured database for storing multimedia metadata, built from JSON files into DuckDB and copied to SQLite.
This is a simplified version of the multi-dimensional media model M<sup>3</sup> (pronounced emm-cube) ([Paper1](https://dl.acm.org/doi/abs/10.1145/3549555.3549558), [Paper2](https://dl.acm.org/doi/abs/10.1145/3512527.3531352)).

The model represents media entities, such as videos, images and texts, and attaches typed metadata to them in a consistent way.

* A tagset is a metadata category, for example "Category" or "Upload Date".
* A tag is a value within a tagset, for example "Urban" under "Category".
* A tagtype is the data type of a tagset's values: text, integer, decimal, date, timestamp, time or JSON.

[The M3 model](docs/model.md) explains the model with a worked example, the ER diagram and the tables.

## Quick start

Install the dependencies with [uv](https://docs.astral.sh/uv/), then build the example collection.

```bash
uv sync
cd example
bash example.sh        # or ./example.ps1 in PowerShell
```

The script builds `example.duckdb` from the JSON files in the folder, then copies it to the SQLite file `example.db`.

```bash
uv run m3db build example.duckdb .
uv run m3db to-sqlite example.duckdb example.db
```

## Your own collection

Describe the collection in four JSON files, and put them in one folder.

| File | Holds |
|---|---|
| `tagsets.json` | The tagsets, each with its tagtype and optionally its values |
| `tags.json` | More values for tagsets that exist (optional) |
| `medias.json` | The medias, with an optional thumbnail and group |
| `taggings.json` | The values of each media, per tagset |

For example, a video and one of its keyframes, both tagged with a category.

```jsonc
// tagsets.json
[
    {
        "name": "Category",
        "tagtype": "alphanumerical",
        "tags": ["Urban"]
    }
]

// medias.json
[
    {
        "source": "traffic.mp4",
        "source_type": "video"
    },
    {
        "source": "traffic_frame_12000.jpg",
        "source_type": "image",
        "group": "traffic.mp4"
    }
]

// taggings.json
[
    {
        "media_source": "traffic.mp4",
        "tagsets": {
            "Category": ["Urban"]
        }
    },
    {
        "media_source": "traffic_frame_12000.jpg",
        "tagsets": {
            "Category": ["Urban"]
        }
    }
]
```

Then build the database, and copy it to SQLite if you need a SQLite file.

```bash
uv run m3db build traffic.duckdb path/to/folder
uv run m3db to-sqlite traffic.duckdb traffic.db
```

The loader checks every file, and stops with an error that names the problem, such as a value that does not fit its tagtype or a tagging for a media that does not exist.

## Learn more

* [The JSON files](docs/json-files.md) describes each file in full, splitting a large collection over several files, media groups, and JSONL.
* [Commands](docs/commands.md) covers adding files to an existing database, what the loader checks, `to-sqlite` and `to-duckdb`, and the options for memory and logging.
* [Query examples](example/queries.md) shows SQL queries on the example collection, from simple lookups to filters on several tagsets.
* [The M3 model](docs/model.md) explains the model, the ER diagram and the tables.

## Development

```bash
uv run pytest                     # the tests, one file per module in tests/
uv run ruff format m3db tests     # format the code
uv run ruff check m3db tests      # lint the code
```
