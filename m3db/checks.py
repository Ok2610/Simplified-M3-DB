"""Database checks that every add command runs before it commits.

The large DuckDB tables have no keys, so these checks catch what keys and foreign keys would.
"""

import duckdb
from loguru import logger

from m3db import M3DBError
from m3db.db import TAG_TYPES, execute
from m3db.logs import phase

# Every value row of every tag type, with the tag type ID of its table
ALL_VALUE_ROWS = " UNION ALL ".join(
    f"SELECT id, tagset_id, {tagtype_id} AS tagtype_id FROM {type_name}_tags"
    for tagtype_id, (type_name, _) in TAG_TYPES.items()
)
VALUES_LISTED_TWICE = " UNION ALL ".join(
    f"SELECT tagset_id FROM {type_name}_tags GROUP BY tagset_id, value HAVING count(*) > 1"
    for type_name, _ in TAG_TYPES.values()
)

# Each check as the problem it finds and the SQL that counts the rows with that problem
CHECKS = [
    (
        "medias.source listed twice",
        "SELECT count(*) FROM (SELECT source FROM medias GROUP BY source HAVING count(*) > 1)",
    ),
    (
        "medias.id listed twice",
        "SELECT count(*) FROM (SELECT id FROM medias GROUP BY id HAVING count(*) > 1)",
    ),
    (
        "medias.group_id with no media",
        """
        SELECT count(*) FROM medias
        WHERE group_id IS NOT NULL AND group_id NOT IN (SELECT id FROM medias)
        """,
    ),
    (
        "tags.id listed twice",
        "SELECT count(*) FROM (SELECT id FROM tags GROUP BY id HAVING count(*) > 1)",
    ),
    (
        "tag values listed twice in a tagset",
        f"SELECT count(*) FROM ({VALUES_LISTED_TWICE})",
    ),
    (
        "tags without exactly one value row",
        f"""
        SELECT count(*)
        FROM tags
        LEFT JOIN (
            SELECT id, tagset_id, tagtype_id, count(*) AS value_rows
            FROM ({ALL_VALUE_ROWS})
            GROUP BY ALL
        ) value_counts USING (id, tagset_id, tagtype_id)
        WHERE value_counts.value_rows IS DISTINCT FROM 1
        """,
    ),
    (
        "tag value rows with no tags row",
        f"""
        SELECT count(*) FROM ({ALL_VALUE_ROWS}) value_row
        WHERE NOT EXISTS (
            SELECT 1 FROM tags
            WHERE tags.id = value_row.id
              AND tags.tagset_id = value_row.tagset_id
              AND tags.tagtype_id = value_row.tagtype_id
        )
        """,
    ),
    (
        "taggings listed twice",
        """
        SELECT count(*) FROM (
            SELECT media_id FROM taggings GROUP BY media_id, tag_id HAVING count(*) > 1
        )
        """,
    ),
    (
        "taggings.tag_id with no tag",
        "SELECT count(*) FROM taggings WHERE tag_id NOT IN (SELECT id FROM tags)",
    ),
    (
        "taggings.media_id with no media",
        "SELECT count(*) FROM taggings WHERE media_id NOT IN (SELECT id FROM medias)",
    ),
]


def run_checks(connection: duckdb.DuckDBPyConnection) -> None:
    """Run every check on the database of CONNECTION, and raise an M3DBError naming each problem."""
    problems = []
    with phase("Checks"):
        for problem, count_sql in CHECKS:
            count = execute(connection, count_sql).fetchone()[0]
            if count:
                problems.append(f"{count:,} {problem}")
    if problems:
        raise M3DBError(f"The database checks found {'; '.join(problems)}. Nothing was changed.")
    logger.info("Checks passed")
