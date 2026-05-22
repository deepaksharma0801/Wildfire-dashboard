from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from app.data import BBox
from app.weather import WeatherUnavailable, get_weather_context, unavailable_weather_context

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


def detection_where_clauses(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
) -> tuple[list[str], list[Any]]:
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

    return where_clauses, params


def fetch_fire_clusters(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    radius_km: float = 25,
) -> dict[str, Any]:
    where_clauses, params = detection_where_clauses(
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
    )
    eps_degrees = radius_km / 111.0
    query = f"""
        WITH filtered AS (
            SELECT *
            FROM fire_detections
            WHERE {" AND ".join(where_clauses)}
        ),
        clustered AS (
            SELECT
                *,
                ST_ClusterDBSCAN(geom, eps := %s, minpoints := 1) OVER () AS cluster_no
            FROM filtered
        ),
        grouped AS (
            SELECT
                cluster_no,
                ST_Centroid(ST_Collect(geom)) AS geom,
                COUNT(*) AS detection_count,
                AVG(confidence)::numeric(6,1) AS avg_confidence,
                MAX(frp_mw) AS max_frp_mw,
                MIN(acq_datetime) AS time_start,
                MAX(acq_datetime) AS time_end,
                ARRAY_AGG(id ORDER BY acq_datetime DESC) AS detection_ids,
                ARRAY_AGG(DISTINCT county) FILTER (WHERE county IS NOT NULL AND county <> 'Unknown') AS counties
            FROM clustered
            GROUP BY cluster_no
        )
        SELECT
            'cluster-' || md5(array_to_string(detection_ids, '|')) AS id,
            detection_count,
            avg_confidence::float AS avg_confidence,
            max_frp_mw,
            to_char(time_start AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS time_start,
            to_char(time_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS time_end,
            detection_ids,
            COALESCE(counties, ARRAY[]::text[]) AS counties,
            ST_AsGeoJSON(geom)::json AS geometry
        FROM grouped
        ORDER BY detection_count DESC, time_end DESC
    """
    params.append(eps_degrees)

    with connect() as connection:
        rows = connection.execute(query, params).fetchall()

    features = []
    for row in rows:
        geometry = parse_geojson_geometry(row.pop("geometry"))
        row["radius_km"] = radius_km
        row["source"] = "postgis_cluster"
        features.append({"type": "Feature", "geometry": geometry, "properties": row})

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "source": "postgis",
            "cluster_method": "ST_ClusterDBSCAN",
            "radius_km": radius_km,
        },
    }


def fetch_incident_summary(
    incident_id: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    radius_km: float = 25,
) -> dict[str, Any] | None:
    clusters = fetch_fire_clusters(
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
        radius_km=radius_km,
    )
    cluster = next(
        (feature for feature in clusters["features"] if feature["properties"]["id"] == incident_id),
        None,
    )
    if not cluster:
        return None

    longitude, latitude = cluster["geometry"]["coordinates"]
    properties = cluster["properties"]

    exposure_query = """
        WITH target AS (
            SELECT
                ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 5070) AS center_geom
        ),
        buffer AS (
            SELECT ST_Buffer(center_geom, %s) AS geom FROM target
        ),
        county_overlap AS (
            SELECT
                c.geoid,
                c.name,
                e.population,
                e.households,
                e.median_household_income,
                e.source,
                GREATEST(
                    0,
                    LEAST(
                        1,
                        ST_Area(ST_Intersection(ST_Transform(c.geom, 5070), b.geom))
                        / NULLIF(ST_Area(ST_Transform(c.geom, 5070)), 0)
                    )
                ) AS overlap_ratio
            FROM az_counties c
            JOIN county_exposure e ON e.geoid = c.geoid
            CROSS JOIN buffer b
            WHERE ST_Intersects(ST_Transform(c.geom, 5070), b.geom)
        )
        SELECT
            geoid,
            name,
            population,
            households,
            median_household_income,
            source,
            overlap_ratio,
            ROUND(COALESCE(population, 0) * overlap_ratio)::int AS estimated_population,
            ROUND(COALESCE(households, 0) * overlap_ratio)::int AS estimated_households
        FROM county_overlap
        ORDER BY estimated_population DESC
    """
    places_query = """
        WITH target AS (
            SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography AS geom
        )
        SELECT
            p.id,
            p.name,
            p.county,
            p.population,
            p.latitude,
            p.longitude,
            ROUND((ST_Distance(p.geom::geography, t.geom) / 1000)::numeric, 1)::float AS distance_km
        FROM az_places p
        CROSS JOIN target t
        ORDER BY ST_Distance(p.geom::geography, t.geom)
        LIMIT 5
    """

    radius_m = radius_km * 1000
    with connect() as connection:
        exposure_rows = connection.execute(exposure_query, [longitude, latitude, radius_m]).fetchall()
        place_rows = connection.execute(places_query, [longitude, latitude]).fetchall()

    estimated_population = sum(int(row.get("estimated_population") or 0) for row in exposure_rows)
    estimated_households = sum(int(row.get("estimated_households") or 0) for row in exposure_rows)

    try:
        weather = get_weather_context(latitude, longitude)
    except WeatherUnavailable as error:
        weather = unavailable_weather_context(str(error))

    return {
        "id": incident_id,
        "source": "postgis_summary",
        "center": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius_km,
        "detection_count": properties["detection_count"],
        "time_start": properties["time_start"],
        "time_end": properties["time_end"],
        "avg_confidence": properties["avg_confidence"],
        "max_frp_mw": properties["max_frp_mw"],
        "affected_counties": exposure_rows,
        "estimated_population_exposed": estimated_population,
        "estimated_households_exposed": estimated_households,
        "nearby_places": place_rows,
        "weather": weather,
        "data_caveats": [
            "Exposure is estimated by area-weighting county ACS population across a circular incident buffer.",
            "FIRMS detections are hotspots, not official fire perimeters.",
        ],
    }
