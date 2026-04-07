import logging
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIEditorial,
    POIEvidence,
    POIThemeEditorial,
    POIThemeMembership,
)
from poi_curator_domain.descriptions import choose_short_description_for_poi
from poi_curator_domain.logging_utils import log_event
from poi_curator_domain.schemas import (
    AdminMatchDiagnosticItem,
    AdminPOIAliasItem,
    AdminPOIEvidenceItem,
    AdminPOIEvidenceResponse,
    AdminPOIItem,
    AdminPOIPatchRequest,
    AdminPOIPatchResponse,
    AdminThemeAutomatedMembership,
    AdminThemeEditorialRecord,
    AdminThemeEffectiveOutcome,
    AdminThemeMembershipDetailResponse,
    AdminThemeMembershipQueueItem,
    AdminThemeReviewResponse,
    AdminThemeSummaryItem,
    NearbyQuerySummary,
    NearbyResult,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIThemeItem,
    POIDetailResponse,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
    ThemeEvidenceReference,
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
from poi_curator_domain.themes import THEME_LABELS, is_query_theme_active
from shapely.geometry import Point
from sqlalchemy import cast, func, select
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
from poi_curator_scoring.shared_scoring import build_badges, build_why_it_matters

logger = logging.getLogger(__name__)


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
    )
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
            query_summary=QuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                theme=payload.theme,
                max_detour_meters=payload.max_detour_meters,
                limit=payload.limit,
            ),
            results=[],
        )

    scored_results: list[tuple[float, RouteResult]] = []
    for poi in pois:
        if not category_matches(payload, poi):
            continue
        if not _poi_matches_theme(poi, payload.theme):
            continue

        centroid = to_shape(poi.centroid)
        metrics = compute_candidate_metrics(payload, route_line, centroid)
        if not is_within_budget(payload, metrics):
            continue

        score, score_breakdown, category_match = score_candidate(poi, payload, metrics)
        scored_results.append(
            (
                score,
                build_route_result(
                    poi,
                    centroid,
                    metrics,
                    score,
                    score_breakdown,
                    category_match,
                    requested_theme=payload.theme,
                ),
            )
        )

    scored_results.sort(key=lambda item: item[0], reverse=True)
    response = RouteSuggestResponse(
        query_summary=QuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            theme=payload.theme,
            max_detour_meters=payload.max_detour_meters,
            limit=payload.limit,
        ),
        results=[result for _, result in scored_results[: payload.limit]],
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
    )
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
    scored_results: list[tuple[float, NearbyResult]] = []
    for poi in pois:
        if not category_matches(payload, poi):
            continue
        if not _poi_matches_theme(poi, payload.theme):
            continue

        centroid = to_shape(poi.centroid)
        metrics = compute_point_candidate_metrics(payload, query_point, centroid)
        if not is_within_radius(payload, metrics):
            continue

        score, score_breakdown, category_match = score_point_candidate(poi, payload, metrics)
        scored_results.append(
            (
                score,
                build_nearby_result(
                    poi,
                    centroid,
                    metrics,
                    score,
                    score_breakdown,
                    category_match,
                    payload.travel_mode,
                    requested_theme=payload.theme,
                ),
            )
        )

    scored_results.sort(key=lambda item: item[0], reverse=True)
    response = NearbySuggestResponse(
        query_summary=NearbyQuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            theme=payload.theme,
            radius_meters=payload.radius_meters,
            limit=payload.limit,
        ),
        results=[result for _, result in scored_results[: payload.limit]],
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
            joinedload(POI.aliases),
            joinedload(POI.theme_memberships).joinedload(POIThemeMembership.evidence_links),
            joinedload(POI.theme_editorials),
        )
    )
    if poi is None:
        return None
    _ensure_theme_memberships(db, [poi])

    centroid = to_shape(poi.centroid)
    return POIDetailResponse(
        poi_id=poi.poi_id,
        name=poi.canonical_name,
        primary_category=poi.normalized_category,
        secondary_categories=[
            category for category in poi.display_categories if category != poi.normalized_category
        ],
        coordinates=[centroid.x, centroid.y],
        short_description=choose_short_description_for_poi(poi),
        why_it_matters=build_why_it_matters(poi),
        badges=build_badges(poi, include_source_badges=True),
        provenance={
            "primary_source": poi.primary_source,
            "osm_id": poi.osm_id,
            "wikidata_id": poi.wikidata_id,
            "wikipedia_title": poi.wikipedia_title,
            "raw_source_count": len(poi.raw_sources),
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
            theme_slug=theme_slug,
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
    return _build_admin_theme_membership_detail(poi, theme_slug)


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


def patch_admin_poi(
    db: Session,
    poi_id: str,
    payload: AdminPOIPatchRequest,
) -> AdminPOIPatchResponse | None:
    poi = db.scalar(
        select(POI)
        .where(POI.poi_id == poi_id)
        .options(joinedload(POI.editorial))
    )
    if poi is None:
        return None

    changes = payload.model_dump(exclude_none=True)
    editorial = poi.editorial
    if editorial is None:
        editorial = POIEditorial(
            poi_id=poi.poi_id,
            editorial_status=poi.review_status,
            editorial_boost=0,
        )
        db.add(editorial)
        poi.editorial = editorial

    for field, value in changes.items():
        setattr(editorial, field, value)
    editorial.last_reviewed_at = datetime.now(UTC)
    db.commit()

    log_event(
        logger,
        "admin_poi_patch_persisted",
        poi_id=poi.poi_id,
        changed_fields=",".join(sorted(changes)),
    )
    return AdminPOIPatchResponse(
        poi_id=poi_id,
        applied_changes=changes,
        persisted=True,
        message="Persisted editorial overrides.",
    )


def build_admin_match_diagnostic_item(item: OfficialMatchDiagnostic) -> AdminMatchDiagnosticItem:
    return AdminMatchDiagnosticItem(
        id=item.id,
        source_id=item.source_id,
        source_name=item.source.source_name if item.source is not None else None,
        source_type=item.source.source_type if item.source is not None else None,
        region=item.region,
        external_record_id=item.external_record_id,
        external_name=item.external_name,
        normalized_name=normalized_name_for_diagnostic(item),
        best_candidate_poi_id=item.matched_poi_id,
        best_candidate_name=(
            item.poi.canonical_name if item.poi is not None else item.best_candidate_name
        ),
        resolved_poi_id=item.resolved_poi_id,
        resolved_poi_name=(
            item.resolved_poi.canonical_name if item.resolved_poi is not None else None
        ),
        best_similarity=item.best_similarity,
        match_strategy=item.match_strategy,
        resolution_method=item.resolution_method,
        why_not_auto_linked=why_not_auto_linked(item),
        status=item.status,
        reviewed_at=item.reviewed_at,
        reviewed_by=item.reviewed_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def match_method_for_evidence(item: object) -> str | None:
    raw = getattr(item, "raw_evidence_json", None) or {}
    match_strategy = raw.get("match_strategy")
    if isinstance(match_strategy, str):
        return match_strategy
    return None


def normalized_name_for_diagnostic(item: OfficialMatchDiagnostic) -> str:
    from poi_curator_enrichment.historic_register import normalize_historic_name

    return normalize_historic_name(item.external_name, relaxed=True)


def why_not_auto_linked(item: OfficialMatchDiagnostic) -> str:
    if item.status == "resolved":
        target_name = (
            item.resolved_poi.canonical_name
            if item.resolved_poi is not None
            else item.best_candidate_name
        )
        resolution_method = item.resolution_method or "manual review"
        return f"Resolved manually to '{target_name}' via {resolution_method}."
    if item.status == "suppressed":
        return "Suppressed during editorial review."
    if item.best_candidate_name is None:
        return "No plausible canonical POI candidate was found."
    similarity = item.best_similarity or 0.0
    strategy = item.match_strategy or "fuzzy_fallback"
    return (
        f"Best candidate '{item.best_candidate_name}' via {strategy} scored "
        f"{similarity:.3f}, below the auto-link threshold."
    )


def _status_for_poi(poi: POI) -> str:
    if poi.editorial is not None:
        return poi.editorial.editorial_status
    return poi.review_status


def _metric_space(expression: object) -> ColumnElement[object]:
    return func.ST_Transform(cast(expression, Geometry(srid=4326)), 3857)


def _nearby_prefilter_clause(lon: float, lat: float, radius_meters: int) -> ColumnElement[bool]:
    query_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    return func.ST_DWithin(
        _metric_space(POI.centroid),
        _metric_space(query_point),
        radius_meters,
    )


def _route_prefilter_clause(route_wkt: str, max_detour_meters: int) -> ColumnElement[bool]:
    route_geom = func.ST_GeomFromText(route_wkt, 4326)
    return func.ST_DWithin(
        _metric_space(POI.centroid),
        _metric_space(route_geom),
        max_detour_meters,
    )


def _ensure_theme_memberships(db: Session, pois: list[POI]) -> None:
    if not pois:
        return
    if sync_theme_memberships(db, pois):
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
        str(editorial.theme_slug): editorial for editorial in getattr(poi, "theme_editorials", []) or []
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
                evidence=_build_theme_evidence_references(automated_membership, evidence_by_id),
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
    return pois


def _build_admin_theme_membership_detail(
    poi: POI,
    theme_slug: str,
) -> AdminThemeMembershipDetailResponse:
    evidence_by_id = {item.id: item for item in getattr(poi, "evidence_items", []) or []}
    membership = get_theme_membership_by_slug(poi, theme_slug)
    editorial = get_theme_editorial_by_slug(poi, theme_slug)
    effective = resolve_effective_theme_membership(theme_slug, membership, editorial)

    automated_membership = None
    if membership is not None:
        automated_membership = AdminThemeAutomatedMembership(
            status=membership.status,
            assignment_basis=membership.assignment_basis,
            confidence=round(float(membership.confidence), 2),
            rationale_summary=membership.rationale_summary,
            computed_at=membership.computed_at,
            evidence=_build_theme_evidence_references(membership, evidence_by_id),
        )

    editorial_record = None
    if editorial is not None:
        editorial_record = AdminThemeEditorialRecord(
            editorial_decision=editorial.editorial_decision,
            notes=editorial.notes,
            reviewed_by=editorial.reviewed_by,
            reviewed_at=editorial.reviewed_at,
            reviewed_membership_computed_at=editorial.reviewed_membership_computed_at,
        )

    effective_outcome = None
    if effective is not None:
        effective_outcome = AdminThemeEffectiveOutcome(
            status=effective.status,
            assignment_basis=effective.assignment_basis,
            confidence=effective.confidence,
            rationale_summary=effective.rationale_summary,
        )

    return AdminThemeMembershipDetailResponse(
        poi_id=poi.poi_id,
        poi_name=poi.canonical_name,
        city=poi.city,
        primary_category=poi.normalized_category,
        theme_slug=theme_slug,
        theme_label=THEME_LABELS.get(theme_slug, theme_slug),
        is_query_active=is_query_theme_active(theme_slug),
        automated_membership=automated_membership,
        editorial_record=editorial_record,
        effective_outcome=effective_outcome,
    )


def _build_theme_evidence_references(
    membership: POIThemeMembership | None,
    evidence_by_id: dict[int, POIEvidence],
) -> list[ThemeEvidenceReference]:
    if membership is None:
        return []
    return [
        ThemeEvidenceReference(
            evidence_id=link.poi_evidence_id,
            source_id=evidence_by_id[link.poi_evidence_id].source_id,
            evidence_type=evidence_by_id[link.poi_evidence_id].evidence_type,
            label=evidence_by_id[link.poi_evidence_id].evidence_label,
            confidence=evidence_by_id[link.poi_evidence_id].confidence,
        )
        for link in sorted(
            getattr(membership, "evidence_links", []) or [],
            key=lambda item: item.poi_evidence_id,
        )
        if link.poi_evidence_id in evidence_by_id
    ]


def _review_state_priority(review_state: str) -> int:
    priorities = {"unreviewed": 0, "stale": 1, "reviewed": 2}
    return priorities.get(review_state, 3)


def _automated_status_priority(status: str | None) -> int:
    priorities = {"candidate": 0, "accepted": 1}
    return priorities.get(status, 2)
