from __future__ import annotations

from typing import Any

from app.risk import risk_class

VALID_FORECAST_HORIZONS = {24, 48, 72}
FORECAST_MODEL_VERSION = "baseline-risk-forecast-v0.1"


def forecast_weights(horizon_hours: int) -> dict[str, float]:
    if horizon_hours == 24:
        return {"recent_activity": 0.45, "intensity": 0.25, "historical_prior": 0.20, "exposure_proxy": 0.10}
    if horizon_hours == 48:
        return {"recent_activity": 0.38, "intensity": 0.22, "historical_prior": 0.25, "exposure_proxy": 0.15}
    return {"recent_activity": 0.32, "intensity": 0.18, "historical_prior": 0.30, "exposure_proxy": 0.20}


def recency_decay(horizon_hours: int, intensity: float) -> float:
    base_decay = {24: 0.86, 48: 0.72, 72: 0.58}[horizon_hours]
    return min(0.96, base_decay + intensity * (1 - base_decay) * 0.45)


def trend_from_delta(delta: float) -> str:
    if delta >= 3:
        return "rising"
    if delta <= -3:
        return "falling"
    return "stable"


def driver_summary(properties: dict[str, Any], trend: str) -> str:
    drivers = sorted(
        [
            ("recent FIRMS activity", properties["recent_activity"]),
            ("FRP intensity", properties["intensity"]),
            ("historical prior", properties["historical_prior"]),
            ("exposure proxy", properties["exposure_proxy"]),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    primary = drivers[0][0]
    secondary = drivers[1][0]
    return f"{trend.title()} baseline driven by {primary} and {secondary}."


def forecast_feature(feature: dict[str, Any], *, horizon_hours: int) -> dict[str, Any]:
    properties = feature["properties"]
    weights = forecast_weights(horizon_hours)
    intensity = float(properties["intensity"])
    recent_decay = recency_decay(horizon_hours, intensity)
    recent_forecast = float(properties["recent_activity"]) * recent_decay
    intensity_forecast = intensity * (0.72 + recent_decay * 0.28)
    score_now = float(properties["risk_score"])
    score_forecast = round(
        100
        * (
            weights["recent_activity"] * recent_forecast
            + weights["intensity"] * intensity_forecast
            + weights["historical_prior"] * float(properties["historical_prior"])
            + weights["exposure_proxy"] * float(properties["exposure_proxy"])
        ),
        1,
    )
    delta = round(score_forecast - score_now, 1)
    trend = trend_from_delta(delta)
    forecast_properties = {
        **properties,
        "risk_score_now": score_now,
        "risk_score_forecast": score_forecast,
        "risk_delta": delta,
        "trend": trend,
        "risk_class_forecast": risk_class(score_forecast),
        "forecast_horizon_hours": horizon_hours,
        "forecast_model_version": FORECAST_MODEL_VERSION,
        "driver_summary": driver_summary(properties, trend),
    }
    return {**feature, "properties": forecast_properties}


def build_forecast_grid(risk_grid: dict[str, Any], *, horizon_hours: int) -> dict[str, Any]:
    features = [
        forecast_feature(feature, horizon_hours=horizon_hours)
        for feature in risk_grid.get("features", [])
    ]
    rising = sum(1 for feature in features if feature["properties"]["trend"] == "rising")
    falling = sum(1 for feature in features if feature["properties"]["trend"] == "falling")
    stable = len(features) - rising - falling
    features.sort(key=lambda feature: feature["properties"]["risk_delta"], reverse=True)
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "source": risk_grid.get("metadata", {}).get("source", "unknown"),
            "base_model_version": risk_grid.get("metadata", {}).get("model_version"),
            "forecast_model_version": FORECAST_MODEL_VERSION,
            "horizon_hours": horizon_hours,
            "trend_counts": {"rising": rising, "stable": stable, "falling": falling},
            "method": "transparent_decay_and_weight_shift_baseline",
            "limitations": [
                "Forecast is a trend baseline, not a validated fire-spread prediction.",
                "Recent detections decay over time while historical and exposure proxies remain stable.",
                "Weather forecast variables are not yet included in the grid forecast.",
            ],
        },
    }
