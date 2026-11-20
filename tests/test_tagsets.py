"""Tests for m3db add-tagsets and m3db add-tags."""

import datetime
from decimal import Decimal

import pytest

PEOPLE_AND_YEAR = [
    {"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Bo"]},
    {"name": "Year", "tagtype": "numerical_int", "tags": [2019, 2020, 2021]},
]


def all_tags(query) -> list[tuple]:
    """Every tag as (tag id, tagset name, value as text), in tag id order."""
    return query(
        """
        SELECT t.id, ts.name, coalesce(a.value, n.value::VARCHAR)
        FROM tags t
        JOIN tagsets ts ON ts.id = t.tagset_id
        LEFT JOIN alphanumerical_tags a ON a.id = t.id
        LEFT JOIN numerical_int_tags n ON n.id = t.id
        ORDER BY t.id
        """
    )


def database_snapshot(query) -> tuple:
    """The tagsets, tags and tag values in the test database, to show a command changed nothing."""
    return (
        query("SELECT * FROM tagsets ORDER BY id"),
        query("SELECT * FROM tags ORDER BY id"),
        all_tags(query),
    )


# add-tagsets: IDs and values


def test_tagsets_and_tags_take_ids_in_file_order(m3db, new_db, write_json, query):
    m3db("add-tagsets", new_db, write_json("tagsets.json", PEOPLE_AND_YEAR))

    assert query("SELECT id, name, tagtype_id FROM tagsets ORDER BY id") == [
        (1, "People", 1),
        (2, "Year", 5),
    ]
    assert all_tags(query) == [
        (1, "People", "Anna"),
        (2, "People", "Bo"),
        (3, "Year", "2019"),
        (4, "Year", "2020"),
        (5, "Year", "2021"),
    ]


def test_each_tag_type_is_stored_with_its_native_type(m3db, new_db, write_json, query):
    tagsets = [
        {"name": "Moment", "tagtype": "timestamp", "tags": ["2019-01-02 10:11:12"]},
        {"name": "Clock", "tagtype": "time", "tags": ["10:11:12"]},
        {"name": "Day", "tagtype": "date", "tags": ["2019-01-02"]},
        {"name": "Score", "tagtype": "numerical_dec", "tags": [0.5]},
        {"name": "Box", "tagtype": "json", "tags": [{"x": 1}]},
    ]
    m3db("add-tagsets", new_db, write_json("tagsets.json", tagsets))

    assert query("SELECT value FROM timestamp_tags") == [
        (datetime.datetime(2019, 1, 2, 10, 11, 12),)
    ]
    assert query("SELECT value FROM time_tags") == [(datetime.time(10, 11, 12),)]
    assert query("SELECT value FROM date_tags") == [(datetime.date(2019, 1, 2),)]
    assert query("SELECT value FROM numerical_dec_tags") == [(Decimal("0.50000"),)]
    assert query("SELECT value FROM json_tags") == [('{"x":1}',)]


def test_tag_types_are_matched_without_case(m3db, new_db, write_json, query):
    tagsets = [{"name": "People", "tagtype": "Alphanumerical", "tags": []}]

    m3db("add-tagsets", new_db, write_json("tagsets.json", tagsets))

    assert query("SELECT name, tagtype_id FROM tagsets") == [("People", 1)]


def test_a_tagset_without_tags_is_added(m3db, new_db, write_json, query):
    m3db(
        "add-tagsets",
        new_db,
        write_json("tagsets.json", [{"name": "People", "tagtype": "alphanumerical"}]),
    )

    assert query("SELECT name FROM tagsets") == [("People",)]


def test_a_value_listed_twice_keeps_its_first_position(m3db, new_db, write_json, query):
    tagsets = [
        {"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Bo", "Anna", "Cy"]}
    ]

    m3db("add-tagsets", new_db, write_json("tagsets.json", tagsets))

    assert all_tags(query) == [(1, "People", "Anna"), (2, "People", "Bo"), (3, "People", "Cy")]


def test_status_line_counts_what_was_added(m3db, new_db, write_json):
    result = m3db("add-tagsets", new_db, write_json("tagsets.json", PEOPLE_AND_YEAR))

    assert "Added 2 tagsets and 5 tags" in result.stderr


# add-tagsets: existing tagsets


def test_a_rerun_stops_on_the_existing_tagset_and_adds_nothing(m3db, new_db, write_json, query):
    tagsets_json = write_json("tagsets.json", PEOPLE_AND_YEAR)
    m3db("add-tagsets", new_db, tagsets_json)
    before = database_snapshot(query)

    result = m3db("add-tagsets", new_db, tagsets_json, exit_code=1)

    assert 'Tagset "People" already exists' in result.stderr
    assert database_snapshot(query) == before


def test_a_rerun_with_ignore_existing_adds_nothing(m3db, new_db, write_json, query):
    tagsets_json = write_json("tagsets.json", PEOPLE_AND_YEAR)
    m3db("add-tagsets", new_db, tagsets_json)
    before = database_snapshot(query)

    result = m3db("add-tagsets", new_db, tagsets_json, "--ignore-existing")

    assert "Added 0 tagsets and 0 tags" in result.stderr
    assert database_snapshot(query) == before


def test_ignore_existing_still_adds_new_tags_to_an_existing_tagset(m3db, new_db, write_json, query):
    m3db("add-tagsets", new_db, write_json("first.json", PEOPLE_AND_YEAR))
    more = [
        {"name": "People", "tagtype": "alphanumerical", "tags": ["Bo", "Dee"]},
        {"name": "Place", "tagtype": "alphanumerical", "tags": ["Oslo"]},
    ]

    m3db("add-tagsets", new_db, write_json("more.json", more), "--ignore-existing")

    assert query("SELECT id, name FROM tagsets ORDER BY id")[-1] == (3, "Place")
    assert all_tags(query)[-2:] == [(6, "People", "Dee"), (7, "Place", "Oslo")]


