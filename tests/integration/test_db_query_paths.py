from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from poi_curator_api.main import app
from poi_curator_domain.db import (
    POI,
    POIEditorial,
    POISignals,
    POIThemeMembership,
    get_session_factory,
)
from shapely.geometry import Point
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError

client = TestClient(app)


@pytest.fixture
def db_query_fixture() -> Iterator[dict[str, str]]:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(text("select 1"))
    except OperationalError:
        pytest.skip("Local Postgres is not available for DB-backed integration tests.")

    region = f"it-region-{uuid4().hex[:8]}"
    near_poi_id = str(uuid4())
    secondary_poi_id = str(uuid4())
    far_poi_id = str(uuid4())
    poi_ids = [near_poi_id, secondary_poi_id, far_poi_id]
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add_all(
            [
                POI(
                    poi_id=near_poi_id,
                    canonical_name="Integration History House",
                    slug=f"integration-history-house-{region}",
                    geom=from_shape(Point(-105.9380, 35.6870), srid=4326),
                    centroid=from_shape(Point(-105.9380, 35.6870), srid=4326),
                    city=region,
                    region=region,
                    country="USA",
                    normalized_category="history",
                    normalized_subcategory="historic_site",
                    display_categories=["history"],
                    short_description="Historic site for integration testing.",
                    primary_source="test",
                    raw_tag_summary_json={"name": "Integration Acequia House", "man_made": "canal"},
                    historical_flag=True,
                    cultural_flag=False,
                    scenic_flag=False,
                    infrastructure_flag=False,
                    food_identity_flag=False,
                    walk_affinity_hint=0.8,
                    drive_affinity_hint=0.7,
                    base_significance_score=72.0,
                    quality_score=80.0,
                    review_status="needs_review",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                POI(
                    poi_id=secondary_poi_id,
                    canonical_name="Integration Civic Plaza",
                    slug=f"integration-civic-plaza-{region}",
                    geom=from_shape(Point(-105.9390, 35.6874), srid=4326),
                    centroid=from_shape(Point(-105.9390, 35.6874), srid=4326),
                    city=region,
                    region=region,
                    country="USA",
                    normalized_category="civic",
                    normalized_subcategory="civic_space_plaza",
                    display_categories=["civic", "history"],
                    short_description="Civic place with historical secondary meaning.",
                    primary_source="test",
                    raw_tag_summary_json={},
                    historical_flag=True,
                    cultural_flag=False,
                    scenic_flag=False,
                    infrastructure_flag=True,
                    food_identity_flag=False,
                    walk_affinity_hint=0.9,
                    drive_affinity_hint=0.6,
                    base_significance_score=65.0,
                    quality_score=75.0,
                    review_status="needs_review",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                POI(
                    poi_id=far_poi_id,
                    canonical_name="Far Test History Site",
                    slug=f"far-test-history-site-{region}",
                    geom=from_shape(Point(-106.2500, 35.6870), srid=4326),
                    centroid=from_shape(Point(-106.2500, 35.6870), srid=4326),
                    city=region,
                    region=region,
                    country="USA",
                    normalized_category="history",
                    normalized_subcategory="historic_site",
                    display_categories=["history"],
                    short_description="Far away history site.",
                    primary_source="test",
                    raw_tag_summary_json={},
                    historical_flag=True,
                    cultural_flag=False,
                    scenic_flag=False,
                    infrastructure_flag=False,
                    food_identity_flag=False,
                    walk_affinity_hint=0.3,
                    drive_affinity_hint=0.3,
                    base_significance_score=90.0,
                    quality_score=85.0,
                    review_status="needs_review",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add_all(
            [
                POISignals(
                    poi_id=near_poi_id,
                    source_count=1,
                    has_wikidata=False,
                    has_wikipedia=False,
                    has_official_heritage_match=False,
                    official_corroboration_score=0.2,
                    district_membership_score=0.1,
                    institutional_identity_score=0.0,
                    osm_tag_richness=0.4,
                    description_quality=0.7,
                    entity_type_confidence=0.8,
                    local_identity_score=0.5,
                    interpretive_value_score=0.7,
                    genericity_penalty=0.0,
                    editorial_priority_seed=0.0,
                    computed_at=now,
                ),
                POISignals(
                    poi_id=secondary_poi_id,
                    source_count=1,
                    has_wikidata=False,
                    has_wikipedia=False,
                    has_official_heritage_match=False,
                    official_corroboration_score=0.1,
                    district_membership_score=0.2,
                    institutional_identity_score=0.0,
                    osm_tag_richness=0.4,
                    description_quality=0.7,
                    entity_type_confidence=0.8,
                    local_identity_score=0.5,
                    interpretive_value_score=0.7,
                    genericity_penalty=0.0,
                    editorial_priority_seed=0.0,
                    computed_at=now,
                ),
                POISignals(
                    poi_id=far_poi_id,
                    source_count=1,
                    has_wikidata=False,
                    has_wikipedia=False,
                    has_official_heritage_match=False,
                    official_corroboration_score=0.0,
                    district_membership_score=0.0,
                    institutional_identity_score=0.0,
                    osm_tag_richness=0.3,
                    description_quality=0.7,
                    entity_type_confidence=0.7,
                    local_identity_score=0.3,
                    interpretive_value_score=0.6,
                    genericity_penalty=0.0,
                    editorial_priority_seed=0.0,
                    computed_at=now,
                ),
            ]
        )
        session.commit()

    yield {
        "region": region,
        "near_poi_id": near_poi_id,
        "secondary_poi_id": secondary_poi_id,
        "far_poi_id": far_poi_id,
    }

    with session_factory() as session:
        session.execute(delete(POIEditorial).where(POIEditorial.poi_id.in_(poi_ids)))
        session.execute(delete(POIThemeMembership).where(POIThemeMembership.poi_id.in_(poi_ids)))
        session.execute(delete(POISignals).where(POISignals.poi_id.in_(poi_ids)))
        session.execute(delete(POI).where(POI.poi_id.in_(poi_ids)))
        session.commit()


def test_nearby_suggest_uses_db_backed_pois(db_query_fixture: dict[str, str]) -> None:
    response = client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 35.6870, "lon": -105.9380},
            "travel_mode": "walking",
            "category": "history",
            "radius_meters": 500,
            "region_hint": db_query_fixture["region"],
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    result_ids = [item["poi_id"] for item in payload["results"]]
    assert db_query_fixture["near_poi_id"] in result_ids
    assert db_query_fixture["far_poi_id"] not in result_ids
    assert payload["results"][0]["score_breakdown"] is not None


def test_route_suggest_uses_db_backed_pois(db_query_fixture: dict[str, str]) -> None:
    response = client.post(
        "/v1/route/suggest",
        json={
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[-105.9400, 35.6870], [-105.9360, 35.6870]],
            },
            "origin": {"name": "A", "coordinates": [-105.9400, 35.6870]},
            "destination": {"name": "B", "coordinates": [-105.9360, 35.6870]},
            "travel_mode": "walking",
            "category": "history",
            "max_detour_meters": 600,
            "max_extra_minutes": 10,
            "region_hint": db_query_fixture["region"],
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    result_ids = [item["poi_id"] for item in payload["results"]]
    assert db_query_fixture["near_poi_id"] in result_ids
    assert db_query_fixture["far_poi_id"] not in result_ids
    assert payload["results"][0]["score_breakdown"] is not None


def test_nearby_suggest_water_theme_filters_and_persists_membership(
    db_query_fixture: dict[str, str],
) -> None:
    response = client.post(
        "/v1/nearby/suggest",
        json={
            "center": {"lat": 35.6870, "lon": -105.9380},
            "travel_mode": "walking",
            "category": "mixed",
            "theme": "water",
            "radius_meters": 500,
            "region_hint": db_query_fixture["region"],
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    result_ids = [item["poi_id"] for item in payload["results"]]
    assert result_ids == [db_query_fixture["near_poi_id"]]
    assert any(reason.startswith("reveals acequia or water corridor") for reason in payload["results"][0]["why_it_matters"])
    assert "water theme" in payload["results"][0]["badges"]

    with get_session_factory()() as session:
        membership = session.scalar(
            select(POIThemeMembership).where(
                POIThemeMembership.poi_id == db_query_fixture["near_poi_id"],
                POIThemeMembership.theme_slug == "water",
            )
        )
        assert membership is not None
        assert membership.status == "accepted"


def test_admin_poi_patch_persists_editorial_overrides(db_query_fixture: dict[str, str]) -> None:
    response = client.patch(
        f"/v1/admin/poi/{db_query_fixture['near_poi_id']}",
        json={
            "editorial_status": "featured",
            "editorial_title_override": "Edited History House",
            "editorial_boost": 4,
            "editorial_notes": "integration test",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is True
    assert payload["applied_changes"]["editorial_title_override"] == "Edited History House"

    with get_session_factory()() as session:
        editorial = session.get(POIEditorial, db_query_fixture["near_poi_id"])
        assert editorial is not None
        assert editorial.editorial_status == "featured"
        assert editorial.editorial_title_override == "Edited History House"
        assert editorial.editorial_boost == 4
