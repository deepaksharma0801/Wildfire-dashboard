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
    assert payload["metadata"]["source"] == "sample_firms_like_arizona"


def test_counties_returns_geojson() -> None:
    response = client.get("/api/counties?data_source=sample")
    payload = response.json()

    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["count"] == 15
    assert payload["features"][0]["properties"]["name"]


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
