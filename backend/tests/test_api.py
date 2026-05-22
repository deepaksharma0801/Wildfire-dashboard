from fastapi.testclient import TestClient

from app.main import app

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
