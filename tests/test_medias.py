"""Tests for m3db add-medias."""

import pytest


def media(
    source: str, group: str | None = None, source_type: str = "image", thumbnail: str | None = None
) -> dict:
    """One medias.json entry, leaving out the keys that are None."""
    entry = {"source": source, "source_type": source_type, "thumbnail": thumbnail, "group": group}
    return {key: value for key, value in entry.items() if value is not None}


def medias_by_id(query) -> list[tuple]:
    """Every media as (id, source, source of its group), in id order."""
    return query(
        """
        SELECT m.id, m.source, g.source
        FROM medias m LEFT JOIN medias g ON g.id = m.group_id
        ORDER BY m.id
        """
    )


# IDs


def test_medias_without_groups_take_ids_in_file_order(m3db, new_db, write_json, query):
    m3db(
        "add-medias",
        new_db,
        write_json("medias.json", [media("b.jpg"), media("a.jpg"), media("c.jpg")]),
    )

    assert medias_by_id(query) == [(1, "b.jpg", None), (2, "a.jpg", None), (3, "c.jpg", None)]


def test_members_follow_their_leader_and_ungrouped_medias_keep_their_place(
    m3db, new_db, write_json, query
):
    medias = [media("v1.mp4"), media("a.jpg", "v1.mp4"), media("x.jpg"), media("b.jpg", "v1.mp4")]

    m3db("add-medias", new_db, write_json("medias.json", medias))

    assert medias_by_id(query) == [
        (1, "v1.mp4", None),
        (2, "a.jpg", "v1.mp4"),
        (3, "b.jpg", "v1.mp4"),
        (4, "x.jpg", None),
    ]


def test_a_member_listed_before_its_leader_follows_the_leader(m3db, new_db, write_json, query):
    medias = [media("a.jpg", "v1.mp4"), media("v1.mp4"), media("x.jpg")]

    m3db("add-medias", new_db, write_json("medias.json", medias))

    assert medias_by_id(query) == [(1, "v1.mp4", None), (2, "a.jpg", "v1.mp4"), (3, "x.jpg", None)]


def test_a_leader_that_is_also_a_member_follows_its_own_leader(m3db, new_db, write_json, query):
    medias = [
        media("v0.mp4"),
        media("s1.mp4", "v0.mp4"),
        media("k1.jpg", "s1.mp4"),
        media("s2.mp4", "v0.mp4"),
        media("k2.jpg", "s2.mp4"),
    ]

    m3db("add-medias", new_db, write_json("medias.json", medias))

    assert medias_by_id(query) == [
        (1, "v0.mp4", None),
        (2, "s1.mp4", "v0.mp4"),
        (3, "s2.mp4", "v0.mp4"),
        (4, "k1.jpg", "s1.mp4"),
        (5, "k2.jpg", "s2.mp4"),
    ]


def test_a_leader_listed_before_its_own_leader_keeps_its_place(m3db, new_db, write_json, query):
    medias = [media("s1.mp4", "v0.mp4"), media("k1.jpg", "s1.mp4"), media("v0.mp4")]

    m3db("add-medias", new_db, write_json("medias.json", medias))

    assert medias_by_id(query) == [
        (1, "s1.mp4", "v0.mp4"),
        (2, "k1.jpg", "s1.mp4"),
        (3, "v0.mp4", None),
    ]


def test_a_media_can_be_its_own_group(m3db, new_db, write_json, query):
    m3db("add-medias", new_db, write_json("medias.json", [media("v1.mp4", "v1.mp4")]))

    assert medias_by_id(query) == [(1, "v1.mp4", "v1.mp4")]


def test_source_type_and_thumbnail_are_stored(m3db, new_db, write_json, query):
    medias = [
        media("v1.mp4", source_type="Video", thumbnail="v1.jpg"),
        media("notes.txt", source_type="text"),
    ]

    m3db("add-medias", new_db, write_json("medias.json", medias))

    assert query(
        """
        SELECT m.source, s.name, m.thumbnail_uri
        FROM medias m JOIN source_types s ON s.id = m.source_type ORDER BY m.id
        """
    ) == [
        ("v1.mp4", "Video", "v1.jpg"),
        ("notes.txt", "Text", None),
    ]


