from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import psycopg

from app.db import DEFAULT_DATABASE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "infra" / "sql" / "001_init.sql"
SAMPLE_FIRES_PATH = PROJECT_ROOT / "data" / "sample" / "firms_arizona_sample.geojson"
LIVE_FIRES_PATH = PROJECT_ROOT / "data" / "processed" / "firms_arizona_latest.geojson"
SAMPLE_COUNTIES_PATH = PROJECT_ROOT / "data" / "sample" / "arizona_counties_sample.geojson"
OFFICIAL_COUNTIES_PATH = PROJECT_ROOT / "data" / "processed" / "arizona_counties.geojson"
SAMPLE_EXPOSURE_PATH = PROJECT_ROOT / "data" / "sample" / "arizona_county_exposure_sample.json"
ACS_EXPOSURE_PATH = PROJECT_ROOT / "data" / "processed" / "arizona_county_exposure_acs2024.json"
PLACES_PATH = PROJECT_ROOT / "data" / "sample" / "arizona_places_sample.json"


def default_fire_path() -> Path:
    return LIVE_FIRES_PATH if LIVE_FIRES_PATH.exists() else SAMPLE_FIRES_PATH


def default_county_path() -> Path:
    return OFFICIAL_COUNTIES_PATH if OFFICIAL_COUNTIES_PATH.exists() else SAMPLE_COUNTIES_PATH


def default_exposure_path() -> Path:
    return ACS_EXPOSURE_PATH if ACS_EXPOSURE_PATH.exists() else SAMPLE_EXPOSURE_PATH


