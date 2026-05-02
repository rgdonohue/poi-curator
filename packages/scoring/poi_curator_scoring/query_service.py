import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast as type_cast

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from poi_curator_domain.admin_responses import (
    build_admin_match_diagnostic_item,
    build_admin_theme_membership_detail,
    build_theme_evidence_references,
    match_method_for_evidence,
)
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIEvidence,
    POIFieldProvenance,
    POIMatchLog,
    POIThemeMembership,
)
from poi_curator_domain.descriptions import choose_short_description_for_poi
from poi_curator_domain.logging_utils import log_event
from poi_curator_domain.provenance import provenance_conflicts, stable_value_key
from poi_curator_domain.schemas import (
    AdminConflictItem,
    AdminConflictListResponse,
    AdminCoverageResponse,
    AdminFieldProvenanceItem,
    AdminMatchDiagnosticItem,
    AdminMatchLogItem,
    AdminMatchLogListResponse,
    AdminPOIAliasItem,
    AdminPOIDetailEvidenceItem,
    AdminPOIDetailMatchDiagnosticItem,
    AdminPOIDetailResponse,
    AdminPOIEditorialOverrideItem,
    AdminPOIEvidenceItem,
    AdminPOIEvidenceResponse,
    AdminPOIItem,
    AdminPOIListItem,
    AdminPOIListResponse,
    AdminPOIMapFeature,
    AdminPOIMapFeatureCollection,
    AdminPOIMapFeatureGeometry,
    AdminPOIMapFeatureProperties,
    AdminPOIMapResponse,
    AdminPOIProvenanceResponse,
    AdminThemeMembershipDetailResponse,
    AdminThemeMembershipQueueItem,
    AdminThemeSummaryItem,
    NearbyQuerySummary,
    NearbyResult,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIDetailResponse,
    POIThemeItem,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
from poi_curator_domain.theme_service import (
    get_theme_editorial_by_slug,
    get_theme_membership_by_slug,
    resolve_effective_theme_membership,
    resolve_effective_theme_memberships,
    reviewable_theme_slugs,
    sync_theme_memberships,
    theme_review_state,
)
from poi_curator_domain.themes import (
    THEME_LABELS,
    ThemeSlug,
    is_query_theme_active,
)
from shapely.geometry import Point
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.elements import ColumnElement

from poi_curator_scoring.db_point_scoring import (
    build_nearby_result,
    compute_point_candidate_metrics,
    is_within_radius,
    score_point_candidate,
)
from poi_curator_scoring.db_route_scoring import (
    build_route_line,
    build_route_result,
    category_matches,
    compute_candidate_metrics,
    is_within_budget,
    score_candidate,
)
from poi_curator_scoring.place_representation import build_place_representation
from poi_curator_scoring.shared_scoring import build_badges, build_why_it_matters

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminPOIBrowserRecord:
    poi: POI
    item: AdminPOIListItem


def suggest_places(db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
    candidate_query = select(POI).options(
        joinedload(POI.signals),
        joinedload(POI.editorial),
    )
    if payload.theme is not None:
        candidate_query = candidate_query.options(
            joinedload(POI.aliases),
            joinedload(POI.evidence_items),
            joinedload(POI.theme_memberships),
            joinedload(POI.theme_editorials),
        )
    if payload.region_hint is not None:
        candidate_query = candidate_query.where(POI.city == payload.region_hint)

    route_line = build_route_line(payload)
    candidate_query = candidate_query.where(
        POI.is_active.is_(True),
        _route_prefilter_clause(route_line.wkt, payload.max_detour_meters),
    ).order_by(POI.poi_id)
    pois = db.execute(candidate_query).unique().scalars().all()
    if payload.theme is not None:
        _ensure_theme_memberships(db, pois)
    log_event(
        logger,
        "route_candidates_prefiltered",
        region=payload.region_hint,
        category=payload.category,
        theme=payload.theme,
        mode=payload.travel_mode,
        max_detour_meters=payload.max_detour_meters,
        candidate_count=len(pois),
    )
    if not pois:
        return RouteSuggestResponse(
            data_source="database",
            query_summary=QuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                theme=payload.theme,
                max_detour_meters=payload.max_detour_meters,
                limit=payload.limit,
            ),
            results=[],
        )

    scored_results: list[tuple[float, str, RouteResult]] = []
    for poi in pois:
        if not category_matches(payload, poi):
            continue
        if not _poi_matches_theme(poi, payload.theme):
            continue

        geometry = to_shape(poi.geom)
        centroid = to_shape(poi.centroid)
        representation = build_place_representation(
            poi,
            geometry,
            query_geometry=route_line,
            fallback_point=centroid,
        )
        metrics = compute_candidate_metrics(payload, route_line, representation.anchor_point)
        if not is_within_budget(payload, metrics):
            continue

        score, score_breakdown, category_match = score_candidate(poi, payload, metrics)
        scored_results.append(
            (
                score,
                poi.poi_id,
                build_route_result(
                    poi,
                    representation.anchor_point,
                    metrics,
                    score,
                    score_breakdown,
                    category_match,
                    requested_theme=payload.theme,
                    extended_place=representation.extended_place,
                ),
            )
        )

    scored_results.sort(key=lambda item: (-item[0], item[1]))
    response = RouteSuggestResponse(
        data_source="database",
        query_summary=QuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            theme=payload.theme,
            max_detour_meters=payload.max_detour_meters,
            limit=payload.limit,
        ),
        results=[result for _, _, result in scored_results[: payload.limit]],
    )
    log_event(
        logger,
        "route_suggest_completed",
        region=payload.region_hint,
        category=payload.category,
        theme=payload.theme,
        mode=payload.travel_mode,
        candidate_count=len(pois),
        result_count=len(response.results),
    )
    return response


