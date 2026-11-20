"""Tests for m3db build."""

import json
from pathlib import Path

import duckdb

TAGSETS = [
    {"name": "People", "tagtype": "alphanumerical", "tags": ["Anna"]},
    {"name": "Year", "tagtype": "numerical_int", "tags": []},
]
TAGS = [{"tagset_name": "People", "tags": ["Bo"]}, {"tagset_name": "Year", "tags": [2019, 2020]}]
MEDIAS = [
    {"source": "v1.mp4", "source_type": "video"},
    {"source": "a.jpg", "source_type": "image", "group": "v1.mp4"},
]
TAGGINGS = [
    {"media_source": "v1.mp4", "tagsets": {"Year": [2019]}},
    {"media_source": "a.jpg", "tagsets": {"People": ["Anna", "Bo"], "Year": [2020]}},
]
TABLES = ["tagsets", "tags", "alphanumerical_tags", "numerical_int_tags", "medias", "taggings"]


def write_folder(folder: Path, files: dict[str, list]) -> Path:
    """Write each JSON file of FILES (name to data) into FOLDER and return FOLDER."""
    folder.mkdir()
    for name, data in files.items():
        (folder / name).write_text(json.dumps(data))
    return folder


def all_rows(db_file: Path) -> dict[str, list[tuple]]:
    """Every row of the loaded tables in DB_FILE, sorted, per table."""
    with duckdb.connect(db_file, read_only=True) as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in TABLES
        }


def build_with_separate_commands(m3db, db_file: Path, folder: Path, names: list[str]) -> None:
    """Build DB_FILE with init and one add command per file in NAMES, in that order."""
    m3db("init", db_file)
    for name in names:
        command = "add-" + Path(name).stem.split("_")[-1]
        m3db(command, db_file, folder / name)


def test_build_gives_the_same_database_as_the_separate_commands(m3db, tmp_path):
    files = {
        "tagsets.json": TAGSETS,
        "tags.json": TAGS,
        "medias.json": MEDIAS,
        "taggings.json": TAGGINGS,
    }
    folder = write_folder(tmp_path / "collection", files)

    result = m3db("build", tmp_path / "built.duckdb", folder)
    build_with_separate_commands(m3db, tmp_path / "separate.duckdb", folder, list(files))

    assert "Built" in result.stderr
    assert all_rows(tmp_path / "built.duckdb") == all_rows(tmp_path / "separate.duckdb")
    assert len(all_rows(tmp_path / "built.duckdb")["taggings"]) == 4


def test_build_skips_a_missing_tags_json(m3db, tmp_path):
    folder = write_folder(tmp_path / "collection", {"tagsets.json": TAGSETS, "medias.json": MEDIAS})

    result = m3db("build", tmp_path / "built.duckdb", folder)

    assert "No tags file" in result.stderr
    assert "No taggings file" in result.stderr
    assert len(all_rows(tmp_path / "built.duckdb")["medias"]) == 2


def test_split_files_load_one_at_a_time_in_name_order(m3db, tmp_path):
    split = {
        "tagsets.json": TAGSETS,
        "year_tags.json": TAGS[1:],
        "people_tags.json": TAGS[:1],
        "medias.json": MEDIAS,
        "b_taggings.json": TAGGINGS[1:],
        "a_taggings.json": TAGGINGS[:1],
    }
    folder = write_folder(tmp_path / "collection", split)
    in_name_order = [
        "tagsets.json",
        "people_tags.json",
        "year_tags.json",
        "medias.json",
        "a_taggings.json",
        "b_taggings.json",
    ]

    m3db("build", tmp_path / "built.duckdb", folder)
    build_with_separate_commands(m3db, tmp_path / "separate.duckdb", folder, in_name_order)

    assert all_rows(tmp_path / "built.duckdb") == all_rows(tmp_path / "separate.duckdb")


def test_a_json_file_with_another_name_is_ignored_with_a_warning(m3db, tmp_path):
    folder = write_folder(tmp_path / "collection", {"tagsets.json": TAGSETS, "notes.json": []})

    result = m3db("build", tmp_path / "built.duckdb", folder)

    assert "Ignored notes.json" in result.stderr


def test_an_error_in_a_file_stops_the_build(m3db, tmp_path):
    bad_taggings = [{"media_source": "z.jpg", "tagsets": {"People": ["Anna"]}}]
    files = {"tagsets.json": TAGSETS, "medias.json": MEDIAS, "taggings.json": bad_taggings}
    folder = write_folder(tmp_path / "collection", files)

    result = m3db("build", tmp_path / "built.duckdb", folder, exit_code=1)

    assert 'Media "z.jpg" in taggings.json does not exist' in result.stderr
    assert "Built" not in result.stderr


