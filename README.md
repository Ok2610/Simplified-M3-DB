# Simplified Multi-dimensional Media Model

A structured SQLite database for storing multimedia metadata.
This is a simplified version of the multi-dimensional media model (![Paper](https://dl.acm.org/doi/pdf/10.1145/3549555.3549558)).

This repository defines a database schema and an import process for organizing media and attaching structured metadata to it. It is meant to serve as a stable foundation within a larger workflow — not as a standalone application.

You provide metadata in JSON files. The database is initialized and populated from those files into a consistent, queryable structure.

## The Model

Every asset is stored in the `medias` table and assigned an **integer ID**.

A media entry includes:

* A unique `source` (URI or identifier)
* A `source_type` (Image, Video, Audio, Text, or Other)
* An optional `thumbnail_uri`
* An optional `group_id` for linking related media

This allows media items to stand on their own while still supporting relationships, see video and keyframe example below.

Metadata fields are referred to as `tagsets`. Example of a tagset could be "Location (Country)" with tags such as "Denmark", "Netherlands", or "Iceland".
In the full version of the M^3 model hierarchies of tagsets can be maintained, such that you could have tagset hierarchies "Country", "City", "Street", and name the hiearchy as "Location".
Hierarchies are not supported in this simplified version.

A tagset has:

* A unique `name`
* An explicit tag type such as text, integer, date, timestamp, decimal, or JSON

`tags` (values in a tagset) are stored once in their respective typed tables (e.g., `alphanumerical_tags`, `numerical_int_tags`, etc.) and linked to media through a mapping table (`taggings`). This keeps the structure consistent and avoids duplication as the dataset grows.

---

### Examples of Multimedia objects and their metadata

#### Video

```id="videx"
Media ID: 1001
Source: "s3://videos/traffic.mp4"
Source Type: Video

  ├── Index ID (integer): 48219
  ├── Title (text): "Downtown Traffic Scene"
  ├── Category (text): "Urban"
  ├── Upload Date (date): 2026-02-10
  ├── Objects (alphanumerical): ["car", "person"]
```

---

#### Keyframe

```id="kfex"
Media ID: 2050
Source: "s3://videos/traffic_frame_120000.jpg"
Source Type: Image
Parent (group_id): 1001

  ├── Index ID (integer): 48219
  ├── Start (ms) (integer): 120000
  ├── End (ms) (integer): 127000
  ├── Keyframe (ms) (integer): 127000
  ├── Objects (alphanumerical): ["car"]
```

The keyframe is a separate media entry that references the video through `group_id`. Fields such as `Keyframe (ms)` typically describe its position within the video, while `Start (ms)` and `End (ms)` could mean it represents a segment, but the schema itself remains neutral, as in, it stores structured data without imposing meaning. 

These metadata fields would be translated into Tagsets in the M^3 model and their values into tags with the appropriate type.


---

## Using the Repository

1. Initialize the database.
2. Provide:

   * `tagsets.json`
   * `tags.json`
   * `medias.json`
   * `taggings.json`

3. Run the import script.

After import, your metadata lives in a structured SQLite database and is ready to be queried or integrated into your workflow.

## Step by step data prep and loading process

The goal is to create 3-4 JSON files and run a set of commands to generate the SQLite3 database file.

### Tagsets

We start by defining the unique metadata category fields in your collection, as in the overarching categories, "Uplaod Date", "Title", "Description", "User Tags", "Duration (ms)", "CLIP Index Id".

These fields are referred to as `tagsets` in the model, and besides their unique name they also have a data type for their values, such as alphanumerical (string), timestamp, date, time, numerical integer, numerical decimal, or JSON. 

In this repository, you can choose to define them in the database along with or without their distinct values, as once a tagset is defined you can always keep adding new values to it. 

Below are examples of how to create the tagsets.json file with tags and without tags (field has an empty array).

*tagsets.json*

```json
[
  { "name": "Start (ms)", "type": "numerical_int", "tags": [0, 2000, 5000] },
  { "name": "End (ms)", "type": "numerical_int", "tags": [5000, 12000, 180000] },
  { "name": "User Tags", "type": "alphanumerical", "tags": [] },
  { "name": "Categories", "type": "alphanumerical", "tags": ["sports"] },
  { "name": "Caption", "type": "alphanumerical", "tags": [] },
  { "name": "Day", "type": "numerical_int", "tags": [1] },
  { "name": "Objects", "type": "alphanumerical", "tags": [] },
  { "name": "Text", "type": "alphanumerical", "tags": [] },
  { "name": "Closest Keyframe", "type": "alphanumerical", "tags": ["image_1.jpg"] },
  { "name": "CLIP Index Id", "type": "numerical_int", "tags": [23] },
  { "name": "Caption Index Id", "type": "numerical_int", "tags": [0] },
  { "name": "Transcript Index Id", "type": "numerical_int", "tags": [0] }
]
```


You can also add tags for a tagset later by using the following JSON array.

*tags.json*

```json
[
  { "tagset_name": "User Tags", "tags": ["cycle", "sport", "crazy stunts"] },
  { "tagset_name": "Text", "tags" : ["Here are highlights from day one of the BMX event"] },
  { "tagset_name": "Caption", "tags" : ["Highlights of a sports event showcasing BMX stunts", "Person on a bicycle performing a stunt"] }
]
```

### Medias and Taggings

Below are a handful of examples of different media and tagging JSON objects for the `medias.json` and `taggings.json` files.

**NOTE: The files contain JSON arrays with objects in the shown format**

#### Videos

```json
// Media Object
{
  "source": "video_1.mp4",
  "source_type": "video",
  "thumbnail": "optional_img.jpg",
  "group": "optional.mp4" // if the media is a video segment from a larger video
}

// Tagging Object 
{
  "media_src": "video_1.mp4",
  "tagsets": {
    "Start (sec)": [0],
    "End (sec)": [180],
    "User Tags": ["cycle", "sport", "crazy stunts"],
    "Categories": ["sport"],
    "Day": [1],
    "Caption": ["Highlights of a sports event showcasing BMX stunts"],
    "Segment_Caption_Index_Id": [0] // could also create segment captions as own media similar to transcripts
  }
}
```

#### Images

```json
// Media Object
{
    "source": "image_1.jpg",
    "source_type": "image",
    "thumbnail": "optional_img.jpg",
    "group": "video_1.mp4"
}

// Tagging Object
{
    "media_src": "image_1.jpg",
    "tagsets": {
      "Start (sec)": [5],
      "End (sec)": [5],
      "Objects": ["person", "cycle", "ramp"],
      "Caption": ["Person on a bicycle performing a stunt"],
      "Clip_Index_Id": [23],
      "Caption_KF_Index_Id": [12]
    }
}
```

#### Transcripts

```json
// Media Object
{
    "source": "transcript_text_1",
    "source_type": "text",
    "thumbnail": null,
    "group": "video_1.mp4"
}

// Tagging Object
{
    "media_src": "transcript_text_1",
    "tagsets": {
      "Start (sec)": [2],
      "End (sec)": [12],
      "Transcript": ["Here are highlights from day one of the BMX event"],
      "Transcript_Index_Id": [0],
      "Closest_Keyframe": ["image_1.jpg"] // Can precompute this, but also possible to do via function
    }
}
```

### Example running Simplified-M3-DB with the 4 required files

**Initialize Database**

```bash
uv run python main.py initdb <database_name>
```

```bash
uv run python main.py initdb testdb
```

**Add Tagsets**

```bash
uv run python main.py add-tagsets-from-json <database_file> <tagset_json_file> <--ignore-existing>
```

```bash
uv run python main.py add-tagsets-from-json testdb.db example/example_tagsets.json
```

**Add Tags**

```bash
uv run python main.py add-tagsets-from-json <database_file> <tags_json_file>
```

```bash
uv run python main.py add-tags-from-json testdb.db example/example_tags.json
```

**Add medias**
```bash
uv run python ../main.py add-medias-from-json <database_file> <medias_json_file>  
```

```bash
uv run python ../main.py add-medias-from-json example.db example_medias.json  
```

**Adding media taggings**
```bash
uv run python ../main.py add-media-taggings-from-json <database_file> <tagging_json_file>
```

```bash
uv run python ../main.py add-media-taggings-from-json example.db example_taggings.json
```


## Basic Query Examples

```SQL
-- Get media source for id 1234
SELECT m.source
FROM medias m 
WHERE m.id = 1234
```

```SQL
-- Get all tagsets for a given media id e.g. 1234
SELECT tset.id, tset.name
FROM taggings tgs
JOIN tags t ON tgs.tag_id = t.id 
JOIN tagsets tset ON tset.id = t.tagset_id
WHERE tgs.id = 1234
```

```SQL
-- Get all media ids, source URI's, and thumbnail URI's of keyframes belonging to video "Trip to Europe 2026"
-- NOTE that there is an assumption that a tagset exists called "Title"
WITH (
SELECT m.id as video_id
FROM tagsets tset
JOIN alphanumerical_tags at ON tset.id = at.tagset_id
JOIN taggings tgs ON tgs.tag_id = at.id
WHERE tset.name = "Title"
AND at.value = "Trip to Europe 2026"
) video_media_id,
SELECT m.id, m.source, m.thumbnail_uri
FROM medias m
WHERE m.group_id = (SELECT video_id FROM video_media_id)
```

```SQL
-- Get all media objects uploaded before 2026-01-01
-- NOTE: Assumes there exists a tagset named "Upload Date"
WITH (
SELECT m.id as bef_id
FROM tagsets tset
JOIN date_tags dt ON tset.id = dt.tagset_id
JOIN taggings tgs ON tgs.tag_id = dt.id
WHERE tset.name = "Upload Date"
AND at.value < "2026-01-01"
) before_media_ids,
SELECT *
FROM medias m
WHERE m.id IN (SELECT bef_id FROM before_media_ids)
-- Could add this to be sure that it gets Image source type
-- AND m.source_type = 1
```

```SQL
-- Get all media objects uploaded before 2026-01-01 from "Denmark" or "Netherlands"
-- NOTE: Assumes there exists a tagset named "Upload Date" and "Location (Country)"
WITH (
SELECT m.id 
FROM tagsets tset
JOIN date_tags dt ON tset.id = dt.tagset_id
JOIN taggings tgs ON tgs.tag_id = dt.id
WHERE tset.name = "Upload Date"
AND at.value < "2026-01-01"
INTERSECT
SELECT m.id
FROM tagsets tset
JOIN alphanumerical_tags at ON tset.id = at.tagset_id
JOIN taggings tgs ON tgs.tag_id = at.id
WHERE tset.name = "Location (Country)"
AND at.value IN ("Denmark", "Netherlands")
) upl_loc_ids,
SELECT *
FROM medias m
WHERE m.id IN (SELECT id FROM upl_loc_ids)
```

## Model ER Diagram and Table Definitions

![ER Diagram](Entities.png)

The simplified version of the multi-dimensional database consists of the following schema.

* Tagtype: (ID, description)
  - Different column types for tags
  - Default types: alphanumerical, timestamp, time, date, numerical_int, numerical_dec, json
  - Depending on the underlying DB some tag types are less supported, i.e., using numerical_dec with SQLite3 is not recommended as it is treated as TEXT.
  
* Tagsets: (ID, name, tagtype_id)
  - A tagset is a metadata category 
  - For instance: "Day", "Objects", "Categories", and "CLIP Index Id"

* Tags: (ID, tagset_id, tagtype_id)
  - A tag represents a value of the tagset (metadata category).
  - Each tagtype has a representative table, such as alphanumerical_tags (ID, value, tagset_id), where ID is the same as in the tag table.

* Medias: (ID, source, source_type, thumbnail_uri, group_id)
  - A media represents the multimedia data item / object. In the original M3 definition this schema element was referred to as Objects.
  - source_type refers to the ID of a source_type table with the types being: Image, Video, Audio, Text, and Other.
  - The source is the URI to the media, and the thumbnail_uri is an optional field to add an image representation of the media.
  - Group_id refers to another media objects id, making it possible to have one media related to many others, for instance a video media object having many keyframe image media objects.


* Source types: (ID, name)
  - The type of the media
  - Default values (Image, Video, Audio, Text, Other)
