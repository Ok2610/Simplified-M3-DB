# Query examples

These queries run on the example collection in this folder, in both SQLite and DuckDB. Build it first, then open `example.db` with `sqlite3`, or `example.duckdb` with DuckDB.

```bash
cd example
bash example.sh
sqlite3 example.db
```

The first queries are simple lookups. The ones after [How a query finds its rows](#how-a-query-finds-its-rows) combine tagsets, groups and tag types.

## Simple queries

Each value table, such as `alphanumerical_tags`, uses the same id as the tag in `tags`. So a tagging links straight to its value with `taggings.tag_id = alphanumerical_tags.id`.

```sql
-- Get the source of media 1
SELECT source
FROM medias
WHERE id = 1;
-- video_1.mp4
```

```sql
-- Get the medias in the group of video_1.mp4
SELECT id, source
FROM medias
WHERE group_id = (SELECT id FROM medias WHERE source = 'video_1.mp4')
ORDER BY id;
-- 2, image_1.jpg
-- 3, transcript_text_1
```

```sql
-- Get the categories of video_1.mp4
SELECT alphanumerical_tags.value
FROM medias
JOIN taggings ON taggings.media_id = medias.id
JOIN alphanumerical_tags ON alphanumerical_tags.id = taggings.tag_id
JOIN tagsets ON tagsets.id = alphanumerical_tags.tagset_id
WHERE medias.source = 'video_1.mp4'
  AND tagsets.name = 'Categories';
-- sport
```

```sql
-- Get the CLIP Index ID of every media that has one
SELECT medias.source, numerical_int_tags.value
FROM medias
JOIN taggings ON taggings.media_id = medias.id
JOIN numerical_int_tags ON numerical_int_tags.id = taggings.tag_id
JOIN tagsets ON tagsets.id = numerical_int_tags.tagset_id
WHERE tagsets.name = 'CLIP Index ID'
ORDER BY medias.source;
-- image_1.jpg, 23
```

```sql
-- Get the medias that start before 5000 ms
SELECT medias.source, numerical_int_tags.value
FROM medias
JOIN taggings ON taggings.media_id = medias.id
JOIN numerical_int_tags ON numerical_int_tags.id = taggings.tag_id
JOIN tagsets ON tagsets.id = numerical_int_tags.tagset_id
WHERE tagsets.name = 'Start (ms)'
  AND numerical_int_tags.value < 5000
ORDER BY numerical_int_tags.value;
-- video_1.mp4, 0
-- transcript_text_1, 2000
```

## How a query finds its rows

In the SQLite file, a query moves through the schema along these keys and indexes.

* From a tagset name to its values, through the unique index on `(tagset_id, value)` of each value table, such as `alphanumerical_tags`. A filter like "Categories is sport" reads only the matching value rows.
* From a value to its taggings, through the index on `taggings.tag_id`. A value row has the same id as its tag in `tags`, so `taggings.tag_id = alphanumerical_tags.id` links them directly.
* From a media to its taggings, through the key of `taggings`, which starts with `media_id`.
* From a media to the members of its group, through the index on `medias.group_id`.

So the fastest queries start from what they filter on, a tagset and a value or a media, and follow these keys from there.

The DuckDB file has no indexes on its large tables. DuckDB scans them on several cores and skips the blocks of rows that cannot match a filter, so the same queries are fast there too, and filters that match many rows are often faster.

## Medias in a group

`medias` is joined to itself, once as the video and once as its members. The join follows the index on `medias.group_id`.

```sql
SELECT member.id, member.source
FROM medias video
JOIN medias member ON member.group_id = video.id
WHERE video.source = 'video_1.mp4'
ORDER BY member.id;
-- 2, image_1.jpg
-- 3, transcript_text_1
```

## Every tagset and value of one media

Each tag type keeps its values in its own table, so `UNION ALL` gathers the seven value tables into one column of text. SQLite and DuckDB look up only the tags of the media in each table, so whole tables are not read.

```sql
SELECT tagsets.name, value_row.value
FROM medias
JOIN taggings ON taggings.media_id = medias.id
JOIN tags ON tags.id = taggings.tag_id
JOIN tagsets ON tagsets.id = tags.tagset_id
JOIN (
    SELECT id, CAST(value AS TEXT) AS value FROM alphanumerical_tags
    UNION ALL SELECT id, CAST(value AS TEXT) FROM timestamp_tags
    UNION ALL SELECT id, CAST(value AS TEXT) FROM time_tags
    UNION ALL SELECT id, CAST(value AS TEXT) FROM date_tags
    UNION ALL SELECT id, CAST(value AS TEXT) FROM numerical_int_tags
    UNION ALL SELECT id, CAST(value AS TEXT) FROM numerical_dec_tags
    UNION ALL SELECT id, CAST(value AS TEXT) FROM json_tags
) value_row ON value_row.id = tags.id
WHERE medias.source = 'image_1.jpg'
ORDER BY tagsets.name, value_row.value;
-- CLIP Index ID, 23
-- Caption, Person on a bicycle performing a stunt
-- Caption Index ID, 12
-- End (ms), 5000
-- Objects, cycle
-- Objects, person
-- Objects, ramp
-- Start (ms), 5000
```

## Medias of a video within a time range

This finds the members of `video_1.mp4` that start in its first 5 seconds. The range compares numbers, so it uses `numerical_int_tags` and not the text of the value.

```sql
SELECT member.source, start_tag.value AS start_ms
FROM medias video
JOIN medias member ON member.group_id = video.id
JOIN taggings ON taggings.media_id = member.id
JOIN numerical_int_tags start_tag ON start_tag.id = taggings.tag_id
JOIN tagsets ON tagsets.id = start_tag.tagset_id
WHERE video.source = 'video_1.mp4'
  AND tagsets.name = 'Start (ms)'
  AND start_tag.value BETWEEN 0 AND 5000
ORDER BY start_tag.value;
-- transcript_text_1, 2000
-- image_1.jpg, 5000
```

## Medias that match two tagsets

Each part of the `INTERSECT` finds the medias of one value, starting from its tagset and value, and `INTERSECT` keeps the medias found by both. Starting from the values reads only their taggings, not every media.

```sql
SELECT medias.id, medias.source
FROM medias
WHERE medias.id IN (
    SELECT taggings.media_id
    FROM tagsets
    JOIN alphanumerical_tags ON alphanumerical_tags.tagset_id = tagsets.id
    JOIN taggings ON taggings.tag_id = alphanumerical_tags.id
    WHERE tagsets.name = 'Categories'
      AND alphanumerical_tags.value = 'sport'
    INTERSECT
    SELECT taggings.media_id
    FROM tagsets
    JOIN numerical_int_tags ON numerical_int_tags.tagset_id = tagsets.id
    JOIN taggings ON taggings.tag_id = numerical_int_tags.id
    WHERE tagsets.name = 'Day'
      AND numerical_int_tags.value = 1
)
ORDER BY medias.id;
-- 1, video_1.mp4
```

Use `UNION` in place of `INTERSECT` for medias that match either value, and `EXCEPT` for medias that match the first but not the second.

## Values of the members of filtered groups

This gets the CLIP Index ID of each member of the videos in the category "sport". The inner query finds the videos from their value, and the outer query reads one tagset of their members.

```sql
SELECT member.source, clip.value AS clip_index_id
FROM medias member
JOIN taggings ON taggings.media_id = member.id
JOIN numerical_int_tags clip ON clip.id = taggings.tag_id
JOIN tagsets ON tagsets.id = clip.tagset_id
WHERE tagsets.name = 'CLIP Index ID'
  AND member.group_id IN (
      SELECT taggings.media_id
      FROM tagsets
      JOIN alphanumerical_tags ON alphanumerical_tags.tagset_id = tagsets.id
      JOIN taggings ON taggings.tag_id = alphanumerical_tags.id
      WHERE tagsets.name = 'Categories'
        AND alphanumerical_tags.value = 'sport'
  )
ORDER BY member.source;
-- image_1.jpg, 23
```