def test_a_tagset_listed_twice_stops_without_ignore_existing(m3db, new_db, write_json, query):
    tagsets = PEOPLE_AND_YEAR + [{"name": "People", "tagtype": "alphanumerical", "tags": []}]

    result = m3db("add-tagsets", new_db, write_json("tagsets.json", tagsets), exit_code=1)

    assert 'Tagset "People" is listed twice in tagsets.json' in result.stderr
    assert query("SELECT count(*) FROM tagsets") == [(0,)]


def test_a_tagset_listed_twice_with_ignore_existing_merges_its_tags(
    m3db, new_db, write_json, query
):
    tagsets = PEOPLE_AND_YEAR + [
        {"name": "People", "tagtype": "alphanumerical", "tags": ["Anna", "Cy"]}
    ]

    m3db("add-tagsets", new_db, write_json("tagsets.json", tagsets), "--ignore-existing")

    assert query("SELECT count(*) FROM tagsets") == [(2,)]
    assert all_tags(query)[-1] == (6, "People", "Cy")


# add-tagsets: errors that stop the command


@pytest.mark.parametrize(
    "tagsets, message",
    [
        (
            [{"name": "People", "tagtype": "words", "tags": []}],
            'Unknown tag type "words" for tagset "People"',
        ),
        ([{"name": "People", "tags": []}], 'Unknown tag type "" for tagset "People"'),
        ([{"tagtype": "alphanumerical", "tags": []}], "A tagset in tagsets.json has no name"),
        (
            [{"name": "Year", "tagtype": "numerical_int", "tags": [2019, "soon"]}],
            'Value "soon" in tagsets.json does not fit the numerical_int tagset "Year"',
        ),
        (
            [{"name": "Day", "tagtype": "date", "tags": ["2019-13-40"]}],
            'Value "2019-13-40" in tagsets.json does not fit the date tagset "Day"',
        ),
        (
            [{"name": "Nickname", "tagtype": "alphanumerical", "tags": [None]}],
            'Value "null" in tagsets.json does not fit the alphanumerical tagset "Nickname"',
        ),
    ],
)
def test_bad_tagsets_stop_the_command_and_change_nothing(
    m3db, new_db, write_json, query, tagsets, message
):
    result = m3db(
        "add-tagsets",
        new_db,
        write_json("tagsets.json", PEOPLE_AND_YEAR[:1] + tagsets),
        exit_code=1,
    )

    assert message in result.stderr
    assert database_snapshot(query) == ([], [], [])


def test_a_file_that_is_not_json_stops_the_command(m3db, new_db, tmp_path):
    broken = tmp_path / "tagsets.json"
    broken.write_text('[{"name": "People",')

    result = m3db("add-tagsets", new_db, broken, exit_code=1)

    assert "ERROR" in result.stderr


# add-tags


def test_add_tags_continues_the_tag_ids(m3db, new_db, write_json, query):
    m3db("add-tagsets", new_db, write_json("tagsets.json", PEOPLE_AND_YEAR))
    tags = [{"tagset_name": "People", "tags": ["Cy"]}, {"tagset_name": "Year", "tags": [2022]}]

    result = m3db("add-tags", new_db, write_json("tags.json", tags))

    assert "Added 2 tags" in result.stderr
    assert all_tags(query)[-2:] == [(6, "People", "Cy"), (7, "Year", "2022")]


def test_add_tags_keeps_file_order_for_a_tagset_split_over_entries(m3db, new_db, write_json, query):
    m3db("add-tagsets", new_db, write_json("tagsets.json", PEOPLE_AND_YEAR))
    tags = [
        {"tagset_name": "People", "tags": ["Cy", "Dee"]},
        {"tagset_name": "Year", "tags": [2022]},
        {"tagset_name": "People", "tags": ["Dee", "Eli"]},
    ]

    m3db("add-tags", new_db, write_json("tags.json", tags))

    assert all_tags(query)[5:] == [
        (6, "People", "Cy"),
        (7, "People", "Dee"),
        (8, "Year", "2022"),
        (9, "People", "Eli"),
    ]


def test_add_tags_skips_values_the_tagset_has(m3db, new_db, write_json, query):
    m3db("add-tagsets", new_db, write_json("tagsets.json", PEOPLE_AND_YEAR))
    tags_json = write_json("tags.json", [{"tagset_name": "People", "tags": ["Anna", "Cy"]}])

    m3db("add-tags", new_db, tags_json)
    rerun = m3db("add-tags", new_db, tags_json)

    assert "Added 0 tags" in rerun.stderr
    assert [value for (_, name, value) in all_tags(query) if name == "People"] == [
        "Anna",
        "Bo",
        "Cy",
    ]


@pytest.mark.parametrize(
    "tags, message",
    [
        (
            [{"tagset_name": "Place", "tags": ["Oslo"]}],
            'Tagset "Place" in tags.json does not exist',
        ),
        (
            [{"tagset_name": "Year", "tags": ["soon", "later"]}],
            'Value "soon" in tags.json does not fit the numerical_int tagset "Year", '
            "and 1 more value does not fit",
        ),
    ],
)
def test_bad_tags_stop_the_command_and_change_nothing(
    m3db, new_db, write_json, query, tags, message
):
    m3db("add-tagsets", new_db, write_json("tagsets.json", PEOPLE_AND_YEAR))
    before = database_snapshot(query)
    good = [{"tagset_name": "People", "tags": ["Cy"]}]

    result = m3db("add-tags", new_db, write_json("tags.json", good + tags), exit_code=1)

    assert message in result.stderr
    assert database_snapshot(query) == before
