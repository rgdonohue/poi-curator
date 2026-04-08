from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from poi_curator_domain.db import POI
from poi_curator_domain.descriptions import choose_short_description_for_poi
from poi_curator_domain.schemas import (
    NearbySuggestRequest,
    RouteResult,
    RouteSuggestRequest,
)
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform

from poi_curator_scoring.shared_scoring import (
    build_badges,
    build_why_it_matters,
    compute_category_context_components,
    compute_non_spatial_score_components,
    compute_theme_context_components,
)


@dataclass(frozen=True)
class CandidateMetrics:
    distance_from_route_m: int
    estimated_detour_m: int
    estimated_extra_minutes: int
    proximity_score: float
    detour_score: float
    budget_score: float


CategoryMatchTypeInternal = Literal["primary", "secondary", "mixed", "none"]


@lru_cache
def get_metric_transformer() -> Transformer:
    return Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


def build_route_line(payload: RouteSuggestRequest) -> LineString:
    return LineString(payload.route_geometry.coordinates)


def project_geometry(geometry: LineString | Point) -> LineString | Point:
    transformer = get_metric_transformer()
    return transform(transformer.transform, geometry)


def category_matches(
    payload: RouteSuggestRequest | NearbySuggestRequest,
    poi: POI,
) -> bool:
    match_type = category_match_type(payload, poi)
    if match_type == "none":
        return False
    return _passes_category_specific_eligibility(payload.category, poi)


def category_match_type(
    payload: RouteSuggestRequest | NearbySuggestRequest,
    poi: POI,
) -> CategoryMatchTypeInternal:
    if payload.category == "mixed":
        return "mixed"
    if poi.normalized_category == payload.category:
        return "primary"
    if payload.category in poi.display_categories:
        return "secondary"
    return "none"


def compute_candidate_metrics(
    payload: RouteSuggestRequest,
    route_line: LineString,
    centroid: Point,
) -> CandidateMetrics:
    projected_route = project_geometry(route_line)
    projected_centroid = project_geometry(centroid)
    distance_m = int(round(projected_route.distance(projected_centroid)))
    estimated_detour_m = distance_m * 2
    speed_m_per_minute = 250.0 if payload.travel_mode == "driving" else 80.0
    estimated_extra_minutes = max(1, int(round(estimated_detour_m / speed_m_per_minute)))

    corridor_limit = max(120, int(payload.max_detour_meters * 0.8))
    proximity_score = max(0.0, 15.0 - (distance_m / max(corridor_limit, 1)) * 15.0)
    detour_score = max(
        0.0,
        15.0 - (estimated_detour_m / max(payload.max_detour_meters, 1)) * 15.0,
    )
    detour_headroom = max(payload.max_detour_meters - estimated_detour_m, 0)
    minute_headroom = max(payload.max_extra_minutes - estimated_extra_minutes, 0)
    budget_score = (
        (
            detour_headroom / max(payload.max_detour_meters, 1)
            + minute_headroom / max(payload.max_extra_minutes, 1)
        )
        / 2.0
    ) * 5.0

    return CandidateMetrics(
        distance_from_route_m=distance_m,
        estimated_detour_m=estimated_detour_m,
        estimated_extra_minutes=estimated_extra_minutes,
        proximity_score=proximity_score,
        detour_score=detour_score,
        budget_score=budget_score,
    )


def is_within_budget(payload: RouteSuggestRequest, metrics: CandidateMetrics) -> bool:
    return (
        metrics.estimated_detour_m <= payload.max_detour_meters
        and metrics.estimated_extra_minutes <= payload.max_extra_minutes
    )


def score_candidate(
    poi: POI,
    payload: RouteSuggestRequest,
    metrics: CandidateMetrics,
) -> tuple[float, dict[str, float], Literal["primary", "secondary", "mixed"]]:
    match_type = _route_score_match_type(payload, poi)
    category_bonus = score_category_match(match_type)
    category_intent_guardrail = score_category_intent_guardrail(match_type, metrics)
    route_proximity = round(metrics.proximity_score, 2)
    detour_fit = round(metrics.detour_score, 2)
    budget_fit = round(metrics.budget_score, 2)
    common_components = compute_non_spatial_score_components(
        poi,
        travel_mode=payload.travel_mode,
    )
    category_context = compute_category_context_components(
        poi,
        requested_category=payload.category,
    )
    theme_context = compute_theme_context_components(
        poi,
        requested_category=payload.category,
        requested_theme=payload.theme,
    )

    score_breakdown = {
        "route_proximity": route_proximity,
        "detour_fit": detour_fit,
        "budget_fit": budget_fit,
        **common_components,
        **category_context,
        **theme_context,
        "category_bonus": category_bonus,
        "category_intent_guardrail": category_intent_guardrail,
    }
    total_score = round(sum(score_breakdown.values()), 1)
    return total_score, score_breakdown, _match_type_for_result(match_type)


