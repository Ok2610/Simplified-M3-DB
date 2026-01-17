# Simplified-M3-DB
A database loader for a simplified version (no hierarchies) of the ObjectCube data model using SQLite3 (plan to add support for DuckDB and PostgreSQL in the future)

## ObjectCube / M3 DB
The simplified version of the ObjectCube database consists of the following schema.

* Tagtype: (ID, description)
  - Different column types for tags
  - Default types: alphanumerical, timestamp, time, date, numerical_int, numerical_dec, json
  - Depending on  the underlying DB some tag types are less supported, i.e., using numerical_dec with SQLite3 is not recommended as it is treated as TEXT.
  
* Tagsets: (ID, name, tagtype_id)
  - A tagset is a metadata category 
  - For instance: "Day", "Objects", "Categories", and "CLIP Index Id"

* Tags: (ID, tagset_id, tagtype_id)
  - A tag represents a value of the tagset (metadata category).
  - Each tagtype has a representative table, such as alphanumerical_tags (ID, value, tagset_id), where ID is the same as in the tag table.

* Medias: (ID, source, source_type, thumbnail_uri, group_id)
  - A media represents the multimedia data item / object. In the original ObjectCube definition this schema element was referred to as Objects.
  - source_type refers to the ID of a source_type table with the types being: Image, Video, Audio, Text, and Other.
  - The source is the URI to the media, and the thumbnail_uri is an optional field to add an image representation of the media.
  - Group_id refers to another media objects id, making it possible to have one media related to many others, for instance a video media object having many keyframe image media objects.

## Example JSON Input Objects

### Tagsets

```json
// Tagset Object
{ "name": "Start (ms)", "type": "numerical_int", "tags": [0, 2000, 5000] }

// Tagset List format
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

Notice that tags can be an empty array, since tags can be added and expanded later as well.
### Tags

```json
// Tags Object
{ "name": "Objects", "values": ["person", "cycle", "ramp"] }

// Tag List format
[
    { "name": "User Tags": ["cycle", "sport", "crazy stunts"],
    { "name": "Text": ["Here are highlights from day one of the BMX event"],
    { "name": "Caption": ["Highlights of a sports event showcasing BMX stunts", "Person on a bicycle performing a stunt"]
]
```
### Medias and Taggings

**NOTE: The corresponding JSON files of these expect a JSON array of the following objects** 

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
    "Start (sec)": [0],
    "End (sec)": [180],
    "User Tags": ["cycle", "sport", "crazy stunts"],
    "Categories": ["sport"],
    "Day": [1],
    "Caption": ["Highlights of a sports event showcasing BMX stunts"],
    "Segment_Caption_Index_Id": [0] // could also create segment captions as own media similar to transcripts
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
    "Start (sec)": [5],
    "End (sec)": [5],
    "Objects": ["person", "cycle", "ramp"],
    "Caption": ["Person on a bicycle performing a stunt"],
    "Clip_Index_Id": [23],
    "Caption_KF_Index_Id": [12]
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
    "Start (sec)": [2],
    "End (sec)": [12],
    "Transcript": ["Here are highlights from day one of the BMX event"],
    "Transcript_Index_Id": [0],
    "Closest_Keyframe": ["image_1.jpg"] // Can precompute this, but also possible to do via function
}
```

## Example running Simplified-M3-DB

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
