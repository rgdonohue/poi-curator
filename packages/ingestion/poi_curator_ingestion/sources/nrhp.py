from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.request import Request, urlopen

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
from poi_curator_domain.historic_register import NRHP_SOURCE_ID, build_nrhp_evidence_key
from poi_curator_domain.provenance import record_canonical_provenance, record_sourced_field_values
from poi_curator_domain.settings import get_settings
from poi_curator_domain.text import slugify
from shapely.geometry import Point
from sqlalchemy import select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from poi_curator_ingestion.matching import IncomingSourceRecord, match_incoming_record
from poi_curator_ingestion.pipeline import ensure_editorial_stub

SANTA_FE_COUNTY = "SANTA FE"
NRHP_LICENSE_NOTES = "NPS public National Register listed-properties download."


@dataclass(frozen=True)
class NRHPRecord:
    reference_number: str
    property_name: str
    state: str
    county: str
    city: str | None
    street_address: str | None
    category_of_property: str | None
    listed_date: str | None
    external_link: str | None
    other_names: str | None
    lon: float | None
    lat: float | None
    wikidata_id: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class NRHPIngestSummary:
    region: str
    candidate_record_count: int
    canonical_created: int
    evidence_attached: int
    ambiguous_count: int
    skipped_without_coordinates: int
    stale_deactivated: int


