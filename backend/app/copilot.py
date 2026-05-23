from __future__ import annotations

from collections import Counter
from typing import Any

from app.exposure import load_county_exposure

EXAMPLE_QUERIES = [
    "Show wildfire risk near dense population zones in Arizona.",
    "Which counties are most vulnerable next week?",
    "Show recent active fire clusters.",
    "Summarize the top incident.",
]

COPILOT_CAVEATS = [
    "Copilot answers are generated from computed dashboard metrics only.",
    "FIRMS detections are hotspots, not official fire perimeters.",
    "Risk and forecast outputs are baseline screening layers, not operational guidance.",
]


def detect_intent(query: str) -> str:
    text = query.lower()
    if not text.strip() or "help" in text or "example" in text:
        return "help"
    if "population" in text or "dense" in text or "community" in text:
        return "risk_near_population"
    if "county" in text or "counties" in text or "vulnerable" in text or "vulnerability" in text:
        return "county_vulnerability"
    if "summary" in text or "summarize" in text or "incident" in text:
        return "incident_summary"
    if "cluster" in text or "recent" in text or "active" in text or "detections" in text:
        return "recent_fire_clusters"
    if "risk" in text:
        return "risk_near_population"
    return "help"


def empty_collection() -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": []}


def help_response(query: str) -> dict[str, Any]:
    return {
        "query": query,
        "intent": "help",
        "answer": "I can answer supported spatial questions about wildfire risk, vulnerable counties, recent clusters, and top incident summaries.",
        "overlay": empty_collection(),
        "metrics": {"supported_examples": EXAMPLE_QUERIES},
        "actions": [{"type": "show_examples", "label": example} for example in EXAMPLE_QUERIES],
        "caveats": COPILOT_CAVEATS,
    }


def top_risk_near_population(query: str, risk_grid: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        feature
        for feature in risk_grid.get("features", [])
        if feature["properties"].get("risk_score", 0) >= 30
        and feature["properties"].get("exposure_proxy", 0) >= 0.05
    ]
    candidates.sort(
        key=lambda feature: (
            feature["properties"]["risk_score"],
            feature["properties"]["exposure_proxy"],
        ),
        reverse=True,
    )
    overlay = {"type": "FeatureCollection", "features": candidates[:8]}
    if not candidates:
        answer = "No high-risk grid cells with elevated population exposure were found for the current filters."
        max_risk = 0
        avg_exposure = 0
    else:
        max_risk = max(feature["properties"]["risk_score"] for feature in candidates)
        avg_exposure = round(
            sum(feature["properties"]["exposure_proxy"] for feature in candidates[:8])
            / len(candidates[:8]),
            3,
        )
        answer = (
            f"Found {len(candidates)} risk cells near denser population proxies. "
            f"The top cell has risk score {max_risk}/100 and average selected exposure proxy {avg_exposure}."
        )
    return {
        "query": query,
        "intent": "risk_near_population",
        "answer": answer,
        "overlay": overlay,
        "metrics": {
            "selected_cell_count": len(overlay["features"]),
            "candidate_cell_count": len(candidates),
            "max_risk_score": max_risk,
            "avg_exposure_proxy": avg_exposure,
            "fields_used": ["risk_score", "exposure_proxy", "recent_activity", "historical_prior"],
        },
        "actions": [{"type": "apply_overlay", "label": "Highlight risk near population"}],
        "caveats": COPILOT_CAVEATS,
    }


def county_name(properties: dict[str, Any]) -> str:
    return str(properties.get("name") or properties.get("NAME") or "")


def county_vulnerability(query: str, counties: dict[str, Any], fires: dict[str, Any]) -> dict[str, Any]:
    detections_by_county = Counter(
        str(feature.get("properties", {}).get("county") or "").replace(" County", "")
        for feature in fires.get("features", [])
    )
    exposure_by_name = {
        str(row["name"]).replace(" County", ""): row for row in load_county_exposure()
    }
    ranked = []
    for feature in counties.get("features", []):
        name = county_name(feature["properties"]).replace(" County", "")
        exposure = exposure_by_name.get(name, {})
        population = int(exposure.get("population") or 0)
        detections = detections_by_county.get(name, 0)
        score = round(detections * 12 + min(population / 100_000, 10), 1)
        if score > 0:
            enriched = {
                **feature,
                "properties": {
                    **feature["properties"],
                    "copilot_vulnerability_score": score,
                    "copilot_detection_count": detections,
                    "copilot_population": population,
                },
            }
            ranked.append(enriched)
    ranked.sort(key=lambda feature: feature["properties"]["copilot_vulnerability_score"], reverse=True)
    overlay = {"type": "FeatureCollection", "features": ranked[:5]}
    top_names = [
        f"{county_name(feature['properties'])} ({feature['properties']['copilot_vulnerability_score']})"
        for feature in ranked[:3]
    ]
    answer = (
        "Top vulnerable counties by current detection count and population proxy: "
        + (", ".join(top_names) if top_names else "no counties matched current filters.")
    )
    return {
        "query": query,
        "intent": "county_vulnerability",
        "answer": answer,
        "overlay": overlay,
        "metrics": {
            "ranked_county_count": len(ranked),
            "fields_used": ["county detection count", "county population proxy"],
            "top_counties": top_names,
        },
        "actions": [{"type": "apply_overlay", "label": "Highlight vulnerable counties"}],
        "caveats": COPILOT_CAVEATS,
    }


