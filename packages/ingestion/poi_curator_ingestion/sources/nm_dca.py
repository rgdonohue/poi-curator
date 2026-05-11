from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import orjson
from geoalchemy2.shape import from_shape
from poi_curator_domain.db import (
    POI,
    POIEvidence,
    POIMatchLog,
    POISignals,
    POISourceRaw,
    SourceRegistry,
)
from poi_curator_domain.descriptions import description_quality_score
from poi_curator_domain.provenance import record_canonical_provenance, record_sourced_field_values
from poi_curator_domain.text import slugify
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from poi_curator_ingestion.matching import IncomingSourceRecord, match_incoming_record
from poi_curator_ingestion.pipeline import ensure_editorial_stub

NM_DCA_SOURCE_ID = "nm_dca"
DCA_CULTUREPASS_URL = "https://www.dca.nm.gov/visit/culturepass"
DCA_ABOUT_URL = "https://www.dca.nm.gov/about"
DCA_LICENSE_NOTES = (
    "Public New Mexico Department of Cultural Affairs museum and historic-site listings; "
    "bootstrap coordinates are maintained manually from public institution pages."
)
SANTA_FE_REGION = "santa-fe"

DCA_RECORD_TYPE_POLICY: dict[str, frozenset[str]] = {
    # Public visitor-facing institutions are stop-shaped enough to create a canonical if unmatched.
    "canonical_create": frozenset({"state_museum", "museum_campus", "historic_site"}),
    # Administrative programs/divisions are useful context but not automatic Detour stops.
    "evidence_only": frozenset({"administrative_division", "program"}),
}

BOOTSTRAP_DCA_ROWS: tuple[dict[str, Any], ...] = (
    {
        "external_id": "nm-dca-history-museum",
        "name": "New Mexico History Museum",
        "record_type": "state_museum",
        "division": "New Mexico History Museum",
        "city": "Santa Fe",
        "address": "113 Lincoln Avenue, Santa Fe, NM 87501",
        "lon": -105.9380178,
        "lat": 35.6882912,
        "source_url": "https://www.nmhistorymuseum.org/",
    },
    {
        "external_id": "nm-dca-palace-of-the-governors",
        "name": "Palace of the Governors",
        "record_type": "historic_site",
        "division": "New Mexico History Museum",
        "city": "Santa Fe",
        "address": "Palace Avenue at Santa Fe Plaza, Santa Fe, NM",
        "lon": -105.9381526,
        "lat": 35.6879138,
        "source_url": "https://www.nmhistorymuseum.org/about/campus/the-palace-of-the-governors.html",
    },
    {
        "external_id": "nm-dca-museum-of-art-plaza",
        "name": "New Mexico Museum of Art",
        "record_type": "state_museum",
        "division": "New Mexico Museum of Art",
        "campus": "Plaza Building",
        "city": "Santa Fe",
        "address": "107 West Palace Avenue, Santa Fe, NM 87501",
        "lon": -105.9391366,
        "lat": 35.6882471,
        "source_url": "https://www.nmartmuseum.org/",
    },
    {
        "external_id": "nm-dca-vladem-contemporary",
        "name": "New Mexico Museum of Art - Vladem Contemporary",
        "record_type": "museum_campus",
        "division": "New Mexico Museum of Art",
        "campus": "Vladem Contemporary",
        "city": "Santa Fe",
        "address": "404 Montezuma Ave, Santa Fe, NM 87501",
        "lon": -105.946334,
        "lat": 35.684194,
        "source_url": "https://www.nmartmuseum.org/about-us/contact/",
    },
    {
        "external_id": "nm-dca-international-folk-art",
        "name": "Museum of International Folk Art",
        "record_type": "state_museum",
        "division": "Museum of International Folk Art",
        "city": "Santa Fe",
        "address": "706 Camino Lejo, Santa Fe, NM 87505",
        "lon": -105.926534,
        "lat": 35.6640565,
        "source_url": "https://www.internationalfolkart.org/about/contact-us.html",
    },
    {
        "external_id": "nm-dca-indian-arts-culture",
        "name": "Museum of Indian Arts and Culture",
        "record_type": "state_museum",
        "division": "Museum of Indian Arts and Culture",
        "city": "Santa Fe",
        "address": "710 Camino Lejo, Santa Fe, NM 87505",
        "lon": -105.9248451,
        "lat": 35.665089,
        "source_url": "https://www.indianartsandculture.org/contact-us/",
    },
)


