"""Add medias from medias.json (m3db add-medias)."""

from pathlib import Path

import duckdb

from m3db import M3DBError
from m3db.checks import run_checks
from m3db.db import execute, transaction
from m3db.json_input import read_json
from m3db.logs import phase

MEDIA_COLUMNS = {
    "source": "VARCHAR",
    "source_type": "VARCHAR",
    "thumbnail": "VARCHAR",
    "group": "VARCHAR",
}
SOURCE_TYPE_NAMES = "image, video, audio, text, other"


def add_medias(
    connection: duckdb.DuckDBPyConnection, medias_json: Path, ignore_existing: bool = False
) -> tuple[int, int]:
    """Add the medias in MEDIAS_JSON, in one transaction.

    A media takes the next ID where it appears in the file, and the members of a group follow
    their group's media. Returns the number of medias added and of existing medias skipped.
    """
    file_name = medias_json.name
    with transaction(connection):
        with phase(f"Read {file_name}"):
            execute(
                connection,
                f"""
                CREATE TEMP TABLE media_entries AS
                SELECT ordinality AS position, source, source_type, thumbnail,
                       "group" AS group_source
                FROM {read_json(medias_json, MEDIA_COLUMNS)}
                """,
            )

        with phase("Check medias"):
            check_media_entries(connection, file_name, ignore_existing)
            # Keep the first entry of a source listed twice (allowed with --ignore-existing)
            execute(
                connection,
                """
                DELETE FROM media_entries WHERE position IN (
                    SELECT position FROM media_entries
                    QUALIFY row_number() OVER (PARTITION BY source ORDER BY position) > 1)
                """,
            )
            find_groups(connection)
            check_groups(connection, file_name)

        with phase("Number new medias"):
            number_new_medias(connection)

        with phase("Insert medias"):
            medias_added = execute(
                connection,
                """
                INSERT INTO medias (id, source, source_type, thumbnail_uri, group_id)
                SELECT new.id, entry.source, source_types.id, entry.thumbnail,
                       coalesce(new_group.id, groups.existing_group_id)
                FROM new_media_ids new
                JOIN media_entries entry USING (position)
                JOIN media_groups groups USING (position)
                JOIN source_types ON lower(source_types.name) = lower(entry.source_type)
                LEFT JOIN new_media_ids new_group ON new_group.position = groups.group_position
                ORDER BY new.id
                """,
            ).fetchone()[0]
        medias_skipped = execute(
            connection, "SELECT count(*) FROM media_groups WHERE exists_already"
        ).fetchone()[0]
        execute(
            connection,
            "DROP TABLE media_entries; DROP TABLE media_groups; DROP TABLE new_media_ids",
        )
        run_checks(connection)
    return medias_added, medias_skipped


def check_media_entries(
    connection: duckdb.DuckDBPyConnection, file_name: str, ignore_existing: bool
) -> None:
    """Raise an M3DBError for a media in media_entries with no source, an unknown
    source_type, or a source that is taken."""
    no_source = execute(
        connection,
        "SELECT position FROM media_entries WHERE source IS NULL ORDER BY position LIMIT 1",
    ).fetchone()
    if no_source:
        raise M3DBError(f"A media in {file_name} has no source (entry {no_source[0]}).")

    unknown_type = execute(
        connection,
        """
        SELECT source, coalesce(source_type, '') FROM media_entries
        WHERE source_type IS NULL
           OR lower(source_type) NOT IN (SELECT lower(name) FROM source_types)
        ORDER BY position LIMIT 1
        """,
    ).fetchone()
    if unknown_type:
        source, source_type = unknown_type
        raise M3DBError(
            f'Unknown source_type "{source_type}" for media "{source}" in {file_name}. '
            f"Use one of {SOURCE_TYPE_NAMES}."
        )

    if ignore_existing:
        return
    existing = execute(
        connection,
        """
        SELECT source FROM media_entries WHERE source IN (SELECT source FROM medias)
        ORDER BY position LIMIT 1
        """,
    ).fetchone()
    if existing:
        raise M3DBError(
            f'Media "{existing[0]}" already exists. '
            "Use --ignore-existing to skip medias that exist."
        )
    listed_twice = execute(
        connection,
        """
        SELECT source FROM media_entries GROUP BY source HAVING count(*) > 1
        ORDER BY min(position) LIMIT 1
        """,
    ).fetchone()
    if listed_twice:
        raise M3DBError(
            f'Media "{listed_twice[0]}" is listed twice in {file_name}. '
            "Use --ignore-existing to keep its first entry."
        )


def find_groups(connection: duckdb.DuckDBPyConnection) -> None:
    """Create media_groups, which holds what decides the ID and group_id of each media entry."""
    execute(
        connection,
        """
        CREATE TEMP TABLE media_groups AS
        SELECT entry.position,
               existing.id IS NOT NULL AS exists_already,
               group_entry.position AS group_position,
               existing_group.id AS existing_group_id,
               entry.source IN (
                   SELECT group_source FROM media_entries WHERE group_source IS NOT NULL
               ) AS leads_a_group
        FROM media_entries entry
        LEFT JOIN medias existing ON existing.source = entry.source
        LEFT JOIN media_entries group_entry ON group_entry.source = entry.group_source
        LEFT JOIN medias existing_group ON existing_group.source = entry.group_source
        """,
    )


def check_groups(connection: duckdb.DuckDBPyConnection, file_name: str) -> None:
    """Raise an M3DBError for a group that names no media in the file or in the database."""
    missing = execute(
        connection,
        """
        SELECT entry.group_source, entry.source
        FROM media_entries entry JOIN media_groups groups USING (position)
        WHERE entry.group_source IS NOT NULL
          AND groups.group_position IS NULL
          AND groups.existing_group_id IS NULL
        ORDER BY entry.position LIMIT 1
        """,
    ).fetchone()
    if missing:
        group_source, source = missing
        raise M3DBError(
            f'Group "{group_source}" of media "{source}" '
            f"is not a media in {file_name} or in the database."
        )


def number_new_medias(connection: duckdb.DuckDBPyConnection) -> None:
    """Create new_media_ids, the next free ID for each new media in media_groups.

    Medias are numbered in file order, where a member takes the place of its group's media.
    A media that leads a group itself keeps its own place when it comes before its group's media.
    """
    execute(
        connection,
        """
        CREATE TEMP TABLE new_media_ids AS
        SELECT position, group_position,
               (SELECT coalesce(max(id), 0) FROM medias)
               + row_number() OVER (
                   ORDER BY CASE WHEN is_member THEN group_position ELSE position END,
                            is_member, position
               ) AS id
        FROM (
            SELECT position, group_position,
                   group_position IS NOT NULL
                   AND (NOT leads_a_group OR group_position < position) AS is_member
            FROM media_groups
            WHERE NOT exists_already
        )
        """,
    )
