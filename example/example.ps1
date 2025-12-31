rm example.db

echo "Initializing example.db"
uv run python ../main.py initdb example ../ddl.sql

echo "Adding tagsets"
uv run python ../main.py add-tagsets-from-json example.db example_tagsets.json  

echo "Adding tags"
uv run python ../main.py add-tags-from-json example.db example_tags.json  

echo "Adding medias"
uv run python ../main.py add-medias-from-json example.db example_medias.json  

echo "Adding media taggings"
uv run python ../main.py add-media-taggings-from-json example.db example_taggings.json  

echo "All done"