def recent_fire_clusters(query: str, clusters: dict[str, Any]) -> dict[str, Any]:
    features = sorted(
        clusters.get("features", []),
        key=lambda feature: (
            feature["properties"].get("detection_count", 0),
            feature["properties"].get("max_frp_mw", 0),
        ),
        reverse=True,
    )
    overlay = {"type": "FeatureCollection", "features": features[:8]}
    if features:
        top = features[0]["properties"]
        answer = (
            f"Found {len(features)} active clusters. The top cluster has "
            f"{top['detection_count']} detections, average confidence {top['avg_confidence']}%, "
            f"and max FRP {top['max_frp_mw']} MW."
        )
    else:
        answer = "No active clusters matched the current filters."
    return {
        "query": query,
        "intent": "recent_fire_clusters",
        "answer": answer,
        "overlay": overlay,
        "metrics": {
            "cluster_count": len(features),
            "fields_used": ["detection_count", "avg_confidence", "max_frp_mw", "time_end"],
        },
        "actions": [{"type": "apply_overlay", "label": "Highlight recent clusters"}],
        "caveats": COPILOT_CAVEATS,
    }


def incident_summary(query: str, clusters: dict[str, Any], summary: dict[str, Any] | None = None) -> dict[str, Any]:
    features = sorted(
        clusters.get("features", []),
        key=lambda feature: feature["properties"].get("detection_count", 0),
        reverse=True,
    )
    overlay = {"type": "FeatureCollection", "features": features[:1]}
    if summary:
        weather = summary.get("weather") or {}
        weather_text = "weather unavailable"
        if not weather.get("unavailable") and weather.get("current_period"):
            period = weather["current_period"]
            weather_text = f"{period.get('temperature', 'n/a')}{period.get('temperature_unit', '')}, {period.get('wind_speed', 'wind n/a')}"
        answer = (
            f"Top incident {summary['id']} contains {summary['detection_count']} detections, "
            f"estimated population exposure {summary['estimated_population_exposed']}, "
            f"and current weather context: {weather_text}."
        )
        metrics = {
            "incident_id": summary["id"],
            "detection_count": summary["detection_count"],
            "estimated_population_exposed": summary["estimated_population_exposed"],
            "fields_used": ["detection_count", "estimated_population_exposed", "weather"],
        }
    elif features:
        top = features[0]["properties"]
        answer = (
            f"Top incident cluster {top['id']} has {top['detection_count']} detections, "
            f"average confidence {top['avg_confidence']}%, and max FRP {top['max_frp_mw']} MW."
        )
        metrics = {"incident_id": top["id"], "detection_count": top["detection_count"]}
    else:
        answer = "No incident cluster is available for the current filters."
        metrics = {}
    return {
        "query": query,
        "intent": "incident_summary",
        "answer": answer,
        "overlay": overlay,
        "metrics": metrics,
        "actions": [{"type": "apply_overlay", "label": "Highlight top incident"}],
        "caveats": COPILOT_CAVEATS,
    }


def build_copilot_response(
    *,
    query: str,
    fires: dict[str, Any],
    counties: dict[str, Any],
    clusters: dict[str, Any],
    risk_grid: dict[str, Any],
    top_incident_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intent = detect_intent(query)
    if intent == "risk_near_population":
        return top_risk_near_population(query, risk_grid)
    if intent == "county_vulnerability":
        return county_vulnerability(query, counties, fires)
    if intent == "recent_fire_clusters":
        return recent_fire_clusters(query, clusters)
    if intent == "incident_summary":
        return incident_summary(query, clusters, top_incident_summary)
    return help_response(query)
