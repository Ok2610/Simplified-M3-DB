Remove-Item example.duckdb -ErrorAction SilentlyContinue

Write-Output "Building example.duckdb from the example JSON files"
uv run m3db build example.duckdb .

Write-Output "All done"
