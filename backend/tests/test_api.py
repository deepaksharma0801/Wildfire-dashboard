import subprocess
import sys

from fastapi.testclient import TestClient

from app.main import app
from app.weather import WeatherUnavailable

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_fires_returns_geojson() -> None:
    response = client.get("/api/fires?data_source=sample")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["count"] == len(payload["features"])
    assert payload["metadata"]["count"] > 0


def test_fires_filters_by_confidence() -> None:
    response = client.get("/api/fires?data_source=sample&min_confidence=90")
    payload = response.json()

    assert response.status_code == 200
    assert payload["metadata"]["count"] > 0
    assert all(feature["properties"]["confidence"] >= 90 for feature in payload["features"])


def test_fires_rejects_invalid_date_range() -> None:
    response = client.get("/api/fires?start_date=2026-05-21&end_date=2026-05-01")

    assert response.status_code == 400


def test_fires_metadata_includes_requested_data_source() -> None:
    response = client.get("/api/fires?data_source=sample")
    payload = response.json()

    assert response.status_code == 200
    assert payload["metadata"]["requested_data_source"] == "sample"
    assert payload["metadata"]["source"] == "sample_firms_like_southwest"


def test_counties_returns_geojson() -> None:
    response = client.get("/api/counties?data_source=sample")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["count"] == 15
    assert payload["features"][0]["properties"]["name"]


def test_regions_returns_southwest_scope() -> None:
    response = client.get("/api/regions")
    payload = response.json()
    codes = {region["code"] for region in payload["regions"]}

    assert response.status_code == 200
    assert {"AZ", "CA", "NV", "NM", "TX", "CO", "southwest"}.issubset(codes)
    assert payload["default_region"] == "AZ"


def test_clusters_returns_geojson() -> None:
    response = client.get("/api/fires/clusters?data_source=sample&radius_km=25")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["count"] > 0
    assert payload["features"][0]["properties"]["detection_count"] >= 1


def test_incident_summary_returns_exposure_metrics() -> None:
    clusters = client.get("/api/fires/clusters?data_source=sample&radius_km=25").json()
    incident_id = clusters["features"][0]["properties"]["id"]
    response = client.get(f"/api/incidents/{incident_id}/summary?data_source=sample&radius_km=25")
    payload = response.json()

    assert response.status_code == 200
    assert payload["id"] == incident_id
    assert "estimated_population_exposed" in payload
    assert payload["nearby_places"]
    assert "weather" in payload


def test_weather_point_handles_unavailable_weather(monkeypatch) -> None:
    def fail_weather(latitude: float, longitude: float) -> dict:
        raise WeatherUnavailable("boom")

    monkeypatch.setattr("app.main.get_weather_context", fail_weather)
    response = client.get("/api/weather/point?latitude=34.05&longitude=-111.09")
    payload = response.json()

    assert response.status_code == 200
    assert payload["unavailable"] is True


