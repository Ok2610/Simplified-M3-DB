rm -f example.duckdb

echo "Building example.duckdb from the example JSON files"
uv run m3db build example.duckdb .

echo "All done"
