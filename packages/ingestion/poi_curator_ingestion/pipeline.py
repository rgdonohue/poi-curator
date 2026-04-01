from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import orjson
from geoalchemy2.shape import from_shape
from poi_curator_domain.db import POI, IngestRun, POIEditorial, POISignals, POISourceRaw
from poi_curator_domain.regions import RegionSpec
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from poi_curator_ingestion.normalize import (
    NormalizedPOI,
    geometry_from_overpass_element,
    normalize_osm_element,
    source_record_id_for_element,
)

OSM_SOURCE_NAME = "osm_overpass"


@dataclass(frozen=True)
class OSMIngestSummary:
    region: str
    fetched_count: int
    raw_inserted: int
    raw_updated: int
    canonical_inserted: int
    canonical_updated: int
    skipped_without_name_or_type: int
    ingest_run_id: int


def ingest_osm_elements(
    session: Session,
    region: RegionSpec,
    elements: list[dict[str, Any]],
) -> OSMIngestSummary:
    started_at = datetime.now(UTC)
    ingest_run = IngestRun(
        source_name=OSM_SOURCE_NAME,
        region=region.slug,
        status="running",
        started_at=started_at,
    )
    session.add(ingest_run)
    session.flush()

    raw_inserted = 0
    raw_updated = 0
    for element in elements:
        inserted = persist_raw_element(session, ingest_run, element)
        if inserted:
            raw_inserted += 1
        else:
            raw_updated += 1

    canonical_inserted = 0
    canonical_updated = 0
    skipped_without_name_or_type = 0

    current_records = session.scalars(
        select(POISourceRaw)
        .join(POISourceRaw.ingest_run)
        .where(
            POISourceRaw.source_name == OSM_SOURCE_NAME,
            POISourceRaw.is_current.is_(True),
            IngestRun.region == region.slug,
        )
        .options(joinedload(POISourceRaw.canonical_poi))
    ).all()

    for raw_record in current_records:
        normalized = normalize_osm_element(raw_record.raw_payload_json, region)
        if normalized is None:
            skipped_without_name_or_type += 1
            continue

        created = upsert_canonical_poi(session, raw_record, normalized)
        if created:
            canonical_inserted += 1
        else:
            canonical_updated += 1

    ingest_run.status = "completed"
    ingest_run.raw_count = len(elements)
    ingest_run.canonical_insert_count = canonical_inserted
    ingest_run.canonical_update_count = canonical_updated
    ingest_run.completed_at = datetime.now(UTC)
    session.commit()

    return OSMIngestSummary(
        region=region.slug,
        fetched_count=len(elements),
        raw_inserted=raw_inserted,
        raw_updated=raw_updated,
        canonical_inserted=canonical_inserted,
        canonical_updated=canonical_updated,
        skipped_without_name_or_type=skipped_without_name_or_type,
        ingest_run_id=ingest_run.id,
    )


def persist_raw_element(session: Session, ingest_run: IngestRun, element: dict[str, Any]) -> bool:
    source_record_id = source_record_id_for_element(element)
    content_hash = hash_payload(element)
    existing_current = session.scalar(
        select(POISourceRaw).where(
            POISourceRaw.source_name == OSM_SOURCE_NAME,
            POISourceRaw.source_record_id == source_record_id,
            POISourceRaw.is_current.is_(True),
        )
    )

    geom = from_shape(
        normalize_osm_element_geometry(element),
        srid=4326,
    )
    fetched_at = datetime.now(UTC)
    source_url = f"https://www.openstreetmap.org/{source_record_id}"

    if existing_current is not None:
        if existing_current.content_hash == content_hash:
            existing_current.fetched_at = fetched_at
            existing_current.ingest_run = ingest_run
            existing_current.source_url = source_url
            existing_current.raw_payload_json = element
            return False
        existing_current.is_current = False

    raw_record = POISourceRaw(
        source_name=OSM_SOURCE_NAME,
        source_record_id=source_record_id,
        source_url=source_url,
        raw_payload_json=element,
        geom=geom,
        fetched_at=fetched_at,
        content_hash=content_hash,
        is_current=True,
        license="ODbL-1.0",
        ingest_run=ingest_run,
    )
    session.add(raw_record)
    session.flush()
    return True


