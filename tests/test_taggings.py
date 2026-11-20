"""Tests for m3db add-taggings."""

import pytest

TAGSETS = [
    {"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Bo"]},
    {"name": "Year", "tagtype": "numerical_int", "tags": [2019, 2020]},
    {"name": "Day", "tagtype": "date", "tags": ["2019-01-02"]},
]
MEDIAS = [
    {"source": "a.jpg", "source_type": "image"},
    {"source": "b.jpg", "source_type": "image"},
]


@pytest.fixture
def loaded_db(m3db, new_db, write_json):
    """A test database with the tagsets People, Year and Day, and the medias a.jpg and b.jpg."""
    m3db("add-tagsets", new_db, write_json("tagsets.json", TAGSETS))
    m3db("add-medias", new_db, write_json("medias.json", MEDIAS))
    return new_db


def all_taggings(query) -> list[tuple]:
    """Every tagging as (media source, tagset name, value as text), sorted."""
    return query(
        """
        SELECT m.source, ts.name, coalesce(a.value, n.value::VARCHAR, d.value::VARCHAR)
        FROM taggings tg
        JOIN medias m ON m.id = tg.media_id
        JOIN tags t ON t.id = tg.tag_id
        JOIN tagsets ts ON ts.id = t.tagset_id
        LEFT JOIN alphanumerical_tags a ON a.id = t.id
        LEFT JOIN numerical_int_tags n ON n.id = t.id
        LEFT JOIN date_tags d ON d.id = t.id
        ORDER BY ALL
        """
    )


def test_taggings_join_medias_and_tags_by_source_tagset_and_value(
    m3db, loaded_db, write_json, query
):
    taggings = [
        {"media_source": "a.jpg", "tagsets": {"People": ["Anna", "Bo"], "Year": [2019]}},
        {"media_source": "b.jpg", "tagsets": {"Day": ["2019-01-02"]}},
    ]

    result = m3db("add-taggings", loaded_db, write_json("taggings.json", taggings))

    assert result.exit_code == 0, result.output
    assert "Added 4 taggings" in result.stderr
    assert all_taggings(query) == [
        ("a.jpg", "People", "Anna"),
        ("a.jpg", "People", "Bo"),
        ("a.jpg", "Year", "2019"),
        ("b.jpg", "Day", "2019-01-02"),
    ]


def test_values_match_by_type_not_by_text(m3db, loaded_db, write_json, query):
    taggings = [{"media_source": "a.jpg", "tagsets": {"Year": ["2020"], "Day": ["2019-1-2"]}}]

    m3db("add-taggings", loaded_db, write_json("taggings.json", taggings))

    assert all_taggings(query) == [("a.jpg", "Day", "2019-01-02"), ("a.jpg", "Year", "2020")]


def test_a_tagging_listed_twice_is_added_once(m3db, loaded_db, write_json, query):
    taggings = [
        {"media_source": "a.jpg", "tagsets": {"People": ["Anna", "Anna"]}},
        {"media_source": "a.jpg", "tagsets": {"People": ["Anna"]}},
    ]

    m3db("add-taggings", loaded_db, write_json("taggings.json", taggings))

    assert all_taggings(query) == [("a.jpg", "People", "Anna")]


def test_a_rerun_adds_nothing(m3db, loaded_db, write_json, query):
    taggings_json = write_json(
        "taggings.json", [{"media_source": "a.jpg", "tagsets": {"People": ["Anna"]}}]
    )
    m3db("add-taggings", loaded_db, taggings_json)

    result = m3db("add-taggings", loaded_db, taggings_json)

    assert result.exit_code == 0, result.output
    assert "Added 0 taggings" in result.stderr
    assert all_taggings(query) == [("a.jpg", "People", "Anna")]


# Taggings that are skipped and reported


def test_taggings_for_an_unknown_tagset_are_skipped_and_reported(
    m3db, loaded_db, write_json, query
):
    taggings = [{"media_source": "a.jpg", "tagsets": {"Place": ["Oslo", "Rome"], "People": ["Bo"]}}]

    result = m3db("add-taggings", loaded_db, write_json("taggings.json", taggings))

    assert result.exit_code == 0, result.output
    assert 'Skipped 2 taggings for the unknown tagset "Place"' in result.stderr
    assert all_taggings(query) == [("a.jpg", "People", "Bo")]


def test_taggings_for_values_that_are_not_tags_are_skipped_and_reported(
    m3db, loaded_db, write_json, query
):
    taggings = [
        {"media_source": "a.jpg", "tagsets": {"People": ["Cy", "Dee", "Eli", "Fay", "Bo"]}},
    ]

    result = m3db("add-taggings", loaded_db, write_json("taggings.json", taggings))

    assert result.exit_code == 0, result.output
    assert (
        'Skipped 4 taggings whose value is not a tag of "People", '
        'for example "Cy", "Dee", "Eli"' in result.stderr
    )
    assert all_taggings(query) == [("a.jpg", "People", "Bo")]


def test_taggings_whose_value_does_not_fit_are_skipped_and_reported(
    m3db, loaded_db, write_json, query
):
    taggings = [{"media_source": "a.jpg", "tagsets": {"Year": ["soon", 2019]}}]

    result = m3db("add-taggings", loaded_db, write_json("taggings.json", taggings))

    assert result.exit_code == 0, result.output
    assert (
        'Skipped 1 tagging whose value does not fit the numerical_int tagset "Year", '
        'for example "soon"' in result.stderr
    )
    assert all_taggings(query) == [("a.jpg", "Year", "2019")]


# Errors that stop the command


@pytest.mark.parametrize(
    "taggings, message",
    [
        (
            [{"media_source": "z.jpg", "tagsets": {"People": ["Anna"]}}],
            'Media "z.jpg" in taggings.json does not exist',
        ),
        (
            [{"tagsets": {"People": ["Anna"]}}],
            "A tagging in taggings.json has no media_source (entry 2)",
        ),
    ],
)
def test_bad_taggings_stop_the_command_and_change_nothing(
    m3db, loaded_db, write_json, query, taggings, message
):
    good = [{"media_source": "a.jpg", "tagsets": {"People": ["Anna"]}}]

    result = m3db("add-taggings", loaded_db, write_json("taggings.json", good + taggings))

    assert result.exit_code == 1
    assert message in result.stderr
    assert all_taggings(query) == []
