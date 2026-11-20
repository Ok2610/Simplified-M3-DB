# The JSON files

A collection is described by four kinds of file, loaded in this order.

| File | Holds | Required |
|---|---|---|
| `tagsets.json` | The metadata categories, each with its tag type, and optionally its values | Yes |
| `tags.json` | More values for tagsets that already exist | No |
| `medias.json` | The media objects | Yes |
| `taggings.json` | The values of each media, per tagset | Yes |

Each file is a JSON list of objects. It may also be [JSONL](#json-or-jsonl), with one object per line.

## tagsets.json

Each tagset has a unique `name`, a `tagtype`, and a list of `tags` (its values), which may be empty or left out. The tagtype is one of `alphanumerical`, `timestamp`, `time`, `date`, `numerical_int`, `numerical_dec` or `json`.

```json
[
    {
        "name": "Duration (ms)",
        "tagtype": "numerical_int",
        "tags": [60000]
    },
    {
        "name": "Start (ms)",
        "tagtype": "numerical_int",
        "tags": [10000]
    },
    {
        "name": "End (ms)",
        "tagtype": "numerical_int",
        "tags": [15000]
    },
    {
        "name": "Keyframe (ms)",
        "tagtype": "numerical_int",
        "tags": [12000]
    },
    {
        "name": "CLIP Index ID",
        "tagtype": "numerical_int",
        "tags": [42]
    },
    {
        "name": "Transcript Index ID",
        "tagtype": "numerical_int",
        "tags": [7]
    },
    {
        "name": "Transcript",
        "tagtype": "alphanumerical",
        "tags": []
    },
    {
        "name": "Category",
        "tagtype": "alphanumerical",
        "tags": ["Urban"]
    },
    {
        "name": "Upload Date",
        "tagtype": "date",
        "tags": []
    }
]
```

## tags.json

Each entry adds values to a tagset that already exists. A tagset may have several entries.

```json
[
    {
        "tagset_name": "Category",
        "tags": ["Nature", "Sport"]
    },
    {
        "tagset_name": "Upload Date",
        "tags": ["2026-02-10", "2026-02-11"]
    },
    {
        "tagset_name": "Transcript",
        "tags": ["The light turns green and the cars move on"]
    }
]
```

## medias.json

Each media has a unique `source` and a `source_type`, one of `image`, `video`, `audio`, `text` or `other`. The `thumbnail` and `group` are optional. A `group` names the source of another media, here the video that the keyframe and the transcript belong to.

```json
[
    {
        "source": "traffic.mp4",
        "source_type": "video",
        "thumbnail": "traffic_thumbnail.jpg"
    },
    {
        "source": "traffic_frame_12000.jpg",
        "source_type": "image",
        "group": "traffic.mp4"
    },
    {
        "source": "traffic_transcript_10000.txt",
        "source_type": "text",
        "group": "traffic.mp4"
    }
]
```

## taggings.json

Each entry names a media by its `media_source` and lists its values per tagset. Each value must be a tag of that tagset, from `tagsets.json` or `tags.json`.

```json
[
    {
        "media_source": "traffic.mp4",
        "tagsets": {
            "Duration (ms)": [60000],
            "Category": ["Urban"],
            "Upload Date": ["2026-02-10"]
        }
    },
    {
        "media_source": "traffic_frame_12000.jpg",
        "tagsets": {
            "Start (ms)": [10000],
            "End (ms)": [15000],
            "Keyframe (ms)": [12000],
            "CLIP Index ID": [42]
        }
    },
    {
        "media_source": "traffic_transcript_10000.txt",
        "tagsets": {
            "Start (ms)": [10000],
            "End (ms)": [15000],
            "Transcript": ["The light turns green and the cars move on"],
            "Transcript Index ID": [7]
        }
    }
]
```

## Why tags and taggings have their own files

* Tags can be added later. When new medias bring values a tagset does not have yet, add those values with a tags file first, then add the medias and their taggings.
* Tags and taggings can be split over several files, for example one `people_tags.json` and one `people_taggings.json` per tagset, and added one at a time. Each file is loaded on its own, so a collection that does not fit in memory all at once can still be loaded.
* A big tags list can also be split over several entries for the same tagset, in one file.

New tags take the next IDs in the order the files are added in, and within a file in the order the values are listed.

## Media groups

* A group's media must be in the same file as its members, or added before them. Otherwise `add-medias` stops with an error.
* Within one medias file, the members of a group get the IDs right after their group's media.
* Members added in a later file keep their `group_id`, but take the next free IDs.
* IDs never change once added, because files outside the database, such as exquisitor's embeddings, are indexed by media ID.

## JSON or JSONL

Every command reads a `.json` file as a JSON list and a `.jsonl` file as one object per line, with the same keys. JSONL is easier to write in a stream and to split, for example with `split -l`.

DuckDB limits the length of one JSONL line. Lines under 16 MB are always safe, so split a long tags list over several lines for the same tagset. A JSON list has no such limit per entry.

```
{"source": "traffic.mp4", "source_type": "video", "thumbnail": "traffic_thumbnail.jpg"}
{"source": "traffic_frame_12000.jpg", "source_type": "image", "group": "traffic.mp4"}
```