def suggest_nearby_places(db: Session, payload: NearbySuggestRequest) -> NearbySuggestResponse:
    candidate_query = select(POI).options(
        joinedload(POI.signals),
        joinedload(POI.editorial),
    )
    if payload.theme is not None:
        candidate_query = candidate_query.options(
            joinedload(POI.aliases),
            joinedload(POI.evidence_items),
            joinedload(POI.theme_memberships),
            joinedload(POI.theme_editorials),
        )
    if payload.region_hint is not None:
        candidate_query = candidate_query.where(POI.city == payload.region_hint)

    candidate_query = candidate_query.where(
        POI.is_active.is_(True),
        _nearby_prefilter_clause(payload.center.lon, payload.center.lat, payload.radius_meters),
    ).order_by(POI.poi_id)
    pois = db.execute(candidate_query).unique().scalars().all()
    if payload.theme is not None:
        _ensure_theme_memberships(db, pois)
    log_event(
        logger,
        "nearby_candidates_prefiltered",
        region=payload.region_hint,
        category=payload.category,
        theme=payload.theme,
        mode=payload.travel_mode,
        radius_meters=payload.radius_meters,
        candidate_count=len(pois),
    )
    if not pois:
        return NearbySuggestResponse(
            data_source="database",
            query_summary=NearbyQuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                theme=payload.theme,
                radius_meters=payload.radius_meters,
                limit=payload.limit,
            ),
            results=[],
        )

    query_point = Point(payload.center.lon, payload.center.lat)
    scored_results: list[tuple[float, str, NearbyResult]] = []
    for poi in pois:
        if not category_matches(payload, poi):
            continue
        if not _poi_matches_theme(poi, payload.theme):
            continue

        geometry = to_shape(poi.geom)
        centroid = to_shape(poi.centroid)
        representation = build_place_representation(
            poi,
            geometry,
            query_geometry=query_point,
            fallback_point=centroid,
        )
        metrics = compute_point_candidate_metrics(payload, query_point, representation.anchor_point)
        if not is_within_radius(payload, metrics):
            continue

        score, score_breakdown, category_match = score_point_candidate(poi, payload, metrics)
        scored_results.append(
            (
                score,
                poi.poi_id,
                build_nearby_result(
                    poi,
                    representation.anchor_point,
                    metrics,
                    score,
                    score_breakdown,
                    category_match,
                    payload.travel_mode,
                    requested_theme=payload.theme,
                    extended_place=representation.extended_place,
                ),
            )
        )

    scored_results.sort(key=lambda item: (-item[0], item[1]))
    response = NearbySuggestResponse(
        data_source="database",
        query_summary=NearbyQuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            theme=payload.theme,
            radius_meters=payload.radius_meters,
            limit=payload.limit,
        ),
        results=[result for _, _, result in scored_results[: payload.limit]],
    )
    log_event(
        logger,
        "nearby_suggest_completed",
        region=payload.region_hint,
        category=payload.category,
        theme=payload.theme,
        mode=payload.travel_mode,
        radius_meters=payload.radius_meters,
        candidate_count=len(pois),
        result_count=len(response.results),
    )
    return response


def get_poi_detail(db: Session, poi_id: str) -> POIDetailResponse | None:
    poi = db.scalar(
        select(POI)
        .where(POI.poi_id == poi_id)
        .options(
            joinedload(POI.raw_sources),
            joinedload(POI.signals),
            joinedload(POI.editorial),
            joinedload(POI.evidence_items),
            joinedload(POI.field_provenance),
            joinedload(POI.aliases),
            joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
            joinedload(POI.theme_editorials),
        )
    )
    if poi is None:
        return None
    _ensure_theme_memberships(db, [poi])

    geometry = to_shape(poi.geom)
    centroid = to_shape(poi.centroid)
    representation = build_place_representation(
        poi,
        geometry,
        fallback_point=centroid,
    )
    return POIDetailResponse(
        poi_id=poi.poi_id,
        name=poi.canonical_name,
        primary_category=poi.normalized_category,
        secondary_categories=[
            category for category in poi.display_categories if category != poi.normalized_category
        ],
        coordinates=[representation.anchor_point.x, representation.anchor_point.y],
        short_description=choose_short_description_for_poi(poi),
        why_it_matters=build_why_it_matters(poi),
        badges=build_badges(poi, include_source_badges=True),
        provenance={
            "primary_source": poi.primary_source,
            "osm_id": poi.osm_id,
            "wikidata_id": poi.wikidata_id,
            "wikipedia_title": poi.wikipedia_title,
            "raw_source_count": len(poi.raw_sources),
            "field_sources": _field_sources(poi.field_provenance),
        },
        evidence=[
            {
                "source_id": item.source_id,
                "evidence_type": item.evidence_type,
                "label": item.evidence_label,
                "text": item.evidence_text,
                "url": item.evidence_url,
                "confidence": item.confidence,
            }
            for item in sorted(
                poi.evidence_items,
                key=lambda item: (item.source_id, item.evidence_type, item.evidence_label or ""),
            )
        ],
        themes=_build_theme_items(poi),
        extended_place=representation.extended_place,
    )


