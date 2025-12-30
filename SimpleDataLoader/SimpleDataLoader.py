from dataclasses import dataclass
from enum import Enum
from typing import List, Any, Optional
from duckdb import DuckDBPyConnection


class TagType(Enum):
    ALPHANUMERICAL = 1
    TIMESTAMP = 2
    TIME = 3
    DATE = 4
    NUMERICAL_INT = 5
    NUMERICAL_DEC = 6
    JSON = 7

    def get_tagtype_name_by_value(value):
        for member in TagType:
            if member.value == value:
                return member.name
        raise ValueError(f"No TagType with value: {value}")


@dataclass
class Tags():
    tagset_name: str
    tags: List[Any]

    def __init__(self, tagset_name: str,  tags: List[Any]):
        self.tagset_name = tagset_name
        self.tags = tags


@dataclass
class Tagset():
    name: str
    tagtype: TagType
    tags: List[Tags]

    def __init__(self, name: str, tagtype: TagType, tags: List[Tags]):
        self.name = name
        self.tagtype = tagtype
        self.tags = tags


class MediaSourceType(Enum):
    IMAGE = 1,
    VIDEO = 2,
    AUDIO = 3,
    TEXT = 4,
    OTHER = 5

    def get_source_type_name_by_value(value):
        for member in MediaSourceType:
            if member.value == value:
                return member.name
        raise ValueError(f"No TagType with value: {value}")


@dataclass
class MediaObject():
    source: str
    source_type: str
    thumbnail: Optional[str] = None,
    group: Optional[str] = None # if the media is a video segment from a larger video

    def __init__(
        self, 
        source: str, 
        source_type: str, 
        thumbnail: Optional[str] = None,
        group: Optional[str] = None
    ):
        self.source = source
        self.source_type = source_type
        self.thumbnail = thumbnail
        self.group = group


def add_tagsets(connection: DuckDBPyConnection, tagsets: List[Tagset], ignore_existing: bool = False):
    cursor = None
    try:
        ignore_existing_clause = "OR IGNORE" if ignore_existing else ""
        cursor = connection.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        cursor.executemany(
            f"""
            INSERT {ignore_existing_clause} INTO tagsets (name, tagtype_id)
            VALUES (?, ?)
            """,
            [[tagset.name, tagset.tagtype.value] for tagset in tagsets]
        )
        cursor.execute("COMMIT;")
        cursor.close()
        for tagset in tagsets:
            if len(tagset.tags.tags) > 0:
                print(f'Adding tags for tagset: {tagset.name}...')
                add_tags(connection, tagset.tags)
    except Exception as e:
        print("(SDL.add_tagsets) Error adding tagsets: ", e)
        if cursor:
            cursor.execute("ROLLBACK;")
    finally:
        if cursor:
            cursor.close()


def add_tags(connection: DuckDBPyConnection, tags: Tags):
    cursor = None
    try:
        cursor = connection.cursor()
        (tagset_id, tagtype_id) = cursor.execute(
            "SELECT id, tagtype_id FROM tagsets WHERE name = ?", 
            [tags.tagset_name]
        ).fetchone()

        cursor.execute("BEGIN TRANSACTION;")
        # Add to tags to the table and get the id of the last inserted tag
        res = cursor.executemany(
            """
            INSERT INTO tags (tagset_id, tagtype_id)
            VALUES (?, ?)
            RETURNING id;
            """,
            [[tagset_id, tagtype_id] for _ in range(len(tags.tags))],
        ).fetchone() # Gets the id of the last inserted row

        # The bulk insert via the transaction ensures that all inserted tag ids are in a sequence
        tag_ids = list(range(res[0] - len(tags.tags) + 1, res[0] + 1))

        # Add tags to their appropriate tagtype table
        cursor.executemany(
            f"""
            INSERT INTO {TagType.get_tagtype_name_by_value(tagtype_id).lower()}_tags (id, value, tagset_id) 
            VALUES ($1, $2, $3)
            """,
            [[tag_id, val, tagset_id] for tag_id, val in zip(tag_ids, tags.tags)]
        )
        cursor.execute("COMMIT;")
    except Exception as e:
        print(f"(SDL.add_tags) Error adding tags ({tags.tagset_name}): ", e)
        if cursor:
            cursor.execute("ROLLBACK;")
    finally:
        if cursor:
            cursor.close()


