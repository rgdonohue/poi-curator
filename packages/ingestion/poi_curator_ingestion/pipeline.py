import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, cast

import orjson
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
)
from poi_curator_domain.descriptions import description_quality_score
from poi_curator_domain.logging_utils import log_event
from poi_curator_domain.regions import RegionSpec
from poi_curator_domain.theme_service import sync_theme_memberships
from sqlalchemy import delete, false, select, true
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, joinedload

from poi_curator_ingestion.normalize import (
    NormalizedPOI,
    geometry_from_overpass_element,
    normalize_osm_element,
    source_record_id_for_element,
)

OSM_SOURCE_NAME = "osm_overpass"
OSM_OVERWRITE_DIAGNOSTIC_STRATEGY = "canonical_overwrite_protection"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OSMIngestSummary:
    region: str
    fetched_count: int
    raw_inserted: int
    raw_updated: int
    canonical_inserted: int
    canonical_updated: int
    skipped_without_name_or_type: int
    stale_deactivated: int
    ingest_run_id: int


@dataclass(frozen=True)
class OSMResetSummary:
    region: str
    poi_deleted: int
    raw_deleted: int
    ingest_runs_deleted: int


@dataclass(frozen=True)
class OSMRefreshSummary:
    region: str
    canonical_inserted: int
    canonical_updated: int
    skipped_without_name_or_type: int


@dataclass(frozen=True)
class CanonicalOverwriteConflict:
    field_name: str
    existing_value: Any
    incoming_value: Any
    reason: str


def ingest_osm_elements(
    session: Session,
    region: RegionSpec,
    elements: list[dict[str, Any]],
    *,
    deactivate_stale: bool = True,
) -> OSMIngestSummary:
    log_event(logger, "osm_ingest_started", region=region.slug, fetched_count=len(elements))
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
    active_osm_ids: set[str] = set()

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

        active_osm_ids.add(normalized.source_record_id)
        created = upsert_canonical_poi(session, raw_record, normalized)
        if created:
            canonical_inserted += 1
        else:
            canonical_updated += 1

    stale_deactivated = 0
    if deactivate_stale:
        stale_deactivated = deactivate_stale_osm_pois(session, region, active_osm_ids)

    ingest_run.status = "completed"
    ingest_run.raw_count = len(elements)
    ingest_run.canonical_insert_count = canonical_inserted
    ingest_run.canonical_update_count = canonical_updated
    ingest_run.completed_at = datetime.now(UTC)
    session.commit()

    summary = OSMIngestSummary(
        region=region.slug,
        fetched_count=len(elements),
        raw_inserted=raw_inserted,
        raw_updated=raw_updated,
        canonical_inserted=canonical_inserted,
        canonical_updated=canonical_updated,
        skipped_without_name_or_type=skipped_without_name_or_type,
        stale_deactivated=stale_deactivated,
        ingest_run_id=ingest_run.id,
    )
    log_event(
        logger,
        "osm_ingest_completed",
        region=summary.region,
        fetched_count=summary.fetched_count,
        raw_inserted=summary.raw_inserted,
        raw_updated=summary.raw_updated,
        canonical_inserted=summary.canonical_inserted,
        canonical_updated=summary.canonical_updated,
        skipped=summary.skipped_without_name_or_type,
        stale_deactivated=summary.stale_deactivated,
        ingest_run_id=summary.ingest_run_id,
    )
    return summary


def refresh_osm_region_from_current_raw(session: Session, region: RegionSpec) -> OSMRefreshSummary:
    log_event(logger, "osm_refresh_started", region=region.slug)
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

    session.commit()
    summary = OSMRefreshSummary(
        region=region.slug,
        canonical_inserted=canonical_inserted,
        canonical_updated=canonical_updated,
        skipped_without_name_or_type=skipped_without_name_or_type,
    )
    log_event(
        logger,
        "osm_refresh_completed",
        region=summary.region,
        canonical_inserted=summary.canonical_inserted,
        canonical_updated=summary.canonical_updated,
        skipped=summary.skipped_without_name_or_type,
    )
    return summary