def get_admin_queue(
    db: Session,
    *,
    status: str,
    city: str | None,
) -> list[AdminPOIItem]:
    query = select(POI).options(joinedload(POI.editorial))
    if city is not None:
        query = query.where(POI.city == city)
    pois = db.scalars(query.order_by(POI.updated_at.desc())).all()
    return [
        AdminPOIItem(
            poi_id=poi.poi_id,
            name=poi.canonical_name,
            city=poi.city,
            status=_status_for_poi(poi),
            primary_category=poi.normalized_category,
            notes=f"source={poi.primary_source} quality={poi.quality_score:.1f}",
        )
        for poi in pois
        if _status_for_poi(poi) == status
    ]


def get_admin_poi_list(
    db: Session,
    *,
    search: str | None,
    category: str | None,
    review_state: str | None,
    source: str | None,
    themes: Sequence[str],
    theme_match: str,
    has_diagnostics: bool | None,
    has_editorial_overrides: bool | None,
    active_only: bool,
    limit: int,
    offset: int,
) -> AdminPOIListResponse:
    records = _load_admin_poi_browser_records(
        db,
        search=search,
        category=category,
        review_state=review_state,
        source=source,
        themes=themes,
        theme_match=theme_match,
        has_diagnostics=has_diagnostics,
        has_editorial_overrides=has_editorial_overrides,
        active_only=active_only,
        bbox=None,
    )
    total = len(records)
    page = records[offset : offset + limit]
    return AdminPOIListResponse(
        items=[record.item for record in page],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_admin_poi_map(
    db: Session,
    *,
    search: str | None,
    category: str | None,
    review_state: str | None,
    source: str | None,
    themes: Sequence[str],
    theme_match: str,
    has_diagnostics: bool | None,
    has_editorial_overrides: bool | None,
    active_only: bool,
    bbox: str | None,
    limit: int,
) -> AdminPOIMapResponse:
    records = _load_admin_poi_browser_records(
        db,
        search=search,
        category=category,
        review_state=review_state,
        source=source,
        themes=themes,
        theme_match=theme_match,
        has_diagnostics=has_diagnostics,
        has_editorial_overrides=has_editorial_overrides,
        active_only=active_only,
        bbox=_parse_bbox(bbox),
    )
    records = sorted(records, key=lambda record: record.item.poi_id)
    total = len(records)
    returned_records = records[:limit]
    features = [
        AdminPOIMapFeature(
            geometry=AdminPOIMapFeatureGeometry(coordinates=record.item.coordinates or []),
            properties=AdminPOIMapFeatureProperties(
                poi_id=record.item.poi_id,
                name=record.item.name,
                primary_category=record.item.primary_category,
                review_state=record.item.review_state,
                source=record.item.source,
                themes=record.item.themes,
                has_diagnostics=record.item.has_diagnostics,
                has_editorial_overrides=record.item.has_editorial_overrides,
                is_active=record.item.is_active,
                stale_since=record.item.stale_since,
            ),
        )
        for record in returned_records
        if record.item.coordinates is not None
    ]
    return AdminPOIMapResponse(
        feature_collection=AdminPOIMapFeatureCollection(features=features),
        total_matching=total,
        returned=len(features),
        truncated=total > limit,
        limit=limit,
    )


def get_admin_poi_detail(
    db: Session,
    poi_id: str,
) -> AdminPOIDetailResponse | None:
    canonical = get_poi_detail(db, poi_id)
    if canonical is None:
        return None

    poi = db.scalar(
        select(POI)
        .where(POI.poi_id == poi_id)
        .options(
            joinedload(POI.aliases),
            joinedload(POI.editorial),
            joinedload(POI.evidence_items).joinedload(POIEvidence.source),
            joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
            joinedload(POI.theme_editorials),
        )
    )
    if poi is None:
        return None

    diagnostics = _load_match_diagnostics_by_poi_ids(db, [poi.poi_id]).get(poi.poi_id, [])
    return AdminPOIDetailResponse(
        poi_id=poi.poi_id,
        canonical=canonical,
        editorial_overrides=_build_editorial_overrides(poi),
        aliases=_build_alias_items(poi),
        evidence=_build_detail_evidence_items(poi),
        themes=canonical.themes,
        match_diagnostics=[
            _build_poi_detail_match_diagnostic_item(diagnostic)
            for diagnostic in sorted(
                diagnostics,
                key=lambda item: (item.updated_at, item.id),
                reverse=True,
            )
        ],
        external_links=_build_external_links(poi),
        last_updated=poi.updated_at,
    )


def get_admin_poi_evidence(
    db: Session,
    poi_id: str,
) -> AdminPOIEvidenceResponse | None:
    poi = db.scalar(
        select(POI)
        .where(POI.poi_id == poi_id)
        .options(
            joinedload(POI.aliases),
            joinedload(POI.evidence_items).joinedload(POIEvidence.source),
            joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
            joinedload(POI.theme_editorials),
        )
    )
    if poi is None:
        return None
    _ensure_theme_memberships(db, [poi])

    evidence_items = sorted(
        poi.evidence_items,
        key=lambda item: (item.observed_at, item.source_id, item.evidence_type),
        reverse=True,
    )
    return AdminPOIEvidenceResponse(
        poi_id=poi.poi_id,
        name=poi.canonical_name,
        primary_category=poi.normalized_category,
        aliases=[
            AdminPOIAliasItem(
                alias_name=alias.alias_name,
                normalized_alias=alias.normalized_alias,
                alias_type=alias.alias_type,
                source=alias.source,
                confidence=alias.confidence,
                is_preferred=alias.is_preferred,
                notes=alias.notes,
                created_at=alias.created_at,
            )
            for alias in sorted(
                poi.aliases,
                key=lambda alias: (not alias.is_preferred, alias.alias_name.lower()),
            )
        ],
        evidence=[
            AdminPOIEvidenceItem(
                source_id=item.source_id,
                source_name=item.source.source_name if item.source is not None else None,
                source_type=item.source.source_type if item.source is not None else None,
                trust_class=item.source.trust_class if item.source is not None else None,
                evidence_type=item.evidence_type,
                label=item.evidence_label,
                text=item.evidence_text,
                url=item.evidence_url,
                external_record_id=item.external_record_id,
                confidence=item.confidence,
                match_method=match_method_for_evidence(item),
                observed_at=item.observed_at,
            )
            for item in evidence_items
        ],
        themes=_build_theme_items(poi),
    )


def get_admin_theme_summaries(
    db: Session,
    *,
    city: str | None,
) -> list[AdminThemeSummaryItem]:
    pois = _load_admin_theme_pois(db, city=city)
    counts_by_theme: dict[str, dict[str, int]] = {
        theme_slug: {
            "automated_accepted_count": 0,
            "automated_candidate_count": 0,
            "reviewed_count": 0,
            "unreviewed_count": 0,
            "stale_count": 0,
            "force_included_count": 0,
            "force_excluded_count": 0,
        }
        for theme_slug in THEME_LABELS
    }

    for poi in pois:
        for theme_slug in reviewable_theme_slugs(poi):
            membership = get_theme_membership_by_slug(poi, theme_slug)
            editorial = get_theme_editorial_by_slug(poi, theme_slug)
            if membership is not None:
                if membership.status == "accepted":
                    counts_by_theme[theme_slug]["automated_accepted_count"] += 1
                elif membership.status == "candidate":
                    counts_by_theme[theme_slug]["automated_candidate_count"] += 1

            review_state = theme_review_state(membership, editorial)
            counts_by_theme[theme_slug][f"{review_state}_count"] += 1

            if editorial is not None and editorial.editorial_decision == "force_include":
                counts_by_theme[theme_slug]["force_included_count"] += 1
            if editorial is not None and editorial.editorial_decision == "force_exclude":
                counts_by_theme[theme_slug]["force_excluded_count"] += 1

    return [
        AdminThemeSummaryItem(
            theme_slug=type_cast(ThemeSlug, theme_slug),
            label=THEME_LABELS[theme_slug],
            is_query_active=is_query_theme_active(theme_slug),
            automated_accepted_count=counts["automated_accepted_count"],
            automated_candidate_count=counts["automated_candidate_count"],
            reviewed_count=counts["reviewed_count"],
            unreviewed_count=counts["unreviewed_count"],
            stale_count=counts["stale_count"],
            force_included_count=counts["force_included_count"],
            force_excluded_count=counts["force_excluded_count"],
        )
        for theme_slug, counts in counts_by_theme.items()
    ]


def get_admin_theme_memberships(
    db: Session,
    *,
    theme_slug: str | None,
    city: str | None,
    automated_status: str | None,
    review_state: str | None,
    editorial_decision: str | None,
    limit: int,
) -> list[AdminThemeMembershipQueueItem]:
    pois = _load_admin_theme_pois(db, city=city)
    items: list[AdminThemeMembershipQueueItem] = []

    for poi in pois:
        for candidate_theme_slug in reviewable_theme_slugs(poi):
            if theme_slug is not None and candidate_theme_slug != theme_slug:
                continue
            membership = get_theme_membership_by_slug(poi, candidate_theme_slug)
            editorial = get_theme_editorial_by_slug(poi, candidate_theme_slug)
            if membership is None and editorial is None:
                continue

            if automated_status is not None and (
                membership is None or membership.status != automated_status
            ):
                continue
            if editorial_decision is not None and (
                editorial is None or editorial.editorial_decision != editorial_decision
            ):
                continue

            item_review_state = theme_review_state(membership, editorial)
            if review_state is not None and item_review_state != review_state:
                continue

            effective = resolve_effective_theme_membership(
                candidate_theme_slug,
                membership,
                editorial,
            )
            items.append(
                AdminThemeMembershipQueueItem(
                    poi_id=poi.poi_id,
                    poi_name=poi.canonical_name,
                    city=poi.city,
                    primary_category=poi.normalized_category,
                    theme_slug=candidate_theme_slug,
                    theme_label=THEME_LABELS[candidate_theme_slug],
                    automated_status=membership.status if membership is not None else None,
                    automated_assignment_basis=(
                        membership.assignment_basis if membership is not None else None
                    ),
                    automated_confidence=(
                        round(float(membership.confidence), 2) if membership is not None else None
                    ),
                    evidence_count=len(getattr(membership, "evidence_links", []) or []),
                    computed_at=membership.computed_at if membership is not None else None,
                    editorial_decision=(
                        editorial.editorial_decision if editorial is not None else None
                    ),
                    review_state=item_review_state,
                    reviewed_at=editorial.reviewed_at if editorial is not None else None,
                    effective_status=effective.status if effective is not None else None,
                )
            )

    items.sort(
        key=lambda item: (
            _review_state_priority(item.review_state),
            _automated_status_priority(item.automated_status),
            item.automated_confidence if item.automated_confidence is not None else 1.0,
            item.poi_name.casefold(),
        )
    )
    return items[:limit]


def get_admin_theme_membership_detail(
    db: Session,
    *,
    poi_id: str,
    theme_slug: str,
) -> AdminThemeMembershipDetailResponse | None:
    poi = db.scalar(
        select(POI)
        .where(POI.poi_id == poi_id)
        .options(
            joinedload(POI.evidence_items),
            joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
            joinedload(POI.theme_editorials),
        )
    )
    if poi is None:
        return None

    _ensure_theme_memberships(db, [poi])
    membership = get_theme_membership_by_slug(poi, theme_slug)
    editorial = get_theme_editorial_by_slug(poi, theme_slug)
    if membership is None and editorial is None:
        return None
    return build_admin_theme_membership_detail(poi, theme_slug)


def get_admin_match_diagnostics(
    db: Session,
    *,
    region: str | None,
    source_id: str | None,
    status: str,
    limit: int,
) -> list[AdminMatchDiagnosticItem]:
    query = select(OfficialMatchDiagnostic).options(
        joinedload(OfficialMatchDiagnostic.source),
        joinedload(OfficialMatchDiagnostic.poi),
        joinedload(OfficialMatchDiagnostic.resolved_poi),
    )
    if region is not None:
        query = query.where(OfficialMatchDiagnostic.region == region)
    if source_id is not None:
        query = query.where(OfficialMatchDiagnostic.source_id == source_id)
    if status == "unreviewed":
        query = query.where(OfficialMatchDiagnostic.status.in_(("unreviewed", "unmatched")))
    elif status != "all":
        query = query.where(OfficialMatchDiagnostic.status == status)
    diagnostics = db.scalars(
        query.order_by(OfficialMatchDiagnostic.updated_at.desc()).limit(limit)
    ).all()
    return [build_admin_match_diagnostic_item(item) for item in diagnostics]


def get_admin_poi_provenance(
    db: Session,
    poi_id: str,
) -> AdminPOIProvenanceResponse | None:
    poi = db.scalar(
        select(POI)
        .where(POI.poi_id == poi_id)
        .options(joinedload(POI.field_provenance))
    )
    if poi is None:
        return None
    rows = sorted(
        poi.field_provenance,
        key=lambda row: (row.field_name, not row.is_canonical, row.source_id, row.observed_at),
    )
    by_field: dict[str, list[AdminFieldProvenanceItem]] = {}
    for row in rows:
        by_field.setdefault(row.field_name, []).append(_build_field_provenance_item(row))
    conflict_rows = provenance_conflicts(rows)
    return AdminPOIProvenanceResponse(
        poi_id=poi.poi_id,
        name=poi.canonical_name,
        fields=by_field,
        conflicts={
            field_name: [_build_field_provenance_item(row) for row in field_rows]
            for field_name, field_rows in conflict_rows.items()
        },
    )


def get_admin_conflicts(
    db: Session,
    *,
    source_pair: str | None,
    field_name: str | None,
    limit: int,
    offset: int,
) -> AdminConflictListResponse:
    rows = db.scalars(
        select(POIFieldProvenance)
        .join(POI)
        .options(joinedload(POIFieldProvenance.poi))
        .order_by(POIFieldProvenance.observed_at.desc(), POIFieldProvenance.id.desc())
    ).all()
    requested_sources = {
        item.strip() for item in source_pair.split(",")
    } if source_pair else set()
    grouped: dict[tuple[str, str], list[POIFieldProvenance]] = {}
    for row in rows:
        if field_name is not None and row.field_name != field_name:
            continue
        grouped.setdefault((row.poi_id, row.field_name), []).append(row)

    items: list[AdminConflictItem] = []
    for (_poi_id, grouped_field), field_rows in grouped.items():
        if len({stable_value_key(row.value) for row in field_rows}) <= 1:
            continue
        sources = sorted({row.source_id for row in field_rows})
        if requested_sources and not requested_sources.issubset(set(sources)):
            continue
        canonical_row = next((row for row in field_rows if row.is_canonical), None)
        poi = field_rows[0].poi
        items.append(
            AdminConflictItem(
                poi_id=poi.poi_id,
                name=poi.canonical_name,
                field_name=grouped_field,
                canonical_value=canonical_row.value if canonical_row is not None else None,
                sources=sources,
                values=[_build_field_provenance_item(row) for row in field_rows],
                last_observed_at=max(row.observed_at for row in field_rows),
            )
        )
    items.sort(key=lambda item: (item.last_observed_at, item.poi_id, item.field_name), reverse=True)
    total = len(items)
    return AdminConflictListResponse(
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_admin_coverage(db: Session) -> AdminCoverageResponse:
    rows = db.scalars(select(POIFieldProvenance)).all()
    sources_by_poi: dict[str, set[str]] = {}
    for row in rows:
        sources_by_poi.setdefault(row.poi_id, set()).add(row.source_id)
    total_pois = db.scalar(select(func.count()).select_from(POI)) or 0
    by_source: dict[str, int] = {}
    by_source_pair: dict[str, int] = {}
    single_source_gaps: dict[str, int] = {}
    for sources in sources_by_poi.values():
        for source in sources:
            by_source[source] = by_source.get(source, 0) + 1
        sorted_sources = sorted(sources)
        if len(sorted_sources) == 1:
            only = sorted_sources[0]
            single_source_gaps[only] = single_source_gaps.get(only, 0) + 1
        for left_index, left in enumerate(sorted_sources):
            for right in sorted_sources[left_index + 1 :]:
                key = f"{left}+{right}"
                by_source_pair[key] = by_source_pair.get(key, 0) + 1
    return AdminCoverageResponse(
        by_source=dict(sorted(by_source.items())),
        by_source_pair=dict(sorted(by_source_pair.items())),
        single_source_gaps=dict(sorted(single_source_gaps.items())),
        total_pois=int(total_pois),
    )


def get_admin_match_logs(
    db: Session,
    *,
    source: str | None,
    decision: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int,
    offset: int,
) -> AdminMatchLogListResponse:
    query = select(POIMatchLog).options(joinedload(POIMatchLog.canonical_poi))
    if source is not None:
        query = query.where(POIMatchLog.candidate_source == source)
    if decision is not None:
        query = query.where(POIMatchLog.decision == decision)
    if start is not None:
        query = query.where(POIMatchLog.decided_at >= start)
    if end is not None:
        query = query.where(POIMatchLog.decided_at <= end)
    all_rows = db.scalars(
        query.order_by(POIMatchLog.decided_at.desc(), POIMatchLog.id.desc())
    ).all()
    page = all_rows[offset : offset + limit]
    return AdminMatchLogListResponse(
        items=[
            AdminMatchLogItem(
                id=row.id,
                canonical_poi_id=row.canonical_poi_id,
                canonical_name=row.canonical_poi.canonical_name
                if row.canonical_poi is not None
                else None,
                candidate_source=row.candidate_source,
                candidate_external_id=row.candidate_external_id,
                match_strategy=row.match_strategy,
                match_score=row.match_score,
                decision=row.decision,
                decided_at=row.decided_at,
                decided_by=row.decided_by,
                notes=row.notes,
            )
            for row in page
        ],
        total=len(all_rows),
        limit=limit,
        offset=offset,
    )


def _load_admin_poi_browser_records(
    db: Session,
    *,
    search: str | None,
    category: str | None,
    review_state: str | None,
    source: str | None,
    themes: Sequence[str],
    theme_match: str,
    has_diagnostics: bool | None,
    has_editorial_overrides: bool | None,
    active_only: bool,
    bbox: tuple[float, float, float, float] | None,
) -> list[AdminPOIBrowserRecord]:
    query = select(POI).options(
        joinedload(POI.aliases),
        joinedload(POI.editorial),
        joinedload(POI.evidence_items).joinedload(POIEvidence.source),
        joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
        joinedload(POI.theme_editorials),
    )
    if active_only:
        query = query.where(POI.is_active.is_(True))
    if category is not None:
        query = query.where(POI.normalized_category == category)

    pois = db.execute(query.order_by(POI.updated_at.desc(), POI.poi_id)).unique().scalars().all()
    diagnostics_by_poi_id = _load_match_diagnostics_by_poi_ids(
        db,
        [poi.poi_id for poi in pois],
    )
    normalized_search = search.casefold().strip() if search else None
    normalized_source = source.casefold().strip() if source else None
    requested_themes = [theme.strip() for theme in themes if theme.strip()]
    records: list[AdminPOIBrowserRecord] = []

    for poi in pois:
        item_review_state = _status_for_poi(poi)
        if review_state is not None and item_review_state != review_state:
            continue
        if normalized_search is not None and not _matches_search(poi, normalized_search):
            continue
        if normalized_source is not None and not _matches_source(poi, normalized_source):
            continue

        effective_themes = _theme_slugs_for_poi(poi)
        if requested_themes and not _matches_theme_set(
            effective_themes,
            requested_themes,
            theme_match,
        ):
            continue

        has_diagnostic_rows = bool(diagnostics_by_poi_id.get(poi.poi_id))
        if has_diagnostics is not None and has_diagnostic_rows != has_diagnostics:
            continue

        has_overrides = _has_editorial_overrides(poi)
        if has_editorial_overrides is not None and has_overrides != has_editorial_overrides:
            continue

        coordinates = _coordinates_for_poi(poi)
        if bbox is not None and not _coordinates_within_bbox(coordinates, bbox):
            continue

        records.append(
            AdminPOIBrowserRecord(
                poi=poi,
                item=AdminPOIListItem(
                    poi_id=poi.poi_id,
                    name=poi.canonical_name,
                    primary_category=poi.normalized_category,
                    secondary_categories=[
                        category
                        for category in poi.display_categories
                        if category != poi.normalized_category
                    ],
                    review_state=item_review_state,
                    source=poi.primary_source,
                    themes=effective_themes,
                    last_updated=poi.updated_at,
                    coordinates=coordinates,
                    has_diagnostics=has_diagnostic_rows,
                    has_editorial_overrides=has_overrides,
                    is_active=poi.is_active,
                    stale_since=_stale_since_for_poi(poi, item_review_state),
                ),
            )
        )

    return records


def _build_field_provenance_item(row: POIFieldProvenance) -> AdminFieldProvenanceItem:
    return AdminFieldProvenanceItem(
        id=row.id,
        field_name=row.field_name,
        source_id=row.source_id,
        value=row.value,
        confidence=row.confidence,
        observed_at=row.observed_at,
        is_canonical=row.is_canonical,
    )


def _field_sources(rows: Sequence[POIFieldProvenance]) -> dict[str, list[str]]:
    sources: dict[str, set[str]] = {}
    for row in rows:
        sources.setdefault(row.field_name, set()).add(row.source_id)
    return {field_name: sorted(field_sources) for field_name, field_sources in sources.items()}


def _load_match_diagnostics_by_poi_ids(
    db: Session,
    poi_ids: Sequence[str],
) -> dict[str, list[OfficialMatchDiagnostic]]:
    if not poi_ids:
        return {}
    diagnostics = db.scalars(
        select(OfficialMatchDiagnostic)
        .where(
            or_(
                OfficialMatchDiagnostic.matched_poi_id.in_(poi_ids),
                OfficialMatchDiagnostic.resolved_poi_id.in_(poi_ids),
            )
        )
        .options(
            joinedload(OfficialMatchDiagnostic.source),
            joinedload(OfficialMatchDiagnostic.poi),
            joinedload(OfficialMatchDiagnostic.resolved_poi),
        )
        .order_by(OfficialMatchDiagnostic.updated_at.desc(), OfficialMatchDiagnostic.id)
    ).all()
    by_poi_id: dict[str, list[OfficialMatchDiagnostic]] = {poi_id: [] for poi_id in poi_ids}
    for diagnostic in diagnostics:
        if diagnostic.matched_poi_id in by_poi_id:
            by_poi_id[diagnostic.matched_poi_id].append(diagnostic)
        if (
            diagnostic.resolved_poi_id in by_poi_id
            and diagnostic.resolved_poi_id != diagnostic.matched_poi_id
        ):
            by_poi_id[diagnostic.resolved_poi_id].append(diagnostic)
    return by_poi_id


def _matches_search(poi: POI, normalized_search: str) -> bool:
    if normalized_search in poi.canonical_name.casefold():
        return True
    return any(
        normalized_search in alias.alias_name.casefold()
        or normalized_search in alias.normalized_alias.casefold()
        for alias in getattr(poi, "aliases", []) or []
    )


def _matches_source(poi: POI, normalized_source: str) -> bool:
    if normalized_source in poi.primary_source.casefold():
        return True
    for item in getattr(poi, "evidence_items", []) or []:
        source_values = [
            item.source_id,
            item.source.source_name if item.source is not None else None,
            item.source.source_type if item.source is not None else None,
        ]
        if any(
            value is not None and normalized_source in value.casefold()
            for value in source_values
        ):
            return True
    return False


def _theme_slugs_for_poi(poi: POI) -> list[str]:
    resolved = resolve_effective_theme_memberships(poi)
    return [
        str(theme_slug)
        for theme_slug, membership in sorted(resolved.items())
        if membership.status != "suppressed"
    ]


def _matches_theme_set(
    effective_themes: Sequence[str],
    requested_themes: Sequence[str],
    theme_match: str,
) -> bool:
    effective = set(effective_themes)
    requested = set(requested_themes)
    if theme_match == "all":
        return requested.issubset(effective)
    return bool(effective.intersection(requested))


def _coordinates_for_poi(poi: POI) -> list[float] | None:
    if poi.centroid is None:
        return None
    point = to_shape(poi.centroid)
    return [point.x, point.y]


def _coordinates_within_bbox(
    coordinates: list[float] | None,
    bbox: tuple[float, float, float, float],
) -> bool:
    if coordinates is None:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    lon, lat = coordinates
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _parse_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if value is None or not value.strip():
        return None
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat")
    try:
        min_lon, min_lat, max_lon, max_lat = [float(part.strip()) for part in parts]
    except ValueError as exc:
        raise ValueError("bbox must contain numeric coordinates") from exc
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("bbox minimum coordinates must be less than maximum coordinates")
    return (min_lon, min_lat, max_lon, max_lat)


def _has_editorial_overrides(poi: POI) -> bool:
    editorial = poi.editorial
    return editorial is not None and any(
        (
            editorial.editorial_title_override is not None,
            editorial.editorial_description_override is not None,
            editorial.editorial_category_override is not None,
            editorial.editorial_boost != 0,
        )
    )


def _stale_since_for_poi(poi: POI, review_state: str) -> datetime | None:
    if not poi.is_active and review_state == "stale":
        return poi.updated_at
    return None


def _build_editorial_overrides(poi: POI) -> dict[str, AdminPOIEditorialOverrideItem]:
    editorial = poi.editorial
    if editorial is None:
        return {}
    updated_at = editorial.last_reviewed_at
    updated_by = editorial.reviewed_by
    overrides: dict[str, AdminPOIEditorialOverrideItem] = {}
    if editorial.editorial_title_override is not None:
        overrides["name"] = AdminPOIEditorialOverrideItem(
            value=editorial.editorial_title_override,
            source_value=poi.canonical_name,
            updated_at=updated_at,
            updated_by=updated_by,
        )
    if editorial.editorial_description_override is not None:
        overrides["short_description"] = AdminPOIEditorialOverrideItem(
            value=editorial.editorial_description_override,
            source_value=poi.short_description,
            updated_at=updated_at,
            updated_by=updated_by,
        )
    if editorial.editorial_category_override is not None:
        overrides["primary_category"] = AdminPOIEditorialOverrideItem(
            value=editorial.editorial_category_override,
            source_value=poi.normalized_category,
            updated_at=updated_at,
            updated_by=updated_by,
        )
    if editorial.editorial_boost != 0:
        overrides["editorial_boost"] = AdminPOIEditorialOverrideItem(
            value=editorial.editorial_boost,
            source_value=0,
            updated_at=updated_at,
            updated_by=updated_by,
        )
    return overrides


def _build_alias_items(poi: POI) -> list[AdminPOIAliasItem]:
    return [
        AdminPOIAliasItem(
            alias_name=alias.alias_name,
            normalized_alias=alias.normalized_alias,
            alias_type=alias.alias_type,
            source=alias.source,
            confidence=alias.confidence,
            is_preferred=alias.is_preferred,
            notes=alias.notes,
            created_at=alias.created_at,
        )
        for alias in sorted(
            getattr(poi, "aliases", []) or [],
            key=lambda alias: (not alias.is_preferred, alias.alias_name.casefold()),
        )
    ]


def _build_detail_evidence_items(poi: POI) -> list[AdminPOIDetailEvidenceItem]:
    return [
        AdminPOIDetailEvidenceItem(
            evidence_id=item.id,
            source_id=item.source_id,
            source_name=item.source.source_name if item.source is not None else None,
            source_type=item.source.source_type if item.source is not None else None,
            trust_class=item.source.trust_class if item.source is not None else None,
            evidence_type=item.evidence_type,
            label=item.evidence_label,
            text=item.evidence_text,
            url=item.evidence_url,
            external_record_id=item.external_record_id,
            confidence=item.confidence,
            match_method=match_method_for_evidence(item),
            observed_at=item.observed_at,
            raw_payload=item.raw_evidence_json,
        )
        for item in sorted(
            getattr(poi, "evidence_items", []) or [],
            key=lambda item: (item.observed_at, item.source_id, item.evidence_type),
            reverse=True,
        )
    ]


def _build_poi_detail_match_diagnostic_item(
    item: OfficialMatchDiagnostic,
) -> AdminPOIDetailMatchDiagnosticItem:
    base = build_admin_match_diagnostic_item(item)
    raw_payload = item.raw_payload_json or {}
    reviewer_notes = raw_payload.get("reviewer_notes")
    return AdminPOIDetailMatchDiagnosticItem(
        id=base.id,
        source_id=base.source_id,
        source_name=base.source_name,
        source_type=base.source_type,
        external_record_id=base.external_record_id,
        external_name=base.external_name,
        best_candidate_poi_id=base.best_candidate_poi_id,
        best_candidate_name=base.best_candidate_name,
        resolved_poi_id=base.resolved_poi_id,
        resolved_poi_name=base.resolved_poi_name,
        best_similarity=base.best_similarity,
        match_strategy=base.match_strategy,
        resolution_method=base.resolution_method,
        why_not_auto_linked=base.why_not_auto_linked,
        state=base.status,
        reviewer_notes=reviewer_notes if isinstance(reviewer_notes, str) else None,
        reviewed_at=base.reviewed_at,
        reviewed_by=base.reviewed_by,
        created_at=base.created_at,
        updated_at=base.updated_at,
    )


def _build_external_links(poi: POI) -> dict[str, str]:
    links: dict[str, str] = {}
    if poi.osm_id:
        osm_id = poi.osm_id.strip("/")
        if "/" in osm_id:
            links["osm"] = f"https://www.openstreetmap.org/{osm_id}"
        else:
            links["osm"] = f"https://www.openstreetmap.org/node/{osm_id}"
    if poi.wikidata_id:
        links["wikidata"] = f"https://www.wikidata.org/wiki/{poi.wikidata_id}"
    return links


def _status_for_poi(poi: POI) -> str:
    if poi.editorial is not None:
        return poi.editorial.editorial_status
    return poi.review_status


def _metric_space(expression: object) -> ColumnElement[object]:
    return func.ST_Transform(cast(expression, Geometry(srid=4326)), 3857)


def _nearby_prefilter_clause(lon: float, lat: float, radius_meters: int) -> ColumnElement[bool]:
    query_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    return func.ST_DWithin(
        _metric_space(POI.geom),
        _metric_space(query_point),
        radius_meters,
    )


def _route_prefilter_clause(route_wkt: str, max_detour_meters: int) -> ColumnElement[bool]:
    route_geom = func.ST_GeomFromText(route_wkt, 4326)
    return func.ST_DWithin(
        _metric_space(POI.geom),
        _metric_space(route_geom),
        max_detour_meters,
    )


def _ensure_theme_memberships(db: Session, pois: Sequence[POI]) -> None:
    if not pois:
        return
    if sync_theme_memberships(db, list(pois)):
        db.commit()


def _poi_matches_theme(poi: POI, theme: str | None) -> bool:
    if theme is None:
        return True
    if not is_query_theme_active(theme):
        return False
    resolved = resolve_effective_theme_membership(
        theme,
        get_theme_membership_by_slug(poi, theme),
        get_theme_editorial_by_slug(poi, theme),
    )
    return resolved is not None and resolved.status == "accepted"


def _build_theme_items(poi: POI) -> list[POIThemeItem]:
    evidence_by_id = {item.id: item for item in getattr(poi, "evidence_items", []) or []}
    editorial_by_slug = {
        str(editorial.theme_slug): editorial
        for editorial in getattr(poi, "theme_editorials", []) or []
    }
    items: list[POIThemeItem] = []
    resolved_memberships = resolve_effective_theme_memberships(poi)
    for theme_slug, membership in sorted(
        resolved_memberships.items(),
        key=lambda item: (item[0] != "water", item[0]),
    ):
        if membership.status == "suppressed":
            continue
        automated_membership = get_theme_membership_by_slug(poi, theme_slug)
        editorial = editorial_by_slug.get(str(theme_slug))
        items.append(
            POIThemeItem(
                theme_slug=theme_slug,
                label=THEME_LABELS.get(theme_slug, theme_slug),
                status=membership.status,
                assignment_basis=membership.assignment_basis,
                confidence=membership.confidence,
                rationale_summary=membership.rationale_summary,
                is_query_active=is_query_theme_active(theme_slug),
                editorial_decision=(
                    editorial.editorial_decision if editorial is not None else None
                ),
                evidence=build_theme_evidence_references(automated_membership, evidence_by_id),
            )
        )
    return items


def _load_admin_theme_pois(
    db: Session,
    *,
    city: str | None,
) -> list[POI]:
    query = select(POI).options(
        joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
        joinedload(POI.theme_editorials),
    )
    if city is not None:
        query = query.where(POI.city == city)
    pois = db.execute(query.order_by(POI.updated_at.desc())).unique().scalars().all()
    _ensure_theme_memberships(db, pois)
    return list(pois)


def _review_state_priority(review_state: str) -> int:
    priorities = {"unreviewed": 0, "stale": 1, "reviewed": 2}
    return priorities.get(review_state, 3)


def _automated_status_priority(status: str | None) -> int:
    if status is None:
        return 2
    priorities = {"candidate": 0, "accepted": 1}
    return priorities.get(status, 2)