def fetch_nrhp_csv_rows(csv_url: str, *, timeout_seconds: int = 60) -> list[dict[str, str]]:
    request = Request(
        csv_url,
        headers={"User-Agent": "poi-curator/0.1.0", "Accept": "text/csv,text/plain,*/*"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        text = response.read().decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(text.splitlines())]


def ingest_nrhp_records(
    session: Session,
    region: str,
    *,
    row_loader: Callable[[], list[dict[str, Any]]] | None = None,
    deactivate_stale: bool = True,
) -> NRHPIngestSummary:
    settings = get_settings()
    rows = row_loader() if row_loader else fetch_nrhp_csv_rows(settings.nrhp_listed_csv_url)
    records = filter_nrhp_records(parse_nrhp_records(rows))
    ensure_nrhp_source_registry(session)

    canonical_created = 0
    evidence_attached = 0
    ambiguous_count = 0
    skipped_without_coordinates = 0
    active_reference_numbers: set[str] = set()

    for record in records:
        if record.lon is None or record.lat is None:
            skipped_without_coordinates += 1
            continue
        active_reference_numbers.add(record.reference_number)
        persist_nrhp_raw_record(session, record)
        match_result = match_incoming_record(
            session,
            IncomingSourceRecord(
                source_id=NRHP_SOURCE_ID,
                external_id=record.reference_number or record.property_name,
                name=record.property_name,
                lon=record.lon,
                lat=record.lat,
                region=region,
                wikidata_id=record.wikidata_id,
                raw_payload=record.raw_payload,
            ),
            decided_by="ingest:nrhp",
        )
        if match_result.decision == "ambiguous":
            ambiguous_count += 1
            continue
        if match_result.poi is None:
            poi = create_nrhp_canonical_poi(session, record, region)
            canonical_created += 1
            record_canonical_provenance(
                session,
                poi,
                source_id=NRHP_SOURCE_ID,
                confidence=0.9,
                observed_at=datetime.now(UTC),
            )
            session.add(
                POIMatchLog(
                    canonical_poi_id=poi.poi_id,
                    candidate_source=NRHP_SOURCE_ID,
                    candidate_external_id=record.reference_number,
                    match_strategy=match_result.strategy,
                    match_score=match_result.score,
                    decision="new",
                    decided_at=datetime.now(UTC),
                    decided_by="ingest:nrhp",
                    notes="Canonical POI created for unmatched NRHP record.",
                )
            )
        else:
            poi = match_result.poi

        upsert_nrhp_evidence(session, poi.poi_id, record)
        record_sourced_field_values(
            session,
            poi_id=poi.poi_id,
            source_id=NRHP_SOURCE_ID,
            values=field_values_for_record(record),
            confidence=0.9,
            observed_at=datetime.now(UTC),
        )
        if poi.heritage_id is None:
            poi.heritage_id = record.reference_number
        evidence_attached += 1

    stale_deactivated = (
        deactivate_stale_nrhp_pois(session, region, active_reference_numbers)
        if deactivate_stale
        else 0
    )
    session.commit()
    return NRHPIngestSummary(
        region=region,
        candidate_record_count=len(records),
        canonical_created=canonical_created,
        evidence_attached=evidence_attached,
        ambiguous_count=ambiguous_count,
        skipped_without_coordinates=skipped_without_coordinates,
        stale_deactivated=stale_deactivated,
    )


def deactivate_stale_nrhp_pois(
    session: Session,
    region: str,
    active_reference_numbers: set[str],
) -> int:
    stale_filter: ColumnElement[bool]
    if not active_reference_numbers:
        stale_filter = true()
    else:
        stale_filter = POI.heritage_id.not_in(active_reference_numbers)
    stale_pois = session.scalars(
        select(POI).where(
            POI.city == region,
            POI.primary_source == NRHP_SOURCE_ID,
            POI.is_active.is_(True),
            stale_filter,
        )
    ).all()
    now = datetime.now(UTC)
    for poi in stale_pois:
        poi.is_active = False
        poi.review_status = "stale"
        poi.updated_at = now
    return len(stale_pois)


def parse_nrhp_records(rows: Iterable[dict[str, Any]]) -> list[NRHPRecord]:
    records: list[NRHPRecord] = []
    for row in rows:
        name = first_value(row, "Property Name", "property_name", "name")
        state = first_value(row, "State", "state")
        reference_number = first_value(row, "Ref#", "refnum", "reference_number", "RefNum")
        if not name or not state:
            continue
        records.append(
            NRHPRecord(
                reference_number=reference_number or slugify(name),
                property_name=name,
                state=state,
                county=first_value(row, "County", "county"),
                city=first_value(row, "City ", "City", "city") or None,
                street_address=first_value(row, "Street & Number", "Address", "street_address")
                or None,
                category_of_property=first_value(row, "Category of Property", "Resource Type")
                or None,
                listed_date=first_value(row, "Listed Date", "listed_date") or None,
                external_link=first_value(row, "External Link", "url") or None,
                other_names=first_value(row, "Other Names", "other_names") or None,
                lon=parse_float(first_value(row, "Longitude", "LONGITUDE", "lon", "x")),
                lat=parse_float(first_value(row, "Latitude", "LATITUDE", "lat", "y")),
                wikidata_id=first_value(row, "wikidata_id", "Wikidata", "wikidata") or None,
                raw_payload={str(key): value for key, value in row.items()},
            )
        )
    return records


def filter_nrhp_records(records: Iterable[NRHPRecord]) -> list[NRHPRecord]:
    return [
        record
        for record in records
        if record.state.strip().upper() in {"NM", "NEW MEXICO"}
        and record.county.strip().upper() == SANTA_FE_COUNTY
    ]


def create_nrhp_canonical_poi(session: Session, record: NRHPRecord, region: str) -> POI:
    now = datetime.now(UTC)
    point = Point(record.lon, record.lat)
    poi = POI(
        canonical_name=record.property_name,
        slug=unique_slug(
            session,
            f"{record.property_name}-{NRHP_SOURCE_ID}-{record.reference_number}",
        ),
        geom=from_shape(point, srid=4326),
        centroid=from_shape(point, srid=4326),
        city=region,
        region="New Mexico",
        country="US",
        normalized_category="history",
        normalized_subcategory="historic_register_property",
        display_categories=["history"],
        short_description="National Register of Historic Places listed property.",
        primary_source=NRHP_SOURCE_ID,
        heritage_id=record.reference_number,
        raw_tag_summary_json={
            "source": NRHP_SOURCE_ID,
            "reference_number": record.reference_number,
        },
        historical_flag=True,
        cultural_flag=False,
        scenic_flag=False,
        infrastructure_flag=False,
        food_identity_flag=False,
        walk_affinity_hint=0.45,
        drive_affinity_hint=0.5,
        base_significance_score=6.0,
        quality_score=65.0,
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
            has_official_heritage_match=True,
            official_corroboration_score=1.0,
            district_membership_score=0.0,
            institutional_identity_score=0.0,
            description_quality=description_quality_score(
                poi.short_description,
                poi.normalized_subcategory,
            ),
            entity_type_confidence=0.8,
            local_identity_score=0.5,
            interpretive_value_score=0.6,
            genericity_penalty=0.05,
            editorial_priority_seed=0.7,
            computed_at=now,
        )
    )
    ensure_editorial_stub(session, poi)
    return poi


