import logging
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from poi_curator_domain.db import POI, OfficialMatchDiagnostic, POIEditorial, POIEvidence
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
    NearbyQuerySummary,
    NearbyResult,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIDetailResponse,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
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
    if payload.region_hint is not None:
        candidate_query = candidate_query.where(POI.city == payload.region_hint)

    route_line = build_route_line(payload)
    candidate_query = candidate_query.where(
        POI.is_active.is_(True),
        _route_prefilter_clause(route_line.wkt, payload.max_detour_meters),
    )
    pois = db.execute(candidate_query).unique().scalars().all()
    log_event(
        logger,
        "route_candidates_prefiltered",
        region=payload.region_hint,
        category=payload.category,
        mode=payload.travel_mode,
        max_detour_meters=payload.max_detour_meters,
        candidate_count=len(pois),
    )
    if not pois:
        return RouteSuggestResponse(
            query_summary=QuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                max_detour_meters=payload.max_detour_meters,
                limit=payload.limit,
            ),
            results=[],
        )

    scored_results: list[tuple[float, RouteResult]] = []
    for poi in pois:
        if not category_matches(payload, poi):
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
                ),
            )
        )

    scored_results.sort(key=lambda item: item[0], reverse=True)
    response = RouteSuggestResponse(
        query_summary=QuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
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
    if payload.region_hint is not None:
        candidate_query = candidate_query.where(POI.city == payload.region_hint)

    candidate_query = candidate_query.where(
        POI.is_active.is_(True),
        _nearby_prefilter_clause(payload.center.lon, payload.center.lat, payload.radius_meters),
    )
    pois = db.execute(candidate_query).unique().scalars().all()
    log_event(
        logger,
        "nearby_candidates_prefiltered",
        region=payload.region_hint,
        category=payload.category,
        mode=payload.travel_mode,
        radius_meters=payload.radius_meters,
        candidate_count=len(pois),
    )
    if not pois:
        return NearbySuggestResponse(
            query_summary=NearbyQuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
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
                ),
            )
        )

    scored_results.sort(key=lambda item: item[0], reverse=True)
    response = NearbySuggestResponse(
        query_summary=NearbyQuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
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
        )
    )
    if poi is None:
        return None

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
        )
    )
    if poi is None:
        return None

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
    )


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
