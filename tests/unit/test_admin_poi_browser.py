from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from poi_curator_api.main import app
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIAlias,
    POIEditorial,
    POIEvidence,
    POISignals,
    POIThemeMembership,
    POIThemeMembershipEvidence,
    SourceRegistry,
    get_session_factory,
)
from poi_curator_domain.settings import get_settings
from shapely.geometry import Point
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError

client = TestClient(app)
ADMIN_KEY = "unit-test-admin-key"
ADMIN_HEADERS = {"X-POI-Curator-Admin-Key": ADMIN_KEY}


@pytest.fixture(autouse=True)
def configure_admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("POI_CURATOR_ADMIN_KEY", ADMIN_KEY)
    get_settings.cache_clear()
    client.headers.update(ADMIN_HEADERS)
    yield
    client.headers.pop("X-POI-Curator-Admin-Key", None)
    get_settings.cache_clear()


@pytest.fixture
def admin_poi_fixture() -> Iterator[dict[str, Any]]:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(text("select 1"))
    except OperationalError:
        pytest.skip("Local Postgres is not available for admin POI browser tests.")

    suffix = uuid4().hex[:8]
    region = f"admin-browser-{suffix}"
    history_category = f"admin_history_{suffix}"
    art_category = f"admin_art_{suffix}"
    reviewed_state = f"reviewed_{suffix}"
    now = datetime.now(UTC)
    source_ids = [f"osm-{suffix}", f"wikidata-{suffix}", f"sf-gis-{suffix}"]
    poi_ids = [str(uuid4()) for _ in range(4)]

    with session_factory() as session:
        session.add_all(
            [
                SourceRegistry(
                    source_id=source_ids[0],
                    organization_name="Test OSM",
                    source_name="OpenStreetMap Test",
                    source_type="osm",
                    trust_class="community",
                    base_url=None,
                    license_notes=None,
                    crawl_allowed=False,
                    ingest_method="test",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SourceRegistry(
                    source_id=source_ids[1],
                    organization_name="Test Wikidata",
                    source_name="Wikidata Test",
                    source_type="linked_open_data",
                    trust_class="reference",
                    base_url=None,
                    license_notes=None,
                    crawl_allowed=False,
                    ingest_method="test",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SourceRegistry(
                    source_id=source_ids[2],
                    organization_name="Test Santa Fe GIS",
                    source_name="Santa Fe GIS Test",
                    source_type="city_gis",
                    trust_class="official_city",
                    base_url=None,
                    license_notes=None,
                    crawl_allowed=False,
                    ingest_method="test",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        rows = [
            {
                "poi_id": poi_ids[0],
                "name": "Admin Acequia House",
                "category": history_category,
                "source": source_ids[0],
                "point": Point(-105.93, 35.68),
                "themes": ["water"],
                "active": True,
                "review_status": "needs_review",
            },
            {
                "poi_id": poi_ids[1],
                "name": "Admin Rail Gallery",
                "category": art_category,
                "source": source_ids[1],
                "point": Point(-105.95, 35.68),
                "themes": ["rail"],
                "active": True,
                "review_status": reviewed_state,
            },
            {
                "poi_id": poi_ids[2],
                "name": "Admin Water Rail Depot",
                "category": history_category,
                "source": source_ids[2],
                "point": Point(-105.91, 35.69),
                "themes": ["water", "rail"],
                "active": True,
                "review_status": "needs_review",
            },
            {
                "poi_id": poi_ids[3],
                "name": "Admin Stale OSM Site",
                "category": history_category,
                "source": source_ids[0],
                "point": Point(-106.0, 35.7),
                "themes": [],
                "active": False,
                "review_status": "stale",
            },
        ]
        for index, row in enumerate(rows):
            poi = POI(
                poi_id=row["poi_id"],
                canonical_name=row["name"],
                slug=f"{row['name'].lower().replace(' ', '-')}-{suffix}",
                geom=from_shape(row["point"], srid=4326),
                centroid=from_shape(row["point"], srid=4326),
                city=region,
                region=region,
                country="USA",
                normalized_category=row["category"],
                normalized_subcategory=None,
                display_categories=[row["category"]],
                short_description=f"{row['name']} test description.",
                primary_source=row["source"],
                osm_id=f"node/{index + 1}" if row["source"] == source_ids[0] else None,
                wikidata_id="Q123" if row["source"] == source_ids[1] else None,
                wikipedia_title=None,
                heritage_id=None,
                raw_tag_summary_json={"name": row["name"]},
                historical_flag=row["category"] == "history",
                cultural_flag=row["category"] == "art",
                scenic_flag=False,
                infrastructure_flag=False,
                food_identity_flag=False,
                walk_affinity_hint=0.5,
                drive_affinity_hint=0.5,
                base_significance_score=50.0,
                quality_score=70.0,
                review_status=row["review_status"],
                is_active=row["active"],
                created_at=now,
                updated_at=now,
            )
            session.add(poi)
            session.add(
                POISignals(
                    poi_id=row["poi_id"],
                    source_count=1,
                    has_wikidata=row["source"] == source_ids[1],
                    has_wikipedia=False,
                    has_official_heritage_match=False,
                    official_corroboration_score=0.0,
                    district_membership_score=0.0,
                    institutional_identity_score=0.0,
                    osm_tag_richness=0.5,
                    description_quality=0.7,
                    entity_type_confidence=0.8,
                    local_identity_score=0.6,
                    interpretive_value_score=0.6,
                    genericity_penalty=0.0,
                    editorial_priority_seed=0.0,
                    computed_at=now,
                )
            )
            session.add(
                POIEvidence(
                    evidence_key=f"evidence-{suffix}-{index}",
                    poi_id=row["poi_id"],
                    source_id=source_ids[index % len(source_ids)],
                    evidence_type="identity",
                    evidence_label=f"{row['name']} evidence",
                    evidence_text="Evidence text.",
                    evidence_url=None,
                    external_record_id=f"external-{index}",
                    confidence=0.9,
                    raw_evidence_json={"raw": row["name"], "index": index},
                    observed_at=now,
                )
            )
            for theme_slug in row["themes"]:
                session.add(
                    POIThemeMembership(
                        poi_id=row["poi_id"],
                        theme_slug=theme_slug,
                        status="accepted",
                        assignment_basis="test",
                        confidence=0.9,
                        rationale_summary=f"{theme_slug} test membership",
                        computed_at=now,
                    )
                )

        session.add(
            POIAlias(
                poi_id=poi_ids[0],
                alias_name="Acequia Alias",
                normalized_alias="acequia alias",
                alias_type="test",
                source="test",
                confidence=1.0,
                is_preferred=False,
                notes=None,
                created_at=now,
            )
        )
        session.add(
            POIEditorial(
                poi_id=poi_ids[0],
                editorial_status="reviewed",
                editorial_title_override="Edited Acequia House",
                editorial_description_override=None,
                editorial_category_override=None,
                editorial_boost=0,
                editorial_notes=None,
                city_pack=None,
                last_reviewed_at=now,
                reviewed_by="unit-test",
            )
        )
        session.add(
            OfficialMatchDiagnostic(
                source_id=source_ids[2],
                region=region,
                external_record_id=f"diag-{suffix}",
                external_name="Admin Acequia House Register",
                matched_poi_id=poi_ids[0],
                resolved_poi_id=None,
                best_candidate_name="Admin Acequia House",
                best_similarity=0.74,
                match_strategy="test",
                status="unreviewed",
                resolution_method=None,
                raw_payload_json={"reviewer_notes": "Needs identity review."},
                reviewed_at=None,
                reviewed_by=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        evidence_id = session.scalar(
            select(POIEvidence.id).where(POIEvidence.poi_id == poi_ids[0])
        )
        membership_id = session.scalar(
            select(POIThemeMembership.id).where(
                POIThemeMembership.poi_id == poi_ids[0],
                POIThemeMembership.theme_slug == "water",
            )
        )
        assert evidence_id is not None
        assert membership_id is not None
        session.add(
            POIThemeMembershipEvidence(
                membership_id=membership_id,
                poi_evidence_id=evidence_id,
                contribution_type="positive",
                weight=1.0,
            )
        )
        session.commit()

    yield {
        "region": region,
        "poi_ids": poi_ids,
        "source_ids": source_ids,
        "history_category": history_category,
        "art_category": art_category,
        "reviewed_state": reviewed_state,
    }

    with session_factory() as session:
        session.execute(
            delete(POIThemeMembershipEvidence).where(
                POIThemeMembershipEvidence.membership_id.in_(
                    select(POIThemeMembership.id).where(
                        POIThemeMembership.poi_id.in_(poi_ids)
                    )
                )
            )
        )
        session.execute(delete(POIThemeMembership).where(POIThemeMembership.poi_id.in_(poi_ids)))
        session.execute(
            delete(OfficialMatchDiagnostic).where(OfficialMatchDiagnostic.region == region)
        )
        session.execute(delete(POIEditorial).where(POIEditorial.poi_id.in_(poi_ids)))
        session.execute(delete(POIAlias).where(POIAlias.poi_id.in_(poi_ids)))
        session.execute(delete(POIEvidence).where(POIEvidence.poi_id.in_(poi_ids)))
        session.execute(delete(POISignals).where(POISignals.poi_id.in_(poi_ids)))
        session.execute(delete(POI).where(POI.poi_id.in_(poi_ids)))
        session.execute(delete(SourceRegistry).where(SourceRegistry.source_id.in_(source_ids)))
        session.commit()


def test_admin_poi_list_filters_and_theme_semantics(
    admin_poi_fixture: dict[str, Any],
) -> None:
    poi_ids = admin_poi_fixture["poi_ids"]
    source_ids = admin_poi_fixture["source_ids"]

    category_response = client.get(
        f"/v1/admin/pois?category={admin_poi_fixture['art_category']}"
    )
    assert category_response.status_code == 200
    assert [item["poi_id"] for item in category_response.json()["items"]] == [poi_ids[1]]

    review_response = client.get(
        f"/v1/admin/pois?review_state={admin_poi_fixture['reviewed_state']}"
    )
    assert review_response.status_code == 200
    assert [item["poi_id"] for item in review_response.json()["items"]] == [poi_ids[1]]

    source_response = client.get(f"/v1/admin/pois?source={source_ids[1]}")
    assert source_response.status_code == 200
    assert [item["poi_id"] for item in source_response.json()["items"]] == [poi_ids[1]]

    search_response = client.get("/v1/admin/pois?search=acequia%20alias")
    assert search_response.status_code == 200
    assert [item["poi_id"] for item in search_response.json()["items"]] == [poi_ids[0]]

    diagnostics_response = client.get("/v1/admin/pois?search=Admin&has_diagnostics=true")
    assert diagnostics_response.status_code == 200
    assert [item["poi_id"] for item in diagnostics_response.json()["items"]] == [poi_ids[0]]

    overrides_response = client.get("/v1/admin/pois?search=Admin&has_editorial_overrides=true")
    assert overrides_response.status_code == 200
    assert [item["poi_id"] for item in overrides_response.json()["items"]] == [poi_ids[0]]

    combined_response = client.get(
        f"/v1/admin/pois?category={admin_poi_fixture['history_category']}"
        f"&source={source_ids[0]}&search=acequia&has_diagnostics=true"
    )
    assert combined_response.status_code == 200
    assert [item["poi_id"] for item in combined_response.json()["items"]] == [poi_ids[0]]

    theme_any_response = client.get(
        "/v1/admin/pois?search=Admin&theme=water,rail&theme_match=any"
    )
    assert theme_any_response.status_code == 200
    assert {item["poi_id"] for item in theme_any_response.json()["items"]} == set(poi_ids[:3])

    theme_all_response = client.get(
        "/v1/admin/pois?search=Admin&theme=water,rail&theme_match=all"
    )
    assert theme_all_response.status_code == 200
    assert [item["poi_id"] for item in theme_all_response.json()["items"]] == [poi_ids[2]]


def test_admin_poi_list_pagination_and_inactive_audit(
    admin_poi_fixture: dict[str, Any],
) -> None:
    stale_poi_id = admin_poi_fixture["poi_ids"][3]

    active_response = client.get("/v1/admin/pois?search=Admin&limit=2&offset=0")
    assert active_response.status_code == 200
    active_payload = active_response.json()
    assert active_payload["total"] == 3
    assert active_payload["limit"] == 2
    assert active_payload["offset"] == 0
    assert len(active_payload["items"]) == 2

    boundary_response = client.get("/v1/admin/pois?search=Admin&limit=2&offset=3")
    assert boundary_response.status_code == 200
    assert boundary_response.json()["items"] == []

    inactive_response = client.get(
        "/v1/admin/pois?search=Admin&active_only=false&limit=10&offset=0"
    )
    assert inactive_response.status_code == 200
    inactive_payload = inactive_response.json()
    assert inactive_payload["total"] == 4
    stale_items = [
        item for item in inactive_payload["items"] if item["poi_id"] == stale_poi_id
    ]
    assert stale_items
    assert stale_items[0]["is_active"] is False
    assert stale_items[0]["stale_since"] is not None


def test_admin_poi_detail_adds_admin_only_fields(
    admin_poi_fixture: dict[str, Any],
) -> None:
    poi_id = admin_poi_fixture["poi_ids"][0]

    public_response = client.get(f"/v1/poi/{poi_id}")
    admin_response = client.get(f"/v1/admin/pois/{poi_id}")

    assert public_response.status_code == 200
    assert admin_response.status_code == 200
    public_payload = public_response.json()
    admin_payload = admin_response.json()

    assert "editorial_overrides" not in public_payload
    assert "match_diagnostics" not in public_payload
    assert "raw_payload" not in public_payload["evidence"][0]

    assert admin_payload["canonical"]["poi_id"] == poi_id
    assert admin_payload["editorial_overrides"]["name"]["value"] == "Edited Acequia House"
    assert admin_payload["evidence"][0]["raw_payload"]["raw"] == "Admin Acequia House"
    assert admin_payload["match_diagnostics"][0]["state"] == "unreviewed"
    assert admin_payload["match_diagnostics"][0]["reviewer_notes"] == "Needs identity review."


def test_admin_poi_map_truncates_with_deterministic_order(
    admin_poi_fixture: dict[str, Any],
) -> None:
    poi_ids = admin_poi_fixture["poi_ids"]

    response = client.get("/v1/admin/pois/map?search=Admin&active_only=false&limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matching"] == 4
    assert payload["returned"] == 2
    assert payload["truncated"] is True
    returned_ids = [
        feature["properties"]["poi_id"]
        for feature in payload["feature_collection"]["features"]
    ]
    assert returned_ids == sorted(poi_ids)[:2]


def test_admin_poi_map_bbox_filter(
    admin_poi_fixture: dict[str, Any],
) -> None:
    poi_id = admin_poi_fixture["poi_ids"][0]

    response = client.get(
        "/v1/admin/pois/map?search=Admin&bbox=-105.94,35.67,-105.92,35.69"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matching"] == 1
    assert payload["returned"] == 1
    feature = payload["feature_collection"]["features"][0]
    assert feature["properties"]["poi_id"] == poi_id
