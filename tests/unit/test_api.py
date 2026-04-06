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


def test_route_suggest_endpoint_accepts_active_water_theme() -> None:
    response = client.post(
        "/v1/route/suggest",
        json={
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[-105.9345, 35.6812], [-105.9308, 35.6842]],
            },
            "origin": {"name": "Acequia West", "coordinates": [-105.9345, 35.6812]},
            "destination": {"name": "Acequia East", "coordinates": [-105.9308, 35.6842]},
            "travel_mode": "walking",
            "category": "mixed",
            "theme": "water",
            "max_detour_meters": 450,
            "max_extra_minutes": 8,
            "region_hint": "santa-fe",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_summary"]["theme"] == "water"


def test_nearby_suggest_endpoint_accepts_active_rail_theme() -> None:
    response = client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 35.6821, "lon": -105.9495},
            "travel_mode": "walking",
            "category": "mixed",
            "theme": "rail",
            "radius_meters": 900,
            "region_hint": "santa-fe",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_summary"]["theme"] == "rail"


def test_nearby_suggest_rejects_inactive_theme() -> None:
    response = client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 35.687, "lon": -105.9378},
            "travel_mode": "walking",
            "category": "mixed",
            "theme": "public_memory",
            "radius_meters": 1200,
            "region_hint": "santa-fe",
            "limit": 5,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert "not yet active for query use" in str(payload["detail"])


def test_point_suggest_endpoint() -> None:
    response = client.post(
        "/v1/point/suggest",
        json={
            "location": {"name": "Plaza", "coordinates": [-105.9378, 35.687]},
            "travel_mode": "walking",
            "category": "mixed",
            "radius_meters": 1200,
            "region_hint": "santa-fe",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_summary"]["radius_meters"] == 1200
    assert len(payload["results"]) >= 1
    assert "distance_from_center_meters" in payload["results"][0]


def test_nearby_suggest_endpoint_returns_results_and_breakdown() -> None:
    response = client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 35.687, "lon": -105.9378},
            "travel_mode": "walking",
            "category": "history",
            "radius_meters": 1200,
            "region_hint": "santa-fe",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_summary"]["category"] == "history"
    assert len(payload["results"]) >= 1
    assert "score_breakdown" in payload["results"][0]
    assert "distance_from_center_meters" in payload["results"][0]


def test_nearby_suggest_endpoint_can_return_empty_results() -> None:
    response = client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 0.0, "lon": 0.0},
            "travel_mode": "walking",
            "category": "history",
            "radius_meters": 100,
            "region_hint": "santa-fe",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == []


def test_poi_detail_endpoint_includes_evidence_field() -> None:
    response = client.get("/v1/poi/poi-santa-fe-plaza")

    assert response.status_code == 200
    payload = response.json()
    assert payload["poi_id"] == "poi-santa-fe-plaza"
    assert "evidence" in payload
    assert "themes" in payload


def test_admin_poi_evidence_endpoint() -> None:
    response = client.get("/v1/admin/poi/poi-santa-fe-plaza/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["poi_id"] == "poi-santa-fe-plaza"
    assert "aliases" in payload
    assert "evidence" in payload
    assert "themes" in payload


def test_admin_match_diagnostics_endpoint() -> None:
    response = client.get("/v1/admin/match-diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
