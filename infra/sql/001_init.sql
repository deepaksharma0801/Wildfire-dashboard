CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS fire_detections (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    state TEXT,
    county TEXT,
    area_label TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    confidence INTEGER NOT NULL DEFAULT 0,
    confidence_label TEXT,
    brightness_kelvin DOUBLE PRECISION,
    satellite TEXT,
    instrument TEXT,
    acq_date DATE,
    acq_time TEXT,
    acq_datetime TIMESTAMPTZ NOT NULL,
    frp_mw DOUBLE PRECISION,
    daynight TEXT,
    version TEXT,
    sample BOOLEAN NOT NULL DEFAULT FALSE,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS fire_detections_geom_idx
    ON fire_detections USING GIST (geom);

CREATE INDEX IF NOT EXISTS fire_detections_acq_datetime_idx
    ON fire_detections (acq_datetime);

CREATE INDEX IF NOT EXISTS fire_detections_confidence_idx
    ON fire_detections (confidence);

CREATE TABLE IF NOT EXISTS az_counties (
    geoid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    statefp TEXT,
    countyfp TEXT,
    aland NUMERIC,
    awater NUMERIC,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS az_counties_geom_idx
    ON az_counties USING GIST (geom);
