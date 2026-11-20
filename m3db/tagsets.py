"""Add tagsets and tags from tagsets.json and tags.json (m3db add-tagsets and m3db add-tags)."""
from pathlib import Path

import duckdb

from m3db import M3DBError
from m3db.db import execute, transaction
from m3db.json_input import read_json
from m3db.logs import phase

# Each tag type ID with its tag type name and the SQL that turns a JSON value `j` into
# the type of the value column in the table {name}_tags
TAG_TYPES = {
    1: ("alphanumerical", "j->>'$'"),
    2: ("timestamp", "CAST(j->>'$' AS TIMESTAMP)"),
    3: ("time", "CAST(j->>'$' AS TIME)"),
    4: ("date", "CAST(j->>'$' AS DATE)"),
    5: ("numerical_int", "CAST(j->>'$' AS BIGINT)"),
    6: ("numerical_dec", "CAST(j->>'$' AS DECIMAL(10,5))"),
    7: ("json", "j->>'$'"),
}
TAG_TYPE_NAMES = ", ".join(name for name, _ in TAG_TYPES.values())


def add_tagsets(connection: duckdb.DuckDBPyConnection, tagsets_json: Path, ignore_existing: bool = False) -> tuple[int, int]:
    """Add the tagsets in TAGSETS_JSON and the tags listed with them, in one transaction.

    New tagsets and tags take the next IDs in file order. Returns the number of tagsets and of tags added.
    """
    file_name = tagsets_json.name
    with transaction(connection):
        with phase(f"Read {file_name}"):
            execute(connection, f"""
                CREATE TEMP TABLE tag_lists AS
                SELECT ordinality AS entry, name AS tagset_name, tagtype, tags
                FROM {read_json(tagsets_json, {"name": "VARCHAR", "tagtype": "VARCHAR", "tags": "JSON[]"})}""")
        check_tagset_entries(connection, file_name, ignore_existing)
        with phase("Add tagsets"):
            tagsets_added = insert_tagsets(connection)
        tags_added = add_tag_lists(connection, file_name)
    return tagsets_added, tags_added


def add_tags(connection: duckdb.DuckDBPyConnection, tags_json: Path) -> int:
    """Add the tags in TAGS_JSON to existing tagsets, in one transaction.

    New tags take the next IDs in file order. Returns the number of tags added.
    """
    file_name = tags_json.name
    with transaction(connection):
        with phase(f"Read {file_name}"):
            execute(connection, f"""
                CREATE TEMP TABLE tag_lists AS
                SELECT ordinality AS entry, tagset_name, tags
                FROM {read_json(tags_json, {"tagset_name": "VARCHAR", "tags": "JSON[]"})}""")
        unknown = execute(connection, """
            SELECT coalesce(tagset_name, '') FROM tag_lists
            WHERE tagset_name IS NULL OR tagset_name NOT IN (SELECT name FROM tagsets)
            ORDER BY entry LIMIT 1""").fetchone()
        if unknown:
            raise M3DBError(f'Tagset "{unknown[0]}" in {file_name} does not exist. Add it with m3db add-tagsets first.')
        return add_tag_lists(connection, file_name)


def check_tagset_entries(connection: duckdb.DuckDBPyConnection, file_name: str, ignore_existing: bool) -> None:
    """Raise an M3DBError for a tagset in tag_lists with no name, an unknown tag type, or a name that is taken."""
    no_name = execute(connection, "SELECT entry FROM tag_lists WHERE tagset_name IS NULL ORDER BY entry LIMIT 1").fetchone()
    if no_name:
        raise M3DBError(f"A tagset in {file_name} has no name (entry {no_name[0]}).")

    unknown_type = execute(connection, """
        SELECT tagset_name, coalesce(tagtype, '') FROM tag_lists
        WHERE tagtype IS NULL OR lower(tagtype) NOT IN (SELECT description FROM tag_types)
        ORDER BY entry LIMIT 1""").fetchone()
    if unknown_type:
        name, tagtype = unknown_type
        raise M3DBError(f'Unknown tag type "{tagtype}" for tagset "{name}" in {file_name}. Use one of {TAG_TYPE_NAMES}.')

    if ignore_existing:
        return
    existing = execute(connection, """
        SELECT tagset_name FROM tag_lists WHERE tagset_name IN (SELECT name FROM tagsets)
        ORDER BY entry LIMIT 1""").fetchone()
    if existing:
        raise M3DBError(f'Tagset "{existing[0]}" already exists. Use --ignore-existing to skip it and add only its new tags.')
    listed_twice = execute(connection, """
        SELECT tagset_name FROM tag_lists GROUP BY tagset_name HAVING count(*) > 1
        ORDER BY min(entry) LIMIT 1""").fetchone()
    if listed_twice:
        raise M3DBError(f'Tagset "{listed_twice[0]}" is listed twice in {file_name}. '
                        "Use --ignore-existing to add it once with the tags of every entry.")


