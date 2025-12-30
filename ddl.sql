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
DROP SEQUENCE IF EXISTS media_id_seq;
DROP SEQUENCE IF EXISTS tagset_id_seq;
DROP SEQUENCE IF EXISTS tag_id_seq;

------------------------------------------------------------------------- Source Types
CREATE TABLE source_types (
    id integer PRIMARY KEY,
    name text NOT NULL UNIQUE
);

INSERT INTO source_types (id, name) VALUES
(1, 'Image'),
(2, 'Video'),
(3, 'Audio'),
(4, 'Text'),
(5, 'Other');


------------------------------------------------------------------------- Medias
CREATE SEQUENCE media_id_seq; 
CREATE TABLE medias (
    id integer PRIMARY KEY DEFAULT nextval('media_id_seq'),
    source text NOT NULL UNIQUE, -- URI or special identifier
    source_type integer NOT NULL REFERENCES source_types(id),
    thumbnail_uri text,
    group_id integer REFERENCES medias(id) -- for grouping related media (e.g. video and its thumbnail)
);

------------------------------------------------------------------------- Tag Types
CREATE TABLE tag_types (
    id integer PRIMARY KEY,
    description text NOT NULL
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
CREATE SEQUENCE tagset_id_seq;
CREATE TABLE tagsets (
    id integer PRIMARY KEY DEFAULT nextval('tagset_id_seq'),
    name text NOT NULL UNIQUE,
    tagtype_id integer NOT NULL
);

------------------------------------------------------------------------- Tags
CREATE SEQUENCE tag_id_seq;
CREATE TABLE tags (
    id integer PRIMARY KEY DEFAULT nextval('tag_id_seq'),
    tagtype_id integer NOT NULL,
    tagset_id integer NOT NULL
);

------------------------------------------------------------------------- Alphanumerical Tags
CREATE TABLE alphanumerical_tags (
    id integer PRIMARY KEY REFERENCES tags(id),
    value text NOT NULL,
    tagset_id integer NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id),
);

------------------------------------------------------------------------- Timestamp Tags
CREATE TABLE timestamp_tags (
    id integer PRIMARY KEY REFERENCES tags(id),
    value timestamp without time zone NOT NULL,
    tagset_id integer NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Time Tags
CREATE TABLE time_tags (
    id integer PRIMARY KEY REFERENCES tags(id),
    value time without time zone NOT NULL,
    tagset_id integer NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Date Tags
CREATE TABLE date_tags (
    id integer PRIMARY KEY REFERENCES tags(id),
    value date NOT NULL,
    tagset_id integer NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Numerical Tags
CREATE TABLE numerical_int_tags (
    id integer PRIMARY KEY REFERENCES tags(id),
    value int NOT NULL,
    tagset_id integer NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);

------------------------------------------------------------------------- Numerical Tags
CREATE TABLE numerical_dec_tags (
    id integer PRIMARY KEY REFERENCES tags(id),
    value decimal NOT NULL,
    tagset_id integer NOT NULL REFERENCES tagsets(id),
    UNIQUE (value, tagset_id)
);
------------------------------------------------------------------------- Media-Tag Relations
CREATE TABLE taggings (
    media_id integer NOT NULL REFERENCES medias(id),
    tag_id integer NOT NULL REFERENCES tags(id),
    PRIMARY KEY (media_id, tag_id)
);

