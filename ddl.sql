DROP INDEX IF EXISTS idx_alphanumerical_tagset_id_value;
DROP INDEX IF EXISTS idx_timestamp_tagset_id_value;
DROP INDEX IF EXISTS idx_time_tagset_id_value;
DROP INDEX IF EXISTS idx_date_tagset_id_value;
DROP INDEX IF EXISTS idx_numerical_int_tagset_id_value;
DROP INDEX IF EXISTS idx_numerical_dec_tagset_id_value;
DROP INDEX IF EXISTS idx_json_tagset_id_value;

DROP INDEX IF EXISTS idx_taggings_media_id;
DROP INDEX IF EXISTS idx_taggings_tag_id;


DROP TABLE IF EXISTS taggings;
DROP TABLE IF EXISTS numerical_int_tags;
DROP TABLE IF EXISTS numerical_dec_tags;
DROP TABLE IF EXISTS date_tags;
DROP TABLE IF EXISTS time_tags;
DROP TABLE IF EXISTS timestamp_tags;
DROP TABLE IF EXISTS alphanumerical_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS tagsets;
DROP TABLE IF EXISTS tag_types;
DROP TABLE IF EXISTS medias;
DROP TABLE IF EXISTS source_types;
-- DROP SEQUENCE IF EXISTS media_id_seq;
-- DROP SEQUENCE IF EXISTS tagset_id_seq;
-- DROP SEQUENCE IF EXISTS tag_id_seq;

------------------------------------------------------------------------- Source Types
CREATE TABLE source_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO source_types (id, name) VALUES
(1, 'Image'),
(2, 'Video'),
(3, 'Audio'),
(4, 'Text'),
(5, 'Other');


------------------------------------------------------------------------- Medias
-- CREATE SEQUENCE media_id_seq; 
CREATE TABLE medias (
    id INTEGER PRIMARY KEY, -- DEFAULT nextval('media_id_seq'),
    source TEXT NOT NULL UNIQUE, -- URI or special identifier
    source_type INTEGER NOT NULL REFERENCES source_types(id),
    thumbnail_uri TEXT,
    group_id INTEGER REFERENCES medias(id) -- for grouping related media (e.g. video and its thumbnail)
);

------------------------------------------------------------------------- Tag Types
CREATE TABLE tag_types (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL
);

INSERT INTO tag_types (id, description) VALUES
(1, 'alphanumerical'),
(2, 'timestamp'),
(3, 'time'),
(4, 'date'),
(5, 'numerical_int'),
(6, 'numerical_dec'),
(7, 'json');

------------------------------------------------------------------------- TagSets
-- CREATE SEQUENCE tagset_id_seq;
CREATE TABLE tagsets (
    id INTEGER PRIMARY KEY, -- DEFAULT nextval('tagset_id_seq'),
    name TEXT NOT NULL UNIQUE,
    tagtype_id INTEGER NOT NULL
);

------------------------------------------------------------------------- Tags
-- CREATE SEQUENCE tag_id_seq;
CREATE TABLE tags (
    id INTEGER PRIMARY KEY, -- DEFAULT nextval('tag_id_seq'),
    tagtype_id INTEGER NOT NULL,
    tagset_id INTEGER NOT NULL
);

------------------------------------------------------------------------- Alphanumerical Tags
CREATE TABLE alphanumerical_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TEXT NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Timestamp Tags
CREATE TABLE timestamp_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TIMESTAMP without time zone NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Time Tags
CREATE TABLE time_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TIME without time zone NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Date Tags
CREATE TABLE date_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value DATE NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Numerical Tags
CREATE TABLE numerical_int_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value INTEGER NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Numerical Tags
CREATE TABLE numerical_dec_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value DECIMAL(10,5) NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- JSON Tags
CREATE TABLE json_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TEXT NOT NULL, -- SQLite does not have a built-in JSON field
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Media-Tag Relations
CREATE TABLE taggings (
    media_id INTEGER NOT NULL REFERENCES medias(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (media_id, tag_id)
);

------------------------------------------------------------------------- INDEXES
-- NOTE: If bulk insertion takes too long: 
-- 1. DROP the indexes 
-- 2. Insert data 
-- 3. Create the indexes again

CREATE INDEX idx_alphanumerical_tagset_id_value ON alphanumerical_tags(tagset_id, value);
CREATE INDEX idx_timestamp_tagset_id_value ON timestamp_tags(tagset_id, value);
CREATE INDEX idx_time_tagset_id_value ON time_tags(tagset_id, value);
CREATE INDEX idx_date_tagset_id_value ON date_tags(tagset_id, value);
CREATE INDEX idx_numerical_int_tagset_id_value ON numerical_int_tags(tagset_id, value);
CREATE INDEX idx_numerical_dec_tagset_id_value ON numerical_dec_tags(tagset_id, value);
CREATE INDEX idx_json_tagset_id_value ON json_tags(tagset_id, value);

CREATE INDEX idx_taggings_media_id ON taggings(media_id);
CREATE INDEX idx_taggings_tag_id ON taggings(tag_id);

CREATE INDEX idx_medias_group_id ON medias(group_id);

