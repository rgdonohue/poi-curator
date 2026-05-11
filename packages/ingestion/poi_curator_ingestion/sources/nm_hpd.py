from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4
from xml.etree import ElementTree as ET

import orjson
from geoalchemy2.shape import from_shape
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIEvidence,
    POIMatchLog,
    POISignals,
    POISourceRaw,
    SourceRegistry,
)
from poi_curator_domain.descriptions import description_quality_score
from poi_curator_domain.provenance import record_canonical_provenance, record_sourced_field_values
from poi_curator_domain.settings import get_settings
from poi_curator_domain.text import slugify
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from poi_curator_ingestion.matching import (
    DEFAULT_MATCH_CONFIG,
    IncomingSourceRecord,
    MatchResult,
    match_incoming_record,
    normalized_name_similarity,
    write_match_log,
)
from poi_curator_ingestion.pipeline import ensure_editorial_stub

NM_HPD_SOURCE_ID = "nm_hpd"
LEGACY_NM_HPD_SOURCE_ID = "nm_hpd_register_workbook"
NM_HPD_LICENSE_NOTES = "Public NM HPD State and National Register workbook."
NEW_MEXICO = "NEW MEXICO"
SANTA_FE_COUNTY = "SANTA FE"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NM_HPD_RECORD_POLICY: dict[str, frozenset[str]] = {
    "canonical_create": frozenset({"property"}),
    "evidence_only": frozenset({"district"}),
}

PERSON_RESOURCE_TYPES = {
    "house",
    "houses",
    "building",
    "buildings",
    "residence",
    "store",
    "studio",
}


@dataclass(frozen=True)
class NMHPDRecord:
    register_number: str
    property_name: str
    county: str
    city: str | None
    street_address: str | None
    property_category: str | None
    state_register_year: str
    national_register_year: str | None
    is_nhl: bool
    common_notes: str | None
    restricted: bool
    lon: float | None
    lat: float | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class NMHPDIngestSummary:
    region: str
    candidate_record_count: int
    canonical_created: int
    evidence_attached: int
    district_evidence_attached: int
    ambiguous_count: int
    skipped_without_coordinates: int
    retained_unreviewed: int
    skipped_out_of_scope: int


@dataclass(frozen=True)
class LegacyReconciliationSummary:
    superseded: int
    retained_unreviewed: int
    non_source_noise: int


