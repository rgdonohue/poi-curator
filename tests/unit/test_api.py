from fastapi.testclient import TestClient
from poi_curator_api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "poi-curator"


def test_categories_endpoint() -> None:
    response = client.get("/v1/categories")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["slug"] == "history" for item in payload)


def test_route_suggest_endpoint() -> None:
    response = client.post(
        "/v1/route/suggest",
        json={
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[-105.94, 35.68], [-105.93, 35.67]],
            },
            "origin": {"name": "A", "coordinates": [-105.94, 35.68]},
            "destination": {"name": "B", "coordinates": [-105.93, 35.67]},
            "travel_mode": "driving",
            "category": "history",
            "max_detour_meters": 1600,
            "max_extra_minutes": 8,
            "region_hint": "santa-fe",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_summary"]["category"] == "history"
    assert len(payload["results"]) >= 1
