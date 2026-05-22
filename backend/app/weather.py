from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.data import PROJECT_ROOT

NWS_BASE_URL = "https://api.weather.gov"
WEATHER_CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "weather"
DEFAULT_USER_AGENT = "wildfire-geoai/0.1 (local portfolio project)"
CACHE_TTL = timedelta(minutes=30)


class WeatherUnavailable(RuntimeError):
    """Raised when NWS data cannot be fetched or parsed."""


def nws_user_agent() -> str:
    return os.getenv("NWS_USER_AGENT", DEFAULT_USER_AGENT)


def cache_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.3f}_{longitude:.3f}".replace("-", "m").replace(".", "p")


def read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(payload["cached_at"].replace("Z", "+00:00"))
    if datetime.now(UTC) - cached_at > CACHE_TTL:
        return None
    return payload["data"]


def write_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data": data,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fetch_json(url: str, *, timeout_seconds: int = 20) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": nws_user_agent(),
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WeatherUnavailable(f"failed to fetch NWS data from {url}: {error}") from error


def mph_to_number(value: str | None) -> float | None:
    if not value:
        return None
    numbers = []
    for token in value.replace("to", " ").replace("mph", " ").split():
        try:
            numbers.append(float(token))
        except ValueError:
            continue
    if not numbers:
        return None
    return max(numbers)


def extract_forecast_summary(point_data: dict[str, Any], hourly_data: dict[str, Any]) -> dict[str, Any]:
    properties = point_data.get("properties", {})
    periods = hourly_data.get("properties", {}).get("periods", [])
    next_period = periods[0] if periods else {}
    next_12_hours = periods[:12]

    temperatures = [
        period.get("temperature")
        for period in next_12_hours
        if isinstance(period.get("temperature"), (int, float))
    ]
    wind_speeds = [mph_to_number(period.get("windSpeed")) for period in next_12_hours]
    wind_speeds = [speed for speed in wind_speeds if speed is not None]
    precip_values = [
        period.get("probabilityOfPrecipitation", {}).get("value")
        for period in next_12_hours
        if period.get("probabilityOfPrecipitation", {}).get("value") is not None
    ]

    return {
        "source": "NWS API",
        "grid_id": properties.get("gridId"),
        "grid_x": properties.get("gridX"),
        "grid_y": properties.get("gridY"),
        "forecast_office": properties.get("cwa"),
        "forecast_zone": properties.get("forecastZone"),
        "fire_weather_zone": properties.get("fireWeatherZone"),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "current_period": {
            "name": next_period.get("name"),
            "start_time": next_period.get("startTime"),
            "temperature": next_period.get("temperature"),
            "temperature_unit": next_period.get("temperatureUnit"),
            "wind_speed": next_period.get("windSpeed"),
            "wind_direction": next_period.get("windDirection"),
            "short_forecast": next_period.get("shortForecast"),
        },
        "next_12h": {
            "max_temperature": max(temperatures) if temperatures else None,
            "min_temperature": min(temperatures) if temperatures else None,
            "max_wind_speed_mph": max(wind_speeds) if wind_speeds else None,
            "max_precip_probability": max(precip_values) if precip_values else None,
        },
        "operational_flags": weather_flags(temperatures, wind_speeds, precip_values),
    }


def weather_flags(
    temperatures: list[int | float],
    wind_speeds: list[float],
    precip_values: list[int | float],
) -> list[str]:
    flags = []
    if temperatures and max(temperatures) >= 95:
        flags.append("High heat may increase responder fatigue and drying conditions.")
    if wind_speeds and max(wind_speeds) >= 20:
        flags.append("Elevated wind could support faster spread or spotting.")
    if precip_values and max(precip_values) >= 40:
        flags.append("Meaningful precipitation is possible in the next 12 hours.")
    if not flags:
        flags.append("No major temperature, wind, or precipitation flags in the next 12 hours.")
    return flags


def get_weather_context(latitude: float, longitude: float) -> dict[str, Any]:
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise WeatherUnavailable("invalid latitude/longitude")

    path = WEATHER_CACHE_DIR / f"{cache_key(latitude, longitude)}.json"
    cached = read_cache(path)
    if cached:
        return cached

    point_data = fetch_json(f"{NWS_BASE_URL}/points/{latitude:.4f},{longitude:.4f}")
    hourly_url = point_data.get("properties", {}).get("forecastHourly")
    if not hourly_url:
        raise WeatherUnavailable("NWS point response did not include forecastHourly")

    hourly_data = fetch_json(hourly_url)
    context = extract_forecast_summary(point_data, hourly_data)
    write_cache(path, context)
    return context


def unavailable_weather_context(message: str) -> dict[str, Any]:
    return {
        "source": "NWS API",
        "unavailable": True,
        "message": message,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "current_period": None,
        "next_12h": None,
        "operational_flags": ["Weather context unavailable; retry later."],
    }
