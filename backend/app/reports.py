from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return "unknown"


def first_place(summary: dict[str, Any]) -> dict[str, Any] | None:
    places = summary.get("nearby_places") or []
    return places[0] if places else None


def weather_sentence(summary: dict[str, Any]) -> str:
    weather = summary.get("weather") or {}
    if weather.get("unavailable"):
        return "Weather context is unavailable from NWS for this location right now."

    current = weather.get("current_period") or {}
    flags = weather.get("operational_flags") or []
    temperature = current.get("temperature")
    unit = current.get("temperature_unit") or ""
    wind = current.get("wind_speed") or "wind unavailable"
    direction = current.get("wind_direction") or ""
    forecast = current.get("short_forecast") or "forecast unavailable"
    flag_text = " ".join(flags)

    return (
        f"NWS forecast context shows {temperature}{unit} with {wind} {direction} "
        f"and {forecast.lower()}. {flag_text}"
    ).strip()


def generate_template_report(summary: dict[str, Any]) -> dict[str, Any]:
    place = first_place(summary)
    nearest_place = (
        f"{place['name']} ({place.get('distance_km')} km away)" if place else "no nearby place available"
    )
    affected_counties = summary.get("affected_counties") or []
    county_names = [county.get("name") for county in affected_counties if county.get("name")]
    county_text = ", ".join(county_names[:3]) if county_names else "no county overlap available"
    caveats = summary.get("data_caveats") or []

    sections = {
        "situation": (
            f"Incident {summary['id']} contains {summary['detection_count']} FIRMS detections "
            f"from {summary['time_start']} to {summary['time_end']}. The cluster average confidence is "
            f"{summary['avg_confidence']}% and peak FRP is {summary['max_frp_mw']} MW."
        ),
        "exposure": (
            f"The current {summary['radius_km']} km screening radius intersects {county_text}. "
            f"Estimated exposed population is {number(summary.get('estimated_population_exposed'))} "
            f"people across about {number(summary.get('estimated_households_exposed'))} households. "
            f"Nearest listed place is {nearest_place}."
        ),
        "weather_concerns": weather_sentence(summary),
        "monitoring_priorities": (
            "Prioritize monitoring cluster growth, repeat detections, wind shifts, and any change in "
            "nearby populated-place exposure. Treat this as decision support for triage, not an evacuation order."
        ),
        "data_caveats": " ".join(caveats),
    }

    return {
        "report_id": f"report-{summary['id']}",
        "mode": "template",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "incident_id": summary["id"],
        "sections": sections,
        "grounding": {
            "input_source": summary.get("source"),
            "used_fields": [
                "detection_count",
                "time_start",
                "time_end",
                "avg_confidence",
                "max_frp_mw",
                "estimated_population_exposed",
                "estimated_households_exposed",
                "nearby_places",
                "weather",
                "data_caveats",
            ],
            "unsupported_claims_policy": "Report text is generated only from supplied structured incident metrics.",
        },
    }


def validate_summary(summary: dict[str, Any]) -> None:
    required = [
        "id",
        "detection_count",
        "time_start",
        "time_end",
        "avg_confidence",
        "max_frp_mw",
        "radius_km",
    ]
    missing = [key for key in required if key not in summary]
    if missing:
        raise ValueError(f"incident_summary missing required fields: {', '.join(missing)}")