def upsert_canonical_poi(
    session: Session,
    raw_record: POISourceRaw,
    normalized: NormalizedPOI,
) -> bool:
    poi = session.scalar(select(POI).where(POI.osm_id == normalized.source_record_id))
    created = poi is None

    if poi is None:
        poi = POI(
            canonical_name=normalized.canonical_name,
            slug=normalized.slug,
            geom=from_shape(normalized.geom, srid=4326),
            centroid=from_shape(normalized.centroid, srid=4326),
            city=normalized.city,
            region=normalized.region,
            country=normalized.country,
            normalized_category=normalized.normalized_category,
            normalized_subcategory=normalized.normalized_subcategory,
            display_categories=normalized.display_categories,
            short_description=normalized.short_description,
            primary_source=OSM_SOURCE_NAME,
            osm_id=normalized.source_record_id,
            raw_tag_summary_json=normalized.raw_tag_summary,
            historical_flag=normalized.historical_flag,
            cultural_flag=normalized.cultural_flag,
            scenic_flag=normalized.scenic_flag,
            infrastructure_flag=normalized.infrastructure_flag,
            food_identity_flag=normalized.food_identity_flag,
            walk_affinity_hint=normalized.walk_affinity_hint,
            drive_affinity_hint=normalized.drive_affinity_hint,
            base_significance_score=normalized.base_significance_score,
            quality_score=normalized.quality_score,
            review_status="needs_review",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(poi)
        session.flush()
    else:
        poi.canonical_name = normalized.canonical_name
        poi.slug = normalized.slug
        poi.geom = from_shape(normalized.geom, srid=4326)
        poi.centroid = from_shape(normalized.centroid, srid=4326)
        poi.city = normalized.city
        poi.region = normalized.region
        poi.country = normalized.country
        poi.normalized_category = normalized.normalized_category
        poi.normalized_subcategory = normalized.normalized_subcategory
        poi.display_categories = normalized.display_categories
        poi.short_description = normalized.short_description
        poi.raw_tag_summary_json = normalized.raw_tag_summary
        poi.historical_flag = normalized.historical_flag
        poi.cultural_flag = normalized.cultural_flag
        poi.scenic_flag = normalized.scenic_flag
        poi.infrastructure_flag = normalized.infrastructure_flag
        poi.food_identity_flag = normalized.food_identity_flag
        poi.walk_affinity_hint = normalized.walk_affinity_hint
        poi.drive_affinity_hint = normalized.drive_affinity_hint
        poi.base_significance_score = normalized.base_significance_score
        poi.quality_score = normalized.quality_score
        poi.updated_at = datetime.now(UTC)

    raw_record.canonical_poi = poi
    upsert_signals(session, poi, raw_record.raw_payload_json.get("tags", {}))
    ensure_editorial_stub(session, poi)
    session.flush()
    return created


def upsert_signals(session: Session, poi: POI, tags: dict[str, Any]) -> None:
    signals = session.get(POISignals, poi.poi_id)
    if signals is None:
        signals = POISignals(
            poi_id=poi.poi_id,
            computed_at=datetime.now(UTC),
        )
        session.add(signals)

    source_count = len(poi.raw_sources) if poi.raw_sources else 1
    signals.source_count = source_count
    signals.has_wikidata = "wikidata" in tags
    signals.has_wikipedia = "wikipedia" in tags
    signals.has_official_heritage_match = False
    signals.osm_tag_richness = float(len(tags))
    signals.description_quality = min(float(len(str(tags.get("description", "")))) / 20.0, 10.0)
    signals.entity_type_confidence = 0.75
    signals.local_identity_score = 0.6 if poi.cultural_flag or poi.infrastructure_flag else 0.4
    signals.interpretive_value_score = poi.base_significance_score / 10.0
    signals.genericity_penalty = 0.0 if poi.food_identity_flag or poi.historical_flag else 0.15
    signals.editorial_priority_seed = 0.7 if poi.quality_score >= 65 else 0.4
    signals.computed_at = datetime.now(UTC)


def ensure_editorial_stub(session: Session, poi: POI) -> None:
    editorial = session.get(POIEditorial, poi.poi_id)
    if editorial is None:
        session.add(
            POIEditorial(
                poi_id=poi.poi_id,
                editorial_status="needs_review",
                editorial_boost=0,
            )
        )


def hash_payload(payload: dict[str, Any]) -> str:
    serialized = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    return sha256(serialized).hexdigest()


def normalize_osm_element_geometry(element: dict[str, Any]) -> Any:
    return geometry_from_overpass_element(element)
