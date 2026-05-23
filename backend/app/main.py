from __future__ import annotations

from datetime import date
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.az_intelligence import build_az_risk_intelligence
from app.copilot import build_copilot_response, detect_intent
from app.data import (
    DataSourceUnavailable,
    BBox,
    filter_fire_features,
    load_county_collection,
    load_fire_collection,
    parse_bbox,
)
from app.db import DatabaseUnavailable, fetch_county_collection, fetch_fire_collection
from app.db import fetch_fire_clusters as fetch_db_fire_clusters
from app.db import fetch_incident_summary as fetch_db_incident_summary
from app.exposure import get_cluster_collection, get_incident_summary
from app.imagery import (
    ImageryUnavailable,
    before_after_product,
    imagery_asset_response,
    search_imagery_products,
)
from app.forecast import build_forecast_grid
from app.h3_risk import ALLOWED_H3_RESOLUTIONS, DEFAULT_H3_RESOLUTION, build_h3_risk_grid
from app.reports import generate_template_report, validate_summary
from app.regions import get_region, list_regions
from app.risk import build_file_risk_grid, build_risk_grid_from_features
from app.risk_evaluation import load_or_build_risk_evaluation
from app.simulations import build_risk_scenario
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


class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    data_source: Literal["auto", "sample", "live", "db"] = "auto"
    region: str = Field(default="AZ", max_length=24)
    start_date: date | None = None
    end_date: date | None = None
    min_confidence: int = Field(default=50, ge=0, le=100)


class RiskScenarioRequest(BaseModel):
    region: str = Field(default="southwest", max_length=24)
    h3_resolution: int = Field(default=DEFAULT_H3_RESOLUTION, ge=4, le=6)
    horizon_hours: int = Field(default=72)
    temperature_delta_c: float = Field(default=3, ge=-10, le=10)
    drought_multiplier: float = Field(default=1.2, ge=0.5, le=2.0)
    wind_multiplier: float = Field(default=1.1, ge=0.5, le=2.0)
    data_source: Literal["auto", "sample", "live", "db"] = "auto"


def should_use_database(data_source: str) -> bool:
    return data_source == "db" or (
        data_source == "auto" and os.getenv("FIRE_DATA_SOURCE") == "db"
    )


def get_fire_collection_for_filters(
    *,
    data_source: str,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
) -> dict:
    if should_use_database(data_source):
        try:
            collection = fetch_fire_collection(
                start_date=start_date,
                end_date=end_date,
                bbox=bbox,
                min_confidence=min_confidence,
            )
            collection["metadata"]["requested_data_source"] = data_source
            return collection
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    collection, resolved_source = load_fire_collection(data_source)
    features = filter_fire_features(
        collection,
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
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
        },
    }


def get_county_collection_for_source(data_source: str) -> dict:
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


def get_cluster_collection_for_filters(
    *,
    data_source: str,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    radius_km: float = 25,
) -> dict:
    if should_use_database(data_source):
        try:
            collection = fetch_db_fire_clusters(
                start_date=start_date,
                end_date=end_date,
                bbox=bbox,
                min_confidence=min_confidence,
                radius_km=radius_km,
            )
            collection["metadata"]["requested_data_source"] = data_source
            return collection
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    collection = get_cluster_collection(
        data_source=data_source,
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
        radius_km=radius_km,
    )
    collection["metadata"]["requested_data_source"] = data_source
    return collection


