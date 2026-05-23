from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.exposure import load_county_exposure

MODEL_VERSION = "az-county-risk-intelligence-v0.1"


def normalize_county_name(value: str | None) -> str:
    return (value or "").replace(" County", "").strip()


def county_name(properties: dict[str, Any]) -> str:
    return str(properties.get("name") or properties.get("NAME") or "")


def county_geoid(properties: dict[str, Any]) -> str:
    return str(properties.get("geoid") or properties.get("GEOID") or "")


def polygon_contains(point: tuple[float, float], ring: list[list[float]]) -> bool:
    longitude, latitude = point
    inside = False
    if len(ring) < 3:
        return False
    previous_longitude, previous_latitude = ring[-1]
    for current_longitude, current_latitude in ring:
        intersects = (current_latitude > latitude) != (previous_latitude > latitude)
        if intersects:
            slope_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / ((previous_latitude - current_latitude) or 1e-12)
                + current_longitude
            )
            if longitude < slope_longitude:
                inside = not inside
        previous_longitude, previous_latitude = current_longitude, current_latitude
    return inside


def geometry_contains_point(geometry: dict[str, Any], point: tuple[float, float]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if geometry_type == "Polygon":
        return any(polygon_contains(point, ring) for ring in coordinates)
    if geometry_type == "MultiPolygon":
        return any(
            any(polygon_contains(point, ring) for ring in polygon)
            for polygon in coordinates
        )
    return False


def feature_centroid(feature: dict[str, Any]) -> tuple[float, float]:
    ring = feature["geometry"]["coordinates"][0]
    coordinates = ring[:-1] if len(ring) > 1 else ring
    longitude = sum(point[0] for point in coordinates) / max(len(coordinates), 1)
    latitude = sum(point[1] for point in coordinates) / max(len(coordinates), 1)
    return longitude, latitude


def top_driver(components: dict[str, float]) -> str:
    labels = {
        "risk": "risk grid",
        "detections": "active detections",
        "intensity": "FRP intensity",
        "exposure": "population exposure",
        "trend": "forecast trend",
    }
    key = max(components, key=components.get)
    return labels[key]


def trend_label(rising_cells: int, falling_cells: int) -> str:
    if rising_cells > falling_cells and rising_cells > 0:
        return "rising"
    if falling_cells > rising_cells and falling_cells > 0:
        return "falling"
    return "stable"


def build_az_risk_intelligence(
    *,
    fires: dict[str, Any],
    counties: dict[str, Any],
    risk_grid: dict[str, Any],
    forecast_grid: dict[str, Any],
    horizon_hours: int,
    requested_data_source: str,
) -> dict[str, Any]:
    exposure_by_county = {
        normalize_county_name(str(row.get("name"))): row for row in load_county_exposure()
    }
    county_features = counties.get("features", [])
    county_names = [
        normalize_county_name(county_name(feature.get("properties", {})))
        for feature in county_features
    ]

    detections = defaultdict(list)
    for fire in fires.get("features", []):
        name = normalize_county_name(str(fire.get("properties", {}).get("county") or ""))
        if name:
            detections[name].append(fire)

    forecast_by_id = {
        feature.get("properties", {}).get("id"): feature
        for feature in forecast_grid.get("features", [])
    }
    risk_by_county: dict[str, list[dict[str, Any]]] = {name: [] for name in county_names if name}
    forecast_by_county: dict[str, Counter] = {name: Counter() for name in county_names if name}

    for cell in risk_grid.get("features", []):
        centroid = feature_centroid(cell)
        matched_county = None
        for county in county_features:
            name = normalize_county_name(county_name(county.get("properties", {})))
            if name and geometry_contains_point(county.get("geometry", {}), centroid):
                matched_county = name
                break
        if not matched_county:
            continue
        risk_by_county.setdefault(matched_county, []).append(cell)
        forecast = forecast_by_id.get(cell.get("properties", {}).get("id"))
        if forecast:
            trend = str(forecast.get("properties", {}).get("trend") or "stable")
            forecast_by_county.setdefault(matched_county, Counter())[trend] += 1

    rows = []
    statewide_components = Counter()
    for county in county_features:
        properties = county.get("properties", {})
        name = normalize_county_name(county_name(properties))
        if not name:
            continue
        exposure = exposure_by_county.get(name, {})
        county_detections = detections.get(name, [])
        county_cells = risk_by_county.get(name, [])
        trend_counts = forecast_by_county.get(name, Counter())
        scores = [float(cell["properties"].get("risk_score") or 0) for cell in county_cells]
        max_risk = round(max(scores), 1) if scores else 0.0
        avg_risk = round(sum(scores) / len(scores), 1) if scores else 0.0
        high_extreme_cells = sum(1 for score in scores if score >= 55)
        frps = [float(fire["properties"].get("frp_mw") or 0) for fire in county_detections]
        confidences = [float(fire["properties"].get("confidence") or 0) for fire in county_detections]
        max_frp = round(max(frps), 1) if frps else 0.0
        avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0
        population = int(exposure.get("population") or 0)
        households = int(exposure.get("households") or 0)
        components = {
            "risk": (max_risk / 100 * 35) + (avg_risk / 100 * 15),
            "detections": min(len(county_detections) / 5, 1) * 20,
            "intensity": min(max_frp / 30, 1) * 10,
            "exposure": min(population / 1_000_000, 1) * 10,
            "trend": min(trend_counts.get("rising", 0) / 10, 1) * 10,
        }
        driver = top_driver(components)
        statewide_components.update({driver: 1})
        risk_score = round(sum(components.values()), 1)
        rows.append(
            {
                "county": f"{name} County",
                "county_name": name,
                "geoid": county_geoid(properties),
                "risk_score": risk_score,
                "risk_class": risk_class_for_county(risk_score),
                "rank_components": {key: round(value, 1) for key, value in components.items()},
                "detection_count": len(county_detections),
                "max_frp_mw": max_frp,
                "avg_confidence": avg_confidence,
                "population": population,
                "households": households,
                "max_risk_score": max_risk,
                "avg_risk_score": avg_risk,
                "high_extreme_cell_count": high_extreme_cells,
                "forecast_trend": trend_label(trend_counts.get("rising", 0), trend_counts.get("falling", 0)),
                "forecast_trend_counts": {
                    "rising": trend_counts.get("rising", 0),
                    "stable": trend_counts.get("stable", 0),
                    "falling": trend_counts.get("falling", 0),
                },
                "top_driver": driver,
                "caveat": "County score is a transparent dashboard ranking, not an operational prediction.",
            }
        )

    rows.sort(
        key=lambda row: (
            row["risk_score"],
            row["detection_count"],
            row["max_risk_score"],
            row["population"],
        ),
        reverse=True,
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    top_cells = []
    for cell in sorted(
        risk_grid.get("features", []),
        key=lambda feature: feature["properties"].get("risk_score", 0),
        reverse=True,
    )[:8]:
        properties = cell["properties"]
        drivers = {
            "recent activity": float(properties.get("recent_activity") or 0),
            "FRP intensity": float(properties.get("intensity") or 0),
            "historical prior": float(properties.get("historical_prior") or 0),
            "exposure proxy": float(properties.get("exposure_proxy") or 0),
        }
        top_cells.append(
            {
                "id": properties["id"],
                "risk_score": properties["risk_score"],
                "risk_class": properties["risk_class"],
                "nearby_detection_count": properties["nearby_detection_count"],
                "top_driver": max(drivers, key=drivers.get),
                "drivers": {key: round(value, 3) for key, value in drivers.items()},
            }
        )

    high_extreme_cells = sum(
        1 for feature in risk_grid.get("features", [])
        if float(feature["properties"].get("risk_score") or 0) >= 55
    )
    trend_counts = forecast_grid.get("metadata", {}).get("trend_counts", {})
    highest_risk_county = rows[0] if rows else None
    main_driver = statewide_components.most_common(1)[0][0] if statewide_components else "n/a"

    return {
        "model_version": MODEL_VERSION,
        "region": "AZ",
        "horizon_hours": horizon_hours,
        "summary": {
            "active_detection_count": len(fires.get("features", [])),
            "county_count": len(rows),
            "high_extreme_cell_count": high_extreme_cells,
            "rising_forecast_cell_count": int(trend_counts.get("rising", 0) or 0),
            "highest_risk_county": highest_risk_county["county"] if highest_risk_county else None,
            "highest_risk_score": highest_risk_county["risk_score"] if highest_risk_county else 0,
            "main_driver": main_driver,
        },
        "county_rankings": rows,
        "top_risk_cells": top_cells,
        "driver_breakdown": dict(statewide_components),
        "data_sources": {
            "fires": fires.get("metadata", {}).get("source", "unknown"),
            "counties": counties.get("metadata", {}).get("source", "unknown"),
            "risk_grid": risk_grid.get("metadata", {}).get("source", "unknown"),
            "forecast": forecast_grid.get("metadata", {}).get("source", "unknown"),
            "exposure": "sample_county_exposure",
            "requested_data_source": requested_data_source,
        },
        "caveats": [
            "County rankings are dashboard intelligence scores, not operational fire-spread predictions.",
            "FIRMS detections are hotspots and may include false positives or duplicate thermal observations.",
            "Exposure is county-level screening context unless richer ACS/tract data is loaded.",
            "Forecast trend is a transparent baseline using risk-grid features, not a validated spread model.",
        ],
    }


def risk_class_for_county(score: float) -> str:
    if score >= 70:
        return "extreme"
    if score >= 45:
        return "high"
    if score >= 20:
        return "moderate"
    return "low"