def score_category_match(match_type: CategoryMatchTypeInternal) -> float:
    if match_type == "primary":
        return 10.0
    if match_type == "secondary":
        return 2.5
    return 0.0


def score_category_intent_guardrail(
    match_type: CategoryMatchTypeInternal,
    metrics: CandidateMetrics,
) -> float:
    if match_type != "secondary":
        return 0.0

    route_fit_total = metrics.proximity_score + metrics.detour_score + metrics.budget_score
    if route_fit_total >= 28.0:
        return 0.0
    if route_fit_total >= 24.0:
        return -1.0
    return -2.0


def _match_type_for_result(
    match_type: CategoryMatchTypeInternal,
) -> Literal["primary", "secondary", "mixed"]:
    if match_type == "none":
        raise ValueError("Cannot build a route result for a non-matching category.")
    return match_type


def _route_score_match_type(
    payload: RouteSuggestRequest,
    poi: POI,
) -> CategoryMatchTypeInternal:
    match_type = category_match_type(payload, poi)
    if (
        match_type == "secondary"
        and payload.category == "history"
        and _is_san_miguel_history_route_anchor(poi)
    ):
        return "primary"
    return match_type


def _is_san_miguel_history_route_anchor(poi: POI) -> bool:
    names = {
        str(getattr(poi, "canonical_name", "") or "").casefold(),
    }
    editorial = getattr(poi, "editorial", None)
    if editorial is not None and getattr(editorial, "editorial_title_override", None):
        names.add(str(editorial.editorial_title_override).casefold())

    return (
        bool({"san miguel", "san miguel chapel"} & names)
        and str(getattr(poi, "normalized_subcategory", "") or "") == "ritual_religious_site"
        and "history" in list(getattr(poi, "display_categories", []) or [])
    )


def _passes_category_specific_eligibility(
    requested_category: str,
    poi: POI,
) -> bool:
    if requested_category != "scenic":
        return True

    raw_tags = dict(getattr(poi, "raw_tag_summary_json", {}) or {})
    if poi.normalized_subcategory in {"overlook_vista", "landscape_feature"}:
        return True
    if poi.normalized_subcategory == "trail_river_access":
        return (
            raw_tags.get("tourism") == "viewpoint"
            or "natural" in raw_tags
            or "waterway" in raw_tags
        )
    return False


def build_route_result(
    poi: POI,
    centroid: Point,
    metrics: CandidateMetrics,
    score: float,
    score_breakdown: dict[str, float],
    category_match: Literal["primary", "secondary", "mixed"],
    requested_theme: str | None = None,
) -> RouteResult:
    secondary_categories = [
        category for category in poi.display_categories if category != poi.normalized_category
    ]
    return RouteResult(
        poi_id=poi.poi_id,
        name=poi.editorial.editorial_title_override
        if poi.editorial is not None and poi.editorial.editorial_title_override
        else poi.canonical_name,
        primary_category=(
            poi.editorial.editorial_category_override
            if poi.editorial is not None and poi.editorial.editorial_category_override
            else poi.normalized_category
        ),
        secondary_categories=secondary_categories,
        category_match_type=category_match,
        coordinates=[centroid.x, centroid.y],
        short_description=choose_short_description_for_poi(poi),
        distance_from_route_m=metrics.distance_from_route_m,
        estimated_detour_m=metrics.estimated_detour_m,
        estimated_extra_minutes=metrics.estimated_extra_minutes,
        score=score,
        score_breakdown=score_breakdown,
        why_it_matters=build_why_it_matters(
            poi,
            score_breakdown=score_breakdown,
            category_match=category_match,
            spatial_mode="route",
            include_editorial_reason=True,
            requested_theme=requested_theme,
            theme_match=requested_theme is not None,
        ),
        badges=build_badges(
            poi,
            spatial_mode="route",
            distance_m=metrics.distance_from_route_m,
            estimated_detour_m=metrics.estimated_detour_m,
            requested_theme=requested_theme,
            theme_match=requested_theme is not None,
        ),
    )