def add_medias(
    connection: DuckDBPyConnection,
    media_objects: List[MediaObject],
    no_groups: bool = False,
    ignore_existing: bool = False
):
    cursor = None
    try:
        ignore_existing_clause = "OR IGNORE" if ignore_existing else ""
        group_medias = {}
        groups = []
        if not no_groups:
            for mo in media_objects:
                if mo.group is not None and mo.group not in groups:
                    group_medias[mo.group] = [mo]
                elif mo.group is not None:
                    group_medias[mo.group].append(mo)
                else:
                    groups.append(mo)

        cursor = connection.cursor()
        for grp_mo in groups:
            cursor.execute("BEGIN TRANSACTION;")
            group_id = cursor.execute(
                f"""
                INSERT {ignore_existing_clause} INTO media (source, source_type, thumbnail)
                VALUES (?, ?, ?)
                RETURNING id
                """,
                [grp_mo.source, grp_mo.source_type, grp_mo.thumbnail]
            ).fetchone()[0]
            cursor.executemany(
                f"""
                INSERT {ignore_existing_clause} INTO media (source, source_type, thumbnail, media_group)
                VALUES (?, ?, ?, ?)
                """,
                [[mo.source, mo.source_type, mo.thumbnail, group_id] for mo in group_medias.get(grp_mo.group, [])]
            )
            cursor.execute("COMMIT;")
    except Exception as e:
        print("(SDL.add_medias): ", e)
        if cursor:
            cursor.execute("ROLLBACK;")
    finally:
        if cursor:
            cursor.close()


def get_tag_ids_from_tagset_and_values(connection: DuckDBPyConnection, tagset_name: str, tag_values: List[Any]) -> List[int]:
    try:
        tagset_id, tagtype_id = connection.execute(
                    """
                    SELECT id, tagtype_id 
                    FROM tagsets ts
                    WHERE ts.name = ?
                    """, 
                    [tagset_name]
                ).fetchone()[0]
        values_placeholders = ','.join(['?'] * len(tag_values))
        tags = connection.execute(
            f"""
            SELECT ttg.id, ttg.value
            FROM {TagType.get_tagtype_name_by_value(tagtype_id).lower()}_tags ttg 
            WHERE ttg.tagset_id = ?
              AND ttg.value IN ({values_placeholders})
            """,
            [tagset_id, tag_values]
        ).fetchall()

        if tags is not None:
            return { (tagset_name, t[1]): t[0] for t in tags}
        else:
            print(f'Tag(s) not found: (Tagset, {tagset_name})')
            raise Exception("Tag(s) not found")
    except Exception as e:
        print("(SDL.get_tag_ids_from_tagset_with_values): ", e)


def add_media_taggings(connection: DuckDBPyConnection, media_tag_mappings: List[dict]):
    """
    Add taggings between media and tags in bulk.
    1. Get a list of JSON objects containing {"media_source": "source", "tagset_name": [list_of_tag_values]}
    2. For each JSON object, get the media id, group tagset names and values
    3. For each tagset get the tag ids, such that we have a mapping of (tagset_name, tag_value) -> tag_id
    4. Create a list of taggings (media_id, tag_id) and bulk insert into taggings table
    """
    cursor = None
    try:
        cursor = connection.cursor()
        tagset_to_values = {}
        media_source_to_id = {}

        # Step 2: Group tagset names and values
        for mapping in media_tag_mappings:
            media_source = mapping['media_source']
            if media_source not in media_source_to_id:
                media_id = cursor.execute(
                    """
                    SELECT id 
                    FROM media 
                    WHERE source = ?
                    """,
                    [media_source]
                ).fetchone()[0]
                media_source_to_id[media_source] = media_id

            for tagset_name, tag_values in mapping['tagsets'].items():
                if tagset_name not in tagset_to_values:
                    tagset_to_values[tagset_name] = set()
                tagset_to_values[tagset_name].update(tag_values)

        # Step 3: Get tag ids for each tagset and its values
        # NOTE: Potential for concurrency here if needed
        tag_mapping = {}
        for tagset_name, tag_values in tagset_to_values.items():
            tag_ids = get_tag_ids_from_tagset_and_values(connection, tagset_name, list(tag_values))
            tag_mapping.update(tag_ids)

        # Step 4: Create list of taggings and bulk insert
        taggings = []
        for mapping in media_tag_mappings:
            media_id = media_source_to_id[mapping['media_source']]
            for tagset_name, tag_values in mapping['tagsets'].items():
                for tag_value in tag_values:
                    tag_id = tag_mapping.get((tagset_name, tag_value))
                    if tag_id:
                        taggings.append((media_id, tag_id))

        cursor.executemany(
            """
            INSERT INTO taggings (media_id, tag_id)
            VALUES (?, ?)
            """,
            taggings
        )
    except Exception as e:
        print("(SDL.add_media_taggings): ", e)
    finally:
        if cursor:
            cursor.close()