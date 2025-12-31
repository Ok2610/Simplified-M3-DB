from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, Set
from sqlite3 import Connection


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
    IMAGE = 1
    VIDEO = 2
    AUDIO = 3
    TEXT = 4
    OTHER = 5


@dataclass
class MediaObject():
    source: str
    source_type: MediaSourceType
    thumbnail: Optional[str] = None
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


def add_tagsets(connection: Connection, tagsets: List[Tagset], ignore_existing: bool = False):
    cursor = None
    try:
        ignore_existing_clause = "OR IGNORE" if ignore_existing else ""
        cursor = connection.cursor()
        # cursor.execute("BEGIN TRANSACTION")
        cursor.executemany(
            f"""
            INSERT {ignore_existing_clause} INTO tagsets (name, tagtype_id)
            VALUES (?, ?)
            """,
            [(tagset.name, tagset.tagtype.value) for tagset in tagsets]
        )
        connection.commit()
        # cursor.execute("COMMIT")
        cursor.close()

        for tagset in tagsets:
            if len(tagset.tags.tags) > 0:
                print(f'Adding tags for tagset: {tagset.name}...')
                add_tags(connection, tagset.tags)
    except Exception as e:
        print("(SDL.add_tagsets) Error adding tagsets: ", e)
        # if cursor:
            # cursor.execute("ROLLBACK")
        if connection.in_transaction:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()


def add_tags(connection: Connection, tags: Tags):
    cursor = None
    try:
        cursor = connection.cursor()
        (tagset_id, tagtype_id) = cursor.execute(
            "SELECT id, tagtype_id FROM tagsets WHERE name = ?", 
            [tags.tagset_name]
        ).fetchone()

        # Add to tags to the table and get the id of the last inserted tag
        cursor.executemany(
            """
            INSERT INTO tags (tagset_id, tagtype_id)
            VALUES (?, ?)
            """,
            [[tagset_id, tagtype_id] for _ in range(len(tags.tags))]
        ) 
        res = cursor.execute("SELECT last_insert_rowid()").fetchone()[0]

        # The bulk insert via the transaction ensures that all inserted tag ids are in a sequence
        tag_ids = list(range(res - len(tags.tags) + 1, res + 1))

        # Add tags to their appropriate tagtype table
        cursor.executemany(
            f"""
            INSERT INTO {TagType.get_tagtype_name_by_value(tagtype_id).lower()}_tags (id, value, tagset_id) 
            VALUES ($1, $2, $3)
            """,
            [[tag_id, val, tagset_id] for tag_id, val in zip(tag_ids, tags.tags)]
        )
        connection.commit()
    except Exception as e:
        print(f"(SDL.add_tags) Error adding tags ({tags.tagset_name}): ", e)
        if connection.in_transaction:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()


