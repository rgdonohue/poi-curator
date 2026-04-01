from types import SimpleNamespace
from typing import Any, cast

from poi_curator_domain.schemas import GeoLineString, NamedPoint, RouteSuggestRequest
from poi_curator_scoring.db_route_scoring import (
    CandidateMetrics,
    build_route_line,
    category_match_type,
    category_matches,
    compute_candidate_metrics,
    is_within_budget,
    score_candidate,
)
from shapely.geometry import Point


def make_payload(category: str = "scenic") -> RouteSuggestRequest:
    return RouteSuggestRequest(
        route_geometry=GeoLineString(coordinates=[[-105.94, 35.68], [-105.93, 35.67]]),
        origin=NamedPoint(name="A", coordinates=[-105.94, 35.68]),
        destination=NamedPoint(name="B", coordinates=[-105.93, 35.67]),
        travel_mode="driving",
        category=category,  # type: ignore[arg-type]
        max_detour_meters=1600,
        max_extra_minutes=8,
        region_hint="santa-fe",
        limit=5,
    )


def test_compute_candidate_metrics_for_nearby_point() -> None:
    payload = make_payload()
    route_line = build_route_line(payload)
    centroid = Point(-105.9348, 35.6917)

    metrics = compute_candidate_metrics(payload, route_line, centroid)

    assert metrics.distance_from_route_m > 0
    assert metrics.estimated_detour_m == metrics.distance_from_route_m * 2
    assert metrics.estimated_extra_minutes >= 1


def test_category_matches_uses_secondary_membership() -> None:
    payload = make_payload(category="history")
    poi = cast(
        Any,
        SimpleNamespace(display_categories=["scenic", "history"], normalized_category="scenic"),
    )

    assert category_matches(payload, poi) is True
    assert category_match_type(payload, poi) == "secondary"


def test_score_candidate_returns_breakdown_and_positive_score() -> None:
    payload = make_payload(category="scenic")
    poi = cast(
        Any,
        SimpleNamespace(
            normalized_category="scenic",
            drive_affinity_hint=0.9,
            walk_affinity_hint=0.5,
            base_significance_score=60.0,
            quality_score=80.0,
            editorial=SimpleNamespace(editorial_boost=3),
            signals=SimpleNamespace(genericity_penalty=0.1),
        ),
    )
    metrics = CandidateMetrics(
        estimated_detour_m=400,
        estimated_extra_minutes=3,
        distance_from_route_m=200,
        proximity_score=10.0,
        detour_score=11.0,
        budget_score=3.0,
    )

    score, breakdown, match_type = score_candidate(poi, payload, metrics)

    assert score > 0
    assert match_type == "primary"
    assert breakdown["route_proximity"] == 10.0
    assert breakdown["detour_fit"] == 11.0
    assert breakdown["budget_fit"] == 3.0
    assert breakdown["category_bonus"] == 10.0
    assert breakdown["category_intent_guardrail"] == 0.0
    assert breakdown["editorial_boost"] == 3.0
    assert breakdown["penalties"] < 0


def test_budget_rejects_over_limit_candidate() -> None:
    payload = make_payload()
    metrics = CandidateMetrics(
        distance_from_route_m=2500,
        estimated_detour_m=5000,
        estimated_extra_minutes=12,
        proximity_score=0.0,
        detour_score=0.0,
        budget_score=0.0,
    )

    assert is_within_budget(payload, metrics) is False


def test_primary_match_beats_secondary_when_route_advantage_is_small() -> None:
    payload = make_payload(category="history")
    primary_poi = cast(
        Any,
        SimpleNamespace(
            normalized_category="history",
            display_categories=["history"],
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=70.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    secondary_poi = cast(
        Any,
        SimpleNamespace(
            normalized_category="civic",
            display_categories=["civic", "history"],
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=70.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    primary_metrics = CandidateMetrics(
        distance_from_route_m=250,
        estimated_detour_m=500,
        estimated_extra_minutes=2,
        proximity_score=11.0,
        detour_score=10.0,
        budget_score=3.0,
    )
    secondary_metrics = CandidateMetrics(
        distance_from_route_m=180,
        estimated_detour_m=360,
        estimated_extra_minutes=2,
        proximity_score=12.5,
        detour_score=11.0,
        budget_score=3.5,
    )

    primary_score, _, _ = score_candidate(primary_poi, payload, primary_metrics)
    secondary_score, secondary_breakdown, secondary_match = score_candidate(
        secondary_poi,
        payload,
        secondary_metrics,
    )

    assert secondary_match == "secondary"
    assert secondary_breakdown["category_intent_guardrail"] < 0
    assert primary_score > secondary_score


def test_secondary_match_can_win_with_large_route_advantage() -> None:
    payload = make_payload(category="history")
    primary_poi = cast(
        Any,
        SimpleNamespace(
            normalized_category="history",
            display_categories=["history"],
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=70.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    secondary_poi = cast(
        Any,
        SimpleNamespace(
            normalized_category="civic",
            display_categories=["civic", "history"],
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=70.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    primary_metrics = CandidateMetrics(
        distance_from_route_m=420,
        estimated_detour_m=840,
        estimated_extra_minutes=4,
        proximity_score=9.0,
        detour_score=8.0,
        budget_score=2.0,
    )
    secondary_metrics = CandidateMetrics(
        distance_from_route_m=40,
        estimated_detour_m=80,
        estimated_extra_minutes=1,
        proximity_score=14.5,
        detour_score=14.0,
        budget_score=4.5,
    )

    primary_score, _, _ = score_candidate(primary_poi, payload, primary_metrics)
    secondary_score, secondary_breakdown, secondary_match = score_candidate(
        secondary_poi,
        payload,
        secondary_metrics,
    )

    assert secondary_match == "secondary"
    assert secondary_breakdown["category_intent_guardrail"] == 0.0
    assert secondary_score > primary_score
