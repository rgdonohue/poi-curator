"""Contract tests for the Detour-facing /v1 surface.

These pin the response shapes documented in docs/INTEGRATION_CONTRACT.md:
stable fields must be present, and nothing beyond the documented field set
(stable + advisory + documented-excluded) may appear — so an accidental leak
of admin/editorial internals into a public response model fails here first.

The scoring backend is stubbed via dependency overrides (no PostGIS), with
every optional/advisory field populated so the key-set assertions are
exercised at full response richness.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from poi_curator_api.dependencies import get_db_session, get_default_scoring_backend
from poi_curator_api.main import app
from poi_curator_domain.schemas import (
    EncounterAnchor,
    ExtendedPlaceContext,
    NearbyQuerySummary,
    NearbyResult,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIDetailResponse,
    POIThemeItem,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
    ThemeEvidenceReference,
)

client = TestClient(app)

KNOWN_POI_ID = "poi-contract-1"

# docs/INTEGRATION_CONTRACT.md: stable fields Detour may depend on.
ROUTE_RESULT_STABLE = {
    "data_source",
    "poi_id",
    "name",
    "primary_category",
    "secondary_categories",
    "coordinates",
    "short_description",
    "distance_from_route_m",
    "estimated_detour_m",
    "estimated_extra_minutes",
    "score",
    "why_it_matters",
    "badges",
}
ROUTE_RESULT_ADVISORY = {"category_match_type", "extended_place"}
ROUTE_RESULT_EXCLUDED_BUT_PRESENT = {"score_breakdown"}
ROUTE_RESULT_ALLOWED = (
    ROUTE_RESULT_STABLE | ROUTE_RESULT_ADVISORY | ROUTE_RESULT_EXCLUDED_BUT_PRESENT
)

POI_DETAIL_STABLE = {
    "poi_id",
    "name",
    "primary_category",
    "secondary_categories",
    "coordinates",
    "short_description",
    "why_it_matters",
    "badges",
    "themes",
}
POI_DETAIL_ADVISORY = {"extended_place", "provenance", "evidence"}
POI_DETAIL_ALLOWED = POI_DETAIL_STABLE | POI_DETAIL_ADVISORY

# Internal/admin field names that must never surface in contracted responses.
FORBIDDEN_INTERNAL_FIELDS = {
    "review_status",
    "review_state",
    "is_active",
    "editorial_status",
    "editorial_notes",
    "editorial_boost",
    "editorial_overrides",
    "has_diagnostics",
    "has_editorial_overrides",
    "match_diagnostics",
    "quality_score",
    "base_significance_score",
    "stale_since",
    "raw_tag_summary_json",
}

# An ORS-style densified LineString along Cerrillos Road, Santa Fe.
ORS_STYLE_ROUTE = [
    [-105.9772, 35.6532],
    [-105.9741, 35.6558],
    [-105.9702, 35.6589],
    [-105.9664, 35.6621],
    [-105.9628, 35.6655],
    [-105.9595, 35.6690],
    [-105.9563, 35.6727],
    [-105.9531, 35.6763],
    [-105.9500, 35.6797],
    [-105.9468, 35.6830],
    [-105.9437, 35.6861],
    [-105.9410, 35.6889],
]


class ContractStubBackend:
    """Fixture-free backend returning fully populated contract-shaped responses."""

    def current_scoring_source(self) -> str:
        return "database"

    def _extended_place(self) -> ExtendedPlaceContext:
        return ExtendedPlaceContext(
            place_form="corridor",
            encounter_mode="along_corridor",
            display_hint="corridor",
            encounter_anchors=[
                EncounterAnchor(
                    label="north end",
                    coordinates=[-105.9410, 35.6889],
                    kind="encounter",
                    is_primary=True,
                )
            ],
        )

    def suggest_places(self, db: object, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        del db
        return RouteSuggestResponse(
            data_source="database",
            query_summary=QuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                theme=payload.theme,
                max_detour_meters=payload.max_detour_meters,
                limit=payload.limit,
            ),
            results=[
                RouteResult(
                    data_source="database",
                    poi_id=KNOWN_POI_ID,
                    name="Contract POI",
                    primary_category=payload.category,
                    secondary_categories=["culture"],
                    category_match_type="primary",
                    coordinates=[-105.9505, 35.6870],
                    short_description="A stop used to pin the route contract.",
                    distance_from_route_m=42,
                    estimated_detour_m=120,
                    estimated_extra_minutes=2,
                    score=87.5,
                    score_breakdown={"route_fit": 30.0, "significance": 20.0},
                    why_it_matters=["pinned contract shape"],
                    badges=["historic"],
                    extended_place=self._extended_place(),
                )
            ],
        )

    def suggest_nearby_places(
        self,
        db: object,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse:
        del db
        return NearbySuggestResponse(
            data_source="database",
            query_summary=NearbyQuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                theme=payload.theme,
                radius_meters=payload.radius_meters,
                limit=payload.limit,
            ),
            results=[
                NearbyResult(
                    data_source="database",
                    poi_id=KNOWN_POI_ID,
                    name="Contract POI",
                    primary_category=payload.category,
                    secondary_categories=[],
                    category_match_type="primary",
                    coordinates=[-105.9505, 35.6870],
                    short_description="A stop used to pin the nearby contract.",
                    distance_from_center_meters=80,
                    estimated_access_m=95,
                    estimated_access_minutes=1,
                    score=71.0,
                    score_breakdown={"significance": 18.0},
                    why_it_matters=["pinned contract shape"],
                    badges=[],
                    extended_place=self._extended_place(),
                )
            ],
        )

    def get_poi_detail(self, db: object, poi_id: str) -> POIDetailResponse | None:
        del db
        if poi_id != KNOWN_POI_ID:
            return None
        return POIDetailResponse(
            poi_id=poi_id,
            name="Contract POI",
            primary_category="history",
            secondary_categories=["culture"],
            coordinates=[-105.9505, 35.6870],
            short_description="A stop used to pin the detail contract.",
            why_it_matters=["pinned contract shape"],
            badges=["historic"],
            provenance={
                "primary_source": "osm_overpass",
                "osm_id": "way/123",
                "wikidata_id": "Q1",
                "wikipedia_title": "Contract POI",
                "raw_source_count": 2,
                "field_sources": {"name": ["osm_overpass"]},
            },
            evidence=[
                {
                    "source_id": "nrhp_listed_properties",
                    "evidence_type": "official_register_match",
                    "label": "NRHP",
                    "text": None,
                    "url": None,
                    "confidence": 0.9,
                }
            ],
            themes=[
                POIThemeItem(
                    theme_slug="water",
                    label="Water",
                    status="accepted",
                    assignment_basis="rule",
                    confidence=0.8,
                    rationale_summary="acequia adjacency",
                    is_query_active=True,
                    editorial_decision=None,
                    evidence=[
                        ThemeEvidenceReference(
                            evidence_id=1,
                            source_id="city_gis_historic_districts",
                            evidence_type="district_membership",
                            label="district",
                            confidence=0.8,
                        )
                    ],
                )
            ],
            extended_place=self._extended_place(),
        )


def fake_db_session() -> Iterator[object]:
    yield object()


@pytest.fixture
def contract_client() -> Iterator[TestClient]:
    app.dependency_overrides[get_default_scoring_backend] = lambda: ContractStubBackend()
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def route_suggest_payload() -> dict[str, object]:
    return {
        "route_geometry": {"type": "LineString", "coordinates": ORS_STYLE_ROUTE},
        "origin": {"name": "Santa Fe Place", "coordinates": ORS_STYLE_ROUTE[0]},
        "destination": {"name": "Railyard", "coordinates": ORS_STYLE_ROUTE[-1]},
        "travel_mode": "driving",
        "category": "history",
        "max_detour_meters": 1600,
        "max_extra_minutes": 8,
        "region_hint": "santa-fe",
        "limit": 5,
    }


def test_route_suggest_contract_shape(contract_client: TestClient) -> None:
    response = contract_client.post("/v1/route/suggest", json=route_suggest_payload())

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data_source", "query_summary", "results"}
    assert set(payload["query_summary"]) == {
        "travel_mode",
        "category",
        "theme",
        "max_detour_meters",
        "limit",
    }
    assert payload["data_source"] == "database"
    assert payload["results"], "stub must return at least one result"
    for result in payload["results"]:
        assert set(result) == ROUTE_RESULT_ALLOWED
        assert ROUTE_RESULT_STABLE <= set(result)
        assert not FORBIDDEN_INTERNAL_FIELDS & set(result)
        lon, lat = result["coordinates"]
        assert -180 <= lon <= 180 and -90 <= lat <= 90
        assert lon < -100, "coordinates must be [lon, lat], not [lat, lon]"


def test_route_suggest_rejects_inactive_theme(contract_client: TestClient) -> None:
    payload = route_suggest_payload()
    payload["theme"] = "public_memory"

    response = contract_client.post("/v1/route/suggest", json=payload)

    assert response.status_code == 422


def test_nearby_suggest_contract_shape(contract_client: TestClient) -> None:
    response = contract_client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 35.6870, "lon": -105.9378},
            "travel_mode": "walking",
            "category": "art",
            "radius_meters": 500,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data_source", "query_summary", "results"}
    assert set(payload["query_summary"]) == {
        "travel_mode",
        "category",
        "theme",
        "radius_meters",
        "limit",
    }
    nearby_distance_fields = {
        "distance_from_center_meters",
        "estimated_access_m",
        "estimated_access_minutes",
    }
    for result in payload["results"]:
        assert not FORBIDDEN_INTERNAL_FIELDS & set(result)
        assert nearby_distance_fields <= set(result)


def test_poi_detail_contract_shape(contract_client: TestClient) -> None:
    response = contract_client.get(f"/v1/poi/{KNOWN_POI_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == POI_DETAIL_ALLOWED
    assert POI_DETAIL_STABLE <= set(payload)
    assert not FORBIDDEN_INTERNAL_FIELDS & set(payload)
    lon, lat = payload["coordinates"]
    assert lon < -100, "coordinates must be [lon, lat], not [lat, lon]"
    for theme in payload["themes"]:
        assert {
            "theme_slug",
            "label",
            "status",
            "assignment_basis",
            "confidence",
            "is_query_active",
        } <= set(theme)
    # Advisory provenance keys named by the contract must exist when provenance is present.
    assert {"primary_source", "osm_id", "wikidata_id", "wikipedia_title"} <= set(
        payload["provenance"]
    )


def test_poi_detail_unknown_id_is_404(contract_client: TestClient) -> None:
    response = contract_client.get("/v1/poi/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "POI not found"}
