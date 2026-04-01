from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from poi_curator_domain.db import POI
from poi_curator_domain.schemas import RouteResult, RouteSuggestRequest
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform


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


def category_matches(payload: RouteSuggestRequest, poi: POI) -> bool:
    return category_match_type(payload, poi) != "none"


def category_match_type(
    payload: RouteSuggestRequest,
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
    match_type = category_match_type(payload, poi)
    category_bonus = score_category_match(match_type)
    category_intent_guardrail = score_category_intent_guardrail(match_type, metrics)
    affinity_hint = (
        poi.drive_affinity_hint if payload.travel_mode == "driving" else poi.walk_affinity_hint
    )
    route_proximity = round(metrics.proximity_score, 2)
    detour_fit = round(metrics.detour_score, 2)
    budget_fit = round(metrics.budget_score, 2)
    significance = round((poi.base_significance_score / 100.0) * 30.0, 2)
    quality = round((poi.quality_score / 100.0) * 10.0, 2)
    mode_affinity = round(affinity_hint * 8.0, 2)
    editorial_boost = float(poi.editorial.editorial_boost) if poi.editorial is not None else 0.0
    penalties = 0.0
    if poi.signals is not None:
        penalties += round(poi.signals.genericity_penalty * 10.0, 2)

    score_breakdown = {
        "route_proximity": route_proximity,
        "detour_fit": detour_fit,
        "budget_fit": budget_fit,
        "significance": significance,
        "quality": quality,
        "mode_affinity": mode_affinity,
        "category_bonus": category_bonus,
        "category_intent_guardrail": category_intent_guardrail,
        "editorial_boost": editorial_boost,
        "penalties": -penalties,
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


def build_route_result(
    poi: POI,
    centroid: Point,
    metrics: CandidateMetrics,
    score: float,
    score_breakdown: dict[str, float],
    category_match: Literal["primary", "secondary", "mixed"],
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
        short_description=(
            poi.editorial.editorial_description_override
            if poi.editorial is not None and poi.editorial.editorial_description_override
            else poi.short_description or "No editorial description yet."
        ),
        distance_from_route_m=metrics.distance_from_route_m,
        estimated_detour_m=metrics.estimated_detour_m,
        estimated_extra_minutes=metrics.estimated_extra_minutes,
        score=score,
        score_breakdown=score_breakdown,
        why_it_matters=build_why_it_matters(score_breakdown, poi, category_match),
        badges=build_badges(metrics, poi),
    )


def build_why_it_matters(
    score_breakdown: dict[str, float],
    poi: POI,
    category_match: Literal["primary", "secondary", "mixed"],
) -> list[str]:
    reasons: list[str] = []
    route_fit_total = sum(
        score_breakdown[key] for key in ("route_proximity", "detour_fit", "budget_fit")
    )
    if category_match == "primary":
        reasons.append("strong primary match for the requested category")
    elif category_match == "secondary":
        reasons.append("secondary category match supported by route fit")
    if route_fit_total >= 22:
        reasons.append("close to the route with manageable detour burden")
    if score_breakdown["significance"] >= 18:
        reasons.append("strong base significance for this landscape reading")
    if poi.infrastructure_flag:
        reasons.append("reveals civic or infrastructural traces")
    elif poi.cultural_flag:
        reasons.append("strong local identity and cultural legibility")
    elif poi.scenic_flag:
        reasons.append("offers a clear terrain or landscape read")
    elif poi.historical_flag:
        reasons.append("anchors local historical context")
    if poi.editorial is not None and poi.editorial.editorial_boost > 0:
        reasons.append("editorially boosted candidate")
    return reasons[:3] or ["route-plausible candidate with meaningful local signal"]


def build_badges(metrics: CandidateMetrics, poi: POI) -> list[str]:
    badges: list[str] = []
    if metrics.distance_from_route_m <= 150:
        badges.append("near this route")
    if metrics.estimated_detour_m <= 500:
        badges.append("within budget")
    if poi.editorial is not None and poi.editorial.editorial_status == "featured":
        badges.append("featured")
    if poi.infrastructure_flag:
        badges.append("infrastructure trace")
    elif poi.scenic_flag:
        badges.append("scenic")
    elif poi.cultural_flag:
        badges.append("cultural signal")
    elif poi.historical_flag:
        badges.append("history")
    return badges
