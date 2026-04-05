from types import SimpleNamespace
from typing import Any, cast

from poi_curator_domain.schemas import (
    LatLonPoint,
    NearbySuggestRequest,
)
from poi_curator_scoring.db_point_scoring import (
    PointCandidateMetrics,
    build_nearby_result,
    compute_point_candidate_metrics,
    is_within_radius,
    score_point_candidate,
)
from shapely.geometry import Point


def make_payload(category: str = "history") -> NearbySuggestRequest:
    return NearbySuggestRequest(
        center=LatLonPoint(lat=35.68, lon=-105.94),
        travel_mode="driving",
        category=category,  # type: ignore[arg-type]
        radius_meters=1600,
        region_hint="santa-fe",
        limit=5,
    )


def test_compute_point_candidate_metrics_for_nearby_point() -> None:
    payload = make_payload()
    query_point = Point(-105.94, 35.68)
    centroid = Point(-105.939, 35.681)

    metrics = compute_point_candidate_metrics(payload, query_point, centroid)

    assert metrics.distance_from_point_m > 0
    assert metrics.estimated_access_m == metrics.distance_from_point_m
    assert metrics.estimated_access_minutes >= 1


def test_point_radius_filter_rejects_far_candidate() -> None:
    payload = make_payload()
    metrics = PointCandidateMetrics(
        distance_from_point_m=1800,
        estimated_access_m=1800,
        estimated_access_minutes=8,
        proximity_score=0.0,
        radius_fit_score=0.0,
    )

    assert is_within_radius(payload, metrics) is False


def test_primary_point_match_beats_secondary_without_large_proximity_gap() -> None:
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
    primary_metrics = PointCandidateMetrics(
        distance_from_point_m=320,
        estimated_access_m=320,
        estimated_access_minutes=2,
        proximity_score=14.0,
        radius_fit_score=9.5,
    )
    secondary_metrics = PointCandidateMetrics(
        distance_from_point_m=220,
        estimated_access_m=220,
        estimated_access_minutes=1,
        proximity_score=13.2,
        radius_fit_score=8.3,
    )

    primary_score, _, primary_match = score_point_candidate(primary_poi, payload, primary_metrics)
    secondary_score, secondary_breakdown, secondary_match = score_point_candidate(
        secondary_poi,
        payload,
        secondary_metrics,
    )

    assert primary_match == "primary"
    assert secondary_match == "secondary"
    assert secondary_breakdown["category_intent_guardrail"] < 0
    assert primary_score > secondary_score


def test_secondary_point_match_can_win_if_it_is_much_closer() -> None:
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
    primary_metrics = PointCandidateMetrics(
        distance_from_point_m=900,
        estimated_access_m=900,
        estimated_access_minutes=4,
        proximity_score=7.0,
        radius_fit_score=5.0,
    )
    secondary_metrics = PointCandidateMetrics(
        distance_from_point_m=70,
        estimated_access_m=70,
        estimated_access_minutes=1,
        proximity_score=17.2,
        radius_fit_score=11.4,
    )

    primary_score, _, _ = score_point_candidate(primary_poi, payload, primary_metrics)
    secondary_score, secondary_breakdown, secondary_match = score_point_candidate(
        secondary_poi,
        payload,
        secondary_metrics,
    )

    assert secondary_match == "secondary"
    assert secondary_breakdown["category_intent_guardrail"] == 0.0
    assert secondary_score > primary_score


def test_official_corroboration_contributes_to_point_score() -> None:
    payload = make_payload(category="history")
    poi = cast(
        Any,
        SimpleNamespace(
            normalized_category="history",
            display_categories=["history"],
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=70.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(
                genericity_penalty=0.0,
                official_corroboration_score=0.75,
                district_membership_score=0.4,
                institutional_identity_score=0.5,
            ),
        ),
    )
    metrics = PointCandidateMetrics(
        distance_from_point_m=250,
        estimated_access_m=250,
        estimated_access_minutes=2,
        proximity_score=14.0,
        radius_fit_score=9.0,
    )

    _, breakdown, _ = score_point_candidate(poi, payload, metrics)

    assert breakdown["official_corroboration"] == 6.0
    assert breakdown["district_membership"] == 2.0
    assert breakdown["institutional_identity"] == 2.0


