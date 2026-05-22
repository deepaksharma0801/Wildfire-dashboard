from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from app.data import BBox

DEFAULT_DATABASE_URL = "postgresql://wildfire:wildfire@127.0.0.1:5432/wildfire_geoai"


class DatabaseUnavailable(RuntimeError):
    """Raised when the optional PostGIS database cannot serve a request."""


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    try:
        with psycopg.connect(database_url(), connect_timeout=3, row_factory=dict_row) as connection:
            yield connection
    except psycopg.Error as error:
        raise DatabaseUnavailable(str(error)) from error


def parse_geojson_geometry(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    return value


def fetch_fire_collection(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
) -> dict[str, Any]:
    where_clauses = ["confidence >= %s"]
    params: list[Any] = [min_confidence]

    if start_date:
        where_clauses.append("acq_datetime::date >= %s")
        params.append(start_date)
    if end_date:
        where_clauses.append("acq_datetime::date <= %s")
        params.append(end_date)
    if bbox:
        west, south, east, north = bbox
        where_clauses.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
        params.extend([west, south, east, north])

    query = f"""
        SELECT
            id,
            source,
            state,
            county,
            area_label,
            latitude,
            longitude,
            confidence,
            confidence_label,
            brightness_kelvin,
            satellite,
            instrument,
            acq_date::text AS acq_date,
            acq_time,
            to_char(acq_datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS acq_datetime,
            frp_mw,
            daynight,
            version,
            sample,
            properties,
            ST_AsGeoJSON(geom)::json AS geometry
        FROM fire_detections
        WHERE {" AND ".join(where_clauses)}
        ORDER BY acq_datetime DESC
    """

    with connect() as connection:
        rows = connection.execute(query, params).fetchall()

    features = []
    for row in rows:
        geometry = parse_geojson_geometry(row.pop("geometry"))
        extra_properties = row.pop("properties") or {}
        properties = {**extra_properties, **row}
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "source": "postgis",
        },
    }


def fetch_county_collection() -> dict[str, Any]:
    query = """
        SELECT
            geoid,
            name,
            statefp,
            countyfp,
            aland,
            awater,
            properties,
            ST_AsGeoJSON(geom)::json AS geometry
        FROM az_counties
        ORDER BY name
    """

    with connect() as connection:
        rows = connection.execute(query).fetchall()

    features = []
    for row in rows:
        geometry = parse_geojson_geometry(row.pop("geometry"))
        extra_properties = row.pop("properties") or {}
        properties = {**extra_properties, **row}
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "source": "postgis",
        },
    }
