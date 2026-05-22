from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.data import filter_fire_features, load_fire_collection, parse_bbox

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
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    collection = load_fire_collection()
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
            "source": "sample_firms_like_arizona",
            "filters": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "bbox": bbox,
                "min_confidence": min_confidence,
            },
        },
    }
