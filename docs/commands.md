# Commands

## Building in one step

`m3db build` creates the DuckDB file and loads every M3 file in a folder.

```bash
uv run m3db build v3c.duckdb collections/v3c
```

A file's kind is the end of its name ([details](json-files.md)), so `tags.json`, `v3c_tags.json` and `people_tags.jsonl` are all tags files. The kinds load in the order tagsets, tags, medias, taggings, and files of one kind load in name order. A file that fails stops the build, and the files before it stay loaded.

## Building step by step

The same work as separate commands, which also add files to an existing database.

```bash
uv run m3db init v3c.duckdb
uv run m3db add-tagsets v3c.duckdb tagsets.json
uv run m3db add-tags v3c.duckdb tags.json
uv run m3db add-medias v3c.duckdb medias.json
uv run m3db add-taggings v3c.duckdb taggings.json
```

`init` on an existing file asks before it drops and recreates every table. Adding a tagset or media that exists stops with an error, unless `--ignore-existing` is given to `add-tagsets` or `add-medias`.

Run `uv run m3db COMMAND --help` for the details of each command.

## What the loader checks

Each command loads its file in one transaction, so a failed command leaves the database as it was.

These problems stop the command with an error that names them:

* an unknown tag type or source type;
* a value that does not fit its tag type, such as `"soon"` in a `numerical_int` tagset;
* a tagset in `tags.json`, or a media in `taggings.json`, that does not exist;
* a `group` that names no media;
* a tagset or media listed twice, or one that exists, without `--ignore-existing`.

These taggings are skipped with a WARNING that counts them per tagset and shows up to 3 examples:

* taggings for a tagset that does not exist;
* taggings for a value that is not a tag of its tagset;
* taggings for a value that does not fit the tag type.

Before every commit, the loader also checks the whole database for duplicate keys and for IDs that point to nothing.

## SQLite and DuckDB files

`to-sqlite` writes a SQLite file from a DuckDB file, and `to-duckdb` does the opposite.

```bash
uv run m3db to-sqlite v3c.duckdb v3c.db
uv run m3db to-duckdb v3c.db v3c.duckdb
```

* `to-sqlite` uses the schema in [m3db/ddl.sql](../m3db/ddl.sql) with 16 KB pages, builds the indexes and runs `ANALYZE`. It checks the DuckDB file before the copy and the SQLite file after it.
* `to-duckdb` reads a SQLite file in the current schema or in the one older versions of this repository wrote, and casts every value to its DuckDB type.
* Both refuse an output file that exists, and delete their output on any problem.

SQLite is faster for looking up a page of medias with their metadata. DuckDB is faster for filters and searches that touch many rows, and keeps dates, times and decimals in their own types.

## Options

| Option | Commands | Default | Effect |
|---|---|---|---|
| `--memory-limit` | every command that loads or copies | `8GB` | Memory DuckDB may use for data. Work over it spills to a `.tmp` folder next to the output file, so a collection bigger than memory can still be loaded. The process uses some memory beyond the limit. |
| `--threads` | every command that loads or copies | all cores | Threads DuckDB may use. Fewer threads use less memory. |
| `--cache-mb` | `to-sqlite` | `1024` | SQLite page cache in MB while the indexes are built. |
| `--log-level` | `m3db` itself, before the command | `INFO` | `DEBUG` adds the time of each phase, and `TRACE` adds every SQL statement. |

```bash
uv run m3db --log-level DEBUG build v3c.duckdb collections/v3c --memory-limit 2GB
```

A `.duckdb` file can be written by one process at a time, so close other programs that have it open before loading into it.