def test_civic_query_rewards_historic_rail_depot_anchor() -> None:
    payload = make_payload(category="civic")
    depot = cast(
        Any,
        SimpleNamespace(
            canonical_name="Atchison, Topeka & Santa Fe Railway Depot",
            normalized_category="history",
            normalized_subcategory="historic_site",
            display_categories=["history", "civic"],
            raw_tag_summary_json={
                "name": "Atchison, Topeka & Santa Fe Railway Depot",
                "historic": "railway_station",
            },
            drive_affinity_hint=0.6,
            walk_affinity_hint=0.6,
            base_significance_score=82.0,
            quality_score=85.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    fragment = cast(
        Any,
        SimpleNamespace(
            canonical_name="Rail Trail St. Francis Tunnel Grid Vent",
            normalized_category="civic",
            normalized_subcategory="infrastructure_landmark",
            display_categories=["civic"],
            raw_tag_summary_json={"name": "Rail Trail St. Francis Tunnel Grid Vent"},
            drive_affinity_hint=0.6,
            walk_affinity_hint=0.6,
            base_significance_score=52.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    metrics = PointCandidateMetrics(
        distance_from_point_m=150,
        estimated_access_m=150,
        estimated_access_minutes=2,
        proximity_score=15.5,
        radius_fit_score=10.0,
    )

    depot_score, depot_breakdown, depot_match = score_point_candidate(depot, payload, metrics)
    fragment_score, fragment_breakdown, fragment_match = score_point_candidate(
        fragment,
        payload,
        metrics,
    )

    assert depot_match == "secondary"
    assert fragment_match == "primary"
    assert depot_breakdown["civic_anchor_bonus"] == 10.0
    assert fragment_breakdown["civic_fragment_penalty"] == -5.0
    assert depot_score > fragment_score


def test_build_nearby_result_uses_description_hygiene_fallback() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            poi_id="poi-1",
            canonical_name="Soldiers' Monument",
            normalized_category="history",
            normalized_subcategory="monument_memorial",
            display_categories=["history"],
            short_description="survey new height, confirm former height",
            editorial=None,
            signals=None,
            infrastructure_flag=False,
            cultural_flag=False,
            scenic_flag=False,
            historical_flag=True,
        ),
    )
    result = build_nearby_result(
        poi,
        Point(-105.9385, 35.6874),
        PointCandidateMetrics(
            distance_from_point_m=100,
            estimated_access_m=100,
            estimated_access_minutes=1,
            proximity_score=15.0,
            radius_fit_score=10.0,
        ),
        70.0,
        {
            "significance": 20.0,
            "point_proximity": 15.0,
            "radius_fit": 10.0,
            "official_corroboration": 0.0,
            "district_membership": 0.0,
            "institutional_identity": 0.0,
        },
        "mixed",
        "walking",
    )

    assert result.short_description == "Monument or memorial with strong public memory value."
    assert result.distance_from_center_meters == 100


def test_build_nearby_result_uses_center_distance_field() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            poi_id="poi-2",
            canonical_name="Acequia Madre",
            normalized_category="history",
            normalized_subcategory="infrastructure_landmark",
            display_categories=["history", "civic"],
            short_description="Historic irrigation corridor.",
            editorial=None,
            signals=None,
            infrastructure_flag=True,
            cultural_flag=False,
            scenic_flag=False,
            historical_flag=True,
        ),
    )
    result = build_nearby_result(
        poi,
        Point(-105.9319, 35.6828),
        PointCandidateMetrics(
            distance_from_point_m=84,
            estimated_access_m=84,
            estimated_access_minutes=1,
            proximity_score=16.0,
            radius_fit_score=10.5,
        ),
        77.5,
        {
            "significance": 20.0,
            "point_proximity": 16.0,
            "radius_fit": 10.5,
            "official_corroboration": 0.0,
            "district_membership": 0.0,
            "institutional_identity": 0.0,
            "category_bonus": 8.0,
            "category_intent_guardrail": 0.0,
            "quality": 8.0,
            "mode_affinity": 6.0,
            "editorial_boost": 0.0,
            "penalties": 0.0,
        },
        "primary",
        "walking",
    )

    assert result.distance_from_center_meters == 84
    assert result.estimated_access_m == 84
    assert result.category_match_type == "primary"