def upsert_nrhp_evidence(session: Session, poi_id: str, record: NRHPRecord) -> POIEvidence:
    key = build_nrhp_evidence_key(poi_id, record.reference_number)
    evidence = session.scalar(select(POIEvidence).where(POIEvidence.evidence_key == key))
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=NRHP_SOURCE_ID,
            evidence_type="historic_designation",
            evidence_label=record.property_name,
            evidence_text=evidence_text(record),
            evidence_url=record.external_link,
            external_record_id=record.reference_number,
            confidence=0.9,
            raw_evidence_json=evidence_payload(record),
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
        return evidence
    evidence.evidence_label = record.property_name
    evidence.evidence_text = evidence_text(record)
    evidence.evidence_url = record.external_link
    evidence.external_record_id = record.reference_number
    evidence.confidence = 0.9
    evidence.raw_evidence_json = evidence_payload(record)
    evidence.observed_at = datetime.now(UTC)
    return evidence


def persist_nrhp_raw_record(session: Session, record: NRHPRecord) -> None:
    source_record_id = record.reference_number or slugify(record.property_name)
    content_hash = sha256(orjson.dumps(record.raw_payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
    existing = session.scalar(
        select(POISourceRaw).where(
            POISourceRaw.source_name == NRHP_SOURCE_ID,
            POISourceRaw.source_record_id == source_record_id,
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
            source_name=NRHP_SOURCE_ID,
            source_record_id=source_record_id,
            source_url=record.external_link,
            raw_payload_json=record.raw_payload,
            geom=from_shape(Point(record.lon, record.lat), srid=4326),
            fetched_at=now,
            content_hash=content_hash,
            is_current=True,
            license=NRHP_LICENSE_NOTES,
        )
    )


def ensure_nrhp_source_registry(session: Session) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, NRHP_SOURCE_ID)
    if source is None:
        source = SourceRegistry(
            source_id=NRHP_SOURCE_ID,
            organization_name="National Park Service",
            source_name="National Register of Historic Places Listed Properties",
            source_type="historic_register",
            trust_class="official_heritage",
            base_url=settings.nrhp_listed_csv_url,
            license_notes=NRHP_LICENSE_NOTES,
            crawl_allowed=True,
            ingest_method="csv_download",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(source)
        return
    source.updated_at = now
    source.is_active = True


def field_values_for_record(record: NRHPRecord) -> dict[str, Any]:
    return {
        "name": record.property_name,
        "primary_category": "history",
        "coordinates": {"lon": round(float(record.lon), 7), "lat": round(float(record.lat), 7)}
        if record.lon is not None and record.lat is not None
        else None,
        "short_description": "National Register of Historic Places listed property.",
        "heritage_id": record.reference_number,
        "listed_date": record.listed_date,
        "street_address": record.street_address,
        "category_of_property": record.category_of_property,
        "other_names": record.other_names,
    }


def evidence_text(record: NRHPRecord) -> str:
    if record.listed_date:
        return f"Listed in the National Register of Historic Places on {record.listed_date}."
    return "Listed in the National Register of Historic Places."


def evidence_payload(record: NRHPRecord) -> dict[str, Any]:
    return {
        "city": record.city,
        "county": record.county,
        "street_address": record.street_address,
        "category_of_property": record.category_of_property,
        "listed_date": record.listed_date,
        "other_names": record.other_names,
        "coordinates": {"lon": record.lon, "lat": record.lat},
    }


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
