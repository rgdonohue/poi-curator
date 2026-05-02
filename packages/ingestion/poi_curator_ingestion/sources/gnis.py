from __future__ import annotations

import csv
import io
import zipfile
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
from poi_curator_domain.provenance import record_canonical_provenance, record_sourced_field_values
from poi_curator_domain.text import slugify
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from poi_curator_ingestion.matching import (
    DEFAULT_MATCH_CONFIG,
    IncomingSourceRecord,
    match_by_spatial_name,
    match_incoming_record,
    write_ambiguity_diagnostic,
    write_match_log,
)
from poi_curator_ingestion.pipeline import ensure_editorial_stub

GNIS_SOURCE_ID = "gnis"
GNIS_DOMESTIC_NM_TEXT_URL = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/DomesticNames/"
    "DomesticNames_NM_Text.zip"
)
GNIS_ALL_NAMES_TEXT_URL = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/Topical/"
    "AllNames_National_Text.zip"
)
GNIS_HISTORICAL_TEXT_URL = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/Topical/"
    "HistoricalFeatures_National_Text.zip"
)
GNIS_DOWNLOAD_PAGE_URL = "https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data"
GNIS_LICENSE_NOTES = "USGS GNIS public domain geographic names download."
NEW_MEXICO = "NEW MEXICO"
SANTA_FE_COUNTY = "SANTA FE"

RELEVANT_FEATURE_CLASSES = frozenset(
    {
        "Canal",
        "Civil",
        "Crossing",
        "Military",
        "Populated Place",
    }
)


@dataclass(frozen=True)
class GNISRecord:
    feature_id: str
    feature_name: str
    feature_class: str
    state_name: str
    county_name: str
    map_name: str | None
    date_created: str | None
    date_edited: str | None
    lon: float | None
    lat: float | None
    variant_names: tuple[str, ...]
    is_historical: bool
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class GNISIngestSummary:
    region: str
    candidate_record_count: int
    canonical_created: int
    evidence_attached: int
    variant_evidence_attached: int
    historical_evidence_attached: int
    ambiguous_count: int
    skipped_without_coordinates: int
    skipped_out_of_scope: int
    skipped_feature_class: int
    historical_without_match: int