def reset_osm_region(session: Session, region: RegionSpec) -> OSMResetSummary:
    # FK delete order: membership evidence links -> theme memberships/editorials, aliases,
    # match diagnostics, evidence, source raw, editorial/signals -> canonical POIs -> ingest runs.
    log_event(logger, "osm_reset_started", region=region.slug)
    try:
        poi_ids = session.scalars(
            select(POI.poi_id).where(
                POI.city == region.slug,
                POI.primary_source == OSM_SOURCE_NAME,
            )
        ).all()
        ingest_run_ids = select(IngestRun.id).where(
            IngestRun.region == region.slug,
            IngestRun.source_name == OSM_SOURCE_NAME,
        )

        raw_deleted = cast(
            CursorResult[Any],
            session.execute(
                delete(POISourceRaw).where(
                    (POISourceRaw.canonical_poi_id.in_(poi_ids) if poi_ids else false())
                    | (
                        (POISourceRaw.source_name == OSM_SOURCE_NAME)
                        & POISourceRaw.ingest_run_id.in_(ingest_run_ids)
                    )
                )
            ),
        )
        if poi_ids:
            delete_poi_dependents(session, poi_ids)
        poi_deleted = cast(
            CursorResult[Any],
            session.execute(
                delete(POI).where(
                    POI.city == region.slug,
                    POI.primary_source == OSM_SOURCE_NAME,
                )
            ),
        )
        ingest_runs_deleted = cast(
            CursorResult[Any],
            session.execute(
                delete(IngestRun).where(
                    IngestRun.region == region.slug,
                    IngestRun.source_name == OSM_SOURCE_NAME,
                )
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    summary = OSMResetSummary(
        region=region.slug,
        poi_deleted=poi_deleted.rowcount or 0,
        raw_deleted=raw_deleted.rowcount or 0,
        ingest_runs_deleted=ingest_runs_deleted.rowcount or 0,
    )
    log_event(
        logger,
        "osm_reset_completed",
        region=summary.region,
        poi_deleted=summary.poi_deleted,
        raw_deleted=summary.raw_deleted,
        ingest_runs_deleted=summary.ingest_runs_deleted,
    )
    return summary


def deactivate_stale_osm_pois(
    session: Session,
    region: RegionSpec,
    active_source_record_ids: set[str],
) -> int:
    stale_filter = (
        POI.osm_id.not_in(active_source_record_ids) if active_source_record_ids else true()
    )
    stale_pois = session.scalars(
        select(POI).where(
            POI.city == region.slug,
            POI.primary_source == OSM_SOURCE_NAME,
            POI.is_active.is_(True),
            stale_filter,
        )
    ).all()
    now = datetime.now(UTC)
    for poi in stale_pois:
        poi.is_active = False
        poi.review_status = "stale"
        poi.updated_at = now
    if stale_pois:
        log_event(
            logger,
            "osm_stale_pois_deactivated",
            region=region.slug,
            stale_deactivated=len(stale_pois),
        )
    return len(stale_pois)


def delete_poi_dependents(session: Session, poi_ids: Sequence[str]) -> None:
    membership_ids = select(POIThemeMembership.id).where(POIThemeMembership.poi_id.in_(poi_ids))
    evidence_ids = select(POIEvidence.id).where(POIEvidence.poi_id.in_(poi_ids))
    session.execute(
        delete(POIThemeMembershipEvidence).where(
            (POIThemeMembershipEvidence.membership_id.in_(membership_ids))
            | (POIThemeMembershipEvidence.poi_evidence_id.in_(evidence_ids))
        )
    )
    session.execute(
        delete(OfficialMatchDiagnostic).where(
            (OfficialMatchDiagnostic.matched_poi_id.in_(poi_ids))
            | (OfficialMatchDiagnostic.resolved_poi_id.in_(poi_ids))
        )
    )
    session.execute(delete(POIThemeEditorial).where(POIThemeEditorial.poi_id.in_(poi_ids)))
    session.execute(delete(POIThemeMembership).where(POIThemeMembership.poi_id.in_(poi_ids)))
    session.execute(delete(POIAlias).where(POIAlias.poi_id.in_(poi_ids)))
    session.execute(delete(POIEvidence).where(POIEvidence.poi_id.in_(poi_ids)))
    session.execute(delete(POIEditorial).where(POIEditorial.poi_id.in_(poi_ids)))
    session.execute(delete(POISignals).where(POISignals.poi_id.in_(poi_ids)))


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
        conflicts = update_existing_poi_from_osm(poi, normalized)
        emit_canonical_overwrite_diagnostic(session, poi, normalized, conflicts)
        poi.is_active = True
        if poi.review_status == "stale":
            poi.review_status = "needs_review"

    raw_record.canonical_poi = poi
    upsert_signals(session, poi, raw_record.raw_payload_json.get("tags", {}))
    ensure_editorial_stub(session, poi)
    sync_theme_memberships(session, [poi])
    session.flush()
    return created


def update_existing_poi_from_osm(
    poi: POI,
    normalized: NormalizedPOI,
) -> list[CanonicalOverwriteConflict]:
    conflicts: list[CanonicalOverwriteConflict] = []

    assign_osm_value(
        poi,
        "canonical_name",
        normalized.canonical_name,
        protection_group="title",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "slug",
        normalized.slug,
        protection_group="title",
        conflicts=conflicts,
    )
    poi.geom = from_shape(normalized.geom, srid=4326)
    poi.centroid = from_shape(normalized.centroid, srid=4326)
    poi.city = normalized.city
    poi.region = normalized.region
    poi.country = normalized.country
    assign_osm_value(
        poi,
        "normalized_category",
        normalized.normalized_category,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "normalized_subcategory",
        normalized.normalized_subcategory,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "display_categories",
        normalized.display_categories,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "short_description",
        normalized.short_description,
        protection_group="description",
        conflicts=conflicts,
    )
    poi.raw_tag_summary_json = normalized.raw_tag_summary
    assign_osm_value(
        poi,
        "historical_flag",
        normalized.historical_flag,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "cultural_flag",
        normalized.cultural_flag,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "scenic_flag",
        normalized.scenic_flag,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "infrastructure_flag",
        normalized.infrastructure_flag,
        protection_group="category",
        conflicts=conflicts,
    )
    assign_osm_value(
        poi,
        "food_identity_flag",
        normalized.food_identity_flag,
        protection_group="category",
        conflicts=conflicts,
    )
    poi.walk_affinity_hint = normalized.walk_affinity_hint
    poi.drive_affinity_hint = normalized.drive_affinity_hint
    poi.base_significance_score = normalized.base_significance_score
    poi.quality_score = normalized.quality_score
    poi.updated_at = datetime.now(UTC)
    return conflicts


def assign_osm_value(
    poi: POI,
    field_name: str,
    incoming_value: Any,
    *,
    protection_group: str,
    conflicts: list[CanonicalOverwriteConflict],
) -> None:
    existing_value = getattr(poi, field_name)
    if existing_value == incoming_value:
        return
    if osm_field_is_protected(poi, protection_group):
        conflicts.append(
            CanonicalOverwriteConflict(
                field_name=field_name,
                existing_value=existing_value,
                incoming_value=incoming_value,
                reason=f"{protection_group}_reviewed_or_overridden",
            )
        )
        return
    setattr(poi, field_name, incoming_value)


def osm_field_is_protected(poi: POI, protection_group: str) -> bool:
    editorial = poi.editorial
    if editorial is None:
        return False
    if editorial_status_is_reviewed(editorial.editorial_status):
        return True
    if protection_group == "title":
        return bool(editorial.editorial_title_override)
    if protection_group == "description":
        return bool(editorial.editorial_description_override)
    if protection_group == "category":
        return bool(editorial.editorial_category_override)
    return False


def editorial_status_is_reviewed(status: str | None) -> bool:
    return bool(status and status not in {"unreviewed", "needs_review"})


def emit_canonical_overwrite_diagnostic(
    session: Session,
    poi: POI,
    normalized: NormalizedPOI,
    conflicts: list[CanonicalOverwriteConflict],
) -> None:
    if not conflicts:
        return

    ensure_osm_source_registry(session)
    now = datetime.now(UTC)
    payload = {
        "reason": "incoming_osm_values_conflicted_with_reviewed_canonical_fields",
        "conflicts": [
            {
                "field_name": conflict.field_name,
                "existing_value": conflict.existing_value,
                "incoming_value": conflict.incoming_value,
                "reason": conflict.reason,
            }
            for conflict in conflicts
        ],
    }
    diagnostic = session.scalar(
        select(OfficialMatchDiagnostic).where(
            OfficialMatchDiagnostic.source_id == OSM_SOURCE_NAME,
            OfficialMatchDiagnostic.external_record_id == normalized.source_record_id,
            OfficialMatchDiagnostic.matched_poi_id == poi.poi_id,
            OfficialMatchDiagnostic.match_strategy == OSM_OVERWRITE_DIAGNOSTIC_STRATEGY,
            OfficialMatchDiagnostic.status == "unreviewed",
        )
    )
    if diagnostic is None:
        diagnostic = OfficialMatchDiagnostic(
            source_id=OSM_SOURCE_NAME,
            region=normalized.city,
            external_record_id=normalized.source_record_id,
            external_name=normalized.canonical_name,
            matched_poi_id=poi.poi_id,
            best_candidate_name=poi.canonical_name,
            best_similarity=None,
            match_strategy=OSM_OVERWRITE_DIAGNOSTIC_STRATEGY,
            status="unreviewed",
            resolution_method=None,
            raw_payload_json=payload,
            created_at=now,
            updated_at=now,
        )
        session.add(diagnostic)
        return

    diagnostic.region = normalized.city
    diagnostic.external_name = normalized.canonical_name
    diagnostic.best_candidate_name = poi.canonical_name
    diagnostic.raw_payload_json = payload
    diagnostic.updated_at = now


def ensure_osm_source_registry(session: Session) -> None:
    source = session.get(SourceRegistry, OSM_SOURCE_NAME)
    if source is not None:
        return
    now = datetime.now(UTC)
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
            created_at=now,
            updated_at=now,
        )
    )


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
    signals.official_corroboration_score = 0.0
    signals.district_membership_score = 0.0
    signals.institutional_identity_score = 0.0
    signals.osm_tag_richness = float(len(tags))
    signals.description_quality = description_quality_score(
        poi.short_description,
        poi.normalized_subcategory,
    )
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