def test_status_line_counts_what_was_added(m3db, new_db, write_json):
    result = m3db("add-medias", new_db, write_json("medias.json", [media("a.jpg"), media("b.jpg")]))

    assert "Added 2 medias" in result.stderr


# Medias that exist


def test_new_medias_continue_the_ids_and_may_join_an_existing_group(
    m3db, new_db, write_json, query
):
    m3db(
        "add-medias", new_db, write_json("first.json", [media("v1.mp4"), media("a.jpg", "v1.mp4")])
    )

    m3db("add-medias", new_db, write_json("more.json", [media("b.jpg", "v1.mp4"), media("x.jpg")]))

    assert medias_by_id(query)[2:] == [(3, "b.jpg", "v1.mp4"), (4, "x.jpg", None)]


def test_a_rerun_stops_on_the_existing_media_and_adds_nothing(m3db, new_db, write_json, query):
    medias_json = write_json("medias.json", [media("v1.mp4"), media("a.jpg", "v1.mp4")])
    m3db("add-medias", new_db, medias_json)

    result = m3db("add-medias", new_db, medias_json, exit_code=1)

    assert 'Media "v1.mp4" already exists' in result.stderr
    assert len(medias_by_id(query)) == 2


def test_ignore_existing_skips_existing_medias_and_adds_the_rest(m3db, new_db, write_json, query):
    m3db(
        "add-medias", new_db, write_json("first.json", [media("v1.mp4"), media("a.jpg", "v1.mp4")])
    )
    more = [media("v1.mp4"), media("a.jpg", "v1.mp4"), media("b.jpg", "v1.mp4")]

    result = m3db("add-medias", new_db, write_json("more.json", more), "--ignore-existing")

    assert "Added 1 media" in result.stderr
    assert "Skipped 2 medias that exist" in result.stderr
    assert medias_by_id(query) == [
        (1, "v1.mp4", None),
        (2, "a.jpg", "v1.mp4"),
        (3, "b.jpg", "v1.mp4"),
    ]


def test_a_media_listed_twice_stops_without_ignore_existing(m3db, new_db, write_json, query):
    result = m3db(
        "add-medias",
        new_db,
        write_json("medias.json", [media("a.jpg"), media("b.jpg"), media("a.jpg")]),
        exit_code=1,
    )

    assert 'Media "a.jpg" is listed twice in medias.json' in result.stderr
    assert medias_by_id(query) == []


def test_a_media_listed_twice_with_ignore_existing_keeps_its_first_entry(
    m3db, new_db, write_json, query
):
    medias = [
        media("a.jpg", thumbnail="first.jpg"),
        media("b.jpg"),
        media("a.jpg", thumbnail="second.jpg"),
    ]

    m3db("add-medias", new_db, write_json("medias.json", medias), "--ignore-existing")

    assert query("SELECT id, source, thumbnail_uri FROM medias ORDER BY id") == [
        (1, "a.jpg", "first.jpg"),
        (2, "b.jpg", None),
    ]


# Errors that stop the command


@pytest.mark.parametrize(
    "medias, message",
    [
        (
            [media("a.jpg", source_type="picture")],
            'Unknown source_type "picture" for media "a.jpg" in medias.json',
        ),
        ([{"source": "a.jpg"}], 'Unknown source_type "" for media "a.jpg" in medias.json'),
        ([{"source_type": "image"}], "A media in medias.json has no source (entry 2)"),
        (
            [media("a.jpg", "v9.mp4")],
            'Group "v9.mp4" of media "a.jpg" is not a media in medias.json or in the database',
        ),
    ],
)
def test_bad_medias_stop_the_command_and_change_nothing(
    m3db, new_db, write_json, query, medias, message
):
    medias_json = write_json("medias.json", [media("ok.jpg")] + medias)

    result = m3db("add-medias", new_db, medias_json, exit_code=1)

    assert message in result.stderr
    assert medias_by_id(query) == []
