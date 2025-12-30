# Simplified-M3-DB
A database loader for a simplified version (no hierarchies) of the ObjectCube data model using DuckDB

## Example

**Initialize Database**

```bash
uv run python main.py initdb <database_name>
```

```bash
uv run python main.py initdb testdb
```

**Add Tagsets**

```bash
uv run python main.py add-tagsets-from-json <database_file> <tagset_json_file> <--ignore-existing>
```

```bash
uv run python main.py add-tagsets-from-json testdb.db example/example_tagsets.json
```

**Add Tags**

```bash
uv run python main.py add-tagsets-from-json <database_file> <tags_json_file>
```

```bash
uv run python main.py add-tags-from-json testdb.db example/example_tags.json
```