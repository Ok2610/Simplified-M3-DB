from dataclasses import dataclass
from enum import Enum
from typing import List, Any
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
        print("Error adding tagsets:", e)
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
        print(f"Error adding tags ({tags.tagset_name}):", e)
        if cursor:
            cursor.execute("ROLLBACK;")
    finally:
        if cursor:
            cursor.close()


def add_media_tagging(connection: DuckDBPyConnection, tagset_name, tag_name, media_id):
    cursor = None
    try:
        cursor = connection.cursor()
        tagtype = cursor.execute(
                    """
                    SELECT tt.description 
                    FROM tag_types tt
                    JOIN tagsets ts ON ts.tagtype_id = tt.id 
                    WHERE ts.name = ?
                    """, 
                    [tagset_name]
                ).fetchone()[0]
        tag = cursor.execute(
            f"""
            SELECT ttg.id, ttg.name
            FROM {tagtype}_tags ttg 
            JOIN tagsets ts ON ts.id = ttg.tagset_id 
            WHERE ts.name = ? AND ttg.name = ?
            """,
            [tagset_name, tag_name]
        ).fetchone()
        if tag is not None:
            cursor.execute(
                """
                INSERT INTO taggings (media_id, tag_id)
                VALUES (?, ?)
                """,
                [media_id, tag[0]]
            )
        else:
            print(f'Tag not found: (Tagset, {tagset_name}), (Tag, {tag_name}), (Media, {media_id})')
            raise Exception("Tag not found")
    except Exception as e:
        print(e)
    finally:
        if cursor:
            cursor.close()


# def create_and_add_media_taggings(connection: DuckDBPyConnection, tags: List[Tuple[str, str]], media_id):
#     cursor = None
#     try:
#         cursor = connection.cursor()
#         tagtype = cursor.execute(
#                     """
#                     SELECT tt.description 
#                     FROM tag_types tt
#                     JOIN tagsets ts ON ts.tagtype_id = tt.id 
#                     WHERE ts.name = ?
#                     """, 
#                     [tagset_name]
#                 ).fetchone()[0]
#         tag = cursor.execute(
#             f"""
#             SELECT ttg.id, ttg.name
#             FROM {tagtype}_tags ttg 
#             JOIN tagsets ts ON ts.id = ttg.tagset_id 
#             WHERE ts.name = ? AND ttg.name = ?
#             """,
#             [tagset_name, tag_name]
#         ).fetchone()
#         if tag is not None:
#             cursor.execute(
#                 """
#                 INSERT INTO taggings (media_id, tag_id)
#                 VALUES (?, ?)
#                 """,
#                 [media_id, tag[0]]
#             )
#         else:
#             print(f'Tag not found: (Tagset, {tagset_name}), (Tag, {tag_name}), (Media, {media_id})')
#             raise Exception("Tag not found")
#     except Exception as e:
#         print(e)
#     finally:
#         if cursor:
#             cursor.close()

