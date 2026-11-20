# Build example.duckdb from the example JSON files, then copy it to example.db for SQLite
Remove-Item example.duckdb, example.db -ErrorAction SilentlyContinue

uv run m3db build example.duckdb .
uv run m3db to-sqlite example.duckdb example.db
