from __future__ import annotations

from datetime import date
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.data import (
    DataSourceUnavailable,
    filter_fire_features,
    load_county_collection,
    load_fire_collection,
    parse_bbox,
)
from app.db import DatabaseUnavailable, fetch_county_collection, fetch_fire_collection

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
