from __future__ import annotations

from datetime import date
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.data import (
    DataSourceUnavailable,
    filter_fire_features,
    load_county_collection,
    load_fire_collection,
    parse_bbox,
)
from app.db import DatabaseUnavailable, fetch_county_collection, fetch_fire_collection
from app.db import fetch_fire_clusters as fetch_db_fire_clusters
from app.db import fetch_incident_summary as fetch_db_incident_summary
from app.exposure import get_cluster_collection, get_incident_summary
from app.reports import generate_template_report, validate_summary
from app.risk import build_file_risk_grid, build_risk_grid_from_features
from app.weather import WeatherUnavailable, get_weather_context, unavailable_weather_context

app = FastAPI(
    title="Wildfire GeoAI API",
    description="Arizona-first wildfire intelligence API for map and incident workflows.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentReportRequest(BaseModel):
    incident_summary: dict = Field(description="Structured incident summary returned by the API.")
    mode: Literal["template"] = "template"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wildfire-geoai-api"}


@app.get("/api/fires")
def get_fires(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    bbox: str | None = Query(
        default=None,
        description="Optional west,south,east,north bounding box.",
    ),
    min_confidence: int = Query(default=0, ge=0, le=100),
    data_source: Literal["auto", "sample", "live", "db"] = Query(
        default="auto",
        description="Use sample data, live FIRMS output, PostGIS, or auto-detect.",
    ),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    use_database = data_source == "db" or (
        data_source == "auto" and os.getenv("FIRE_DATA_SOURCE") == "db"
    )

    if use_database:
        try:
            collection = fetch_fire_collection(
                start_date=start_date,
                end_date=end_date,
                bbox=parsed_bbox,
                min_confidence=min_confidence,
            )
            collection["metadata"]["requested_data_source"] = data_source
            collection["metadata"]["filters"] = {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "bbox": bbox,
                "min_confidence": min_confidence,
                "data_source": data_source,
            }
            return collection
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    try:
        collection, resolved_source = load_fire_collection(data_source)
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    features = filter_fire_features(
        collection,
        start_date=start_date,
        end_date=end_date,
        bbox=parsed_bbox,
        min_confidence=min_confidence,
    )

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "source": resolved_source,
            "requested_data_source": data_source,
            "raw_count": len(collection.get("features", [])),
            "filters": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "bbox": bbox,
                "min_confidence": min_confidence,
                "data_source": data_source,
            },
        },
    }


@app.get("/api/counties")
def get_counties(
    data_source: Literal["auto", "sample", "db"] = Query(
        default="auto",
        description="Use sample county boundaries, PostGIS, or auto-detect.",
    ),
) -> dict:
    use_database = data_source == "db" or (
        data_source == "auto" and os.getenv("BOUNDARY_DATA_SOURCE") == "db"
    )

    if use_database:
        try:
            collection = fetch_county_collection()
            collection["metadata"]["requested_data_source"] = data_source
            return collection
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    collection, resolved_source = load_county_collection()
    collection["metadata"] = {
        "count": len(collection.get("features", [])),
        "source": resolved_source,
        "requested_data_source": data_source,
    }
    return collection


@app.get("/api/fires/clusters")
def get_fire_clusters(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    bbox: str | None = Query(default=None),
    min_confidence: int = Query(default=0, ge=0, le=100),
    radius_km: float = Query(default=25, ge=1, le=100),
    data_source: Literal["auto", "sample", "live", "db"] = Query(default="auto"),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    use_database = data_source == "db" or (
        data_source == "auto" and os.getenv("FIRE_DATA_SOURCE") == "db"
    )
    if use_database:
        try:
            collection = fetch_db_fire_clusters(
                start_date=start_date,
                end_date=end_date,
                bbox=parsed_bbox,
                min_confidence=min_confidence,
                radius_km=radius_km,
            )
            collection["metadata"]["requested_data_source"] = data_source
            return collection
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    try:
        collection = get_cluster_collection(
            data_source=data_source,
            start_date=start_date,
            end_date=end_date,
            bbox=parsed_bbox,
            min_confidence=min_confidence,
            radius_km=radius_km,
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    collection["metadata"]["requested_data_source"] = data_source
    return collection


@app.get("/api/incidents/{incident_id}/summary")
def get_incident_summary_endpoint(
    incident_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    bbox: str | None = Query(default=None),
    min_confidence: int = Query(default=0, ge=0, le=100),
    radius_km: float = Query(default=25, ge=1, le=100),
    data_source: Literal["auto", "sample", "live", "db"] = Query(default="auto"),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    use_database = data_source == "db" or (
        data_source == "auto" and os.getenv("FIRE_DATA_SOURCE") == "db"
    )
    if use_database:
        try:
            summary = fetch_db_incident_summary(
                incident_id,
                start_date=start_date,
                end_date=end_date,
                bbox=parsed_bbox,
                min_confidence=min_confidence,
                radius_km=radius_km,
            )
            if summary:
                return summary
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    try:
        summary = get_incident_summary(
            incident_id,
            data_source=data_source,
            start_date=start_date,
            end_date=end_date,
            bbox=parsed_bbox,
            min_confidence=min_confidence,
            radius_km=radius_km,
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if not summary:
        raise HTTPException(status_code=404, detail="incident cluster not found")

    return summary


@app.get("/api/weather/point")
def get_point_weather(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
) -> dict:
    try:
        return get_weather_context(latitude, longitude)
    except WeatherUnavailable as error:
        return unavailable_weather_context(str(error))


@app.post("/api/reports/incident")
def create_incident_report(request: IncidentReportRequest) -> dict:
    try:
        validate_summary(request.incident_summary)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return generate_template_report(request.incident_summary)


@app.get("/api/risk/grid")
def get_risk_grid(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    bbox: str | None = Query(default=None),
    min_confidence: int = Query(default=0, ge=0, le=100),
    horizon_hours: int = Query(default=72, ge=24, le=72),
    cell_size_deg: float = Query(default=0.5, ge=0.25, le=1.0),
    data_source: Literal["auto", "sample", "live", "db"] = Query(default="auto"),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    use_database = data_source == "db" or (
        data_source == "auto" and os.getenv("FIRE_DATA_SOURCE") == "db"
    )
    if use_database:
        try:
            fires = fetch_fire_collection(
                start_date=start_date,
                end_date=end_date,
                bbox=parsed_bbox,
                min_confidence=min_confidence,
            )
            grid = build_risk_grid_from_features(
                fires["features"],
                bbox=parsed_bbox,
                cell_size_deg=cell_size_deg,
                horizon_hours=horizon_hours,
                source="postgis",
            )
            grid["metadata"]["requested_data_source"] = data_source
            return grid
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    try:
        grid = build_file_risk_grid(
            data_source=data_source,
            start_date=start_date,
            end_date=end_date,
            bbox=parsed_bbox,
            min_confidence=min_confidence,
            cell_size_deg=cell_size_deg,
            horizon_hours=horizon_hours,
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    grid["metadata"]["requested_data_source"] = data_source
    return grid
