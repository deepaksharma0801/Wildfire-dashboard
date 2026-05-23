from __future__ import annotations

from typing import Any

from app.h3_risk import county_rankings
from app.risk import risk_class

SIMULATION_MODEL_VERSION = "what-if-risk-scenario-v0.1"


def adjusted_score(
    properties: dict[str, Any],
    *,
    temperature_delta_c: float,
    drought_multiplier: float,
    wind_multiplier: float,
) -> float:
    recent = float(properties.get("recent_activity") or 0)
    intensity = min(float(properties.get("intensity") or 0) * wind_multiplier, 1)
    prior = min(float(properties.get("historical_prior") or 0) * drought_multiplier, 1)
    exposure = float(properties.get("exposure_proxy") or 0)
    temperature_factor = max(-0.12, min(0.24, temperature_delta_c * 0.035))
    score = (0.34 * recent + 0.25 * intensity + 0.28 * prior + 0.13 * exposure + temperature_factor) * 100
    return round(max(0, min(100, score)), 1)


def build_risk_scenario(
    risk_grid: dict[str, Any],
    *,
    region: str,
    h3_resolution: int,
    horizon_hours: int,
    temperature_delta_c: float,
    drought_multiplier: float,
    wind_multiplier: float,
) -> dict[str, Any]:
    scenario = {
        "region": region,
        "h3_resolution": h3_resolution,
        "horizon_hours": horizon_hours,
        "temperature_delta_c": temperature_delta_c,
        "drought_multiplier": drought_multiplier,
        "wind_multiplier": wind_multiplier,
        "model_version": SIMULATION_MODEL_VERSION,
    }
    features = []
    for feature in risk_grid.get("features", []):
        properties = feature["properties"]
        base_score = float(properties.get("risk_score") or 0)
        scenario_score = adjusted_score(
            properties,
            temperature_delta_c=temperature_delta_c,
            drought_multiplier=drought_multiplier,
            wind_multiplier=wind_multiplier,
        )
        delta = round(scenario_score - base_score, 1)
        scenario_properties = {
            **properties,
            "base_risk_score": base_score,
            "scenario_risk_score": scenario_score,
            "scenario_delta": delta,
            "risk_score": scenario_score,
            "risk_class": risk_class(scenario_score),
            "scenario_driver_summary": (
                f"Delta {delta:+.1f}: temperature {temperature_delta_c:+.1f}C, "
                f"drought x{drought_multiplier:.2f}, wind x{wind_multiplier:.2f}."
            ),
            "simulation_model_version": SIMULATION_MODEL_VERSION,
        }
        features.append({**feature, "properties": scenario_properties})

    features.sort(key=lambda item: item["properties"]["scenario_risk_score"], reverse=True)
    overlay_features = features[:180]
    overlay = {
        "type": "FeatureCollection",
        "features": overlay_features,
        "metadata": {
            **risk_grid.get("metadata", {}),
            "simulation_model_version": SIMULATION_MODEL_VERSION,
            "scenario": scenario,
            "displayed_cell_count": len(overlay_features),
            "total_cell_count": len(features),
        },
    }
    return {
        "scenario": scenario,
        "overlay": overlay,
        "top_cells": [
            {
                "h3_cell": feature["properties"]["h3_cell"],
                "risk_score": feature["properties"]["scenario_risk_score"],
                "risk_delta": feature["properties"]["scenario_delta"],
                "nearest_county": feature["properties"].get("nearest_county"),
                "driver_summary": feature["properties"]["scenario_driver_summary"],
            }
            for feature in features[:8]
        ],
        "top_counties": county_rankings(features),
        "caveats": [
            "This is a transparent scenario screen, not an operational prediction.",
            "Temperature, drought, and wind controls reweight baseline risk drivers only.",
            "Use outputs for portfolio decision-support demonstration, not emergency action.",
        ],
    }