@dataclass(frozen=True)
class DCAInstitutionRecord:
    external_id: str
    name: str
    record_type: str
    division: str | None
    campus: str | None
    city: str
    address: str | None
    lon: float | None
    lat: float | None
    source_url: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class DCAIngestSummary:
    region: str
    candidate_record_count: int
    canonical_created: int
    evidence_attached: int
    ambiguous_count: int
    skipped_without_coordinates: int
    skipped_evidence_only_unmatched: int


def load_bootstrap_dca_rows() -> list[dict[str, Any]]:
    """Return the manually maintained Santa Fe DCA bootstrap list.

    DCA publishes a structured-enough public CulturePass/listing page, but no coordinate-bearing
    CSV/ArcGIS feed was found during 2026-05 source discovery. The small Santa Fe institutional
    set is therefore maintained as bootstrap records with source URLs for annual manual refresh.
    """
    return [dict(row) for row in BOOTSTRAP_DCA_ROWS]


def ingest_dca_records(
    session: Session,
    region: str,
    *,
    row_loader: Callable[[], list[dict[str, Any]]] | None = None,
) -> DCAIngestSummary:
    rows = row_loader() if row_loader is not None else load_bootstrap_dca_rows()
    records = filter_dca_records(parse_dca_records(rows), region=region)
    ensure_dca_source_registry(session)

    canonical_created = 0
    evidence_attached = 0
    ambiguous_count = 0
    skipped_without_coordinates = 0
    skipped_evidence_only_unmatched = 0

    for record in records:
        if record.lon is None or record.lat is None:
            skipped_without_coordinates += 1
            continue
        persist_dca_raw_record(session, record)
        match_result = match_incoming_record(
            session,
            IncomingSourceRecord(
                source_id=NM_DCA_SOURCE_ID,
                external_id=record.external_id,
                name=record.name,
                lon=record.lon,
                lat=record.lat,
                region=region,
                raw_payload=record.raw_payload,
            ),
            decided_by="ingest:nm_dca",
        )
        if match_result.decision == "ambiguous":
            ambiguous_count += 1
            continue
        if match_result.poi is None and not should_create_canonical(record):
            skipped_evidence_only_unmatched += 1
            continue
        if match_result.poi is None:
            poi = create_dca_canonical_poi(session, record, region)
            canonical_created += 1
            record_canonical_provenance(
                session,
                poi,
                source_id=NM_DCA_SOURCE_ID,
                confidence=0.9,
                observed_at=datetime.now(UTC),
            )
            session.add(
                POIMatchLog(
                    canonical_poi_id=poi.poi_id,
                    candidate_source=NM_DCA_SOURCE_ID,
                    candidate_external_id=record.external_id,
                    match_strategy=match_result.strategy,
                    match_score=match_result.score,
                    decision="new",
                    decided_at=datetime.now(UTC),
                    decided_by="ingest:nm_dca",
                    notes="Canonical POI created for unmatched DCA institution record.",
                )
            )
        else:
            poi = match_result.poi

        upsert_dca_evidence(session, poi.poi_id, record)
        record_sourced_field_values(
            session,
            poi_id=poi.poi_id,
            source_id=NM_DCA_SOURCE_ID,
            values=field_values_for_record(record),
            confidence=0.9,
            observed_at=datetime.now(UTC),
        )
        if poi.signals is not None:
            poi.signals.institutional_identity_score = max(
                poi.signals.institutional_identity_score,
                0.9,
            )
            poi.signals.source_count = max(poi.signals.source_count, 2)
            poi.signals.computed_at = datetime.now(UTC)
        evidence_attached += 1

    session.commit()
    return DCAIngestSummary(
        region=region,
        candidate_record_count=len(records),
        canonical_created=canonical_created,
        evidence_attached=evidence_attached,
        ambiguous_count=ambiguous_count,
        skipped_without_coordinates=skipped_without_coordinates,
        skipped_evidence_only_unmatched=skipped_evidence_only_unmatched,
    )