def fetch_hpd_workbook_bytes(workbook_url: str, *, timeout_seconds: int = 90) -> bytes:
    request = Request(
        workbook_url,
        headers={
            "User-Agent": "poi-curator/0.1.0",
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def ingest_nm_hpd_records(
    session: Session,
    region: str,
    *,
    workbook_loader: Callable[[], bytes] | None = None,
    reconcile_legacy: bool = True,
) -> NMHPDIngestSummary:
    settings = get_settings()
    workbook_bytes = (
        workbook_loader()
        if workbook_loader is not None
        else fetch_hpd_workbook_bytes(
            settings.nm_hpd_register_workbook_url,
            timeout_seconds=settings.nm_hpd_timeout_seconds,
        )
    )
    records = filter_hpd_records(parse_hpd_workbook(workbook_bytes))
    ensure_nm_hpd_source_registry(session)

    canonical_created = 0
    evidence_attached = 0
    district_evidence_attached = 0
    ambiguous_count = 0
    skipped_without_coordinates = 0
    retained_unreviewed = 0
    skipped_out_of_scope = 0
    current_register_numbers: set[str] = set()

    for record in records:
        current_register_numbers.add(record.register_number)
        match_result = match_hpd_record(session, record, region)
        if match_result.decision == "ambiguous":
            ambiguous_count += 1
            upsert_hpd_diagnostic(session, record, region, match_result, status="ambiguous")
            continue

        if match_result.poi is None:
            if record.lon is None or record.lat is None:
                skipped_without_coordinates += 1
                retained_unreviewed += 1
                upsert_hpd_diagnostic(session, record, region, match_result, status="unreviewed")
                continue
            if not should_create_canonical(record):
                skipped_out_of_scope += 1
                upsert_hpd_diagnostic(session, record, region, match_result, status="unreviewed")
                continue
            poi = create_hpd_canonical_poi(session, record, region)
            canonical_created += 1
            persist_hpd_raw_record(session, record, poi.poi_id)
            record_canonical_provenance(
                session,
                poi,
                source_id=NM_HPD_SOURCE_ID,
                confidence=0.85,
                observed_at=datetime.now(UTC),
            )
            session.add(
                POIMatchLog(
                    canonical_poi_id=poi.poi_id,
                    candidate_source=NM_HPD_SOURCE_ID,
                    candidate_external_id=record.register_number,
                    match_strategy=match_result.strategy,
                    match_score=match_result.score,
                    decision="new",
                    decided_at=datetime.now(UTC),
                    decided_by="ingest:nm_hpd",
                    notes="Canonical POI created for unmatched NM HPD State Register record.",
                )
            )
        else:
            poi = match_result.poi
            if record.lon is not None and record.lat is not None:
                persist_hpd_raw_record(session, record, poi.poi_id)

        created = upsert_hpd_evidence(session, poi.poi_id, record, match_result.strategy)
        if created:
            evidence_attached += 1
            if is_district_designation(record):
                district_evidence_attached += 1
        record_sourced_field_values(
            session,
            poi_id=poi.poi_id,
            source_id=NM_HPD_SOURCE_ID,
            values=field_values_for_record(record),
            confidence=0.85,
            observed_at=datetime.now(UTC),
        )

    if reconcile_legacy:
        session.flush()
        reconcile_legacy_hpd_diagnostics(session, current_register_numbers)

    session.commit()
    return NMHPDIngestSummary(
        region=region,
        candidate_record_count=len(records),
        canonical_created=canonical_created,
        evidence_attached=evidence_attached,
        district_evidence_attached=district_evidence_attached,
        ambiguous_count=ambiguous_count,
        skipped_without_coordinates=skipped_without_coordinates,
        retained_unreviewed=retained_unreviewed,
        skipped_out_of_scope=skipped_out_of_scope,
    )


def parse_hpd_workbook(workbook_bytes: bytes) -> list[NMHPDRecord]:
    workbook_rows = read_xlsx_rows(workbook_bytes)
    rows = best_hpd_sheet_rows(workbook_rows)
    return list(parse_hpd_rows(rows))


def parse_hpd_rows(rows: Iterable[dict[str, str]]) -> Iterable[NMHPDRecord]:
    for row in rows:
        name = first_value(row, "Name of Property", "Property Name", "Name", "Resource Name")
        state_register_year = first_value(row, "STATE\nREGISTER", "STATE REGISTER")
        if not name or not state_register_year:
            continue
        record_id = first_value(row, "SR#", "SR No.", "Register Number", "Number") or slugify(name)
        raw_payload = {str(key): value for key, value in row.items()}
        yield NMHPDRecord(
            register_number=record_id,
            property_name=name,
            county=first_value(row, "County", "COUNTY"),
            city=first_value(row, "City", "City ", "Community", "Town") or None,
            street_address=first_value(row, "Address", "Street & Number", "Location") or None,
            property_category=first_value(row, "Property Category", "Category of Property", "Type")
            or None,
            state_register_year=state_register_year,
            national_register_year=first_value(row, "NATIONAL REGISTER") or None,
            is_nhl=truthy(first_value(row, "NHL")),
            common_notes=first_value(row, "Common Name / Notes", "Other Names", "Notes") or None,
            restricted=truthy(first_value(row, "RESTRICTED", "Restricted")),
            lon=parse_float(first_value(row, "Longitude", "LONGITUDE", "lon", "x")),
            lat=parse_float(first_value(row, "Latitude", "LATITUDE", "lat", "y")),
            raw_payload=raw_payload,
        )


def filter_hpd_records(records: Iterable[NMHPDRecord]) -> list[NMHPDRecord]:
    return [
        record
        for record in records
        if record.county.strip().upper() == SANTA_FE_COUNTY
    ]


def match_hpd_record(session: Session, record: NMHPDRecord, region: str) -> MatchResult:
    if record.lon is not None and record.lat is not None:
        return match_incoming_record(
            session,
            IncomingSourceRecord(
                source_id=NM_HPD_SOURCE_ID,
                external_id=record.register_number,
                name=record.property_name,
                lon=record.lon,
                lat=record.lat,
                region=region,
                raw_payload=record.raw_payload,
            ),
            decided_by="ingest:nm_hpd",
        )
    result = match_hpd_by_name_address(session, record, region)
    write_match_log(
        session,
        IncomingSourceRecord(
            source_id=NM_HPD_SOURCE_ID,
            external_id=record.register_number,
            name=record.property_name,
            lon=None,
            lat=None,
            region=region,
            raw_payload=record.raw_payload,
        ),
        result,
        decided_by="ingest:nm_hpd",
    )
    return result


def match_hpd_by_name_address(session: Session, record: NMHPDRecord, region: str) -> MatchResult:
    pois = (
        session.execute(
            select(POI)
            .where(POI.city == region, POI.is_active.is_(True))
            .options(joinedload(POI.aliases))
        )
        .unique()
        .scalars()
        .all()
    )
    threshold = DEFAULT_MATCH_CONFIG["name_similarity_threshold"]
    candidates: list[tuple[POI, float]] = []
    for poi in pois:
        score = best_hpd_name_similarity(record, poi)
        if score >= threshold:
            candidates.append((poi, score))
    candidates.sort(key=lambda item: (-item[1], item[0].poi_id))
    if len(candidates) == 1:
        poi, score = candidates[0]
        return MatchResult("match", poi, "name_address", round(score, 4), candidate_count=1)
    if len(candidates) > 1:
        _, score = candidates[0]
        return MatchResult(
            "ambiguous",
            None,
            "name_address",
            round(score, 4),
            candidate_count=len(candidates),
            notes=f"candidates={len(candidates)}",
        )
    return MatchResult("new", None, "no_coordinates", None, candidate_count=0)


def best_hpd_name_similarity(record: NMHPDRecord, poi: POI) -> float:
    source_names = source_name_candidates(record)
    poi_names = [poi.canonical_name]
    poi_names.extend(alias.alias_name for alias in getattr(poi, "aliases", []) or [])
    return max(
        normalized_name_similarity(source_name, poi_name)
        for source_name in source_names
        for poi_name in poi_names
    )


def source_name_candidates(record: NMHPDRecord) -> list[str]:
    names = [record.property_name]
    display_name = display_name_for_register_name(record.property_name)
    if display_name != record.property_name:
        names.append(display_name)
    if record.common_notes:
        names.extend(split_note_names(record.common_notes))
    return [name for name in names if name]


def should_create_canonical(record: NMHPDRecord) -> bool:
    return not is_district_designation(record) and record.lon is not None and record.lat is not None


def is_district_designation(record: NMHPDRecord) -> bool:
    category = (record.property_category or "").strip().casefold()
    name = record.property_name.casefold()
    return category == "district" or "historic district" in name or name.endswith(" district")


def create_hpd_canonical_poi(session: Session, record: NMHPDRecord, region: str) -> POI:
    now = datetime.now(UTC)
    if record.lon is None or record.lat is None:
        raise ValueError("Cannot create an NM HPD canonical POI without coordinates.")
    point = Point(record.lon, record.lat)
    display_name = display_name_for_register_name(record.property_name)
    poi = POI(
        canonical_name=display_name,
        slug=unique_slug(session, f"{display_name}-{NM_HPD_SOURCE_ID}-{record.register_number}"),
        geom=from_shape(point, srid=4326),
        centroid=from_shape(point, srid=4326),
        city=region,
        region="New Mexico",
        country="US",
        normalized_category="history",
        normalized_subcategory="state_register_property",
        display_categories=["history"],
        short_description="New Mexico State Register listed property.",
        primary_source=NM_HPD_SOURCE_ID,
        heritage_id=record.register_number,
        raw_tag_summary_json={
            "source": NM_HPD_SOURCE_ID,
            "state_register_number": record.register_number,
            "property_category": record.property_category,
            "street_address": record.street_address,
            "county": record.county,
            "city": record.city,
        },
        historical_flag=True,
        cultural_flag=False,
        scenic_flag=False,
        infrastructure_flag=False,
        food_identity_flag=False,
        walk_affinity_hint=0.45,
        drive_affinity_hint=0.4,
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
            osm_tag_richness=0.0,
            description_quality=description_quality_score(
                poi.short_description,
                poi.normalized_subcategory,
            ),
            entity_type_confidence=0.8,
            local_identity_score=0.5,
            interpretive_value_score=0.55,
            genericity_penalty=0.05,
            editorial_priority_seed=0.7,
            computed_at=now,
        )
    )
    ensure_editorial_stub(session, poi)
    return poi


def upsert_hpd_evidence(
    session: Session,
    poi_id: str,
    record: NMHPDRecord,
    match_strategy: str,
) -> bool:
    evidence_type = (
        "state_register_district_designation"
        if is_district_designation(record)
        else "state_historic_designation"
    )
    evidence_key = build_hpd_evidence_key(poi_id, record)
    existing = session.scalar(select(POIEvidence).where(POIEvidence.evidence_key == evidence_key))
    evidence_text = (
        "Listed as a New Mexico State Register district designation."
        if is_district_designation(record)
        else "Listed in the New Mexico State Register of Cultural Properties."
    )
    raw = {
        "register_number": record.register_number,
        "property_name": record.property_name,
        "display_name": display_name_for_register_name(record.property_name),
        "county": record.county,
        "city": record.city,
        "street_address": record.street_address,
        "property_category": record.property_category,
        "state_register_year": record.state_register_year,
        "national_register_year": record.national_register_year,
        "is_nhl": record.is_nhl,
        "common_notes": record.common_notes,
        "restricted": record.restricted,
        "match_strategy": match_strategy,
        "canonical_policy": "evidence_only" if is_district_designation(record) else "property",
    }
    if existing is None:
        session.add(
            POIEvidence(
                evidence_key=evidence_key,
                poi_id=poi_id,
                source_id=NM_HPD_SOURCE_ID,
                evidence_type=evidence_type,
                evidence_label=record.property_name,
                evidence_text=evidence_text,
                evidence_url=None,
                external_record_id=record.register_number,
                confidence=0.85,
                raw_evidence_json=raw,
                observed_at=datetime.now(UTC),
            )
        )
        return True
    existing.poi_id = poi_id
    existing.evidence_type = evidence_type
    existing.evidence_label = record.property_name
    existing.evidence_text = evidence_text
    existing.external_record_id = record.register_number
    existing.confidence = 0.85
    existing.raw_evidence_json = raw
    existing.observed_at = datetime.now(UTC)
    return False


def field_values_for_record(record: NMHPDRecord) -> dict[str, Any]:
    return {
        "name": record.property_name,
        "primary_category": "history",
        "coordinates": (
            {"lon": round(record.lon, 7), "lat": round(record.lat, 7)}
            if record.lon is not None and record.lat is not None
            else None
        ),
        "short_description": (
            "New Mexico State Register district designation."
            if is_district_designation(record)
            else "New Mexico State Register listed property."
        ),
    }


def persist_hpd_raw_record(session: Session, record: NMHPDRecord, poi_id: str) -> None:
    if record.lon is None or record.lat is None:
        return
    payload = orjson.dumps(record.raw_payload, option=orjson.OPT_SORT_KEYS)
    content_hash = sha256(payload).hexdigest()
    existing = session.scalar(
        select(POISourceRaw).where(
            POISourceRaw.source_name == NM_HPD_SOURCE_ID,
            POISourceRaw.source_record_id == record.register_number,
        )
    )
    now = datetime.now(UTC)
    point = from_shape(Point(record.lon, record.lat), srid=4326)
    if existing is None:
        session.add(
            POISourceRaw(
                source_name=NM_HPD_SOURCE_ID,
                source_record_id=record.register_number,
                source_url=None,
                raw_payload_json=record.raw_payload,
                geom=point,
                fetched_at=now,
                content_hash=content_hash,
                is_current=True,
                license=NM_HPD_LICENSE_NOTES,
                canonical_poi_id=poi_id,
            )
        )
        return
    existing.raw_payload_json = record.raw_payload
    existing.geom = point
    existing.fetched_at = now
    existing.content_hash = content_hash
    existing.is_current = True
    existing.license = NM_HPD_LICENSE_NOTES
    existing.canonical_poi_id = poi_id


def upsert_hpd_diagnostic(
    session: Session,
    record: NMHPDRecord,
    region: str,
    result: MatchResult,
    *,
    status: str,
) -> None:
    existing = session.scalar(
        select(OfficialMatchDiagnostic).where(
            OfficialMatchDiagnostic.source_id == NM_HPD_SOURCE_ID,
            OfficialMatchDiagnostic.region == region,
            OfficialMatchDiagnostic.external_record_id == record.register_number,
        )
    )
    now = datetime.now(UTC)
    raw = {
        "record": record.raw_payload,
        "canonical_policy": "evidence_only" if is_district_designation(record) else "property",
        "reason": "no_public_coordinates" if record.lon is None or record.lat is None else status,
    }
    if existing is None:
        session.add(
            OfficialMatchDiagnostic(
                source_id=NM_HPD_SOURCE_ID,
                region=region,
                external_record_id=record.register_number,
                external_name=record.property_name,
                matched_poi_id=result.poi.poi_id if result.poi is not None else None,
                resolved_poi_id=None,
                best_candidate_name=None,
                best_similarity=result.score,
                match_strategy=result.strategy,
                status=status,
                resolution_method=None,
                raw_payload_json=raw,
                reviewed_at=None,
                reviewed_by=None,
                created_at=now,
                updated_at=now,
            )
        )
        return
    existing.external_name = record.property_name
    existing.matched_poi_id = result.poi.poi_id if result.poi is not None else None
    existing.best_similarity = result.score
    existing.match_strategy = result.strategy
    existing.status = status
    existing.raw_payload_json = raw
    existing.updated_at = now


def reconcile_legacy_hpd_diagnostics(
    session: Session,
    current_register_numbers: set[str],
) -> LegacyReconciliationSummary:
    diagnostics = session.scalars(
        select(OfficialMatchDiagnostic).where(
            OfficialMatchDiagnostic.source_id == LEGACY_NM_HPD_SOURCE_ID,
            OfficialMatchDiagnostic.status == "unreviewed",
        )
    ).all()
    superseded = 0
    retained = 0
    non_source_noise = 0
    now = datetime.now(UTC)
    for diagnostic in diagnostics:
        raw = dict(diagnostic.raw_payload_json or {})
        record_id = diagnostic.external_record_id or ""
        matching_evidence = None
        if record_id in current_register_numbers:
            matching_evidence = session.scalar(
                select(POIEvidence.id)
                .where(
                    POIEvidence.source_id == NM_HPD_SOURCE_ID,
                    POIEvidence.external_record_id == record_id,
                )
                .limit(1)
            )
        classification = classify_legacy_hpd_diagnostic(
            external_record_id=record_id,
            external_name=diagnostic.external_name,
            current_register_numbers=current_register_numbers,
            has_new_evidence=matching_evidence is not None,
        )
        if classification == "non_source_noise":
            raw["legacy_reconciliation_status"] = "non_source_noise"
            diagnostic.raw_payload_json = raw
            diagnostic.status = "out_of_scope"
            diagnostic.resolution_method = "not_hpd_source_record"
            diagnostic.reviewed_at = now
            diagnostic.reviewed_by = "ingest:nm_hpd"
            non_source_noise += 1
            continue
        if classification in {
            "superseded_by_nm_hpd_run",
            "retained_unreviewed_no_coordinates",
        }:
            if classification == "superseded_by_nm_hpd_run":
                raw["legacy_reconciliation_status"] = "superseded_by_nm_hpd_run"
                diagnostic.raw_payload_json = raw
                diagnostic.status = "superseded"
                diagnostic.resolution_method = "nm_hpd_run_superseded"
                diagnostic.reviewed_at = now
                diagnostic.reviewed_by = "ingest:nm_hpd"
                superseded += 1
            else:
                raw["legacy_reconciliation_status"] = "retained_unreviewed_no_coordinates"
                diagnostic.raw_payload_json = raw
                retained += 1
            diagnostic.updated_at = now
            continue
        raw["legacy_reconciliation_status"] = classification
        diagnostic.raw_payload_json = raw
        diagnostic.status = "out_of_scope"
        diagnostic.resolution_method = classification
        diagnostic.reviewed_at = now
        diagnostic.reviewed_by = "ingest:nm_hpd"
        diagnostic.updated_at = now
        non_source_noise += 1
    return LegacyReconciliationSummary(
        superseded=superseded,
        retained_unreviewed=retained,
        non_source_noise=non_source_noise,
    )


def classify_legacy_hpd_diagnostic(
    *,
    external_record_id: str,
    external_name: str,
    current_register_numbers: set[str],
    has_new_evidence: bool,
) -> str:
    if external_name == "Theme Queue Case":
        return "non_source_noise"
    if external_record_id in current_register_numbers and has_new_evidence:
        return "superseded_by_nm_hpd_run"
    if external_record_id in current_register_numbers:
        return "retained_unreviewed_no_coordinates"
    return "not_in_current_hpd_workbook"


def ensure_nm_hpd_source_registry(session: Session) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, NM_HPD_SOURCE_ID)
    if source is None:
        source = SourceRegistry(
            source_id=NM_HPD_SOURCE_ID,
            organization_name="New Mexico Historic Preservation Division",
            source_name="State Register of Cultural Properties",
            source_type="historic_register_workbook",
            trust_class="official_register",
            base_url=settings.nm_hpd_register_workbook_url,
            license_notes=NM_HPD_LICENSE_NOTES,
            crawl_allowed=True,
            ingest_method="xlsx_workbook",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(source)
        return
    source.organization_name = "New Mexico Historic Preservation Division"
    source.source_name = "State Register of Cultural Properties"
    source.source_type = "historic_register_workbook"
    source.trust_class = "official_register"
    source.base_url = settings.nm_hpd_register_workbook_url
    source.license_notes = NM_HPD_LICENSE_NOTES
    source.crawl_allowed = True
    source.ingest_method = "xlsx_workbook"
    source.is_active = True
    source.updated_at = now


def build_hpd_evidence_key(poi_id: str, record: NMHPDRecord) -> str:
    key = record.register_number or record.property_name
    return slugify(f"{poi_id}:{NM_HPD_SOURCE_ID}:{key}")[:255]


def display_name_for_register_name(value: str) -> str:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) < 3:
        return value
    surname = parts[0]
    given = parts[1]
    suffix = ", ".join(parts[2:]).strip()
    suffix_key = re.sub(r"[^A-Za-z ]+", "", suffix).strip().casefold()
    if not surname or not given or suffix_key not in PERSON_RESOURCE_TYPES:
        return value
    return " ".join(part for part in (given, surname, suffix) if part)