def insert_tagsets(connection: duckdb.DuckDBPyConnection) -> int:
    """Insert the tagsets of tag_lists that do not exist yet, with the next IDs in file order. Returns the number inserted."""
    return execute(connection, """
        INSERT INTO tagsets (id, name, tagtype_id)
        SELECT (SELECT coalesce(max(id), 0) FROM tagsets) + row_number() OVER (ORDER BY entry),
               tagset_name, tagtype_id
        FROM (
            SELECT tag_lists.entry, tag_lists.tagset_name, tag_types.id AS tagtype_id
            FROM tag_lists JOIN tag_types ON tag_types.description = lower(tag_lists.tagtype)
            WHERE tag_lists.tagset_name NOT IN (SELECT name FROM tagsets)
            QUALIFY row_number() OVER (PARTITION BY tag_lists.tagset_name ORDER BY tag_lists.entry) = 1
        )""").fetchone()[0]


def add_tag_lists(connection: duckdb.DuckDBPyConnection, file_name: str) -> int:
    """Add the values in the tags lists of tag_lists as tags, and return how many were added.

    A value its tagset has, or one listed earlier, is skipped. New tags take the next IDs in file order.
    """
    with phase("List tag values"):
        execute(connection, """
            CREATE TEMP TABLE tag_values AS
            SELECT lists.entry, lists.position, lists.tagset_name,
                   tagsets.id AS tagset_id, tagsets.tagtype_id, lists.j
            FROM (SELECT entry, tagset_name, unnest(tags) AS j, generate_subscripts(tags, 1) AS position
                  FROM tag_lists) lists
            JOIN tagsets ON tagsets.name = lists.tagset_name""")

    with phase("Check tag values"):
        for type_name, value_sql in TAG_TYPES.values():
            check_values_fit(connection, file_name, type_name, value_sql)

    with phase("Number new tags"):
        new_values = [
            f"""SELECT entry, position, tagset_id, tagtype_id, j
                FROM (SELECT *, {value_sql} AS value FROM tag_values WHERE tagtype_id = {tagtype_id}) candidate
                WHERE NOT EXISTS (SELECT 1 FROM {type_name}_tags existing
                                  WHERE existing.tagset_id = candidate.tagset_id AND existing.value = candidate.value)
                QUALIFY row_number() OVER (PARTITION BY tagset_id, value ORDER BY entry, position) = 1"""
            for tagtype_id, (type_name, value_sql) in TAG_TYPES.items()
        ]
        execute(connection, f"""
            CREATE TEMP TABLE new_tags AS
            SELECT (SELECT coalesce(max(id), 0) FROM tags) + row_number() OVER (ORDER BY entry, position) AS id,
                   tagset_id, tagtype_id, j
            FROM ({" UNION ALL ".join(new_values)})""")

    with phase("Insert tags"):
        tags_added = execute(connection, """
            INSERT INTO tags (id, tagtype_id, tagset_id)
            SELECT id, tagtype_id, tagset_id FROM new_tags ORDER BY id""").fetchone()[0]
        for tagtype_id, (type_name, value_sql) in TAG_TYPES.items():
            execute(connection, f"""
                INSERT INTO {type_name}_tags (id, value, tagset_id)
                SELECT id, {value_sql}, tagset_id FROM new_tags WHERE tagtype_id = {tagtype_id} ORDER BY id""")

    execute(connection, "DROP TABLE tag_lists; DROP TABLE tag_values; DROP TABLE new_tags")
    return tags_added


def check_values_fit(connection: duckdb.DuckDBPyConnection, file_name: str, type_name: str, value_sql: str) -> None:
    """Raise an M3DBError if a value in tag_values does not convert to the type of the TYPE_NAME tagsets."""
    misfit = execute(connection, f"""
        SELECT tagset_name, coalesce(j->>'$', j::VARCHAR, 'null'), count(*) OVER ()
        FROM tag_values JOIN tag_types ON tag_types.id = tag_values.tagtype_id
        WHERE tag_types.description = '{type_name}' AND TRY({value_sql}) IS NULL
        ORDER BY entry, position LIMIT 1""").fetchone()
    if misfit:
        tagset_name, value, count = misfit
        more = {1: "", 2: ", and 1 more value does not fit"}.get(count, f", and {count - 1:,} more values do not fit")
        raise M3DBError(f'Value "{value}" in {file_name} does not fit the {type_name} tagset "{tagset_name}"{more}.')
