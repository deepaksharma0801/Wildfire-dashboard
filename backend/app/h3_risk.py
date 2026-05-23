from __future__ import annotations

from collections import defaultdict
from typing import Any

import h3

from app.data import BBox
from app.exposure import haversine_km
from app.regions import (
    REGIONS,
    STATE_REGION_CODES,
    RegionConfig,
    places_for_codes,
    places_for_region,
    priors_for_codes,
    priors_for_region,
)
from app.risk import clamp, distance_weight, fire_metrics_for_cell, risk_class

H3_MODEL_VERSION = "h3-risk-baseline-v0.1"
ALLOWED_H3_RESOLUTIONS = {4, 5, 6}
DEFAULT_H3_RESOLUTION = 5


def sample_step_for_resolution(resolution: int) -> float:
    if resolution == 4:
        return 0.75
    if resolution == 5:
        return 0.45
    return 0.25


def sampled_h3_cells(bbox: BBox, resolution: int) -> list[str]:
    west, south, east, north = bbox
    step = sample_step_for_resolution(resolution)
    cells: set[str] = set()
    latitude = south + step / 2
    while latitude < north:
        longitude = west + step / 2
        while longitude < east:
            cells.add(h3.latlng_to_cell(latitude, longitude, resolution))
            longitude += step
        latitude += step
    return sorted(cells)


def anchor_disk_size(resolution: int) -> int:
    if resolution == 4:
        return 2
    if resolution == 5:
        return 3
    return 4


def cells_around_anchors(
    *,
    fire_features: list[dict[str, Any]],
    region: RegionConfig,
    resolution: int,
    active_region_codes: set[str],
) -> list[str]:
    west, south, east, north = region.bbox
    anchors: list[tuple[float, float]] = []
    for feature in fire_features:
        longitude, latitude = feature["geometry"]["coordinates"]
        anchors.append((float(latitude), float(longitude)))
    anchors.extend(
        (float(prior["latitude"]), float(prior["longitude"]))
        for prior in priors_for_codes(active_region_codes)
    )
    anchors.extend(
        (float(place["latitude"]), float(place["longitude"]))
        for place in places_for_codes(active_region_codes)
    )

    cells: set[str] = set()
    disk_size = anchor_disk_size(resolution)
    for latitude, longitude in anchors:
        if not (west <= longitude <= east and south <= latitude <= north):
            continue
        origin = h3.latlng_to_cell(latitude, longitude, resolution)
        for cell in h3.grid_disk(origin, disk_size):
            cell_latitude, cell_longitude = h3.cell_to_latlng(cell)
            if west <= cell_longitude <= east and south <= cell_latitude <= north:
                cells.add(cell)
    return sorted(cells)


def regional_sampled_cells(
    *,
    region: RegionConfig,
    resolution: int,
    active_region_codes: set[str],
) -> list[str]:
    if region.code == "southwest":
        cells: set[str] = set()
        for code in STATE_REGION_CODES:
            cells.update(sampled_h3_cells(REGIONS[code].bbox, resolution))
        return sorted(cells)
    if region.code in STATE_REGION_CODES:
        return sampled_h3_cells(region.bbox, resolution)
    return sampled_h3_cells(region.bbox, resolution)


def active_codes_from_features(region: RegionConfig, fire_features: list[dict[str, Any]]) -> set[str]:
    if region.code == "southwest":
        return set(STATE_REGION_CODES)
    if region.code in STATE_REGION_CODES:
        return {region.code}
    states = {
        str(feature.get("properties", {}).get("state") or "").upper()
        for feature in fire_features
    }
    states = states.intersection(set(STATE_REGION_CODES))
    if states:
        return states
    return set()


def h3_cell_polygon(cell: str) -> dict[str, Any]:
    boundary = h3.cell_to_boundary(cell)
    longitudes = [longitude for latitude, longitude in boundary]
    latitudes = [latitude for latitude, longitude in boundary]
    west, east = min(longitudes), max(longitudes)
    south, north = min(latitudes), max(latitudes)
    coordinates = [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
    ]
    return {"type": "Polygon", "coordinates": [coordinates]}


def regional_historical_prior(
    *,
    latitude: float,
    longitude: float,
    region_code: str,
    active_region_codes: set[str],
) -> tuple[float, str | None]:
    score = 0.0
    nearest_county = None
    nearest_distance = float("inf")
    priors = priors_for_codes(active_region_codes) if active_region_codes else priors_for_region(region_code)
    for prior in priors:
        distance = haversine_km(latitude, longitude, float(prior["latitude"]), float(prior["longitude"]))
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_county = str(prior["county"])
        score += distance_weight(distance, decay_km=115) * float(prior["weight"])
    return clamp(score), nearest_county


