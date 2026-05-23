from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.data import BBox


@dataclass(frozen=True)
class RegionConfig:
    code: str
    label: str
    fips: tuple[str, ...]
    bbox: BBox
    center: tuple[float, float]
    zoom: float


REGIONS: dict[str, RegionConfig] = {
    "AZ": RegionConfig("AZ", "Arizona", ("04",), (-115.1, 31.2, -108.8, 37.1), (-111.8, 34.3), 5.7),
    "CA": RegionConfig("CA", "California", ("06",), (-124.5, 32.5, -114.1, 42.1), (-119.6, 37.2), 4.8),
    "NV": RegionConfig("NV", "Nevada", ("32",), (-120.1, 35.0, -114.0, 42.1), (-117.1, 38.7), 5.2),
    "NM": RegionConfig("NM", "New Mexico", ("35",), (-109.1, 31.3, -103.0, 37.1), (-106.0, 34.5), 5.4),
    "TX": RegionConfig("TX", "Texas", ("48",), (-106.7, 25.8, -93.5, 36.6), (-99.3, 31.2), 4.5),
    "CO": RegionConfig("CO", "Colorado", ("08",), (-109.1, 36.9, -102.0, 41.1), (-105.6, 39.0), 5.4),
    "southwest": RegionConfig(
        "southwest",
        "Southwest",
        ("04", "06", "32", "35", "48", "08"),
        (-124.5, 25.8, -93.5, 42.1),
        (-109.0, 34.5),
        4.0,
    ),
}

STATE_REGION_CODES = ("AZ", "CA", "NV", "NM", "TX", "CO")

REGIONAL_PRIORS: list[dict[str, Any]] = [
    {"region": "AZ", "county": "Coconino", "latitude": 35.2, "longitude": -111.6, "weight": 0.82},
    {"region": "AZ", "county": "Yavapai", "latitude": 34.55, "longitude": -112.55, "weight": 0.72},
    {"region": "CA", "county": "Los Angeles", "latitude": 34.25, "longitude": -118.35, "weight": 0.86},
    {"region": "CA", "county": "Butte", "latitude": 39.7, "longitude": -121.7, "weight": 0.82},
    {"region": "CA", "county": "Riverside", "latitude": 33.75, "longitude": -116.3, "weight": 0.74},
    {"region": "NV", "county": "Washoe", "latitude": 39.55, "longitude": -119.8, "weight": 0.66},
    {"region": "NV", "county": "Clark", "latitude": 36.15, "longitude": -115.1, "weight": 0.48},
    {"region": "NM", "county": "San Miguel", "latitude": 35.55, "longitude": -105.3, "weight": 0.76},
    {"region": "NM", "county": "Lincoln", "latitude": 33.75, "longitude": -105.65, "weight": 0.68},
    {"region": "TX", "county": "Travis", "latitude": 30.25, "longitude": -97.75, "weight": 0.52},
    {"region": "TX", "county": "Potter", "latitude": 35.25, "longitude": -101.8, "weight": 0.58},
    {"region": "CO", "county": "Boulder", "latitude": 40.02, "longitude": -105.25, "weight": 0.7},
    {"region": "CO", "county": "Larimer", "latitude": 40.6, "longitude": -105.35, "weight": 0.72},
]

REGIONAL_PLACES: list[dict[str, Any]] = [
    {"region": "AZ", "county": "Maricopa", "name": "Phoenix", "latitude": 33.45, "longitude": -112.07, "population": 1_650_000},
    {"region": "AZ", "county": "Pima", "name": "Tucson", "latitude": 32.22, "longitude": -110.97, "population": 550_000},
    {"region": "CA", "county": "Los Angeles", "name": "Los Angeles", "latitude": 34.05, "longitude": -118.24, "population": 3_820_000},
    {"region": "CA", "county": "San Diego", "name": "San Diego", "latitude": 32.72, "longitude": -117.16, "population": 1_380_000},
    {"region": "CA", "county": "Sacramento", "name": "Sacramento", "latitude": 38.58, "longitude": -121.49, "population": 525_000},
    {"region": "NV", "county": "Clark", "name": "Las Vegas", "latitude": 36.17, "longitude": -115.14, "population": 650_000},
    {"region": "NV", "county": "Washoe", "name": "Reno", "latitude": 39.53, "longitude": -119.81, "population": 275_000},
    {"region": "NM", "county": "Bernalillo", "name": "Albuquerque", "latitude": 35.08, "longitude": -106.65, "population": 560_000},
    {"region": "NM", "county": "Santa Fe", "name": "Santa Fe", "latitude": 35.69, "longitude": -105.94, "population": 90_000},
    {"region": "TX", "county": "Harris", "name": "Houston", "latitude": 29.76, "longitude": -95.37, "population": 2_300_000},
    {"region": "TX", "county": "Travis", "name": "Austin", "latitude": 30.27, "longitude": -97.74, "population": 980_000},
    {"region": "TX", "county": "Dallas", "name": "Dallas", "latitude": 32.78, "longitude": -96.8, "population": 1_300_000},
    {"region": "CO", "county": "Denver", "name": "Denver", "latitude": 39.74, "longitude": -104.99, "population": 715_000},
    {"region": "CO", "county": "El Paso", "name": "Colorado Springs", "latitude": 38.83, "longitude": -104.82, "population": 490_000},
]


def normalize_region_code(region: str | None) -> str:
    code = (region or "AZ").strip()
    if code.lower() == "southwest":
        return "southwest"
    return code.upper()


def get_region(region: str | None) -> RegionConfig:
    code = normalize_region_code(region)
    if code not in REGIONS:
        raise ValueError("region must be one of AZ,CA,NV,NM,TX,CO,southwest")
    return REGIONS[code]


def region_to_dict(region: RegionConfig) -> dict[str, Any]:
    return {
        "code": region.code,
        "label": region.label,
        "fips": list(region.fips),
        "bbox": list(region.bbox),
        "center": {"longitude": region.center[0], "latitude": region.center[1]},
        "zoom": region.zoom,
    }


def list_regions() -> dict[str, Any]:
    return {
        "regions": [region_to_dict(REGIONS[code]) for code in (*STATE_REGION_CODES, "southwest")],
        "default_region": "AZ",
    }


def region_codes_for(region_code: str) -> set[str]:
    if region_code == "southwest":
        return set(STATE_REGION_CODES)
    return {region_code}


def priors_for_region(region_code: str) -> list[dict[str, Any]]:
    codes = region_codes_for(region_code)
    return [prior for prior in REGIONAL_PRIORS if prior["region"] in codes]


def places_for_region(region_code: str) -> list[dict[str, Any]]:
    codes = region_codes_for(region_code)
    return [place for place in REGIONAL_PLACES if place["region"] in codes]


def priors_for_codes(codes: set[str]) -> list[dict[str, Any]]:
    return [prior for prior in REGIONAL_PRIORS if prior["region"] in codes]


def places_for_codes(codes: set[str]) -> list[dict[str, Any]]:
    return [place for place in REGIONAL_PLACES if place["region"] in codes]
