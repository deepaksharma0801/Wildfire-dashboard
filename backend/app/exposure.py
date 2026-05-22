from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from app.data import PROJECT_ROOT, BBox, FeatureCollection, filter_fire_features, load_fire_collection
from app.weather import WeatherUnavailable, get_weather_context, unavailable_weather_context

COUNTY_EXPOSURE_PATH = PROJECT_ROOT / "data" / "sample" / "arizona_county_exposure_sample.json"
PLACES_PATH = PROJECT_ROOT / "data" / "sample" / "arizona_places_sample.json"
EARTH_RADIUS_KM = 6371.0088


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_county_exposure() -> list[dict[str, Any]]:
    return load_json(COUNTY_EXPOSURE_PATH)


def load_places() -> list[dict[str, Any]]:
    return load_json(PLACES_PATH)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def feature_timestamp(feature: dict[str, Any]) -> datetime:
    raw_value = feature["properties"]["acq_datetime"]
    return datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))


def stable_cluster_id(features: list[dict[str, Any]]) -> str:
    ids = sorted(str(feature["properties"]["id"]) for feature in features)
    digest = hashlib.sha1("|".join(ids).encode("utf-8")).hexdigest()[:12]
    return f"cluster-{digest}"


def cluster_fire_features(
    features: list[dict[str, Any]],
    *,
    radius_km: float = 25,
) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []

    for feature in sorted(features, key=feature_timestamp, reverse=True):
        longitude, latitude = feature["geometry"]["coordinates"]
        matched_cluster: list[dict[str, Any]] | None = None

        for cluster in clusters:
            centroid_lon, centroid_lat = cluster_centroid(cluster)
            if haversine_km(latitude, longitude, centroid_lat, centroid_lon) <= radius_km:
                matched_cluster = cluster
                break

        if matched_cluster is None:
            clusters.append([feature])
        else:
            matched_cluster.append(feature)

    return [cluster_to_feature(cluster, radius_km=radius_km) for cluster in clusters]


def cluster_centroid(features: list[dict[str, Any]]) -> tuple[float, float]:
    longitude_total = 0.0
    latitude_total = 0.0
    for feature in features:
        longitude, latitude = feature["geometry"]["coordinates"]
        longitude_total += longitude
        latitude_total += latitude
    return longitude_total / len(features), latitude_total / len(features)


def cluster_to_feature(features: list[dict[str, Any]], *, radius_km: float) -> dict[str, Any]:
    longitude, latitude = cluster_centroid(features)
    timestamps = [feature_timestamp(feature) for feature in features]
    confidences = [int(feature["properties"].get("confidence", 0)) for feature in features]
    frps = [float(feature["properties"].get("frp_mw") or 0) for feature in features]
    counties = sorted(
        {
            str(feature["properties"].get("county"))
            for feature in features
            if feature["properties"].get("county")
            and str(feature["properties"].get("county")).lower() != "unknown"
        }
    )

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "id": stable_cluster_id(features),
            "detection_count": len(features),
            "time_start": min(timestamps).isoformat().replace("+00:00", "Z"),
            "time_end": max(timestamps).isoformat().replace("+00:00", "Z"),
            "avg_confidence": round(sum(confidences) / len(confidences), 1),
            "max_frp_mw": round(max(frps), 2),
            "radius_km": radius_km,
            "counties": counties,
            "detection_ids": [feature["properties"]["id"] for feature in features],
            "source": "file_cluster",
        },
    }


def get_filtered_fire_features(
    *,
    data_source: str,
    start_date,
    end_date,
    bbox: BBox | None,
    min_confidence: int,
) -> tuple[list[dict[str, Any]], str]:
    collection, resolved_source = load_fire_collection(data_source)
    return (
        filter_fire_features(
            collection,
            start_date=start_date,
            end_date=end_date,
            bbox=bbox,
            min_confidence=min_confidence,
        ),
        resolved_source,
    )


def get_cluster_collection(
    *,
    data_source: str,
    start_date=None,
    end_date=None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    radius_km: float = 25,
) -> FeatureCollection:
    features, resolved_source = get_filtered_fire_features(
        data_source=data_source,
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
    )
    clusters = cluster_fire_features(features, radius_km=radius_km)

    return {
        "type": "FeatureCollection",
        "features": clusters,
        "metadata": {
            "count": len(clusters),
            "source": resolved_source,
            "cluster_method": "distance_connected_components",
            "radius_km": radius_km,
        },
    }


def nearest_places(latitude: float, longitude: float, *, limit: int = 5) -> list[dict[str, Any]]:
    ranked = []
    for place in load_places():
        distance_km = haversine_km(latitude, longitude, float(place["latitude"]), float(place["longitude"]))
        ranked.append({**place, "distance_km": round(distance_km, 1)})
    ranked.sort(key=lambda place: place["distance_km"])
    return ranked[:limit]


def county_exposure_for_names(counties: list[str]) -> list[dict[str, Any]]:
    normalized = {county.replace(" County", "").strip().lower() for county in counties}
    rows = []
    for row in load_county_exposure():
        county_name = str(row["name"]).replace(" County", "").strip().lower()
        if county_name in normalized:
            rows.append(row)
    return rows


def summarize_cluster(cluster: dict[str, Any], *, radius_km: float) -> dict[str, Any]:
    properties = cluster["properties"]
    longitude, latitude = cluster["geometry"]["coordinates"]
    county_rows = county_exposure_for_names(properties.get("counties", []))
    population = sum(int(row.get("population", 0)) for row in county_rows)
    households = sum(int(row.get("households", 0)) for row in county_rows)

    try:
        weather = get_weather_context(latitude, longitude)
    except WeatherUnavailable as error:
        weather = unavailable_weather_context(str(error))

    return {
        "id": properties["id"],
        "source": "file_summary",
        "center": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius_km,
        "detection_count": properties["detection_count"],
        "time_start": properties["time_start"],
        "time_end": properties["time_end"],
        "avg_confidence": properties["avg_confidence"],
        "max_frp_mw": properties["max_frp_mw"],
        "affected_counties": county_rows,
        "estimated_population_exposed": population,
        "estimated_households_exposed": households,
        "nearby_places": nearest_places(latitude, longitude),
        "weather": weather,
        "data_caveats": [
            "Exposure is county-level in file mode and should be treated as screening context.",
            "FIRMS detections are hotspots, not official fire perimeters.",
        ],
    }


def get_incident_summary(
    incident_id: str,
    *,
    data_source: str,
    start_date=None,
    end_date=None,
    bbox: BBox | None = None,
    min_confidence: int = 0,
    radius_km: float = 25,
) -> dict[str, Any] | None:
    collection = get_cluster_collection(
        data_source=data_source,
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        min_confidence=min_confidence,
        radius_km=radius_km,
    )
    for cluster in collection["features"]:
        if cluster["properties"]["id"] == incident_id:
            return summarize_cluster(cluster, radius_km=radius_km)
    return None
