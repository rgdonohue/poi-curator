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


def make_rail_membership(
    *,
    assignment_basis: str,
    evidence_links: list[object] | None = None,
) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            theme_slug="rail",
            assignment_basis=assignment_basis,
            evidence_links=evidence_links or [],
        ),
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


def test_san_miguel_is_primary_equivalent_for_history_route_scoring() -> None:
    payload = make_payload(category="history")
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="San Miguel",
            normalized_category="culture",
            normalized_subcategory="ritual_religious_site",
            display_categories=["culture", "history"],
            raw_tag_summary_json={"historic": "building"},
            drive_affinity_hint=0.6,
            walk_affinity_hint=0.5,
            base_significance_score=58.0,
            quality_score=65.0,
            editorial=SimpleNamespace(
                editorial_title_override="San Miguel Chapel",
                editorial_boost=0,
            ),
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    metrics = CandidateMetrics(
        distance_from_route_m=26,
        estimated_detour_m=52,
        estimated_extra_minutes=1,
        proximity_score=14.73,
        detour_score=14.57,
        budget_score=4.62,
    )

    score, breakdown, match_type = score_candidate(poi, payload, metrics)

    assert score > 0
    assert match_type == "primary"
    assert breakdown["category_bonus"] == 10.0
    assert breakdown["category_intent_guardrail"] == 0.0


