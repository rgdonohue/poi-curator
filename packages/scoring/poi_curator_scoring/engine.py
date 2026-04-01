from typing import Literal

from poi_curator_domain.schemas import (
    AdminPOIItem,
    POIDetailResponse,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
)

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