def add_medias(
    connection: Connection,
    media_objects: List[MediaObject],
    ignore_existing: bool = False
):
    cursor = None
    try:
        # Groups are essentially a leader-member relationship where objects without a group are potential leaders
        ignore_existing_clause = "OR IGNORE" if ignore_existing else ""
        group_medias: Dict[str, List[MediaObject]] = {}
        leaders: Dict[str, MediaObject] = {}
        for mo in media_objects:
            if mo.group is not None and mo.group not in group_medias:
                group_medias[mo.group] = [mo]
            elif mo.group is not None:
                group_medias[mo.group].append(mo)
        
        for mo in media_objects:
            if mo.source in group_medias:
                leaders[mo.source] = mo

        for grp in group_medias.keys():
            if grp not in leaders:
                raise ValueError(f"Group leader media object not found for group: {grp}")

        cursor = connection.cursor()
        # First add all media objects without groups
        added = set()
        for grp_lead in leaders:
            grp_mo = leaders[grp_lead]
            group_id = None
            try:
                group_id = cursor.execute(
                    f"""
                    INSERT INTO medias (source, source_type, thumbnail_uri)
                    VALUES (?, ?, ?)
                    RETURNING id
                    """,
                    [grp_mo.source, grp_mo.source_type.value, grp_mo.thumbnail]
                ).fetchone()[0]
                connection.commit()
            except:
                group_id = cursor.execute("SELECT id FROM medias WHERE source = ?", [grp_mo.source]).fetchone()[0]

            added.add(grp_mo.source)

            # Then add all media objects that belong to this group
            if grp_mo.source in group_medias:
                grp_members = []
                for mo in group_medias[grp_mo.source]:
                    # Avoid adding a leader again
                    if mo.source not in added:
                        grp_members.append([mo.source, mo.source_type.value, mo.thumbnail, group_id])
                    else:
                        # Update the group_id of leader media object
                        cursor.execute(
                            """
                            UPDATE medias
                            SET group_id = ?
                            WHERE source = ?
                            """,
                            [group_id, mo.source]
                        )
                cursor.executemany(
                    f"""
                    INSERT {ignore_existing_clause} INTO medias (source, source_type, thumbnail_uri, group_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    grp_members
                )
                added.update([mo[0] for mo in grp_members])
            connection.commit()
    except Exception as e:
        print("(SDL.add_medias): ", e)
        if connection.in_transaction:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()


def get_tag_ids_from_tagset_and_values(connection: Connection, tagset_name: str, tag_values: List[Any]) -> dict:
    try:
        res = connection.execute(
            """
            SELECT id, tagtype_id 
            FROM tagsets ts
            WHERE ts.name = ?
            """, 
            [tagset_name]
        ).fetchone()
        if res is None:
            print(f'"{tagset_name}" tagset not found, skipping...')
            return {}
        tagset_id, tagtype_id = res

        # Get tag ids for the given tagset and values
        values_placeholders = ','.join(['?'] * len(tag_values))
        tags = connection.execute(
            f"""
            SELECT ttg.id, ttg.value
            FROM {TagType.get_tagtype_name_by_value(tagtype_id).lower()}_tags ttg 
            WHERE ttg.tagset_id = ?
              AND ttg.value IN ({values_placeholders})
            """,
            [tagset_id, *tag_values]
        ).fetchall()

        # Return a dictionary mapping (tagset_name, tag_value) to tag_id
        if tags != []:
            return { (tagset_name, t[1]): t[0] for t in tags }
        else:
            print(f'No tag(s) found for "{tagset_name}" tagset, skipping...')
            return {}
    except Exception as e:
        print("(SDL.get_tag_ids_from_tagset_with_values): ", e)


def add_media_taggings(connection: Connection, media_tag_mappings: List[dict]):
    """
    Add taggings between media and tags in bulk.

    Parameters:
    - connection: sqlite3.Connection
    - media_tag_mappings: List of dictionaries with the following structure:
        {
            'media_source': str,
            'tagsets': {
                'tagset_name_1': [tag_value_1, tag_value_2, ...],
                'tagset_name_2': [tag_value_3, tag_value_4, ...],
                ...
            }
        }
    """
    cursor = None
    try:
        cursor = connection.cursor()
        tagset_to_values = {}
        media_source_to_id = {}

        # Step 1: Group tagset names and values
        print("(SDL.add_media_taggings): Step 1)")
        for mapping in media_tag_mappings:
            media_source = mapping['media_source']
            if media_source not in media_source_to_id:
                media_id = cursor.execute(
                    """
                    SELECT id 
                    FROM medias 
                    WHERE source = ?
                    """,
                    [media_source]
                ).fetchone()[0]
                media_source_to_id[media_source] = media_id

            for tagset_name, tag_values in mapping['tagsets'].items():
                if tagset_name not in tagset_to_values:
                    tagset_to_values[tagset_name] = set()
                tagset_to_values[tagset_name].update(tag_values)

        # Step 2: Get tag ids for each tagset and its values
        # NOTE: Potential for concurrency here if needed
        print("(SDL.add_media_taggings): Step 2)")
        tag_mapping = {}
        for tagset_name, tag_values in tagset_to_values.items():
            tag_ids = get_tag_ids_from_tagset_and_values(connection, tagset_name, list(tag_values))
            tag_mapping.update(tag_ids)

        # Step 3: Create list of taggings and bulk insert
        print("(SDL.add_media_taggings): Step 3)")
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
        connection.commit()
    except Exception as e:
        print("(SDL.add_media_taggings): ", e)
        if connection.in_transaction:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()