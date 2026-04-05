from typing import Literal

from poi_curator_domain.schemas import (
    AdminMatchDiagnosticItem,
    AdminPOIEvidenceResponse,
    AdminPOIItem,
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

from poi_curator_scoring.db_route_scoring import get_metric_transformer
from poi_curator_scoring.fixtures import FIXTURE_POIS, POIFixture


def _category_bonus(requested_category: str, fixture: POIFixture) -> float:
    if requested_category == "mixed":
        return 2.0
    if fixture.primary_category == requested_category:
        return 8.0
    if requested_category in fixture.secondary_categories:
        return 4.0
    return -12.0


def _mode_bonus(travel_mode: str, fixture: POIFixture) -> float:
    affinity = fixture.drive_affinity if travel_mode == "driving" else fixture.walk_affinity
    return round(affinity * 8.0, 2)


def _budget_bonus(max_detour_meters: int, max_extra_minutes: int, fixture: POIFixture) -> float:
    if fixture.estimated_detour_m > max_detour_meters:
        return -999.0
    if fixture.estimated_extra_minutes > max_extra_minutes:
        return -999.0

    detour_headroom = max(max_detour_meters - fixture.estimated_detour_m, 0)
    minute_headroom = max(max_extra_minutes - fixture.estimated_extra_minutes, 0)
    return round((detour_headroom / max_detour_meters) * 6 + minute_headroom * 0.8, 2)


def _route_fit_bonus(fixture: POIFixture) -> float:
    return max(0.0, 12.0 - fixture.distance_from_route_m / 40.0)


def _to_route_result(fixture: POIFixture, score: float) -> RouteResult:
    badges = list(dict.fromkeys([*fixture.badges, "scaffold result"]))
    category_match_type: Literal["primary", "mixed"] = (
        "mixed" if fixture.primary_category == "mixed" else "primary"
    )
    return RouteResult(
        poi_id=fixture.poi_id,
        name=fixture.name,
        primary_category=fixture.primary_category,
        secondary_categories=fixture.secondary_categories,
        category_match_type=category_match_type,
        coordinates=fixture.coordinates,
        short_description=fixture.short_description,
        distance_from_route_m=fixture.distance_from_route_m,
        estimated_detour_m=fixture.estimated_detour_m,
        estimated_extra_minutes=fixture.estimated_extra_minutes,
        score=round(score, 1),
        why_it_matters=fixture.why_it_matters,
        badges=badges,
    )


def suggest_places(payload: RouteSuggestRequest) -> RouteSuggestResponse:
    scored_results: list[tuple[float, POIFixture]] = []

    for fixture in FIXTURE_POIS:
        category_bonus = _category_bonus(payload.category, fixture)
        budget_bonus = _budget_bonus(
            payload.max_detour_meters,
            payload.max_extra_minutes,
            fixture,
        )
        if category_bonus < 0 and payload.category != "mixed":
            continue
        if budget_bonus < 0:
            continue

        score = fixture.base_score
        score += category_bonus
        score += _mode_bonus(payload.travel_mode, fixture)
        score += budget_bonus
        score += _route_fit_bonus(fixture)
        scored_results.append((score, fixture))

    scored_results.sort(key=lambda item: item[0], reverse=True)
    results = [
        _to_route_result(fixture, score)
        for score, fixture in scored_results[: payload.limit]
    ]

    return RouteSuggestResponse(
        query_summary=QuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            max_detour_meters=payload.max_detour_meters,
            limit=payload.limit,
        ),
        results=results,
    )