def split_note_names(value: str) -> list[str]:
    return [
        name.strip()
        for name in re.split(r"[;/]", value)
        if name.strip() and not name.strip().lower().startswith("note ")
    ]


def unique_slug(session: Session, base: str) -> str:
    root = slugify(base)[:220] or f"nm-hpd-{uuid4()}"
    candidate = root
    suffix = 2
    while session.scalar(select(POI.poi_id).where(POI.slug == candidate).limit(1)) is not None:
        candidate = f"{root}-{suffix}"
        suffix += 1
    return candidate


def read_xlsx_rows(data: bytes) -> dict[str, list[dict[str, str]]]:
    workbook = zipfile.ZipFile(io.BytesIO(data))
    shared_strings = read_shared_strings(workbook)
    sheets = read_workbook_sheets(workbook)
    return {
        sheet_name: read_sheet_rows(workbook, sheet_path, shared_strings)
        for sheet_name, sheet_path in sheets
    }


def read_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for node in root.findall(f"{{{MAIN_NS}}}si"):
        strings.append(
            "".join(text_node.text or "" for text_node in node.iterfind(f".//{{{MAIN_NS}}}t"))
        )
    return strings


def read_workbook_sheets(workbook: zipfile.ZipFile) -> list[tuple[str, str]]:
    root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    sheets: list[tuple[str, str]] = []
    for sheet in root.findall(f".//{{{MAIN_NS}}}sheet"):
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if rel_id is None or rel_id not in rel_map:
            continue
        target = rel_map[rel_id]
        if target.startswith("worksheets/"):
            sheets.append((sheet.attrib.get("name", target), f"xl/{target}"))
    return sheets


