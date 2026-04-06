from dataclasses import dataclass
from typing import Literal

from poi_curator_domain.db import POI
from poi_curator_domain.descriptions import choose_short_description_for_poi
from poi_curator_domain.schemas import NearbyResult, NearbySuggestRequest
from shapely.geometry import Point

from poi_curator_scoring.db_route_scoring import (
    CategoryMatchTypeInternal,
    _match_type_for_result,
    category_match_type,
    project_geometry,
    score_category_match,
)
from poi_curator_scoring.shared_scoring import (
    build_badges,
    build_why_it_matters,
    compute_category_context_components,
    compute_non_spatial_score_components,
    compute_theme_context_components,
)


@dataclass(frozen=True)
class PointCandidateMetrics:
    distance_from_point_m: int
    estimated_access_m: int
    estimated_access_minutes: int
    proximity_score: float
    radius_fit_score: float


def compute_point_candidate_metrics(
    payload: NearbySuggestRequest,
    query_point: Point,
    centroid: Point,
) -> PointCandidateMetrics:
    projected_query_point = project_geometry(query_point)
    projected_centroid = project_geometry(centroid)
    distance_m = int(round(projected_query_point.distance(projected_centroid)))
    speed_m_per_minute = 250.0 if payload.travel_mode == "driving" else 80.0
    estimated_access_minutes = max(1, int(round(distance_m / speed_m_per_minute)))
    proximity_score = max(0.0, 18.0 - (distance_m / max(payload.radius_meters, 1)) * 18.0)
    radius_fit_score = max(0.0, 12.0 - (distance_m / max(payload.radius_meters, 1)) * 12.0)

    return PointCandidateMetrics(
        distance_from_point_m=distance_m,
        estimated_access_m=distance_m,
        estimated_access_minutes=estimated_access_minutes,
        proximity_score=proximity_score,
        radius_fit_score=radius_fit_score,
    )


def is_within_radius(payload: NearbySuggestRequest, metrics: PointCandidateMetrics) -> bool:
    return metrics.distance_from_point_m <= payload.radius_meters


def score_point_category_intent_guardrail(
    match_type: CategoryMatchTypeInternal,
    metrics: PointCandidateMetrics,
) -> float:
    if match_type != "secondary":
        return 0.0

    point_fit_total = metrics.proximity_score + metrics.radius_fit_score
    if point_fit_total >= 24.0:
        return 0.0
    if point_fit_total >= 18.0:
        return -1.0
    return -2.0


def score_point_candidate(
    poi: POI,
    payload: NearbySuggestRequest,
    metrics: PointCandidateMetrics,
) -> tuple[float, dict[str, float], Literal["primary", "secondary", "mixed"]]:
    match_type = category_match_type(payload, poi)
    category_bonus = score_category_match(match_type)
    category_intent_guardrail = score_point_category_intent_guardrail(match_type, metrics)
    proximity = round(metrics.proximity_score, 2)
    radius_fit = round(metrics.radius_fit_score, 2)
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
        "point_proximity": proximity,
        "radius_fit": radius_fit,
        **common_components,
        **category_context,
        **theme_context,
        "category_bonus": category_bonus,
        "category_intent_guardrail": category_intent_guardrail,
    }
    total_score = round(sum(score_breakdown.values()), 1)
    return total_score, score_breakdown, _match_type_for_result(match_type)


def build_nearby_result(
    poi: POI,
    centroid: Point,
    metrics: PointCandidateMetrics,
    score: float,
    score_breakdown: dict[str, float],
    category_match: Literal["primary", "secondary", "mixed"],
    payload_mode: str,
    requested_theme: str | None = None,
) -> NearbyResult:
    secondary_categories = [
        category for category in poi.display_categories if category != poi.normalized_category
    ]
    return NearbyResult(
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
        distance_from_center_meters=metrics.distance_from_point_m,
        estimated_access_m=metrics.estimated_access_m,
        estimated_access_minutes=metrics.estimated_access_minutes,
        score=score,
        score_breakdown=score_breakdown,
        why_it_matters=build_why_it_matters(
            poi,
            score_breakdown=score_breakdown,
            category_match=category_match,
            spatial_mode="nearby",
            requested_theme=requested_theme,
            theme_match=requested_theme is not None,
        ),
        badges=build_badges(
            poi,
            spatial_mode="nearby",
            distance_m=metrics.distance_from_point_m,
            travel_mode=payload_mode,
            requested_theme=requested_theme,
            theme_match=requested_theme is not None,
        ),
    )
