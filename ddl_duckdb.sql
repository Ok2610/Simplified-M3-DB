DROP TABLE IF EXISTS taggings;
DROP TABLE IF EXISTS numerical_int_tags;
DROP TABLE IF EXISTS numerical_dec_tags;
DROP TABLE IF EXISTS date_tags;
DROP TABLE IF EXISTS time_tags;
DROP TABLE IF EXISTS timestamp_tags;
DROP TABLE IF EXISTS alphanumerical_tags;
DROP TABLE IF EXISTS json_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS tagsets;
DROP TABLE IF EXISTS tag_types;
DROP TABLE IF EXISTS medias;
DROP TABLE IF EXISTS source_types;

-- Same tables and columns as ddl.sql. Only the small tables have keys: an index on
-- the large tables must fit in memory while it is built, so the loader removes
-- duplicates itself and stores every table sorted by its key.

------------------------------------------------------------------------- Source Types
CREATE TABLE source_types (
    id BIGINT PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE
);

INSERT INTO source_types (id, name) VALUES
(1, 'Image'),
(2, 'Video'),
(3, 'Audio'),
(4, 'Text'),
(5, 'Other');


------------------------------------------------------------------------- Medias
CREATE TABLE medias (
    id BIGINT NOT NULL,
    source VARCHAR NOT NULL, -- URI or special identifier
    source_type BIGINT NOT NULL,
    thumbnail_uri VARCHAR,
    group_id BIGINT -- for grouping related media (e.g. video and its thumbnail)
);

------------------------------------------------------------------------- Tag Types
CREATE TABLE tag_types (
    id BIGINT PRIMARY KEY,
    description VARCHAR NOT NULL UNIQUE
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
CREATE TABLE tagsets (
    id BIGINT PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    tagtype_id BIGINT NOT NULL REFERENCES tag_types(id)
);

------------------------------------------------------------------------- Tags
CREATE TABLE tags (
    id BIGINT NOT NULL,
    tagtype_id BIGINT NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Alphanumerical Tags
CREATE TABLE alphanumerical_tags (
    id BIGINT NOT NULL,
    value VARCHAR NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Timestamp Tags
CREATE TABLE timestamp_tags (
    id BIGINT NOT NULL,
    value TIMESTAMP NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Time Tags
CREATE TABLE time_tags (
    id BIGINT NOT NULL,
    value TIME NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Date Tags
CREATE TABLE date_tags (
    id BIGINT NOT NULL,
    value DATE NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Numerical Tags
CREATE TABLE numerical_int_tags (
    id BIGINT NOT NULL,
    value BIGINT NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Numerical Tags
CREATE TABLE numerical_dec_tags (
    id BIGINT NOT NULL,
    value DECIMAL(10,5) NOT NULL,
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- JSON Tags
CREATE TABLE json_tags (
    id BIGINT NOT NULL,
    value VARCHAR NOT NULL, -- text, as in SQLite; existing values are not always valid JSON
    tagset_id BIGINT NOT NULL
);

------------------------------------------------------------------------- Media-Tag Relations
CREATE TABLE taggings (
    media_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL
);
