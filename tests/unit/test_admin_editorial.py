from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import TypedDict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from poi_curator_api.main import app
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIAlias,
    POIEvidence,
    POISignals,
    SourceRegistry,
    get_session_factory,
)
from poi_curator_enrichment.historic_register import NM_STATE_REGISTER_SOURCE_ID
from shapely.geometry import Point
from sqlalchemy import delete, text
from sqlalchemy.exc import OperationalError

client = TestClient(app)


class EditorialCase(TypedDict):
    poi_id: str
    poi_name: str
    diagnostic_id: int
    region: str


class EditorialDBFixture(TypedDict):
    create_case: Callable[..., EditorialCase]


@pytest.fixture
def editorial_db() -> Iterator[EditorialDBFixture]:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(text("select 1"))
    except OperationalError:
        pytest.skip("Local Postgres is not available for editorial integration tests.")

    created_poi_ids: list[str] = []
    created_diagnostic_ids: list[int] = []
    created_source = False

    with session_factory() as session:
        if session.get(SourceRegistry, NM_STATE_REGISTER_SOURCE_ID) is None:
            now = datetime.now(UTC)
            session.add(
                SourceRegistry(
                    source_id=NM_STATE_REGISTER_SOURCE_ID,
                    organization_name="Test Source",
                    source_name="Test State Register",
                    source_type="historic_register_workbook",
                    trust_class="official_state_register",
                    base_url=None,
                    license_notes=None,
                    crawl_allowed=False,
                    ingest_method="test",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            created_source = True
            session.commit()

    def create_case(*, external_name: str, other_names: str | None = None) -> EditorialCase:
        suffix = uuid4().hex[:8]
        poi_id = str(uuid4())
        slug = f"editorial-test-{suffix}"
        region = f"test-city-{suffix}"
        now = datetime.now(UTC)
        with session_factory() as session:
            poi = POI(
                poi_id=poi_id,
                canonical_name=f"Editorial Test House {suffix}",
                slug=slug,
                geom=from_shape(Point(-105.93, 35.68), srid=4326),
                centroid=from_shape(Point(-105.93, 35.68), srid=4326),
                city=region,
                region=region,
                country="USA",
                normalized_category="history",
                normalized_subcategory="historic_site",
                display_categories=["history"],
                short_description="Test historic site.",
                primary_source="test",
                raw_tag_summary_json={},
                historical_flag=True,
                cultural_flag=False,
                scenic_flag=False,
                infrastructure_flag=False,
                food_identity_flag=False,
                walk_affinity_hint=0.8,
                drive_affinity_hint=0.7,
                base_significance_score=0.7,
                quality_score=0.8,
                review_status="needs_review",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(poi)
            session.add(
                POISignals(
                    poi_id=poi_id,
                    source_count=1,
                    has_wikidata=False,
                    has_wikipedia=False,
                    has_official_heritage_match=False,
                    official_corroboration_score=0.0,
                    district_membership_score=0.0,
                    institutional_identity_score=0.0,
                    osm_tag_richness=0.2,
                    description_quality=0.6,
                    entity_type_confidence=0.7,
                    local_identity_score=0.5,
                    interpretive_value_score=0.6,
                    genericity_penalty=0.0,
                    editorial_priority_seed=0.0,
                    computed_at=now,
                )
            )
            session.flush()
            diagnostic = OfficialMatchDiagnostic(
                source_id=NM_STATE_REGISTER_SOURCE_ID,
                region=region,
                external_record_id=f"diag-{suffix}",
                external_name=external_name,
                matched_poi_id=None,
                resolved_poi_id=None,
                best_candidate_name=None,
                best_similarity=None,
                match_strategy=None,
                status="unreviewed",
                resolution_method=None,
                raw_payload_json={
                    "state": "NEW MEXICO",
                    "county": "Santa Fe",
                    "city": region,
                    "street_address": "123 Test St",
                    "category_of_property": "BUILDING",
                    "listed_date": "1966",
                    "other_names": other_names,
                    "state_register_year": "1967",
                },
                reviewed_at=None,
                reviewed_by=None,
                created_at=now,
                updated_at=now,
            )
            session.add(diagnostic)
            session.commit()
            created_poi_ids.append(poi_id)
            created_diagnostic_ids.append(diagnostic.id)
            return {
                "poi_id": poi_id,
                "poi_name": poi.canonical_name,
                "diagnostic_id": diagnostic.id,
                "region": region,
            }

    yield {"create_case": create_case}

    with session_factory() as session:
        if created_diagnostic_ids:
            session.execute(
                delete(OfficialMatchDiagnostic).where(
                    OfficialMatchDiagnostic.id.in_(created_diagnostic_ids)
                )
            )
        if created_poi_ids:
            session.execute(delete(POIEvidence).where(POIEvidence.poi_id.in_(created_poi_ids)))
            session.execute(delete(POIAlias).where(POIAlias.poi_id.in_(created_poi_ids)))
            session.execute(delete(POISignals).where(POISignals.poi_id.in_(created_poi_ids)))
            session.execute(delete(POI).where(POI.poi_id.in_(created_poi_ids)))
        if created_source:
            session.execute(
                delete(SourceRegistry).where(
                    SourceRegistry.source_id == NM_STATE_REGISTER_SOURCE_ID
                )
            )
        session.commit()


def test_resolve_diagnostic_row_to_poi(editorial_db: EditorialDBFixture) -> None:
    case = editorial_db["create_case"](external_name="Resolve House Variant")

    response = client.post(
        f"/v1/admin/match-diagnostics/{case['diagnostic_id']}/resolve",
        json={"poi_id": case["poi_id"], "reviewed_by": "tester"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["resolution_method"] == "manual_link"
    assert payload["resolved_poi_id"] == case["poi_id"]

    with get_session_factory()() as session:
        diagnostic = session.get(OfficialMatchDiagnostic, case["diagnostic_id"])
        assert diagnostic is not None
        assert diagnostic.status == "resolved"
        assert diagnostic.reviewed_by == "tester"
        evidence = session.execute(
            text(
                "select raw_evidence_json->>'match_strategy' from poi_evidence "
                "where poi_id = :poi_id and source_id = :source_id"
            ),
            {"poi_id": case["poi_id"], "source_id": NM_STATE_REGISTER_SOURCE_ID},
        ).scalar_one()
        assert evidence == "manual_link"


def test_create_alias_from_diagnostic_row(editorial_db: EditorialDBFixture) -> None:
    case = editorial_db["create_case"](external_name="Oldest Editorial House")

    response = client.post(
        f"/v1/admin/match-diagnostics/{case['diagnostic_id']}/alias",
        json={"poi_id": case["poi_id"], "reviewed_by": "tester"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["resolution_method"] == "manual_alias"

    with get_session_factory()() as session:
        alias = session.execute(
            text(
                "select alias_name from poi_alias "
                "where poi_id = :poi_id and source = 'manual_diagnostic_resolution'"
            ),
            {"poi_id": case["poi_id"]},
        ).scalar_one()
        assert alias == "Oldest Editorial House"


def test_suppress_diagnostic_row(editorial_db: EditorialDBFixture) -> None:
    case = editorial_db["create_case"](external_name="Suppress Me")

    response = client.post(
        f"/v1/admin/match-diagnostics/{case['diagnostic_id']}/suppress",
        json={"reviewed_by": "tester"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "suppressed"
    assert payload["resolution_method"] == "suppressed"

    with get_session_factory()() as session:
        diagnostic = session.get(OfficialMatchDiagnostic, case["diagnostic_id"])
        assert diagnostic is not None
        assert diagnostic.status == "suppressed"
        evidence_count = session.execute(
            text("select count(*) from poi_evidence where poi_id = :poi_id"),
            {"poi_id": case["poi_id"]},
        ).scalar_one()
        assert evidence_count == 0


def test_add_alias_directly_to_poi(editorial_db: EditorialDBFixture) -> None:
    case = editorial_db["create_case"](external_name="Direct Alias Placeholder")

    response = client.post(
        f"/v1/admin/poi/{case['poi_id']}/aliases",
        json={"alias_name": "Manual Editorial Alias", "alias_type": "common", "notes": "manual"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] is True
    assert payload["alias"]["alias_name"] == "Manual Editorial Alias"


def test_resolved_and_suppressed_diagnostics_do_not_show_as_unreviewed(
    editorial_db: EditorialDBFixture,
) -> None:
    resolved_case = editorial_db["create_case"](external_name="Resolved Variant")
    suppressed_case = editorial_db["create_case"](external_name="Suppressed Variant")

    client.post(
        f"/v1/admin/match-diagnostics/{resolved_case['diagnostic_id']}/resolve",
        json={"poi_id": resolved_case["poi_id"], "reviewed_by": "tester"},
    )
    client.post(
        f"/v1/admin/match-diagnostics/{suppressed_case['diagnostic_id']}/suppress",
        json={"reviewed_by": "tester"},
    )

    unresolved = client.get(f"/v1/admin/match-diagnostics?region={resolved_case['region']}")
    assert unresolved.status_code == 200
    unresolved_ids = {item["id"] for item in unresolved.json()}
    assert resolved_case["diagnostic_id"] not in unresolved_ids

    unresolved = client.get(f"/v1/admin/match-diagnostics?region={suppressed_case['region']}")
    assert unresolved.status_code == 200
    unresolved_ids = {item["id"] for item in unresolved.json()}
    assert suppressed_case["diagnostic_id"] not in unresolved_ids


def test_evidence_history_remains_visible_after_manual_alias_resolution(
    editorial_db: EditorialDBFixture,
) -> None:
    case = editorial_db["create_case"](external_name="Visible Provenance Alias")

    response = client.post(
        f"/v1/admin/match-diagnostics/{case['diagnostic_id']}/alias",
        json={"poi_id": case["poi_id"], "reviewed_by": "tester"},
    )
    assert response.status_code == 200

    evidence_response = client.get(f"/v1/admin/poi/{case['poi_id']}/evidence")
    assert evidence_response.status_code == 200
    payload = evidence_response.json()
    assert any(alias["alias_name"] == "Visible Provenance Alias" for alias in payload["aliases"])
    assert any(
        item["source_id"] == NM_STATE_REGISTER_SOURCE_ID and item["match_method"] == "manual_alias"
        for item in payload["evidence"]
    )
