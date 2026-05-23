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

CREATE TABLE IF NOT EXISTS county_exposure (
    geoid TEXT PRIMARY KEY REFERENCES az_counties(geoid),
    name TEXT NOT NULL,
    statefp TEXT,
    countyfp TEXT,
    population INTEGER,
    households INTEGER,
    median_household_income INTEGER,
    source TEXT,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS az_places (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    county TEXT,
    population INTEGER,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS az_places_geom_idx
    ON az_places USING GIST (geom);

CREATE TABLE IF NOT EXISTS regions (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    fips TEXT[] NOT NULL,
    bbox DOUBLE PRECISION[] NOT NULL,
    center_longitude DOUBLE PRECISION NOT NULL,
    center_latitude DOUBLE PRECISION NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS region_counties (
    geoid TEXT PRIMARY KEY,
    region_code TEXT NOT NULL REFERENCES regions(code),
    name TEXT NOT NULL,
    statefp TEXT,
    countyfp TEXT,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS region_counties_region_code_idx
    ON region_counties (region_code);

CREATE INDEX IF NOT EXISTS region_counties_statefp_idx
    ON region_counties (statefp);

CREATE INDEX IF NOT EXISTS region_counties_geom_idx
    ON region_counties USING GIST (geom);

CREATE TABLE IF NOT EXISTS h3_risk_cells (
    h3_cell TEXT NOT NULL,
    h3_resolution INTEGER NOT NULL,
    region_code TEXT NOT NULL REFERENCES regions(code),
    risk_score DOUBLE PRECISION NOT NULL,
    risk_class TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Polygon, 4326) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (h3_cell, h3_resolution, region_code)
);

CREATE INDEX IF NOT EXISTS h3_risk_cells_region_code_idx
    ON h3_risk_cells (region_code);

CREATE INDEX IF NOT EXISTS h3_risk_cells_h3_cell_idx
    ON h3_risk_cells (h3_cell);

CREATE INDEX IF NOT EXISTS h3_risk_cells_h3_resolution_idx
    ON h3_risk_cells (h3_resolution);

CREATE INDEX IF NOT EXISTS h3_risk_cells_geom_idx
    ON h3_risk_cells USING GIST (geom);