def load_geojson(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def first(properties: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = properties.get(key)
        if value not in (None, ""):
            return value
    return default


def ensure_schema(connection: psycopg.Connection) -> None:
    connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_fires(connection: psycopg.Connection, path: Path) -> int:
    collection = load_geojson(path)
    rows_loaded = 0

    with connection.cursor() as cursor:
        for feature in collection.get("features", []):
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            detected_at = first(properties, "acq_datetime")
            acq_date = first(properties, "acq_date")

            cursor.execute(
                """
                INSERT INTO fire_detections (
                    id, source, state, county, area_label, latitude, longitude,
                    confidence, confidence_label, brightness_kelvin, satellite,
                    instrument, acq_date, acq_time, acq_datetime, frp_mw, daynight,
                    version, sample, properties, geom
                )
                VALUES (
                    %(id)s, %(source)s, %(state)s, %(county)s, %(area_label)s,
                    %(latitude)s, %(longitude)s, %(confidence)s, %(confidence_label)s,
                    %(brightness_kelvin)s, %(satellite)s, %(instrument)s,
                    %(acq_date)s, %(acq_time)s, %(acq_datetime)s, %(frp_mw)s,
                    %(daynight)s, %(version)s, %(sample)s, %(properties)s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%(geometry)s), 4326)
                )
                ON CONFLICT (id) DO UPDATE SET
                    source = EXCLUDED.source,
                    state = EXCLUDED.state,
                    county = EXCLUDED.county,
                    area_label = EXCLUDED.area_label,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    confidence = EXCLUDED.confidence,
                    confidence_label = EXCLUDED.confidence_label,
                    brightness_kelvin = EXCLUDED.brightness_kelvin,
                    satellite = EXCLUDED.satellite,
                    instrument = EXCLUDED.instrument,
                    acq_date = EXCLUDED.acq_date,
                    acq_time = EXCLUDED.acq_time,
                    acq_datetime = EXCLUDED.acq_datetime,
                    frp_mw = EXCLUDED.frp_mw,
                    daynight = EXCLUDED.daynight,
                    version = EXCLUDED.version,
                    sample = EXCLUDED.sample,
                    properties = EXCLUDED.properties,
                    geom = EXCLUDED.geom
                """,
                {
                    "id": first(properties, "id"),
                    "source": first(properties, "source", default="unknown"),
                    "state": first(properties, "state", default="AZ"),
                    "county": first(properties, "county", default="Unknown"),
                    "area_label": first(properties, "area_label", default="Fire detection"),
                    "latitude": first(properties, "latitude"),
                    "longitude": first(properties, "longitude"),
                    "confidence": int(first(properties, "confidence", default=0)),
                    "confidence_label": first(properties, "confidence_label"),
                    "brightness_kelvin": first(properties, "brightness_kelvin"),
                    "satellite": first(properties, "satellite"),
                    "instrument": first(properties, "instrument"),
                    "acq_date": acq_date,
                    "acq_time": first(properties, "acq_time"),
                    "acq_datetime": datetime.fromisoformat(str(detected_at).replace("Z", "+00:00")),
                    "frp_mw": first(properties, "frp_mw"),
                    "daynight": first(properties, "daynight"),
                    "version": first(properties, "version"),
                    "sample": bool(first(properties, "sample", default=False)),
                    "properties": json.dumps(properties),
                    "geometry": json.dumps(geometry),
                },
            )
            rows_loaded += 1

    return rows_loaded


def load_counties(connection: psycopg.Connection, path: Path) -> int:
    collection = load_geojson(path)
    rows_loaded = 0

    with connection.cursor() as cursor:
        for feature in collection.get("features", []):
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            geoid = first(properties, "GEOID", "geoid")
            name = first(properties, "NAME", "name")

            cursor.execute(
                """
                INSERT INTO az_counties (
                    geoid, name, statefp, countyfp, aland, awater, properties, geom
                )
                VALUES (
                    %(geoid)s, %(name)s, %(statefp)s, %(countyfp)s, %(aland)s,
                    %(awater)s, %(properties)s,
                    ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%(geometry)s), 4326))
                )
                ON CONFLICT (geoid) DO UPDATE SET
                    name = EXCLUDED.name,
                    statefp = EXCLUDED.statefp,
                    countyfp = EXCLUDED.countyfp,
                    aland = EXCLUDED.aland,
                    awater = EXCLUDED.awater,
                    properties = EXCLUDED.properties,
                    geom = EXCLUDED.geom
                """,
                {
                    "geoid": geoid,
                    "name": name,
                    "statefp": first(properties, "STATE", "statefp"),
                    "countyfp": first(properties, "COUNTY", "countyfp"),
                    "aland": first(properties, "AREALAND", "aland"),
                    "awater": first(properties, "AREAWATER", "awater"),
                    "properties": json.dumps(properties),
                    "geometry": json.dumps(geometry),
                },
            )
            rows_loaded += 1

    return rows_loaded


def load_county_exposure(connection: psycopg.Connection, path: Path) -> int:
    rows = load_geojson(path) if path.suffix == ".geojson" else json.loads(path.read_text(encoding="utf-8"))
    rows_loaded = 0

    with connection.cursor() as cursor:
        for row in rows:
            cursor.execute(
                """
                INSERT INTO county_exposure (
                    geoid, name, statefp, countyfp, population, households,
                    median_household_income, source, properties
                )
                VALUES (
                    %(geoid)s, %(name)s, %(statefp)s, %(countyfp)s, %(population)s,
                    %(households)s, %(median_household_income)s, %(source)s, %(properties)s
                )
                ON CONFLICT (geoid) DO UPDATE SET
                    name = EXCLUDED.name,
                    statefp = EXCLUDED.statefp,
                    countyfp = EXCLUDED.countyfp,
                    population = EXCLUDED.population,
                    households = EXCLUDED.households,
                    median_household_income = EXCLUDED.median_household_income,
                    source = EXCLUDED.source,
                    properties = EXCLUDED.properties
                """,
                {
                    "geoid": row["geoid"],
                    "name": row["name"],
                    "statefp": row.get("statefp"),
                    "countyfp": row.get("countyfp"),
                    "population": row.get("population"),
                    "households": row.get("households"),
                    "median_household_income": row.get("median_household_income"),
                    "source": row.get("source"),
                    "properties": json.dumps(row),
                },
            )
            rows_loaded += 1

    return rows_loaded


def load_places(connection: psycopg.Connection, path: Path) -> int:
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows_loaded = 0

    with connection.cursor() as cursor:
        for row in rows:
            cursor.execute(
                """
                INSERT INTO az_places (
                    id, name, county, population, latitude, longitude, properties, geom
                )
                VALUES (
                    %(id)s, %(name)s, %(county)s, %(population)s, %(latitude)s,
                    %(longitude)s, %(properties)s,
                    ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    county = EXCLUDED.county,
                    population = EXCLUDED.population,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    properties = EXCLUDED.properties,
                    geom = EXCLUDED.geom
                """,
                {
                    "id": row["id"],
                    "name": row["name"],
                    "county": row.get("county"),
                    "population": row.get("population"),
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "properties": json.dumps(row),
                },
            )
            rows_loaded += 1

    return rows_loaded


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load wildfire GeoJSON data into PostGIS.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="PostgreSQL connection URL.",
    )
    parser.add_argument("--fires", default=default_fire_path(), type=Path, help="Fire GeoJSON path.")
    parser.add_argument(
        "--counties",
        default=default_county_path(),
        type=Path,
        help="Arizona county GeoJSON path.",
    )
    parser.add_argument(
        "--exposure",
        default=default_exposure_path(),
        type=Path,
        help="County exposure JSON path.",
    )
    parser.add_argument("--places", default=PLACES_PATH, type=Path, help="Arizona places JSON path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with psycopg.connect(args.database_url) as connection:
        ensure_schema(connection)
        fire_count = load_fires(connection, args.fires)
        county_count = load_counties(connection, args.counties)
        exposure_count = load_county_exposure(connection, args.exposure)
        place_count = load_places(connection, args.places)
        connection.commit()

    print(f"Loaded fire detections: {fire_count} from {args.fires}")
    print(f"Loaded counties: {county_count} from {args.counties}")
    print(f"Loaded county exposure rows: {exposure_count} from {args.exposure}")
    print(f"Loaded places: {place_count} from {args.places}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