def test_a_folder_without_m3_files_stops_the_build(m3db, tmp_path):
    folder = write_folder(tmp_path / "collection", {})

    result = m3db("build", tmp_path / "built.duckdb", folder, exit_code=1)

    assert "No tagsets, tags, medias or taggings files" in result.stderr
    assert not (tmp_path / "built.duckdb").exists()


def test_build_on_an_existing_file_asks_and_stops_when_declined(m3db, tmp_path, query):
    folder = write_folder(tmp_path / "collection", {"tagsets.json": TAGSETS})
    db_file = tmp_path / "test.duckdb"
    m3db("build", db_file, folder)

    result = m3db("build", db_file, folder, input="n\n", exit_code=1)

    assert "every table" in result.stderr
    assert query("SELECT count(*) FROM tagsets") == [(2,)]


# JSONL files


def write_jsonl_folder(folder: Path, files: dict[str, list]) -> Path:
    """Write each file of FILES (name to data) into FOLDER as one JSON object per line."""
    folder.mkdir()
    for name, data in files.items():
        (folder / name).write_text("".join(json.dumps(entry) + "\n" for entry in data))
    return folder


def test_jsonl_files_give_the_same_database_as_json_files(m3db, tmp_path):
    files = {"tagsets": TAGSETS, "tags": TAGS, "medias": MEDIAS, "taggings": TAGGINGS}
    json_folder = write_folder(tmp_path / "json", {f"{k}.json": v for k, v in files.items()})
    jsonl_folder = write_jsonl_folder(
        tmp_path / "jsonl", {f"{k}.jsonl": v for k, v in files.items()}
    )

    m3db("build", tmp_path / "from_json.duckdb", json_folder)
    m3db("build", tmp_path / "from_jsonl.duckdb", jsonl_folder)

    assert all_rows(tmp_path / "from_jsonl.duckdb") == all_rows(tmp_path / "from_json.duckdb")


def test_a_folder_with_both_tagsets_json_and_tagsets_jsonl_stops_the_build(m3db, tmp_path):
    folder = write_folder(tmp_path / "collection", {"tagsets.json": TAGSETS})
    (folder / "tagsets.jsonl").write_text(json.dumps(TAGSETS[0]) + "\n")

    result = m3db("build", tmp_path / "built.duckdb", folder, exit_code=1)

    assert "has both tagsets.json and tagsets.jsonl" in result.stderr


def test_a_file_that_is_not_json_or_jsonl_stops_the_command(m3db, new_db, tmp_path):
    tagsets_txt = tmp_path / "tagsets.txt"
    tagsets_txt.write_text(json.dumps(TAGSETS))

    result = m3db("add-tagsets", new_db, tagsets_txt, exit_code=1)

    assert "tagsets.txt is not a .json or .jsonl file" in result.stderr


def test_a_jsonl_line_too_long_stops_with_advice_to_split_it(m3db, new_db, tmp_path):
    big_tags = tmp_path / "tags.jsonl"
    big_tags.write_text(json.dumps({"tagset_name": "People", "tags": ["x" * 1000] * 40_000}) + "\n")

    result = m3db("add-tags", new_db, big_tags, exit_code=1)

    assert "tags.jsonl has a line too long to read as JSONL" in result.stderr
    assert "Split" in result.stderr


def test_every_kind_is_found_by_the_end_of_its_name_and_loads_in_kind_order(m3db, tmp_path):
    files = {
        "v3c_taggings.json": TAGGINGS,
        "b_medias.json": MEDIAS[1:],
        "a_medias.jsonl": MEDIAS[:1],
        "v3c_tags.json": TAGS,
        "v3c_tagsets.json": TAGSETS,
    }
    folder = write_folder(
        tmp_path / "collection", {k: v for k, v in files.items() if k.endswith("json")}
    )
    (folder / "a_medias.jsonl").write_text(json.dumps(MEDIAS[0]) + "\n")
    load_order = [
        "v3c_tagsets.json",
        "v3c_tags.json",
        "a_medias.jsonl",
        "b_medias.json",
        "v3c_taggings.json",
    ]

    result = m3db("build", tmp_path / "built.duckdb", folder)
    build_with_separate_commands(m3db, tmp_path / "separate.duckdb", folder, load_order)

    positions = [result.stderr.index(f"Reading {folder / name}") for name in load_order]
    assert positions == sorted(positions)
    assert all_rows(tmp_path / "built.duckdb") == all_rows(tmp_path / "separate.duckdb")
