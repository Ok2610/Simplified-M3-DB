# Build example.duckdb from the example JSON files, then copy it to example.db for SQLite
rm -f example.duckdb example.db

uv run m3db build example.duckdb .
uv run m3db to-sqlite example.duckdb example.db
