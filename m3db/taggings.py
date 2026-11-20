"""Add taggings from taggings.json (m3db add-taggings)."""

from pathlib import Path

import duckdb
from loguru import logger

from m3db import M3DBError
from m3db.checks import run_checks
from m3db.db import TAG_TYPES, execute, transaction
from m3db.json_input import read_json
from m3db.logs import counted, phase

TAGGINGS_COLUMNS = {"media_source": "VARCHAR", "tagsets": "MAP(VARCHAR, JSON[])"}


def add_taggings(connection: duckdb.DuckDBPyConnection, taggings_json: Path) -> int:
    """Add the taggings in TAGGINGS_JSON, in one transaction, and return how many were added.

    A tagging for an unknown tagset, or for a value that is not a tag, is skipped with a WARNING.
    """
    file_name = taggings_json.name
    with transaction(connection):
        with phase(f"Read {file_name}"):
            execute(
                connection,
                f"""
                CREATE TEMP TABLE tagging_lists AS
                SELECT entry, media_source, tagset.key AS tagset_name, tagset.value AS tags
                FROM (
                    SELECT ordinality AS entry, media_source,
                           unnest(map_entries(tagsets)) AS tagset
                    FROM {read_json(taggings_json, TAGGINGS_COLUMNS)}
                )
                """,
            )

        with phase("Check medias and tagsets"):
            check_medias(connection, file_name)
            report_unknown_tagsets(connection)

        with phase("Match values to tags"):
            match_tags(connection)
            report_unmatched_values(connection)

        with phase("Insert taggings"):
            taggings_added = execute(
                connection,
                """
                INSERT INTO taggings (media_id, tag_id)
                SELECT DISTINCT media_id, tag_id FROM tagging_tags new
                WHERE tag_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM taggings existing
                      WHERE existing.media_id = new.media_id AND existing.tag_id = new.tag_id
                  )
                ORDER BY media_id, tag_id
                """,
            ).fetchone()[0]

        execute(connection, "DROP TABLE tagging_lists; DROP TABLE tagging_tags")
        run_checks(connection)
    return taggings_added


def check_medias(connection: duckdb.DuckDBPyConnection, file_name: str) -> None:
    """Raise an M3DBError for a tagging in tagging_lists with no media_source,
    or a media_source that is not a media."""
    no_source = execute(
        connection,
        "SELECT entry FROM tagging_lists WHERE media_source IS NULL ORDER BY entry LIMIT 1",
    ).fetchone()
    if no_source:
        raise M3DBError(f"A tagging in {file_name} has no media_source (entry {no_source[0]}).")

    missing = execute(
        connection,
        """
        SELECT media_source, count(DISTINCT media_source) OVER ()
        FROM tagging_lists
        WHERE media_source NOT IN (SELECT source FROM medias)
        ORDER BY entry LIMIT 1
        """,
    ).fetchone()
    if missing:
        media_source, count = missing
        more = f" ({counted(count, 'missing media')} in all)" if count > 1 else ""
        raise M3DBError(
            f'Media "{media_source}" in {file_name} does not exist{more}. '
            "Add it with m3db add-medias first."
        )


def report_unknown_tagsets(connection: duckdb.DuckDBPyConnection) -> None:
    """Log a WARNING with the tagging count for each tagset in tagging_lists that does not exist."""
    unknown = execute(
        connection,
        """
        SELECT tagset_name, sum(len(tags))
        FROM tagging_lists
        WHERE tagset_name NOT IN (SELECT name FROM tagsets)
        GROUP BY tagset_name
        ORDER BY min(entry)
        """,
    ).fetchall()
    for tagset_name, count in unknown:
        logger.warning(
            f'Skipped {counted(count, "tagging")} for the unknown tagset "{tagset_name}"'
        )


def match_tags(connection: duckdb.DuckDBPyConnection) -> None:
    """Create tagging_tags, each value of tagging_lists with its media_id and tag_id.

    The tag_id is NULL when the value is not a tag of its tagset. Then the row keeps the value
    as text and whether it fits the tag type, for the report.
    """
    matches = [
        f"""
        SELECT value_row.media_id, value_row.tagset_id, tag.id AS tag_id,
               CASE WHEN tag.id IS NULL THEN value_row.entry END AS entry,
               CASE WHEN tag.id IS NULL THEN value_row.position END AS position,
               CASE WHEN tag.id IS NULL THEN coalesce(j->>'$', j::VARCHAR, 'null') END AS text,
               value_row.value IS NOT NULL AS fits
        FROM (
            SELECT media_id, tagset_id, entry, position, j, TRY({value_sql}) AS value
            FROM tagging_values WHERE tagtype_id = {tagtype_id}
        ) value_row
        LEFT JOIN {type_name}_tags tag
          ON tag.tagset_id = value_row.tagset_id AND tag.value = value_row.value
        """
        for tagtype_id, (type_name, value_sql) in TAG_TYPES.items()
    ]
    execute(
        connection,
        f"""
        CREATE TEMP TABLE tagging_tags AS
        WITH tagging_values AS MATERIALIZED (
            SELECT medias.id AS media_id, tagsets.id AS tagset_id, tagsets.tagtype_id,
                   lists.entry, unnest(lists.tags) AS j,
                   generate_subscripts(lists.tags, 1) AS position
            FROM tagging_lists lists
            JOIN medias ON medias.source = lists.media_source
            JOIN tagsets ON tagsets.name = lists.tagset_name
        )
        {" UNION ALL ".join(matches)}
        """,
    )


def report_unmatched_values(connection: duckdb.DuckDBPyConnection) -> None:
    """Log a WARNING per tagset for the values in tagging_tags that are not tags,
    with their count and up to 3 examples."""
    unmatched = execute(
        connection,
        """
        WITH skipped AS (
            SELECT tagset_id, fits, text, entry, position,
                   count(*) OVER (PARTITION BY tagset_id, fits) AS count,
                   row_number() OVER (
                       PARTITION BY tagset_id, fits ORDER BY entry, position
                   ) AS example
            FROM tagging_tags
            WHERE tag_id IS NULL
        )
        SELECT tagsets.name, tag_types.description, skipped.fits, skipped.count,
               string_agg('"' || skipped.text || '"', ', ' ORDER BY skipped.entry, skipped.position)
        FROM skipped
        JOIN tagsets ON tagsets.id = skipped.tagset_id
        JOIN tag_types ON tag_types.id = tagsets.tagtype_id
        WHERE skipped.example <= 3
        GROUP BY ALL
        ORDER BY min(skipped.entry), skipped.fits DESC
        """,
    ).fetchall()
    for tagset_name, type_name, fits, count, examples in unmatched:
        if fits:
            reason = f'whose value is not a tag of "{tagset_name}"'
        else:
            reason = f'whose value does not fit the {type_name} tagset "{tagset_name}"'
        logger.warning(f"Skipped {counted(count, 'tagging')} {reason}, for example {examples}")
