from functools import lru_cache
from typing import Protocol

from geoalchemy2.shape import to_shape
from poi_curator_domain.db import POI
from poi_curator_domain.schemas import (
    AdminPOIItem,
    POIDetailResponse,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from poi_curator_scoring import engine
from poi_curator_scoring.db_route_scoring import (
    build_route_line,
    build_route_result,
    category_matches,
    compute_candidate_metrics,
    is_within_budget,
    score_candidate,
)


class ScoringBackend(Protocol):
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        ...

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None:
        ...

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]:
        ...


class FixtureScoringBackend:
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        del db
        return engine.suggest_places(payload)

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None:
        del db
        return engine.get_poi_detail(poi_id)

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]:
        del db
        return engine.get_admin_queue(status=status, city=city)


class HybridScoringBackend(FixtureScoringBackend):
    def __init__(self, *, allow_fixture_fallback: bool = True) -> None:
        self.allow_fixture_fallback = allow_fixture_fallback

    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        try:
            candidate_query = select(POI).options(
                joinedload(POI.signals),
                joinedload(POI.editorial),
            )
            if payload.region_hint is not None:
                candidate_query = candidate_query.where(POI.city == payload.region_hint)

            pois = db.scalars(candidate_query.where(POI.is_active.is_(True))).all()
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().suggest_places(db, payload)
        if not pois:
            if not self.allow_fixture_fallback:
                return RouteSuggestResponse(
                    query_summary=QuerySummary(
                        travel_mode=payload.travel_mode,
                        category=payload.category,
                        max_detour_meters=payload.max_detour_meters,
                        limit=payload.limit,
                    ),
                    results=[],
                )
            return super().suggest_places(db, payload)

        route_line = build_route_line(payload)
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
        return RouteSuggestResponse(
            query_summary=QuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                max_detour_meters=payload.max_detour_meters,
                limit=payload.limit,
            ),
            results=[result for _, result in scored_results[: payload.limit]],
        )

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None:
        try:
            poi = db.scalar(
                select(POI)
                .where(POI.poi_id == poi_id)
                .options(
                    joinedload(POI.raw_sources),
                    joinedload(POI.signals),
                    joinedload(POI.editorial),
                )
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_poi_detail(db, poi_id)
        if poi is None:
            if not self.allow_fixture_fallback:
                return None
            return super().get_poi_detail(db, poi_id)

        centroid = to_shape(poi.centroid)
        return POIDetailResponse(
            poi_id=poi.poi_id,
            name=poi.canonical_name,
            primary_category=poi.normalized_category,
            secondary_categories=[
                category
                for category in poi.display_categories
                if category != poi.normalized_category
            ],
            coordinates=[centroid.x, centroid.y],
            short_description=poi.short_description or "No editorial description yet.",
            why_it_matters=build_why_it_matters(poi),
            badges=build_badges(poi),
            provenance={
                "primary_source": poi.primary_source,
                "osm_id": poi.osm_id,
                "wikidata_id": poi.wikidata_id,
                "wikipedia_title": poi.wikipedia_title,
                "raw_source_count": len(poi.raw_sources),
            },
        )

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]:
        try:
            query = select(POI).options(joinedload(POI.editorial))
            if city is not None:
                query = query.where(POI.city == city)
            pois = db.scalars(query.order_by(POI.updated_at.desc())).all()
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_queue(db, status=status, city=city)

        items = [
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
        if items:
            return items
        if not self.allow_fixture_fallback:
            return []
        return super().get_admin_queue(db, status=status, city=city)


def _status_for_poi(poi: POI) -> str:
    if poi.editorial is not None:
        return poi.editorial.editorial_status
    return poi.review_status


def build_why_it_matters(poi: POI) -> list[str]:
    reasons: list[str] = []
    if poi.historical_flag:
        reasons.append("historical significance signal present")
    if poi.cultural_flag:
        reasons.append("strong local identity or cultural context")
    if poi.infrastructure_flag:
        reasons.append("reveals civic or infrastructural traces")
    if poi.signals is not None and poi.signals.has_wikidata:
        reasons.append("structured external identity match")
    if not reasons:
        reasons.append("candidate requires editorial review")
    return reasons[:3]


def build_badges(poi: POI) -> list[str]:
    badges: list[str] = []
    if poi.editorial is not None and poi.editorial.editorial_status == "featured":
        badges.append("featured")
    if poi.historical_flag:
        badges.append("history")
    if poi.scenic_flag:
        badges.append("scenic")
    if poi.infrastructure_flag:
        badges.append("infrastructure trace")
    if poi.primary_source == "osm_overpass":
        badges.append("osm-ingested")
    return badges


@lru_cache
def get_default_scoring_backend() -> ScoringBackend:
    return HybridScoringBackend()


def get_database_scoring_backend() -> ScoringBackend:
    return HybridScoringBackend(allow_fixture_fallback=False)