def get_risk_grid_for_filters(
    *,
    data_source: str,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    cell_size_deg: float = 0.5,
) -> dict:
    if should_use_database(data_source):
        try:
            fires = fetch_fire_collection(
                start_date=start_date,
                end_date=end_date,
                bbox=bbox,
                min_confidence=min_confidence,
            )
            grid = build_risk_grid_from_features(
                fires["features"],
                bbox=bbox,
                cell_size_deg=cell_size_deg,
                horizon_hours=72,
                source="postgis",
            )
            grid["metadata"]["requested_data_source"] = data_source
            return grid
        except DatabaseUnavailable as error:
            if data_source == "db":
                raise HTTPException(status_code=503, detail=f"PostGIS unavailable: {error}") from error

    grid = build_file_risk_grid(
        data_source=data_source,
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
        cell_size_deg=cell_size_deg,
        horizon_hours=72,
    )
    grid["metadata"]["requested_data_source"] = data_source
    return grid


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wildfire-geoai-api"}


@app.get("/api/regions")
def get_regions() -> dict:
    return list_regions()


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


@app.get("/api/imagery/search")
def search_imagery(
    query: str | None = Query(default=None),
) -> dict:
    try:
        return search_imagery_products(query=query)
    except ImageryUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/risk/evaluation")
def get_risk_evaluation() -> dict:
    return load_or_build_risk_evaluation()