def regional_exposure_proxy(
    *,
    latitude: float,
    longitude: float,
    region_code: str,
    active_region_codes: set[str],
) -> tuple[float, str | None]:
    score = 0.0
    nearest_county = None
    nearest_distance = float("inf")
    places = places_for_codes(active_region_codes) if active_region_codes else places_for_region(region_code)
    for place in places:
        distance = haversine_km(latitude, longitude, float(place["latitude"]), float(place["longitude"]))
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_county = str(place["county"])
        population_weight = min(float(place.get("population") or 0) / 1_500_000, 1)
        score += distance_weight(distance, decay_km=55) * population_weight
    return clamp(score), nearest_county


def driver_summary(properties: dict[str, Any]) -> str:
    drivers = sorted(
        [
            ("recent activity", properties["recent_activity"]),
            ("FRP intensity", properties["intensity"]),
            ("historical prior", properties["historical_prior"]),
            ("exposure proxy", properties["exposure_proxy"]),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    primary, value = drivers[0]
    return f"Primary driver: {primary} ({round(value * 100)}%)."


def build_h3_risk_grid(
    fire_features: list[dict[str, Any]],
    *,
    region: RegionConfig,
    h3_resolution: int = DEFAULT_H3_RESOLUTION,
    source: str = "unknown",
) -> dict[str, Any]:
    if h3_resolution not in ALLOWED_H3_RESOLUTIONS:
        raise ValueError("h3_resolution must be one of 4, 5, or 6")

    cells = []
    active_region_codes = active_codes_from_features(region, fire_features)
    anchor_cells = cells_around_anchors(
        fire_features=fire_features,
        region=region,
        resolution=h3_resolution,
        active_region_codes=active_region_codes,
    )
    regional_cells = regional_sampled_cells(
        region=region,
        resolution=h3_resolution,
        active_region_codes=active_region_codes,
    )
    candidate_cells = sorted(set(regional_cells).union(anchor_cells))
    for index, cell in enumerate(candidate_cells, start=1):
        latitude, longitude = h3.cell_to_latlng(cell)
        recent_activity, intensity, nearby_count = fire_metrics_for_cell(
            latitude=latitude,
            longitude=longitude,
            fire_features=fire_features,
        )
        historical_prior, prior_county = regional_historical_prior(
            latitude=latitude,
            longitude=longitude,
            region_code=region.code,
            active_region_codes=active_region_codes,
        )
        exposure_proxy, exposure_county = regional_exposure_proxy(
            latitude=latitude,
            longitude=longitude,
            region_code=region.code,
            active_region_codes=active_region_codes,
        )
        raw_score = (
            0.40 * recent_activity
            + 0.22 * intensity
            + 0.25 * historical_prior
            + 0.13 * exposure_proxy
        )
        score = round(raw_score * 100, 1)
        properties = {
            "id": f"h3-{index:04d}",
            "h3_cell": cell,
            "h3_resolution": h3_resolution,
            "display_geometry": "h3_cell_envelope_box",
            "region": region.code,
            "region_label": region.label,
            "risk_score": score,
            "risk_class": risk_class(score),
            "recent_activity": round(recent_activity, 3),
            "historical_prior": round(historical_prior, 3),
            "intensity": round(intensity, 3),
            "exposure_proxy": round(exposure_proxy, 3),
            "nearby_detection_count": nearby_count,
            "nearest_county": prior_county or exposure_county or "n/a",
            "model_version": H3_MODEL_VERSION,
        }
        properties["driver_summary"] = driver_summary(properties)
        cells.append({"type": "Feature", "geometry": h3_cell_polygon(cell), "properties": properties})

    cells.sort(key=lambda feature: feature["properties"]["risk_score"], reverse=True)
    return {
        "type": "FeatureCollection",
        "features": cells,
        "metadata": {
            "count": len(cells),
            "source": source,
            "region": region.code,
            "region_label": region.label,
            "h3_resolution": h3_resolution,
            "model_version": H3_MODEL_VERSION,
            "input_detection_count": len(fire_features),
            "active_region_codes": sorted(active_region_codes),
            "method": "h3_indexed_regional_grid_box_display",
            "top_counties": county_rankings(cells),
            "limitations": [
                "H3 risk is a screening layer, not an operational wildfire forecast.",
                "Non-Arizona regional priors and exposure proxies are deterministic portfolio fallbacks until state loaders are populated.",
                "Cells are generated as a sampled regional H3 grid and displayed as prominent boxes for map readability.",
            ],
        },
    }


def county_rankings(features: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for feature in features:
        county = feature["properties"].get("nearest_county")
        if county and county != "n/a":
            grouped[str(county)].append(float(feature["properties"].get("risk_score") or 0))
    ranked = [
        {
            "county": county,
            "max_risk_score": round(max(scores), 1),
            "avg_risk_score": round(sum(scores) / len(scores), 1),
            "cell_count": len(scores),
        }
        for county, scores in grouped.items()
    ]
    ranked.sort(key=lambda row: (row["max_risk_score"], row["avg_risk_score"]), reverse=True)
    return ranked[:limit]