def parse_dca_records(rows: Iterable[dict[str, Any]]) -> list[DCAInstitutionRecord]:
    records: list[DCAInstitutionRecord] = []
    for row in rows:
        external_id = first_value(row, "external_id", "id")
        name = first_value(row, "name", "institution_name")
        record_type = first_value(row, "record_type", "type")
        if not external_id or not name or not record_type:
            continue
        raw_payload = {str(key): value for key, value in row.items()}
        records.append(
            DCAInstitutionRecord(
                external_id=external_id,
                name=name,
                record_type=record_type,
                division=first_value(row, "division") or None,
                campus=first_value(row, "campus") or None,
                city=first_value(row, "city") or "Santa Fe",
                address=first_value(row, "address") or None,
                lon=parse_float(first_value(row, "lon", "longitude", "x")),
                lat=parse_float(first_value(row, "lat", "latitude", "y")),
                source_url=first_value(row, "source_url", "url") or DCA_CULTUREPASS_URL,
                raw_payload=raw_payload,
            )
        )
    return records


def filter_dca_records(
    records: Iterable[DCAInstitutionRecord],
    *,
    region: str,
) -> list[DCAInstitutionRecord]:
    if region != SANTA_FE_REGION:
        return []
    return [record for record in records if record.city.strip().casefold() == "santa fe"]


def should_create_canonical(record: DCAInstitutionRecord) -> bool:
    return (
        record.record_type in DCA_RECORD_TYPE_POLICY["canonical_create"]
        and record.lon is not None
        and record.lat is not None
    )


