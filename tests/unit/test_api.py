from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from poi_curator_api.main import app
from poi_curator_domain.settings import get_settings

client = TestClient(app)
ADMIN_KEY = "unit-test-admin-key"
ADMIN_HEADERS = {"X-POI-Curator-Admin-Key": ADMIN_KEY}


@pytest.fixture
def admin_headers(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    monkeypatch.setenv("POI_CURATOR_ADMIN_KEY", ADMIN_KEY)
    get_settings.cache_clear()
    yield ADMIN_HEADERS
    get_settings.cache_clear()


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
    assert any(item["slug"] == "mixed" for item in payload)


def test_map_test_page_is_served() -> None:
    response = client.get("/map-test")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "poi-curator" in response.text
    assert "map-test" in response.text


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


def test_route_suggest_rejects_out_of_range_coordinate() -> None:
    response = client.post(
        "/v1/route/suggest",
        json={
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[-105.94, 35.68], [181.0, 35.67]],
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

    assert response.status_code == 422
    assert "longitude must be between -180 and 180" in str(response.json()["detail"])


def test_route_suggest_rejects_single_point_linestring() -> None:
    response = client.post(
        "/v1/route/suggest",
        json={
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[-105.94, 35.68]],
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

    assert response.status_code == 422
    assert "at least 2" in str(response.json()["detail"])


def test_route_suggest_order_is_stable_for_repeated_query() -> None:
    request_json = {
        "route_geometry": {
            "type": "LineString",
            "coordinates": [[-105.94, 35.68], [-105.93, 35.67]],
        },
        "origin": {"name": "A", "coordinates": [-105.94, 35.68]},
        "destination": {"name": "B", "coordinates": [-105.93, 35.67]},
        "travel_mode": "driving",
        "category": "mixed",
        "max_detour_meters": 1600,
        "max_extra_minutes": 8,
        "region_hint": "santa-fe",
        "limit": 5,
    }

    first_response = client.post("/v1/route/suggest", json=request_json)
    second_response = client.post("/v1/route/suggest", json=request_json)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_ids = [item["poi_id"] for item in first_response.json()["results"]]
    second_ids = [item["poi_id"] for item in second_response.json()["results"]]
    assert first_ids == second_ids


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


def test_nearby_suggest_rejects_non_finite_coordinate() -> None:
    response = client.post(
        "/v1/nearby/suggest",
        content=(
            '{"center":{"lat":NaN,"lon":-105.9495},"travel_mode":"walking",'
            '"category":"mixed","radius_meters":900,"region_hint":"santa-fe","limit":5}'
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert "finite longitude and latitude" in str(response.json()["detail"])


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


def test_point_suggest_rejects_out_of_range_coordinate() -> None:
    response = client.post(
        "/v1/point/suggest",
        json={
            "location": {"name": "Bad Point", "coordinates": [-105.9378, 91.0]},
            "travel_mode": "walking",
            "category": "mixed",
            "radius_meters": 1200,
            "region_hint": "santa-fe",
            "limit": 3,
        },
    )

    assert response.status_code == 422
    assert "latitude must be between -90 and 90" in str(response.json()["detail"])


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


def test_poi_detail_endpoint_exposes_extended_place_context_for_acequia_fixture() -> None:
    response = client.get("/v1/poi/poi-acequia-madre")

    assert response.status_code == 200
    payload = response.json()
    assert payload["extended_place"]["place_form"] == "corridor"
    assert payload["extended_place"]["encounter_mode"] == "along_corridor"
    assert payload["extended_place"]["encounter_anchors"][0]["is_primary"] is True


def test_admin_poi_evidence_endpoint_requires_api_key(admin_headers: dict[str, str]) -> None:
    missing_response = client.get("/v1/admin/poi/poi-santa-fe-plaza/evidence")
    assert missing_response.status_code == 401

    bad_response = client.get(
        "/v1/admin/poi/poi-santa-fe-plaza/evidence",
        headers={"X-POI-Curator-Admin-Key": "wrong"},
    )
    assert bad_response.status_code == 401

    response = client.get("/v1/admin/poi/poi-santa-fe-plaza/evidence", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["poi_id"] == "poi-santa-fe-plaza"
    assert "aliases" in payload
    assert "evidence" in payload
    assert "themes" in payload


def test_admin_match_diagnostics_endpoint(admin_headers: dict[str, str]) -> None:
    response = client.get("/v1/admin/match-diagnostics", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
