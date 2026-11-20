"""Tests for the database checks that every add command runs before it commits."""

import duckdb
import pytest

from m3db import M3DBError
from m3db.checks import run_checks

TAGSETS = [{"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Bo"]}]
MEDIAS = [{"source": "a.jpg", "source_type": "image"}, {"source": "b.jpg", "source_type": "image"}]
TAGGINGS = [{"media_source": "a.jpg", "tagsets": {"People": ["Anna"]}}]


@pytest.fixture
def loaded_db(m3db, new_db, write_json):
    """A test database with 1 tagset, 2 tags, 2 medias and 1 tagging, which passes every check."""
    m3db("add-tagsets", new_db, write_json("tagsets.json", TAGSETS))
    m3db("add-medias", new_db, write_json("medias.json", MEDIAS))
    m3db("add-taggings", new_db, write_json("taggings.json", TAGGINGS))
    return new_db


@pytest.mark.parametrize(
    "break_sql, message",
    [
        (
            "INSERT INTO medias VALUES (3, 'a.jpg', 1, NULL, NULL)",
            "1 medias.source listed twice",
        ),
        (
            "INSERT INTO medias VALUES (2, 'c.jpg', 1, NULL, NULL)",
            "1 medias.id listed twice",
        ),
        (
            "UPDATE medias SET group_id = 9 WHERE id = 2",
            "1 medias.group_id with no media",
        ),
        (
            "UPDATE medias SET source_type = 9 WHERE id = 1",
            "1 medias.source_type with no source type",
        ),
        (
            "UPDATE tags SET tagtype_id = 5 WHERE id = 1",
            "1 tags with no tagset of the same tag type",
        ),
        (
            "UPDATE tags SET tagset_id = 9 WHERE id = 1; "
            "UPDATE alphanumerical_tags SET tagset_id = 9 WHERE id = 1",
            "1 tag value rows with no tagset",
        ),
        (
            "INSERT INTO tags VALUES (2, 1, 1); "
            "INSERT INTO alphanumerical_tags VALUES (2, 'Cy', 1)",
            "1 tags.id listed twice",
        ),
        (
            "INSERT INTO tags VALUES (3, 1, 1); "
            "INSERT INTO alphanumerical_tags VALUES (3, 'Bo', 1)",
            "1 tag values listed twice in a tagset",
        ),
        (
            "INSERT INTO tags VALUES (3, 1, 1)",
            "1 tags without exactly one value row",
        ),
        (
            "INSERT INTO alphanumerical_tags VALUES (3, 'Cy', 1)",
            "1 tag value rows with no tags row",
        ),
        (
            "INSERT INTO taggings VALUES (1, 1)",
            "1 taggings listed twice",
        ),
        (
            "INSERT INTO taggings VALUES (1, 9)",
            "1 taggings.tag_id with no tag",
        ),
        (
            "INSERT INTO taggings VALUES (9, 1)",
            "1 taggings.media_id with no media",
        ),
    ],
)
def test_each_check_finds_its_problem(loaded_db, break_sql, message):
    with duckdb.connect(loaded_db) as connection:
        connection.execute(break_sql)

        with pytest.raises(M3DBError, match=message):
            run_checks(connection)


def test_an_add_command_on_a_broken_database_stops_and_changes_nothing(
    m3db, loaded_db, write_json, query
):
    with duckdb.connect(loaded_db) as connection:
        connection.execute("INSERT INTO taggings VALUES (9, 1)")

    result = m3db(
        "add-medias",
        loaded_db,
        write_json("more.json", [{"source": "c.jpg", "source_type": "image"}]),
        exit_code=1,
    )

    assert "1 taggings.media_id with no media" in result.stderr
    assert query("SELECT count(*) FROM medias") == [(2,)]
