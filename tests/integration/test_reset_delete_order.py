from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from poi_curator_domain.db import (
    POI,
    IngestRun,
    OfficialMatchDiagnostic,
    POIAlias,
    POIEditorial,
    POIEvidence,
    POISignals,
    POISourceRaw,
    POIThemeEditorial,
    POIThemeMembership,
    POIThemeMembershipEvidence,
    SourceRegistry,
    ThemeDefinition,
    get_session_factory,
)
from poi_curator_domain.regions import RegionSpec
from poi_curator_ingestion.pipeline import (
    OSM_SOURCE_NAME,
    deactivate_stale_osm_pois,
    reset_osm_region,
)
from shapely.geometry import Point
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement


def test_osm_reset_clears_dependent_rows_without_orphans() -> None:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(text("select 1"))
    except OperationalError:
        pytest.skip("Local Postgres is not available for reset integration tests.")

    now = datetime.now(UTC)
    region_slug = f"reset-{uuid4().hex[:8]}"
    poi_id = str(uuid4())
    theme_slug = f"reset-theme-{uuid4().hex[:8]}"
    region = RegionSpec(
        slug=region_slug,
        name=region_slug,
        bbox=(35.0, -106.0, 36.0, -105.0),
        city=region_slug,
        region="new-mexico",
        country="usa",
    )

    with session_factory() as session:
        if session.get(SourceRegistry, OSM_SOURCE_NAME) is None:
            session.add(
                SourceRegistry(
                    source_id=OSM_SOURCE_NAME,
                    organization_name="OpenStreetMap contributors",
                    source_name="OpenStreetMap Overpass",
                    source_type="community_map",
                    trust_class="source_record",
                    base_url="https://www.openstreetmap.org",
                    license_notes="ODbL-1.0",
                    crawl_allowed=True,
                    ingest_method="overpass",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        session.add(
            ThemeDefinition(
                theme_slug=theme_slug,
                label="Reset Theme",
                description="Reset test theme.",
                region_scope=region_slug,
                is_active=True,
                is_query_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        poi = POI(
            poi_id=poi_id,
            canonical_name="Reset Test POI",
            slug=f"reset-test-poi-{region_slug}",
            geom=from_shape(Point(-105.94, 35.68), srid=4326),
            centroid=from_shape(Point(-105.94, 35.68), srid=4326),
            city=region_slug,
            region="new-mexico",
            country="usa",
            normalized_category="history",
            normalized_subcategory="historic_site",
            display_categories=["history"],
            short_description="Reset test point.",
            primary_source=OSM_SOURCE_NAME,
            osm_id="node/999999",
            raw_tag_summary_json={"name": "Reset Test POI"},
            historical_flag=True,
            cultural_flag=False,
            scenic_flag=False,
            infrastructure_flag=False,
            food_identity_flag=False,
            walk_affinity_hint=0.5,
            drive_affinity_hint=0.5,
            base_significance_score=5.0,
            quality_score=60.0,
            review_status="needs_review",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(poi)
        session.flush()
        ingest_run = IngestRun(
            source_name=OSM_SOURCE_NAME,
            region=region_slug,
            status="completed",
            started_at=now,
            completed_at=now,
        )
        session.add(ingest_run)
        session.flush()
        session.add_all(
            [
                POISourceRaw(
                    source_name=OSM_SOURCE_NAME,
                    source_record_id="node/999999",
                    source_url="https://www.openstreetmap.org/node/999999",
                    raw_payload_json={"type": "node", "id": 999999, "tags": {"name": "Reset"}},
                    geom=from_shape(Point(-105.94, 35.68), srid=4326),
                    fetched_at=now,
                    content_hash="reset-test",
                    is_current=True,
                    license="ODbL-1.0",
                    ingest_run_id=ingest_run.id,
                    canonical_poi_id=poi_id,
                ),
                POIEditorial(poi_id=poi_id, editorial_status="needs_review", editorial_boost=0),
                POISignals(poi_id=poi_id, computed_at=now),
                POIAlias(
                    poi_id=poi_id,
                    alias_name="Reset Alias",
                    normalized_alias="reset alias",
                    alias_type="historic",
                    source="test",
                    confidence=0.9,
                    is_preferred=False,
                    created_at=now,
                ),
                POIThemeEditorial(
                    poi_id=poi_id,
                    theme_slug=theme_slug,
                    editorial_decision="include",
                    reviewed_by="integration-test",
                    reviewed_at=now,
                ),
                OfficialMatchDiagnostic(
                    source_id=OSM_SOURCE_NAME,
                    region=region_slug,
                    external_record_id="node/999999",
                    external_name="Reset Test POI",
                    matched_poi_id=poi_id,
                    status="unreviewed",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        evidence = POIEvidence(
            evidence_key=f"reset-test-{poi_id}",
            poi_id=poi_id,
            source_id=OSM_SOURCE_NAME,
            evidence_type="identity_link",
            evidence_label="Reset evidence",
            external_record_id="node/999999",
            confidence=0.8,
            observed_at=now,
        )
        session.add(evidence)
        session.flush()
        membership = POIThemeMembership(
            poi_id=poi_id,
            theme_slug=theme_slug,
            status="candidate",
            assignment_basis="computed",
            confidence=0.8,
            computed_at=now,
        )
        session.add(membership)
        session.flush()
        session.add(
            POIThemeMembershipEvidence(
                membership_id=membership.id,
                poi_evidence_id=evidence.id,
                contribution_type="supporting",
                weight=1.0,
            )
        )
        evidence_id = evidence.id
        membership_id = membership.id
        session.commit()

    with session_factory() as session:
        reset_osm_region(session, region)

    with session_factory() as session:
        assert count_rows(session, POI, POI.poi_id == poi_id) == 0
        assert count_rows(session, POISourceRaw, POISourceRaw.canonical_poi_id == poi_id) == 0
        assert count_rows(session, POIEvidence, POIEvidence.poi_id == poi_id) == 0
        assert count_rows(session, POIAlias, POIAlias.poi_id == poi_id) == 0
        assert count_rows(session, POIThemeMembership, POIThemeMembership.poi_id == poi_id) == 0
        assert count_rows(session, POIThemeEditorial, POIThemeEditorial.poi_id == poi_id) == 0
        assert (
            count_rows(
                session,
                OfficialMatchDiagnostic,
                OfficialMatchDiagnostic.matched_poi_id == poi_id,
            )
            == 0
        )
        assert (
            count_rows(
                session,
                POIThemeMembershipEvidence,
                (POIThemeMembershipEvidence.poi_evidence_id == evidence_id)
                | (POIThemeMembershipEvidence.membership_id == membership_id),
            )
            == 0
        )
        session.execute(delete(ThemeDefinition).where(ThemeDefinition.theme_slug == theme_slug))
        session.commit()


def test_deactivate_stale_osm_pois_marks_missing_current_batch_inactive() -> None:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(text("select 1"))
    except OperationalError:
        pytest.skip("Local Postgres is not available for stale OSM integration tests.")

    now = datetime.now(UTC)
    region_slug = f"stale-{uuid4().hex[:8]}"
    current_poi_id = str(uuid4())
    stale_poi_id = str(uuid4())
    region = RegionSpec(
        slug=region_slug,
        name=region_slug,
        bbox=(35.0, -106.0, 36.0, -105.0),
        city=region_slug,
        region="new-mexico",
        country="usa",
    )

    with session_factory() as session:
        if session.get(SourceRegistry, OSM_SOURCE_NAME) is None:
            session.add(
                SourceRegistry(
                    source_id=OSM_SOURCE_NAME,
                    organization_name="OpenStreetMap contributors",
                    source_name="OpenStreetMap Overpass",
                    source_type="community_map",
                    trust_class="source_record",
                    base_url="https://www.openstreetmap.org",
                    license_notes="ODbL-1.0",
                    crawl_allowed=True,
                    ingest_method="overpass",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        session.add_all(
            [
                build_test_osm_poi(current_poi_id, region_slug, "node/current", now),
                build_test_osm_poi(stale_poi_id, region_slug, "node/stale", now),
            ]
        )
        session.commit()

    with session_factory() as session:
        deactivated = deactivate_stale_osm_pois(session, region, {"node/current"})
        session.commit()

    with session_factory() as session:
        current_poi = session.get(POI, current_poi_id)
        stale_poi = session.get(POI, stale_poi_id)
        assert deactivated == 1
        assert current_poi is not None
        assert current_poi.is_active is True
        assert stale_poi is not None
        assert stale_poi.is_active is False
        assert stale_poi.review_status == "stale"
        session.execute(delete(POI).where(POI.poi_id.in_([current_poi_id, stale_poi_id])))
        session.commit()


def build_test_osm_poi(
    poi_id: str,
    region_slug: str,
    osm_id: str,
    now: datetime,
) -> POI:
    return POI(
        poi_id=poi_id,
        canonical_name=f"Test {osm_id}",
        slug=f"test-{poi_id}",
        geom=from_shape(Point(-105.94, 35.68), srid=4326),
        centroid=from_shape(Point(-105.94, 35.68), srid=4326),
        city=region_slug,
        region="new-mexico",
        country="usa",
        normalized_category="history",
        normalized_subcategory="historic_site",
        display_categories=["history"],
        short_description="Stale test point.",
        primary_source=OSM_SOURCE_NAME,
        osm_id=osm_id,
        raw_tag_summary_json={"name": f"Test {osm_id}"},
        historical_flag=True,
        cultural_flag=False,
        scenic_flag=False,
        infrastructure_flag=False,
        food_identity_flag=False,
        walk_affinity_hint=0.5,
        drive_affinity_hint=0.5,
        base_significance_score=5.0,
        quality_score=60.0,
        review_status="needs_review",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def count_rows(session: Session, model: type[Any], predicate: ColumnElement[bool]) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(predicate)) or 0)