def fetch_gnis_pipe_zip_rows(zip_url: str, *, timeout_seconds: int = 60) -> list[dict[str, str]]:
    request = Request(
        zip_url,
        headers={"User-Agent": "poi-curator/0.1.0", "Accept": "application/zip,*/*"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        text_names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if not text_names:
            return []
        text = archive.read(text_names[0]).decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(text.splitlines(), delimiter="|")]


def ingest_gnis_records(
    session: Session,
    region: str,
    *,
    row_loader: Callable[[], list[dict[str, Any]]] | None = None,
    variant_row_loader: Callable[[], list[dict[str, Any]]] | None = None,
    historical_row_loader: Callable[[], list[dict[str, Any]]] | None = None,
) -> GNISIngestSummary:
    rows = row_loader() if row_loader else fetch_gnis_pipe_zip_rows(GNIS_DOMESTIC_NM_TEXT_URL)
    variant_rows = (
        variant_row_loader()
        if variant_row_loader
        else fetch_gnis_pipe_zip_rows(GNIS_ALL_NAMES_TEXT_URL)
    )
    historical_rows = (
        historical_row_loader()
        if historical_row_loader
        else fetch_gnis_pipe_zip_rows(GNIS_HISTORICAL_TEXT_URL)
    )
    records = parse_gnis_records(rows, variant_rows=variant_rows, historical_rows=historical_rows)
    ensure_gnis_source_registry(session)

    canonical_created = 0
    evidence_attached = 0
    variant_evidence_attached = 0
    historical_evidence_attached = 0
    ambiguous_count = 0
    skipped_without_coordinates = 0
    skipped_out_of_scope = 0
    skipped_feature_class = 0
    historical_without_match = 0
    candidate_record_count = 0

    for record in records:
        if not is_relevant_feature_class(record):
            skipped_feature_class += 1
            continue
        if record.lon is None or record.lat is None:
            skipped_without_coordinates += 1
            continue
        if record.state_name.strip().upper() != NEW_MEXICO:
            skipped_out_of_scope += 1
            continue

        incoming = IncomingSourceRecord(
            source_id=GNIS_SOURCE_ID,
            external_id=record.feature_id,
            name=record.feature_name,
            lon=record.lon,
            lat=record.lat,
            region=region,
            raw_payload=record.raw_payload,
        )
        in_santa_fe_county = record.county_name.strip().upper() == SANTA_FE_COUNTY
        if in_santa_fe_county:
            candidate_record_count += 1
            persist_gnis_raw_record(session, record)
            match_result = match_incoming_record(session, incoming, decided_by="ingest:gnis")
        else:
            match_result = match_by_spatial_name(
                session,
                incoming,
                config=DEFAULT_MATCH_CONFIG,
            )
            if match_result.decision == "new":
                skipped_out_of_scope += 1
                continue
            candidate_record_count += 1
            write_match_log(session, incoming, match_result, decided_by="ingest:gnis")
            if match_result.decision == "ambiguous":
                write_ambiguity_diagnostic(session, incoming, match_result)
            else:
                persist_gnis_raw_record(session, record)
        if match_result.decision == "ambiguous":
            ambiguous_count += 1
            continue
        if match_result.poi is None and record.is_historical:
            historical_without_match += 1
            continue
        if match_result.poi is None and not should_create_canonical(record):
            skipped_out_of_scope += 1
            continue
        if match_result.poi is None:
            poi = create_gnis_canonical_poi(session, record, region)
            canonical_created += 1
            record_canonical_provenance(
                session,
                poi,
                source_id=GNIS_SOURCE_ID,
                confidence=0.75,
                observed_at=datetime.now(UTC),
            )
            session.add(
                POIMatchLog(
                    canonical_poi_id=poi.poi_id,
                    candidate_source=GNIS_SOURCE_ID,
                    candidate_external_id=record.feature_id,
                    match_strategy=match_result.strategy,
                    match_score=match_result.score,
                    decision="new",
                    decided_at=datetime.now(UTC),
                    decided_by="ingest:gnis",
                    notes="Canonical POI created for unmatched current GNIS record.",
                )
            )
        else:
            poi = match_result.poi

        if record.is_historical:
            upsert_gnis_evidence(session, poi.poi_id, record, evidence_type="historical_feature")
            historical_evidence_attached += 1
        else:
            upsert_gnis_evidence(session, poi.poi_id, record, evidence_type="geographic_name")
            evidence_attached += 1
        record_sourced_field_values(
            session,
            poi_id=poi.poi_id,
            source_id=GNIS_SOURCE_ID,
            values=field_values_for_record(record),
            confidence=0.75 if not record.is_historical else 0.65,
            observed_at=datetime.now(UTC),
        )
        variant_evidence_attached += attach_variant_name_evidence(session, poi.poi_id, record)

    session.commit()
    return GNISIngestSummary(
        region=region,
        candidate_record_count=candidate_record_count,
        canonical_created=canonical_created,
        evidence_attached=evidence_attached,
        variant_evidence_attached=variant_evidence_attached,
        historical_evidence_attached=historical_evidence_attached,
        ambiguous_count=ambiguous_count,
        skipped_without_coordinates=skipped_without_coordinates,
        skipped_out_of_scope=skipped_out_of_scope,
        skipped_feature_class=skipped_feature_class,
        historical_without_match=historical_without_match,
    )


def parse_gnis_records(
    rows: Iterable[dict[str, Any]],
    *,
    variant_rows: Iterable[dict[str, Any]] = (),
    historical_rows: Iterable[dict[str, Any]] = (),
) -> list[GNISRecord]:
    variants_by_feature_id = variants_by_feature(variant_rows)
    historical_ids = {
        first_value(row, "feature_id", "FEATURE_ID")
        for row in historical_rows
        if first_value(row, "feature_id", "FEATURE_ID")
    }
    records: list[GNISRecord] = []
    for row in rows:
        feature_id = first_value(row, "feature_id", "FEATURE_ID")
        feature_name = first_value(row, "feature_name", "FEATURE_NAME", "name")
        feature_class = first_value(row, "feature_class", "FEATURE_CLASS")
        if not feature_id or not feature_name or not feature_class:
            continue
        lon = parse_float(first_value(row, "prim_long_dec", "PRIM_LONG_DEC", "longitude", "lon"))
        lat = parse_float(first_value(row, "prim_lat_dec", "PRIM_LAT_DEC", "latitude", "lat"))
        if lon == 0.0 and lat == 0.0:
            lon = None
            lat = None
        explicit_variants = parse_variant_names(first_value(row, "variant_names", "variants"))
        variant_names = tuple(
            sorted({*variants_by_feature_id.get(feature_id, ()), *explicit_variants})
        )
        is_historical = feature_id in historical_ids or "(historical)" in feature_name.casefold()
        raw_payload = {str(key): value for key, value in row.items()}
        if variant_names:
            raw_payload["variant_names"] = list(variant_names)
        if is_historical:
            raw_payload["historical_designation"] = True
        records.append(
            GNISRecord(
                feature_id=feature_id,
                feature_name=feature_name,
                feature_class=feature_class,
                state_name=first_value(row, "state_name", "STATE_NAME"),
                county_name=first_value(row, "county_name", "COUNTY_NAME"),
                map_name=first_value(row, "map_name", "MAP_NAME") or None,
                date_created=first_value(row, "date_created", "DATE_CREATED") or None,
                date_edited=first_value(row, "date_edited", "DATE_EDITED") or None,
                lon=lon,
                lat=lat,
                variant_names=variant_names,
                is_historical=is_historical,
                raw_payload=raw_payload,
            )
        )
    return records


def variants_by_feature(rows: Iterable[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    variants: dict[str, set[str]] = {}
    for row in rows:
        feature_id = first_value(row, "feature_id", "FEATURE_ID")
        name = first_value(row, "feature_name", "FEATURE_NAME")
        name_kind = first_value(row, "feature_name_official", "name_type", "NAME_TYPE")
        if not feature_id or not name or name_kind.casefold() == "official":
            continue
        variants.setdefault(feature_id, set()).add(name)
    return {feature_id: tuple(sorted(names)) for feature_id, names in variants.items()}


def should_create_canonical(record: GNISRecord) -> bool:
    return (
        record.state_name.strip().upper() == NEW_MEXICO
        and record.county_name.strip().upper() == SANTA_FE_COUNTY
        and is_relevant_feature_class(record)
        and not record.is_historical
        and record.lon is not None
        and record.lat is not None
    )


def is_relevant_feature_class(record: GNISRecord) -> bool:
    return record.feature_class.strip() in RELEVANT_FEATURE_CLASSES


def create_gnis_canonical_poi(session: Session, record: GNISRecord, region: str) -> POI:
    now = datetime.now(UTC)
    point = Point(record.lon, record.lat)
    category, subcategory = category_for_feature_class(record.feature_class)
    poi = POI(
        canonical_name=record.feature_name,
        slug=unique_slug(session, f"{record.feature_name}-{GNIS_SOURCE_ID}-{record.feature_id}"),
        geom=from_shape(point, srid=4326),
        centroid=from_shape(point, srid=4326),
        city=region,
        region="New Mexico",
        country="US",
        normalized_category=category,
        normalized_subcategory=subcategory,
        display_categories=[category],
        short_description=description_for_feature_class(record.feature_class),
        primary_source=GNIS_SOURCE_ID,
        raw_tag_summary_json={
            "source": GNIS_SOURCE_ID,
            "feature_id": record.feature_id,
            "feature_class": record.feature_class,
        },
        historical_flag=record.feature_class in {"Civil", "Military", "Populated Place"},
        cultural_flag=record.feature_class in {"Civil", "Military", "Populated Place"},
        scenic_flag=False,
        infrastructure_flag=record.feature_class in {"Canal", "Crossing"},
        food_identity_flag=False,
        walk_affinity_hint=0.35,
        drive_affinity_hint=0.45,
        base_significance_score=4.5,
        quality_score=50.0,
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
            has_official_heritage_match=False,
            official_corroboration_score=0.0,
            district_membership_score=0.0,
            institutional_identity_score=0.0,
            description_quality=description_quality_score(
                poi.short_description,
                poi.normalized_subcategory,
            ),
            entity_type_confidence=0.65,
            local_identity_score=0.45,
            interpretive_value_score=0.45,
            genericity_penalty=0.15,
            editorial_priority_seed=0.45,
            computed_at=now,
        )
    )
    ensure_editorial_stub(session, poi)
    return poi


def upsert_gnis_evidence(
    session: Session,
    poi_id: str,
    record: GNISRecord,
    *,
    evidence_type: str,
) -> POIEvidence:
    key = evidence_key(poi_id, evidence_type, record.feature_id)
    evidence = session.scalar(select(POIEvidence).where(POIEvidence.evidence_key == key))
    evidence_text = (
        "GNIS historical feature designation; the source indicates the name is no longer "
        "in use or the feature no longer serves its original purpose."
        if evidence_type == "historical_feature"
        else f"USGS GNIS official {record.feature_class} name."
    )
    payload = evidence_payload(record)
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=GNIS_SOURCE_ID,
            evidence_type=evidence_type,
            evidence_label=record.feature_name,
            evidence_text=evidence_text,
            evidence_url=GNIS_DOWNLOAD_PAGE_URL,
            external_record_id=record.feature_id,
            confidence=0.75 if evidence_type != "historical_feature" else 0.65,
            raw_evidence_json=payload,
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
        return evidence
    evidence.evidence_label = record.feature_name
    evidence.evidence_text = evidence_text
    evidence.evidence_url = GNIS_DOWNLOAD_PAGE_URL
    evidence.external_record_id = record.feature_id
    evidence.confidence = 0.75 if evidence_type != "historical_feature" else 0.65
    evidence.raw_evidence_json = payload
    evidence.observed_at = datetime.now(UTC)
    return evidence


def attach_variant_name_evidence(session: Session, poi_id: str, record: GNISRecord) -> int:
    created_or_updated = 0
    for variant_name in record.variant_names:
        key = evidence_key(poi_id, "variant_name", f"{record.feature_id}:{variant_name}")
        evidence = session.scalar(select(POIEvidence).where(POIEvidence.evidence_key == key))
        payload = {
            "feature_id": record.feature_id,
            "official_name": record.feature_name,
            "variant_name": variant_name,
            "feature_class": record.feature_class,
        }
        if evidence is None:
            evidence = POIEvidence(
                evidence_key=key,
                poi_id=poi_id,
                source_id=GNIS_SOURCE_ID,
                evidence_type="variant_name",
                evidence_label=variant_name,
                evidence_text="GNIS variant name for the same geographic feature.",
                evidence_url=GNIS_DOWNLOAD_PAGE_URL,
                external_record_id=record.feature_id,
                confidence=0.7,
                raw_evidence_json=payload,
                observed_at=datetime.now(UTC),
            )
            session.add(evidence)
        else:
            evidence.evidence_label = variant_name
            evidence.evidence_text = "GNIS variant name for the same geographic feature."
            evidence.evidence_url = GNIS_DOWNLOAD_PAGE_URL
            evidence.confidence = 0.7
            evidence.raw_evidence_json = payload
            evidence.observed_at = datetime.now(UTC)
        record_sourced_field_values(
            session,
            poi_id=poi_id,
            source_id=GNIS_SOURCE_ID,
            values={"name": variant_name},
            confidence=0.7,
            observed_at=datetime.now(UTC),
        )
        created_or_updated += 1
    return created_or_updated


def persist_gnis_raw_record(session: Session, record: GNISRecord) -> None:
    content_hash = sha256(orjson.dumps(record.raw_payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
    existing = session.scalar(
        select(POISourceRaw).where(
            POISourceRaw.source_name == GNIS_SOURCE_ID,
            POISourceRaw.source_record_id == record.feature_id,
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
            source_name=GNIS_SOURCE_ID,
            source_record_id=record.feature_id,
            source_url=GNIS_DOWNLOAD_PAGE_URL,
            raw_payload_json=record.raw_payload,
            geom=from_shape(Point(record.lon, record.lat), srid=4326),
            fetched_at=now,
            content_hash=content_hash,
            is_current=True,
            license=GNIS_LICENSE_NOTES,
        )
    )


def ensure_gnis_source_registry(session: Session) -> None:
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, GNIS_SOURCE_ID)
    if source is None:
        source = SourceRegistry(
            source_id=GNIS_SOURCE_ID,
            organization_name="U.S. Geological Survey",
            source_name="Geographic Names Information System",
            source_type="geographic_names",
            trust_class="official_geographic_names",
            base_url=GNIS_DOWNLOAD_PAGE_URL,
            license_notes=GNIS_LICENSE_NOTES,
            crawl_allowed=True,
            ingest_method="pipe_delimited_text_zip",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(source)
        return
    source.updated_at = now
    source.is_active = True


def field_values_for_record(record: GNISRecord) -> dict[str, Any]:
    category, _ = category_for_feature_class(record.feature_class)
    return {
        "name": record.feature_name,
        "primary_category": category,
        "coordinates": {"lon": round(float(record.lon), 7), "lat": round(float(record.lat), 7)}
        if record.lon is not None and record.lat is not None
        else None,
        "short_description": description_for_feature_class(record.feature_class),
        "gnis_feature_id": record.feature_id,
        "gnis_feature_class": record.feature_class,
    }


def evidence_payload(record: GNISRecord) -> dict[str, Any]:
    return {
        "feature_id": record.feature_id,
        "feature_class": record.feature_class,
        "state_name": record.state_name,
        "county_name": record.county_name,
        "map_name": record.map_name,
        "date_created": record.date_created,
        "date_edited": record.date_edited,
        "coordinates": {"lon": record.lon, "lat": record.lat},
        "variant_names": list(record.variant_names),
        "historical_designation": record.is_historical,
    }


def category_for_feature_class(feature_class: str) -> tuple[str, str]:
    if feature_class in {"Canal", "Crossing"}:
        return "civic", "infrastructure_landmark"
    if feature_class == "Military":
        return "history", "historic_site"
    return "civic", "civic_space_plaza"


def description_for_feature_class(feature_class: str) -> str:
    return f"USGS GNIS {feature_class.lower()} geographic name."


def evidence_key(poi_id: str, evidence_type: str, external_id: str) -> str:
    return slugify(f"{poi_id}:{GNIS_SOURCE_ID}:{evidence_type}:{external_id}")[:255]


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


def parse_variant_names(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    normalized = value.replace(";", "|").replace(",", "|")
    return tuple(sorted({part.strip() for part in normalized.split("|") if part.strip()}))


def unique_slug(session: Session, value: str) -> str:
    base = slugify(value)[:220]
    slug = base
    suffix = 2
    while session.scalar(select(POI.poi_id).where(POI.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