def test_history_anchor_bonus_lifts_de_vargas_over_generic_house_inventory() -> None:
    payload = make_payload(category="history")
    inventory_house = cast(
        Any,
        SimpleNamespace(
            canonical_name="Digneo-Valdes House",
            normalized_category="history",
            normalized_subcategory="historic_site",
            display_categories=["history"],
            raw_tag_summary_json={"name": "Digneo-Valdes House", "historic": "yes"},
            drive_affinity_hint=0.9,
            walk_affinity_hint=0.5,
            base_significance_score=75.0,
            quality_score=85.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    de_vargas = cast(
        Any,
        SimpleNamespace(
            canonical_name="De Vargas Street House",
            normalized_category="history",
            normalized_subcategory="historic_site",
            display_categories=["history"],
            raw_tag_summary_json={
                "name": "De Vargas Street House",
                "historic": "yes",
                "tourism": "attraction",
            },
            drive_affinity_hint=0.75,
            walk_affinity_hint=0.5,
            base_significance_score=71.0,
            quality_score=90.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    inventory_metrics = CandidateMetrics(
        distance_from_route_m=65,
        estimated_detour_m=130,
        estimated_extra_minutes=1,
        proximity_score=14.32,
        detour_score=13.92,
        budget_score=4.51,
    )
    de_vargas_metrics = CandidateMetrics(
        distance_from_route_m=29,
        estimated_detour_m=58,
        estimated_extra_minutes=1,
        proximity_score=14.7,
        detour_score=14.52,
        budget_score=4.61,
    )

    inventory_score, inventory_breakdown, _ = score_candidate(
        inventory_house,
        payload,
        inventory_metrics,
    )
    de_vargas_score, de_vargas_breakdown, _ = score_candidate(
        de_vargas,
        payload,
        de_vargas_metrics,
    )

    assert inventory_breakdown["history_anchor_bonus"] == 0.0
    assert de_vargas_breakdown["history_anchor_bonus"] == 6.0
    assert de_vargas_score > inventory_score


def test_official_corroboration_contributes_to_route_score() -> None:
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
                official_corroboration_score=0.8,
                district_membership_score=0.6,
                institutional_identity_score=0.4,
            ),
        ),
    )
    metrics = CandidateMetrics(
        distance_from_route_m=180,
        estimated_detour_m=360,
        estimated_extra_minutes=2,
        proximity_score=12.0,
        detour_score=11.0,
        budget_score=3.0,
    )

    _, breakdown, _ = score_candidate(poi, payload, metrics)

    assert breakdown["official_corroboration"] == 6.4
    assert breakdown["district_membership"] == 3.0
    assert breakdown["institutional_identity"] == 1.6


def test_scenic_query_penalizes_generic_park_candidates() -> None:
    payload = make_payload(category="scenic")
    generic_park = cast(
        Any,
        SimpleNamespace(
            canonical_name="Cathedral Park",
            normalized_category="scenic",
            normalized_subcategory="trail_river_access",
            display_categories=["scenic"],
            raw_tag_summary_json={"name": "Cathedral Park", "leisure": "park"},
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=55.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    overlook = cast(
        Any,
        SimpleNamespace(
            canonical_name="Gronquist Arroyo Overlook",
            normalized_category="scenic",
            normalized_subcategory="overlook_vista",
            display_categories=["scenic", "history"],
            raw_tag_summary_json={
                "name": "Gronquist Arroyo Overlook",
                "tourism": "viewpoint",
            },
            drive_affinity_hint=0.8,
            walk_affinity_hint=0.5,
            base_significance_score=55.0,
            quality_score=70.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
        ),
    )
    metrics = CandidateMetrics(
        distance_from_route_m=180,
        estimated_detour_m=360,
        estimated_extra_minutes=2,
        proximity_score=12.0,
        detour_score=11.0,
        budget_score=3.0,
    )

    generic_score, generic_breakdown, _ = score_candidate(generic_park, payload, metrics)
    overlook_score, overlook_breakdown, _ = score_candidate(overlook, payload, metrics)

    assert generic_breakdown["scenic_specificity"] == -6.0
    assert overlook_breakdown["scenic_specificity"] == 4.0
    assert overlook_score > generic_score


def test_category_matches_filters_generic_scenic_parks_for_scenic_requests() -> None:
    payload = make_payload(category="scenic")
    generic_park = cast(
        Any,
        SimpleNamespace(
            normalized_category="scenic",
            normalized_subcategory="trail_river_access",
            display_categories=["scenic"],
            raw_tag_summary_json={"name": "Cathedral Park", "leisure": "park"},
        ),
    )
    overlook = cast(
        Any,
        SimpleNamespace(
            normalized_category="scenic",
            normalized_subcategory="overlook_vista",
            display_categories=["scenic", "history"],
            raw_tag_summary_json={
                "name": "Gronquist Arroyo Overlook",
                "tourism": "viewpoint",
            },
        ),
    )

    assert category_matches(payload, generic_park) is False
    assert category_matches(payload, overlook) is True


def test_mixed_rail_route_prefers_depot_anchor_over_rule_only_trace() -> None:
    payload = make_payload(category="mixed").model_copy(
        update={"theme": "rail", "travel_mode": "walking"}
    )
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
            walk_affinity_hint=0.55,
            base_significance_score=82.0,
            quality_score=85.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
            theme_memberships=[
                make_rail_membership(
                    assignment_basis="mixed",
                    evidence_links=[object()],
                )
            ],
        ),
    )
    trace = cast(
        Any,
        SimpleNamespace(
            canonical_name="Rail Trail St. Francis Tunnel Grid Vent",
            normalized_category="civic",
            normalized_subcategory="infrastructure_landmark",
            display_categories=["civic"],
            raw_tag_summary_json={"name": "Rail Trail St. Francis Tunnel Grid Vent"},
            drive_affinity_hint=0.6,
            walk_affinity_hint=0.55,
            base_significance_score=64.0,
            quality_score=75.0,
            editorial=None,
            signals=SimpleNamespace(genericity_penalty=0.0),
            theme_memberships=[make_rail_membership(assignment_basis="rule")],
        ),
    )
    depot_metrics = CandidateMetrics(
        distance_from_route_m=185,
        estimated_detour_m=370,
        estimated_extra_minutes=5,
        proximity_score=11.2,
        detour_score=8.8,
        budget_score=2.7,
    )
    trace_metrics = CandidateMetrics(
        distance_from_route_m=119,
        estimated_detour_m=238,
        estimated_extra_minutes=3,
        proximity_score=12.5,
        detour_score=11.0,
        budget_score=3.6,
    )

    depot_score, depot_breakdown, _ = score_candidate(depot, payload, depot_metrics)
    trace_score, trace_breakdown, _ = score_candidate(trace, payload, trace_metrics)

    assert depot_breakdown["rail_anchor_bonus"] == 4.0
    assert trace_breakdown["rail_trace_guardrail"] == -3.0
    assert depot_score > trace_score
