from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_FIRE_DATA_PATH = PROJECT_ROOT / "data" / "sample" / "firms_arizona_sample.geojson"
LIVE_FIRE_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "firms_arizona_latest.geojson"

FeatureCollection = dict[str, Any]
BBox = tuple[float, float, float, float]
DataSource = str


class DataSourceUnavailable(ValueError):
    """Raised when a requested local fire data source does not exist yet."""


def resolve_fire_data_path(data_source: DataSource = "auto") -> tuple[Path, str]:
    if data_source not in {"auto", "sample", "live"}:
        raise ValueError("data_source must be one of auto,sample,live")

    if data_source == "sample":
        return SAMPLE_FIRE_DATA_PATH, "sample_firms_like_arizona"

    if data_source == "live":
        if not LIVE_FIRE_DATA_PATH.exists():
            raise DataSourceUnavailable(
                "live FIRMS data is not available yet; run backend/scripts/ingest_firms.py first"
            )
        return LIVE_FIRE_DATA_PATH, "nasa_firms_area_api"

    preferred_source = os.getenv("FIRE_DATA_SOURCE", "auto")
    if preferred_source == "sample":
        return SAMPLE_FIRE_DATA_PATH, "sample_firms_like_arizona"
    if LIVE_FIRE_DATA_PATH.exists():
        return LIVE_FIRE_DATA_PATH, "nasa_firms_area_api"
    return SAMPLE_FIRE_DATA_PATH, "sample_firms_like_arizona"


def load_fire_collection(data_source: DataSource = "auto") -> tuple[FeatureCollection, str]:
    path, resolved_source = resolve_fire_data_path(data_source)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file), resolved_source


def parse_bbox(value: str | None) -> BBox | None:
    if not value:
        return None

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must contain west,south,east,north")

    west, south, east, north = (float(part) for part in parts)
    if west >= east or south >= north:
        raise ValueError("bbox bounds must be ordered as west,south,east,north")

    return west, south, east, north


def feature_date(feature: dict[str, Any]) -> date:
    raw_value = feature.get("properties", {}).get("acq_datetime")
    if not raw_value:
        raise ValueError("feature is missing acq_datetime")

    return datetime.fromisoformat(str(raw_value).replace("Z", "+00:00")).date()


def feature_in_bbox(feature: dict[str, Any], bbox: BBox) -> bool:
    west, south, east, north = bbox
    longitude, latitude = feature["geometry"]["coordinates"]
    return west <= longitude <= east and south <= latitude <= north


def filter_fire_features(
    collection: FeatureCollection,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for feature in collection.get("features", []):
        properties = feature.get("properties", {})
        confidence = int(properties.get("confidence", 0))

        if confidence < min_confidence:
            continue

        detected_on = feature_date(feature)
        if start_date and detected_on < start_date:
            continue
        if end_date and detected_on > end_date:
            continue
        if bbox and not feature_in_bbox(feature, bbox):
            continue

        filtered.append(feature)

    return filtered
