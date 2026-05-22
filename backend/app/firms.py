from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

FeatureCollection = dict[str, Any]
BBox = tuple[float, float, float, float]

ARIZONA_BBOX: BBox = (-115.1, 31.2, -108.8, 37.1)
DEFAULT_FIRMS_SOURCE = "VIIRS_SNPP_NRT"
FIRMS_AREA_API_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_SOURCE_OPTIONS = (
    "MODIS_NRT",
    "MODIS_SP",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_NRT",
    "VIIRS_SNPP_NRT",
    "VIIRS_SNPP_SP",
)

CONFIDENCE_SCORES = {
    "l": 30,
    "low": 30,
    "n": 60,
    "nominal": 60,
    "h": 90,
    "high": 90,
}


class FirmsIngestionError(RuntimeError):
    """Raised when FIRMS data cannot be downloaded or normalized."""


def bbox_to_api_value(bbox: BBox) -> str:
    return ",".join(f"{coordinate:g}" for coordinate in bbox)


def parse_bbox_value(value: str) -> BBox:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must contain west,south,east,north")

    west, south, east, north = (float(part) for part in parts)
    if west >= east or south >= north:
        raise ValueError("bbox bounds must be ordered as west,south,east,north")

    return west, south, east, north


def build_firms_area_url(
    *,
    map_key: str,
    source: str,
    bbox: BBox = ARIZONA_BBOX,
    day_range: int = 3,
    date: str | None = None,
) -> str:
    if source not in FIRMS_SOURCE_OPTIONS:
        raise ValueError(f"unsupported FIRMS source: {source}")
    if day_range < 1 or day_range > 5:
        raise ValueError("day_range must be between 1 and 5")

    bbox_value = quote(bbox_to_api_value(bbox), safe=",")
    url = f"{FIRMS_AREA_API_BASE_URL}/{map_key}/{source}/{bbox_value}/{day_range}"

    if date:
        datetime.strptime(date, "%Y-%m-%d")
        url = f"{url}/{date}"

    return url


def download_firms_csv(
    *,
    map_key: str,
    source: str = DEFAULT_FIRMS_SOURCE,
    bbox: BBox = ARIZONA_BBOX,
    day_range: int = 3,
    date: str | None = None,
    timeout_seconds: int = 30,
) -> tuple[str, str]:
    url = build_firms_area_url(
        map_key=map_key,
        source=source,
        bbox=bbox,
        day_range=day_range,
        date=date,
    )
    request = Request(url, headers={"User-Agent": "wildfire-geoai/0.1"})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except OSError as error:
        raise FirmsIngestionError(f"failed to download FIRMS data: {error}") from error

    if not body.strip():
        raise FirmsIngestionError("FIRMS returned an empty response")
    if body.lstrip().startswith("<"):
        raise FirmsIngestionError("FIRMS returned HTML instead of CSV")
    if "," not in body.splitlines()[0]:
        raise FirmsIngestionError(body.strip().splitlines()[0])

    return body, url


def confidence_to_score(value: str | int | float | None) -> tuple[int, str]:
    if value is None:
        return 0, "unknown"

    text = str(value).strip()
    if not text:
        return 0, "unknown"

    try:
        numeric = int(float(text))
        return max(0, min(100, numeric)), text
    except ValueError:
        score = CONFIDENCE_SCORES.get(text.lower(), 0)
        return score, text


def parse_acq_datetime(acq_date: str, acq_time: str) -> str:
    padded_time = str(acq_time).strip().zfill(4)
    detected_at = datetime.strptime(f"{acq_date} {padded_time}", "%Y-%m-%d %H%M")
    return detected_at.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def parse_float(row: dict[str, str], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return float(value)
    return default


def stable_detection_id(
    *,
    source: str,
    latitude: float,
    longitude: float,
    acq_datetime: str,
    satellite: str,
    instrument: str,
) -> str:
    fingerprint = "|".join(
        [
            source,
            f"{latitude:.5f}",
            f"{longitude:.5f}",
            acq_datetime,
            satellite,
            instrument,
        ]
    )
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"firms-{digest}"


def normalize_firms_row(row: dict[str, str], *, source: str, state: str = "AZ") -> dict[str, Any]:
    latitude = parse_float(row, "latitude", "lat")
    longitude = parse_float(row, "longitude", "lon")
    acq_date = row["acq_date"].strip()
    acq_time = row["acq_time"].strip().zfill(4)
    acq_datetime = parse_acq_datetime(acq_date, acq_time)
    confidence, confidence_label = confidence_to_score(row.get("confidence"))
    brightness = parse_float(row, "bright_ti4", "brightness", "bright_t31", "bright_ti5")
    frp = parse_float(row, "frp")
    satellite = row.get("satellite", "").strip()
    instrument = row.get("instrument", "").strip()

    detection_id = stable_detection_id(
        source=source,
        latitude=latitude,
        longitude=longitude,
        acq_datetime=acq_datetime,
        satellite=satellite,
        instrument=instrument,
    )

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "id": detection_id,
            "source": source,
            "state": state,
            "county": row.get("county", "Unknown"),
            "area_label": "Live FIRMS detection",
            "latitude": latitude,
            "longitude": longitude,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "brightness_kelvin": brightness,
            "satellite": satellite,
            "instrument": instrument,
            "acq_date": acq_date,
            "acq_time": acq_time,
            "acq_datetime": acq_datetime,
            "frp_mw": frp,
            "daynight": row.get("daynight", "").strip(),
            "version": row.get("version", "").strip(),
            "sample": False,
        },
    }


def dedupe_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []

    for feature in features:
        properties = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"]
        key = (
            properties["source"],
            properties["acq_datetime"],
            round(latitude, 5),
            round(longitude, 5),
            properties.get("satellite", ""),
            properties.get("instrument", ""),
        )
        if key in seen:
            continue

        seen.add(key)
        deduped.append(feature)

    return deduped


def normalize_firms_csv(csv_text: str, *, source: str, state: str = "AZ") -> FeatureCollection:
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames:
        raise FirmsIngestionError("FIRMS CSV is missing a header row")

    required = {"latitude", "longitude", "acq_date", "acq_time"}
    missing = required.difference(reader.fieldnames)
    if missing:
        raise FirmsIngestionError(f"FIRMS CSV is missing required columns: {sorted(missing)}")

    features = [normalize_firms_row(row, source=source, state=state) for row in reader]
    features = dedupe_features(features)
    features.sort(key=lambda feature: feature["properties"]["acq_datetime"], reverse=True)

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "source": "nasa_firms_area_api",
            "firms_source": source,
            "normalized_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    }


def write_json(path: Path, payload: FeatureCollection) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