def _build_nearby_fixture_results(
    *,
    center_lon: float,
    center_lat: float,
    category: str,
    travel_mode: str,
    radius_meters: int,
    limit: int,
) -> list[NearbyResult]:
    scored_results: list[tuple[float, POIFixture, int, int]] = []
    transformer = get_metric_transformer()
    query_point = Point(center_lon, center_lat)
    projected_query_point = Point(transformer.transform(*query_point.coords[0]))

    for fixture in FIXTURE_POIS:
        if category != "mixed" and (
            fixture.primary_category != category
            and category not in fixture.secondary_categories
        ):
            continue

        projected_fixture = Point(
            transformer.transform(fixture.coordinates[0], fixture.coordinates[1])
        )
        distance_m = int(round(projected_query_point.distance(projected_fixture)))
        if distance_m > radius_meters:
            continue

        estimated_access_minutes = max(
            1,
            int(round(distance_m / (250.0 if travel_mode == "driving" else 80.0))),
        )
        category_bonus = 10.0 if fixture.primary_category == category else 2.5
        proximity_bonus = max(0.0, 18.0 - (distance_m / max(radius_meters, 1)) * 18.0)
        radius_fit = max(0.0, 12.0 - (distance_m / max(radius_meters, 1)) * 12.0)
        score = fixture.base_score + category_bonus + _mode_bonus(travel_mode, fixture)
        score += proximity_bonus + radius_fit
        scored_results.append((score, fixture, distance_m, estimated_access_minutes))

    scored_results.sort(key=lambda item: item[0], reverse=True)
    return [
        NearbyResult(
            poi_id=fixture.poi_id,
            name=fixture.name,
            primary_category=fixture.primary_category,
            secondary_categories=fixture.secondary_categories,
            category_match_type=(
                "mixed"
                if category == "mixed"
                else "primary"
                if fixture.primary_category == category
                else "secondary"
            ),
            coordinates=fixture.coordinates,
            short_description=fixture.short_description,
            distance_from_center_meters=distance_m,
            estimated_access_m=distance_m,
            estimated_access_minutes=estimated_access_minutes,
            score=round(score, 1),
            score_breakdown=None,
            why_it_matters=fixture.why_it_matters,
            badges=list(dict.fromkeys([*fixture.badges, "scaffold result"])),
        )
        for score, fixture, distance_m, estimated_access_minutes in scored_results[:limit]
    ]


def suggest_nearby_places(payload: NearbySuggestRequest) -> NearbySuggestResponse:
    results = _build_nearby_fixture_results(
        center_lon=payload.center.lon,
        center_lat=payload.center.lat,
        category=payload.category,
        travel_mode=payload.travel_mode,
        radius_meters=payload.radius_meters,
        limit=payload.limit,
    )

    return NearbySuggestResponse(
        query_summary=NearbyQuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            radius_meters=payload.radius_meters,
            limit=payload.limit,
        ),
        results=results,
    )


def suggest_nearby(payload: NearbySuggestRequest) -> NearbySuggestResponse:
    return suggest_nearby_places(payload)


def get_poi_detail(poi_id: str) -> POIDetailResponse | None:
    fixture = next((item for item in FIXTURE_POIS if item.poi_id == poi_id), None)
    if fixture is None:
        return None

    return POIDetailResponse(
        poi_id=fixture.poi_id,
        name=fixture.name,
        primary_category=fixture.primary_category,
        secondary_categories=fixture.secondary_categories,
        coordinates=fixture.coordinates,
        short_description=fixture.short_description,
        why_it_matters=fixture.why_it_matters,
        badges=fixture.badges,
        provenance=fixture.provenance,
        evidence=[],
    )


def get_admin_queue(status: str, city: str | None) -> list[AdminPOIItem]:
    requested_city = city or "santa-fe"
    return [
        AdminPOIItem(
            poi_id=fixture.poi_id,
            name=fixture.name,
            city=fixture.city,
            status=status,
            primary_category=fixture.primary_category,
            notes="Fixture-backed review candidate.",
        )
        for fixture in FIXTURE_POIS
        if fixture.city == requested_city
    ]


def get_admin_poi_evidence(poi_id: str) -> AdminPOIEvidenceResponse | None:
    fixture = next((item for item in FIXTURE_POIS if item.poi_id == poi_id), None)
    if fixture is None:
        return None
    return AdminPOIEvidenceResponse(
        poi_id=fixture.poi_id,
        name=fixture.name,
        primary_category=fixture.primary_category,
        aliases=[],
        evidence=[],
    )


def get_admin_match_diagnostics(
    *,
    region: str | None,
    source_id: str | None,
    status: str,
    limit: int,
) -> list[AdminMatchDiagnosticItem]:
    del region, source_id, status, limit
    return []