@app.get("/api/risk/h3-grid")
def get_h3_risk_grid(
    region: str = Query(default="AZ"),
    h3_resolution: int = Query(default=DEFAULT_H3_RESOLUTION, ge=4, le=6),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    min_confidence: int = Query(default=0, ge=0, le=100),
    data_source: Literal["auto", "sample", "live", "db"] = Query(default="auto"),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    if h3_resolution not in ALLOWED_H3_RESOLUTIONS:
        raise HTTPException(status_code=422, detail="h3_resolution must be one of 4, 5, or 6")

    try:
        region_config = get_region(region)
        fires = get_fire_collection_for_filters(
            data_source=data_source,
            start_date=start_date,
            end_date=end_date,
            bbox=region_config.bbox,
            min_confidence=min_confidence,
        )
        grid = build_h3_risk_grid(
            fires["features"],
            region=region_config,
            h3_resolution=h3_resolution,
            source=fires.get("metadata", {}).get("source", "unknown"),
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    grid["metadata"]["requested_data_source"] = data_source
    return grid


@app.get("/api/forecast/risk-grid")
def get_risk_forecast_grid(
    horizon_hours: int = Query(default=72),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    bbox: str | None = Query(default=None),
    min_confidence: int = Query(default=0, ge=0, le=100),
    data_source: Literal["auto", "sample", "live", "db"] = Query(default="auto"),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    if horizon_hours not in {24, 48, 72}:
        raise HTTPException(status_code=422, detail="horizon_hours must be one of 24, 48, or 72")

    try:
        parsed_bbox = parse_bbox(bbox)
        risk_grid = get_risk_grid_for_filters(
            data_source=data_source,
            start_date=start_date,
            end_date=end_date,
            bbox=parsed_bbox,
            min_confidence=min_confidence,
            cell_size_deg=0.5,
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    forecast = build_forecast_grid(risk_grid, horizon_hours=horizon_hours)
    forecast["metadata"]["requested_data_source"] = data_source
    return forecast


@app.get("/api/az/risk-intelligence")
def get_az_risk_intelligence(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    min_confidence: int = Query(default=0, ge=0, le=100),
    horizon_hours: int = Query(default=72),
    data_source: Literal["auto", "sample", "live", "db"] = Query(default="auto"),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    if horizon_hours not in {24, 48, 72}:
        raise HTTPException(status_code=422, detail="horizon_hours must be one of 24, 48, or 72")

    try:
        az_region = get_region("AZ")
        fires = get_fire_collection_for_filters(
            data_source=data_source,
            start_date=start_date,
            end_date=end_date,
            bbox=az_region.bbox,
            min_confidence=min_confidence,
        )
        counties = get_county_collection_for_source(
            "db" if data_source == "db" else "auto"
        )
        risk_grid = build_risk_grid_from_features(
            fires["features"],
            bbox=az_region.bbox,
            cell_size_deg=0.5,
            horizon_hours=horizon_hours,
            source=fires.get("metadata", {}).get("source", "unknown"),
        )
        risk_grid["metadata"]["requested_data_source"] = data_source
        forecast = build_forecast_grid(risk_grid, horizon_hours=horizon_hours)
        forecast["metadata"]["requested_data_source"] = data_source
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return build_az_risk_intelligence(
        fires=fires,
        counties=counties,
        risk_grid=risk_grid,
        forecast_grid=forecast,
        horizon_hours=horizon_hours,
        requested_data_source=data_source,
    )


@app.post("/api/copilot/query")
def run_spatial_copilot(request: CopilotQueryRequest) -> dict:
    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    try:
        region_config = get_region(request.region)
        fires = get_fire_collection_for_filters(
            data_source=request.data_source,
            start_date=request.start_date,
            end_date=request.end_date,
            bbox=region_config.bbox,
            min_confidence=request.min_confidence,
        )
        counties = get_county_collection_for_source(
            "db" if request.data_source == "db" else "auto"
        )
        clusters = get_cluster_collection_for_filters(
            data_source=request.data_source,
            start_date=request.start_date,
            end_date=request.end_date,
            bbox=region_config.bbox,
            min_confidence=request.min_confidence,
            radius_km=25,
        )
        risk_grid = build_h3_risk_grid(
            fires["features"],
            region=region_config,
            h3_resolution=DEFAULT_H3_RESOLUTION,
            source=fires.get("metadata", {}).get("source", "unknown"),
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    top_summary = None
    if detect_intent(request.query) == "incident_summary" and clusters.get("features"):
        top_cluster = clusters["features"][0]
        top_id = top_cluster["properties"]["id"]
        try:
            if should_use_database(request.data_source):
                top_summary = fetch_db_incident_summary(
                    top_id,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    bbox=region_config.bbox,
                    min_confidence=request.min_confidence,
                    radius_km=25,
                )
            else:
                top_summary = get_incident_summary(
                    top_id,
                    data_source=request.data_source,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    bbox=region_config.bbox,
                    min_confidence=request.min_confidence,
                    radius_km=25,
                )
        except (DatabaseUnavailable, DataSourceUnavailable, ValueError):
            top_summary = None

    return build_copilot_response(
        query=request.query,
        fires=fires,
        counties=counties,
        clusters=clusters,
        risk_grid=risk_grid,
        top_incident_summary=top_summary,
    )


@app.post("/api/simulations/risk-scenario")
def run_risk_scenario(request: RiskScenarioRequest) -> dict:
    if request.horizon_hours not in {24, 48, 72}:
        raise HTTPException(status_code=422, detail="horizon_hours must be one of 24, 48, or 72")
    if request.h3_resolution not in ALLOWED_H3_RESOLUTIONS:
        raise HTTPException(status_code=422, detail="h3_resolution must be one of 4, 5, or 6")

    try:
        region_config = get_region(request.region)
        fires = get_fire_collection_for_filters(
            data_source=request.data_source,
            bbox=region_config.bbox,
            min_confidence=0,
        )
        risk_grid = build_h3_risk_grid(
            fires["features"],
            region=region_config,
            h3_resolution=request.h3_resolution,
            source=fires.get("metadata", {}).get("source", "unknown"),
        )
    except DataSourceUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return build_risk_scenario(
        risk_grid,
        region=region_config.code,
        h3_resolution=request.h3_resolution,
        horizon_hours=request.horizon_hours,
        temperature_delta_c=request.temperature_delta_c,
        drought_multiplier=request.drought_multiplier,
        wind_multiplier=request.wind_multiplier,
    )


@app.get("/api/imagery/{incident_id}/before-after")
def get_before_after_imagery(incident_id: str) -> dict:
    try:
        return before_after_product(incident_id)
    except ImageryUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/imagery/assets/{file_name}")
def get_imagery_asset(file_name: str):
    try:
        return imagery_asset_response(file_name)
    except ImageryUnavailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