def read_sheet_rows(
    workbook: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[dict[str, str]]:
    root = ET.fromstring(workbook.read(sheet_path))
    row_nodes = root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row")
    parsed_rows = [parse_row(row_node, shared_strings) for row_node in row_nodes]
    parsed_rows = [row for row in parsed_rows if any(value for value in row.values())]
    if not parsed_rows:
        return []
    headers = [value.strip() for _, value in sorted(parsed_rows[0].items())]
    data_rows: list[dict[str, str]] = []
    for row in parsed_rows[1:]:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            record[excel_column_name(index)] = row.get(excel_column_name(index), "").strip()
            record[header] = row.get(excel_column_name(index), "").strip()
        if any(value for value in record.values()):
            data_rows.append(record)
    return data_rows


def parse_row(row_node: ET.Element, shared_strings: list[str]) -> dict[str, str]:
    cells: dict[str, str] = {}
    for cell in row_node.findall(f"{{{MAIN_NS}}}c"):
        reference = cell.attrib.get("r", "")
        column = "".join(char for char in reference if char.isalpha())
        if column:
            cells[column] = cell_value(cell, shared_strings)
    return cells


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iterfind(f".//{{{MAIN_NS}}}t"))
    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    return raw_value


def best_hpd_sheet_rows(workbook_rows: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    best_rows: list[dict[str, str]] | None = None
    best_score = -1
    for rows in workbook_rows.values():
        if not rows:
            continue
        headers = {normalize_header(header) for header in rows[0]}
        score = sum(
            1
            for required in (
                {"name of property", "property name", "name"},
                {"county"},
                {"state register", "state\nregister"},
            )
            if required & headers
        )
        if score > best_score:
            best_rows = rows
            best_score = score
    if best_rows is None:
        raise ValueError("No usable sheet found in HPD register workbook.")
    return best_rows


def normalize_header(header: str) -> str:
    return " ".join(header.strip().lower().split())


def excel_column_name(index: int) -> str:
    result = ""
    current = index + 1
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def first_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def parse_float(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def truthy(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "x"}
