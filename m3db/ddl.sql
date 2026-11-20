-- SQLite schema of an M3 database, the target of m3db to-sqlite.
-- Same tables and columns as ddl_duckdb.sql, with keys and foreign keys.

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
CREATE TABLE medias (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL UNIQUE, -- URI or special identifier
    source_type INTEGER NOT NULL REFERENCES source_types(id),
    thumbnail_uri TEXT,
    group_id INTEGER REFERENCES medias(id) -- for grouping related media (e.g. video and its thumbnail)
);

------------------------------------------------------------------------- Tag Types
CREATE TABLE tag_types (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL UNIQUE
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
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tagtype_id INTEGER NOT NULL REFERENCES tag_types(id),
    UNIQUE (id, tagtype_id)
);

------------------------------------------------------------------------- Tags
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    tagtype_id INTEGER NOT NULL,
    tagset_id INTEGER NOT NULL,
    FOREIGN KEY (tagset_id, tagtype_id) REFERENCES tagsets(id, tagtype_id)
);

-- Each tag value table is unique on (tagset_id, value), which also serves
-- lookups of a value within a tagset

------------------------------------------------------------------------- Alphanumerical Tags
CREATE TABLE alphanumerical_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TEXT NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- Timestamp Tags
CREATE TABLE timestamp_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TIMESTAMP without time zone NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- Time Tags
CREATE TABLE time_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TIME without time zone NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- Date Tags
CREATE TABLE date_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value DATE NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- Numerical Int Tags
CREATE TABLE numerical_int_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value INTEGER NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- Numerical Dec Tags
CREATE TABLE numerical_dec_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value DECIMAL(10,5) NOT NULL,
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- JSON Tags
CREATE TABLE json_tags (
    id INTEGER PRIMARY KEY REFERENCES tags(id),
    value TEXT NOT NULL, -- SQLite does not have a built-in JSON field
    tagset_id INTEGER NOT NULL REFERENCES tagsets(id),
    UNIQUE (tagset_id, value)
);

------------------------------------------------------------------------- Media-Tag Relations
-- Stored in key order without a rowid, so the key also serves lookups by media_id
CREATE TABLE taggings (
    media_id INTEGER NOT NULL REFERENCES medias(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (media_id, tag_id)
) WITHOUT ROWID;

------------------------------------------------------------------------- Indexes
CREATE INDEX idx_taggings_tag_id ON taggings(tag_id);
CREATE INDEX idx_medias_group_id ON medias(group_id);