def test_incident_report_is_grounded_in_summary() -> None:
    clusters = client.get("/api/fires/clusters?data_source=sample&radius_km=25").json()
    incident_id = clusters["features"][0]["properties"]["id"]
    summary = client.get(f"/api/incidents/{incident_id}/summary?data_source=sample&radius_km=25").json()

    response = client.post(
        "/api/reports/incident",
        json={"incident_summary": summary, "mode": "template"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["incident_id"] == incident_id
    assert payload["mode"] == "template"
    assert "situation" in payload["sections"]
    assert "unsupported_claims_policy" in payload["grounding"]


def test_incident_report_rejects_missing_summary_fields() -> None:
    response = client.post("/api/reports/incident", json={"incident_summary": {"id": "x"}})

    assert response.status_code == 400


def test_risk_grid_returns_scored_cells() -> None:
    response = client.get("/api/risk/grid?data_source=sample&horizon_hours=72&cell_size_deg=1")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["method"] == "weighted_distance_baseline"
    assert payload["metadata"]["input_detection_count"] > 0
    assert payload["features"]
    assert "risk_score" in payload["features"][0]["properties"]
    assert payload["features"][0]["properties"]["risk_class"] in {
        "low",
        "moderate",
        "high",
        "extreme",
    }


def test_risk_grid_rejects_invalid_horizon() -> None:
    response = client.get("/api/risk/grid?data_source=sample&horizon_hours=12")

    assert response.status_code == 422


def test_h3_risk_grid_returns_valid_cells() -> None:
    response = client.get("/api/risk/h3-grid?region=southwest&h3_resolution=5&data_source=sample")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["region"] == "southwest"
    assert payload["metadata"]["h3_resolution"] == 5
    assert payload["features"]
    properties = payload["features"][0]["properties"]
    assert "h3_cell" in properties
    assert properties["h3_resolution"] == 5
    assert properties["region"] == "southwest"
    assert "driver_summary" in properties


def test_h3_risk_grid_rejects_invalid_region() -> None:
    response = client.get("/api/risk/h3-grid?region=FL&h3_resolution=5&data_source=sample")

    assert response.status_code == 422


def test_h3_risk_grid_rejects_invalid_resolution() -> None:
    response = client.get("/api/risk/h3-grid?region=AZ&h3_resolution=7&data_source=sample")

    assert response.status_code == 422


def test_risk_evaluation_returns_proxy_metrics() -> None:
    response = client.get("/api/risk/evaluation")
    payload = response.json()

    assert response.status_code == 200
    assert payload["model_version"] == "baseline-risk-v0.1"
    assert payload["sample_size"] > 0
    assert "roc_auc" in payload["metrics"]
    assert "classification" in payload["metrics"]


def test_imagery_search_returns_sample_products() -> None:
    response = client.get("/api/imagery/search")
    payload = response.json()

    assert response.status_code == 200
    assert payload["metadata"]["source"] == "sample_sentinel2_burn_scar_demo"
    assert payload["products"]
    assert "burn_area_hectares" in payload["products"][0]


def test_imagery_before_after_returns_burn_scar_overlay() -> None:
    response = client.get("/api/imagery/sample/before-after")
    payload = response.json()

    assert response.status_code == 200
    assert payload["before_image_url"].endswith(".svg")
    assert payload["after_image_url"].endswith(".svg")
    assert payload["burn_scar"]["type"] == "FeatureCollection"
    assert payload["burn_area_hectares"] > 0


def test_risk_forecast_returns_trend_grid() -> None:
    response = client.get("/api/forecast/risk-grid?data_source=sample&horizon_hours=48")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["forecast_model_version"] == "baseline-risk-forecast-v0.1"
    assert payload["features"]
    properties = payload["features"][0]["properties"]
    assert "risk_score_now" in properties
    assert "risk_score_forecast" in properties
    assert properties["trend"] in {"falling", "stable", "rising"}


def test_risk_forecast_rejects_invalid_horizon() -> None:
    response = client.get("/api/forecast/risk-grid?data_source=sample&horizon_hours=36")

    assert response.status_code == 422


def test_az_risk_intelligence_returns_county_rankings() -> None:
    response = client.get("/api/az/risk-intelligence?data_source=sample&horizon_hours=72")
    payload = response.json()

    assert response.status_code == 200
    assert payload["region"] == "AZ"
    assert payload["summary"]["county_count"] == 15
    assert payload["county_rankings"]
    row = payload["county_rankings"][0]
    assert {
        "county",
        "geoid",
        "risk_score",
        "detection_count",
        "population",
        "max_risk_score",
        "forecast_trend",
        "top_driver",
        "caveat",
    }.issubset(row)
    assert payload["top_risk_cells"]
    assert payload["data_sources"]["requested_data_source"] == "sample"


def test_az_risk_intelligence_handles_empty_detection_filters() -> None:
    response = client.get(
        "/api/az/risk-intelligence?data_source=sample&start_date=2020-01-01&end_date=2020-01-02&min_confidence=100"
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"]["active_detection_count"] == 0
    assert payload["summary"]["county_count"] == 15
    assert all(row["detection_count"] == 0 for row in payload["county_rankings"])


def test_copilot_risk_near_population_returns_overlay() -> None:
    response = client.post(
        "/api/copilot/query",
        json={
            "query": "Show wildfire risk near dense population zones in Arizona.",
            "data_source": "sample",
            "min_confidence": 50,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "risk_near_population"
    assert payload["overlay"]["type"] == "FeatureCollection"
    assert "fields_used" in payload["metrics"]
    assert "evacuation" not in payload["answer"].lower()


def test_copilot_county_vulnerability_returns_ranking() -> None:
    response = client.post(
        "/api/copilot/query",
        json={
            "query": "Which counties are most vulnerable next week?",
            "data_source": "sample",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "county_vulnerability"
    assert payload["overlay"]["type"] == "FeatureCollection"
    assert "top_counties" in payload["metrics"]


def test_copilot_unsupported_query_returns_help() -> None:
    response = client.post(
        "/api/copilot/query",
        json={"query": "Can you order lunch for the response team?", "data_source": "sample"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "help"
    assert payload["metrics"]["supported_examples"]


def test_risk_scenario_returns_overlay_and_caveats() -> None:
    response = client.post(
        "/api/simulations/risk-scenario",
        json={
            "region": "southwest",
            "h3_resolution": 5,
            "horizon_hours": 72,
            "temperature_delta_c": 3,
            "drought_multiplier": 1.2,
            "wind_multiplier": 1.1,
            "data_source": "sample",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["overlay"]["type"] == "FeatureCollection"
    assert payload["top_cells"]
    assert payload["top_counties"]
    assert any("not an operational prediction" in caveat for caveat in payload["caveats"])


def test_etl_sample_mode_runs_without_api_keys(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_etl.py",
            "--mode",
            "sample",
            "--region",
            "southwest",
            "--log-dir",
            str(tmp_path / "logs"),
            "--evaluation-output",
            str(tmp_path / "risk_eval.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert (tmp_path / "risk_eval.json").exists()
    assert list((tmp_path / "logs").glob("etl_sample_*.json"))