def create_dca_canonical_poi(session: Session, record: DCAInstitutionRecord, region: str) -> POI:
    now = datetime.now(UTC)
    point = Point(record.lon, record.lat)
    category, subcategory = category_for_record(record)
    poi = POI(
        canonical_name=record.name,
        slug=unique_slug(session, f"{record.name}-{NM_DCA_SOURCE_ID}-{record.external_id}"),
        geom=from_shape(point, srid=4326),
        centroid=from_shape(point, srid=4326),
        city=region,
        region="New Mexico",
        country="US",
        normalized_category=category,
        normalized_subcategory=subcategory,
        display_categories=[category],
        short_description=description_for_record(record),
        primary_source=NM_DCA_SOURCE_ID,
        raw_tag_summary_json={
            "source": NM_DCA_SOURCE_ID,
            "external_id": record.external_id,
            "record_type": record.record_type,
            "division": record.division,
            "campus": record.campus,
        },
        historical_flag=record.record_type == "historic_site",
        cultural_flag=True,
        scenic_flag=False,
        infrastructure_flag=False,
        food_identity_flag=False,
        walk_affinity_hint=0.55,
        drive_affinity_hint=0.55,
        base_significance_score=6.0,
        quality_score=70.0,
        review_status="needs_review",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(poi)
    session.flush()
    session.add(
        POISignals(
            poi_id=poi.poi_id,
            source_count=1,
            has_official_heritage_match=record.record_type == "historic_site",
            official_corroboration_score=0.7 if record.record_type == "historic_site" else 0.4,
            district_membership_score=0.0,
            institutional_identity_score=1.0,
            description_quality=description_quality_score(
                poi.short_description,
                poi.normalized_subcategory,
            ),
            entity_type_confidence=0.85,
            local_identity_score=0.7,
            interpretive_value_score=0.65,
            genericity_penalty=0.05,
            editorial_priority_seed=0.6,
            computed_at=now,
        )
    )
    ensure_editorial_stub(session, poi)
    return poi


def upsert_dca_evidence(session: Session, poi_id: str, record: DCAInstitutionRecord) -> bool:
    key = evidence_key(poi_id, "dca_institution_membership", record.external_id)
    evidence = pending_evidence_by_key(session, key) or session.scalar(
        select(POIEvidence).where(POIEvidence.evidence_key == key)
    )
    created = evidence is None
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=NM_DCA_SOURCE_ID,
            evidence_type="dca_institution_membership",
            external_record_id=record.external_id,
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
    evidence.evidence_label = record.name
    evidence.evidence_text = evidence_text_for_record(record)
    evidence.evidence_url = record.source_url
    evidence.confidence = 0.9
    evidence.raw_evidence_json = evidence_payload(record)
    evidence.observed_at = datetime.now(UTC)
    return created


def persist_dca_raw_record(session: Session, record: DCAInstitutionRecord) -> None:
    content_hash = sha256(orjson.dumps(record.raw_payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
    existing = session.scalar(
        select(POISourceRaw).where(
            POISourceRaw.source_name == NM_DCA_SOURCE_ID,
            POISourceRaw.source_record_id == record.external_id,
            POISourceRaw.is_current.is_(True),
        )
    )
    now = datetime.now(UTC)
    if existing is not None and existing.content_hash == content_hash:
        existing.fetched_at = now
        return
    if existing is not None:
        existing.is_current = False
    session.add(
        POISourceRaw(
            source_name=NM_DCA_SOURCE_ID,
            source_record_id=record.external_id,
            source_url=record.source_url,
            raw_payload_json=record.raw_payload,
            geom=from_shape(Point(record.lon, record.lat), srid=4326),
            fetched_at=now,
            content_hash=content_hash,
            is_current=True,
            license=DCA_LICENSE_NOTES[:128],
        )
    )


def ensure_dca_source_registry(session: Session) -> None:
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, NM_DCA_SOURCE_ID)
    if source is None:
        session.add(
            SourceRegistry(
                source_id=NM_DCA_SOURCE_ID,
                organization_name="New Mexico Department of Cultural Affairs",
                source_name="DCA State Museums and Historic Sites",
                source_type="official_institution_list",
                trust_class="official_cultural_institution",
                base_url=DCA_CULTUREPASS_URL,
                license_notes=DCA_LICENSE_NOTES,
                crawl_allowed=True,
                ingest_method="manual_bootstrap",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        return
    source.updated_at = now
    source.is_active = True


def field_values_for_record(record: DCAInstitutionRecord) -> dict[str, Any]:
    category, _ = category_for_record(record)
    return {
        "name": record.name,
        "primary_category": category,
        "coordinates": {"lon": round(float(record.lon), 7), "lat": round(float(record.lat), 7)}
        if record.lon is not None and record.lat is not None
        else None,
        "short_description": description_for_record(record),
        "dca_record_type": record.record_type,
        "dca_division": record.division,
        "campus": record.campus,
        "street_address": record.address,
    }


def evidence_payload(record: DCAInstitutionRecord) -> dict[str, Any]:
    return {
        "external_id": record.external_id,
        "record_type": record.record_type,
        "division": record.division,
        "campus": record.campus,
        "city": record.city,
        "address": record.address,
        "coordinates": {"lon": record.lon, "lat": record.lat},
        "source_url": record.source_url,
    }


def evidence_text_for_record(record: DCAInstitutionRecord) -> str:
    if record.record_type == "historic_site":
        return "Listed by New Mexico DCA as a state historic-site institution."
    if record.campus:
        return f"Listed by New Mexico DCA as part of {record.division}."
    return "Listed by New Mexico DCA as a state museum or cultural institution."


def description_for_record(record: DCAInstitutionRecord) -> str:
    if record.record_type == "historic_site":
        return "New Mexico Department of Cultural Affairs historic-site institution."
    return "New Mexico Department of Cultural Affairs museum institution."


def category_for_record(record: DCAInstitutionRecord) -> tuple[str, str]:
    if record.record_type == "historic_site":
        return "history", "historic_site"
    return "culture", "museum"


def pending_evidence_by_key(session: Session, key: str) -> POIEvidence | None:
    for item in getattr(session, "new", []):
        if isinstance(item, POIEvidence) and item.evidence_key == key:
            return item
    return None


def evidence_key(poi_id: str, evidence_type: str, external_id: str) -> str:
    return slugify(f"{poi_id}:{NM_DCA_SOURCE_ID}:{evidence_type}:{external_id}")[:255]


def first_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def parse_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def unique_slug(session: Session, value: str) -> str:
    base = slugify(value)[:220]
    slug = base
    suffix = 2
    while session.scalar(select(POI.poi_id).where(POI.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
