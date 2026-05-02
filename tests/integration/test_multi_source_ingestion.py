from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIEditorial,
    POIEvidence,
    POIFieldProvenance,
    POIMatchLog,
    POISignals,
    POISourceRaw,
    get_session_factory,
)
from poi_curator_ingestion.sources.nrhp import ingest_nrhp_records
from poi_curator_ingestion.sources.sf_arcgis import ingest_historic_district_memberships
from shapely.geometry import Point, Polygon, mapping
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError

TEST_NRHP_REFS = ("test-nrhp-100001", "test-nrhp-100002")


@pytest.fixture
def multi_source_region() -> Iterator[str]:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(text("select 1"))
            session.execute(text("select 1 from poi_field_provenance limit 1"))
    except (OperationalError, ProgrammingError):
        pytest.skip("Local Postgres with latest migrations is not available.")

    region = f"multi-source-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    existing_poi_id = str(uuid4())
    with session_factory() as session:
        session.add(
            POI(
                poi_id=existing_poi_id,
                canonical_name="Palace of the Governors",
                slug=f"palace-{region}",
                geom=from_shape(Point(-105.9383, 35.6878), srid=4326),
                centroid=from_shape(Point(-105.9383, 35.6878), srid=4326),
                city=region,
                region="New Mexico",
                country="US",
                normalized_category="history",
                display_categories=["history"],
                short_description="Existing OSM-backed description.",
                primary_source="osm_overpass",
                historical_flag=True,
                cultural_flag=True,
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
        )
        session.add(POISignals(poi_id=existing_poi_id, computed_at=now))
        session.commit()

    try:
        yield region
    finally:
        with session_factory() as session:
            session.execute(
                delete(POIMatchLog).where(
                    POIMatchLog.candidate_source == "nrhp",
                    POIMatchLog.candidate_external_id.in_(TEST_NRHP_REFS),
                )
            )
            poi_ids = session.scalars(select(POI.poi_id).where(POI.city == region)).all()
            if poi_ids:
                session.execute(delete(POIMatchLog).where(POIMatchLog.canonical_poi_id.in_(poi_ids)))
                session.execute(
                    delete(POIFieldProvenance).where(POIFieldProvenance.poi_id.in_(poi_ids))
                )
                session.execute(
                    delete(OfficialMatchDiagnostic).where(
                        OfficialMatchDiagnostic.matched_poi_id.in_(poi_ids)
                    )
                )
                session.execute(
                    delete(POISourceRaw).where(POISourceRaw.canonical_poi_id.in_(poi_ids))
                )
                session.execute(delete(POIEvidence).where(POIEvidence.poi_id.in_(poi_ids)))
                session.execute(delete(POIEditorial).where(POIEditorial.poi_id.in_(poi_ids)))
                session.execute(delete(POISignals).where(POISignals.poi_id.in_(poi_ids)))
                session.execute(delete(POI).where(POI.poi_id.in_(poi_ids)))
            session.commit()


def test_nrhp_ingest_creates_canonicals_evidence_provenance_and_match_logs(
    multi_source_region: str,
) -> None:
    rows = [
        {
            "Ref#": TEST_NRHP_REFS[0],
            "Property Name": "Palace of the Governors",
            "State": "NEW MEXICO",
            "County": "Santa Fe",
            "City": "Santa Fe",
            "Latitude": "35.68782",
            "Longitude": "-105.93832",
            "Listed Date": "10/15/1966",
        },
        {
            "Ref#": TEST_NRHP_REFS[1],
            "Property Name": "Fixture Listed House",
            "State": "NEW MEXICO",
            "County": "Santa Fe",
            "City": "Santa Fe",
            "Latitude": "35.6812",
            "Longitude": "-105.9221",
            "Listed Date": "1/1/1980",
        },
    ]

    with get_session_factory()() as session:
        summary = ingest_nrhp_records(session, multi_source_region, row_loader=lambda: rows)

    assert summary.canonical_created == 1
    assert summary.evidence_attached == 2
    with get_session_factory()() as session:
        pois = session.scalars(select(POI).where(POI.city == multi_source_region)).all()
        assert len(pois) == 2
        nrhp_evidence = session.scalar(select(POIEvidence).where(POIEvidence.source_id == "nrhp"))
        nrhp_provenance = session.scalar(
            select(POIFieldProvenance).where(POIFieldProvenance.source_id == "nrhp")
        )
        assert nrhp_evidence is not None
        assert nrhp_provenance is not None
        assert session.scalar(select(POIMatchLog).where(POIMatchLog.candidate_source == "nrhp"))


def test_city_historic_district_ingest_attaches_membership_evidence(
    multi_source_region: str,
) -> None:
    polygon = Polygon(
        [
            (-105.94, 35.687),
            (-105.937, 35.687),
            (-105.937, 35.689),
            (-105.94, 35.689),
            (-105.94, 35.687),
        ]
    )
    payload = {
        "features": [
            {
                "id": "1",
                "properties": {"OBJECTID": 1, "HBDIST": "Downtown Historic District"},
                "geometry": mapping(polygon),
            }
        ]
    }

    with get_session_factory()() as session:
        summary = ingest_historic_district_memberships(
            session,
            multi_source_region,
            feature_loader=lambda: payload,
        )

    assert summary.evidence_created == 1
    with get_session_factory()() as session:
        evidence = session.scalar(
            select(POIEvidence).where(POIEvidence.evidence_type == "district_membership")
        )
        assert evidence is not None
        assert evidence.source_id == "city_gis_historic_districts"
