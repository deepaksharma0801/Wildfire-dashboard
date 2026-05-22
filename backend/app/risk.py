from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from app.data import PROJECT_ROOT, BBox
from app.exposure import get_filtered_fire_features, haversine_km, load_places

ARIZONA_BBOX: BBox = (-115.1, 31.2, -108.8, 37.1)
HISTORICAL_PRIORS_PATH = PROJECT_ROOT / "data" / "sample" / "arizona_historical_fire_priors.json"
MODEL_VERSION = "baseline-risk-v0.1"


def load_historical_priors(path: Path = HISTORICAL_PRIORS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def risk_class(score: float) -> str:
    if score >= 75:
        return "extreme"
    if score >= 55:
        return "high"
    if score >= 30:
        return "moderate"
    return "low"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def distance_weight(distance_km: float, decay_km: float) -> float:
    return math.exp(-distance_km / decay_km)


def cell_polygon(west: float, south: float, east: float, north: float) -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
        ],
    }


def cell_windows(bbox: BBox, cell_size_deg: float) -> list[tuple[float, float, float, float]]:
    west, south, east, north = bbox
    cells = []
    current_west = west
    while current_west < east:
        current_east = min(east, current_west + cell_size_deg)
        current_south = south
        while current_south < north:
            current_north = min(north, current_south + cell_size_deg)
            cells.append((current_west, current_south, current_east, current_north))
            current_south = current_north
        current_west = current_east
    return cells


def fire_metrics_for_cell(
    *,
    latitude: float,
    longitude: float,
    fire_features: list[dict[str, Any]],
) -> tuple[float, float, int]:
    recent_activity = 0.0
    intensity = 0.0
    nearby_count = 0

    for feature in fire_features:
        fire_lon, fire_lat = feature["geometry"]["coordinates"]
        distance_km = haversine_km(latitude, longitude, float(fire_lat), float(fire_lon))
        weight = distance_weight(distance_km, decay_km=42)
        properties = feature.get("properties", {})
        confidence = float(properties.get("confidence") or 0)
        frp_mw = float(properties.get("frp_mw") or 0)

        if distance_km <= 50:
            nearby_count += 1

        recent_activity += weight * (confidence / 100)
        intensity += weight * min(frp_mw / 30, 1)

    return clamp(recent_activity), clamp(intensity), nearby_count


def historical_prior_for_cell(
    *,
    latitude: float,
    longitude: float,
    priors: list[dict[str, Any]],
) -> float:
    score = 0.0
    for prior in priors:
        distance_km = haversine_km(
            latitude,
            longitude,
            float(prior["latitude"]),
            float(prior["longitude"]),
        )
        score += distance_weight(distance_km, decay_km=75) * float(prior["weight"])
    return clamp(score)


def exposure_proxy_for_cell(*, latitude: float, longitude: float) -> float:
    score = 0.0
    for place in load_places():
        distance_km = haversine_km(
            latitude,
            longitude,
            float(place["latitude"]),
            float(place["longitude"]),
        )
        population_weight = min(float(place.get("population") or 0) / 500_000, 1)
        score += distance_weight(distance_km, decay_km=35) * population_weight
    return clamp(score)


def horizon_multiplier(horizon_hours: int) -> float:
    if horizon_hours <= 24:
        return 0.85
    if horizon_hours <= 48:
        return 0.93
    return 1.0


def build_risk_grid_from_features(
    fire_features: list[dict[str, Any]],
    *,
    bbox: BBox | None = None,
    cell_size_deg: float = 0.5,
    horizon_hours: int = 72,
    source: str = "unknown",
) -> dict[str, Any]:
    grid_bbox = bbox or ARIZONA_BBOX
    priors = load_historical_priors()
    cells = []

    for index, (west, south, east, north) in enumerate(cell_windows(grid_bbox, cell_size_deg), start=1):
        longitude = (west + east) / 2
        latitude = (south + north) / 2
        recent_activity, intensity, nearby_count = fire_metrics_for_cell(
            latitude=latitude,
            longitude=longitude,
            fire_features=fire_features,
        )
        historical_prior = historical_prior_for_cell(
            latitude=latitude,
            longitude=longitude,
            priors=priors,
        )
        exposure_proxy = exposure_proxy_for_cell(latitude=latitude, longitude=longitude)

        raw_score = (
            0.45 * recent_activity
            + 0.25 * intensity
            + 0.20 * historical_prior
            + 0.10 * exposure_proxy
        ) * horizon_multiplier(horizon_hours)
        score = round(raw_score * 100, 1)

        cells.append(
            {
                "type": "Feature",
                "geometry": cell_polygon(west, south, east, north),
                "properties": {
                    "id": f"risk-{index:03d}",
                    "risk_score": score,
                    "risk_class": risk_class(score),
                    "recent_activity": round(recent_activity, 3),
                    "historical_prior": round(historical_prior, 3),
                    "intensity": round(intensity, 3),
                    "exposure_proxy": round(exposure_proxy, 3),
                    "nearby_detection_count": nearby_count,
                    "horizon_hours": horizon_hours,
                    "model_version": MODEL_VERSION,
                },
            }
        )

    cells.sort(key=lambda feature: feature["properties"]["risk_score"], reverse=True)
    return {
        "type": "FeatureCollection",
        "features": cells,
        "metadata": {
            "count": len(cells),
            "source": source,
            "model_version": MODEL_VERSION,
            "horizon_hours": horizon_hours,
            "cell_size_deg": cell_size_deg,
            "input_detection_count": len(fire_features),
            "historical_prior_source": "sample_arizona_historical_fire_priors",
            "method": "weighted_distance_baseline",
            "limitations": [
                "Baseline risk is a screening layer, not an operational fire forecast.",
                "Historical priors are sample portfolio data until MTBS processing is added.",
                "Weather features are not yet included in this grid score.",
            ],
        },
    }


def build_file_risk_grid(
    *,
    data_source: str,
    start_date: date | None = None,
    end_date: date | None = None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    cell_size_deg: float = 0.5,
    horizon_hours: int = 72,
) -> dict[str, Any]:
    fire_features, resolved_source = get_filtered_fire_features(
        data_source=data_source,
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
    )
    return build_risk_grid_from_features(
        fire_features,
        bbox=bbox,
        cell_size_deg=cell_size_deg,
        horizon_hours=horizon_hours,
        source=resolved_source,
    )
