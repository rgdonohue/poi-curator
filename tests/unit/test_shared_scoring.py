from types import SimpleNamespace
from typing import Any, cast

from poi_curator_scoring.shared_scoring import (
    build_badges,
    build_why_it_matters,
    compute_category_context_components,
    compute_non_spatial_score_components,
)


def make_poi() -> Any:
    return cast(
        Any,
        SimpleNamespace(
            base_significance_score=70.0,
            quality_score=80.0,
            drive_affinity_hint=0.75,
            walk_affinity_hint=0.5,
            editorial=SimpleNamespace(editorial_boost=3, editorial_status="featured"),
            signals=SimpleNamespace(
                official_corroboration_score=0.8,
                district_membership_score=0.6,
                institutional_identity_score=0.4,
                genericity_penalty=0.1,
                has_wikidata=True,
            ),
            infrastructure_flag=True,
            cultural_flag=False,
            scenic_flag=False,
            historical_flag=True,
            primary_source="osm_overpass",
        ),
    )


def test_compute_non_spatial_score_components_uses_shared_weights() -> None:
    breakdown = compute_non_spatial_score_components(make_poi(), travel_mode="driving")

    assert breakdown == {
        "significance": 21.0,
        "quality": 8.0,
        "mode_affinity": 6.0,
        "official_corroboration": 6.4,
        "district_membership": 3.0,
        "institutional_identity": 1.6,
        "editorial_boost": 3.0,
        "penalties": -1.0,
    }


def test_build_why_it_matters_reuses_common_evidence_language() -> None:
    reasons = build_why_it_matters(
        make_poi(),
        score_breakdown={
            "point_proximity": 16.0,
            "radius_fit": 10.0,
            "significance": 21.0,
            "official_corroboration": 6.4,
            "district_membership": 3.0,
            "institutional_identity": 1.6,
        },
        category_match="primary",
        spatial_mode="nearby",
    )

    assert reasons == [
        "strong primary match for the requested category",
        "very close to the pinned location",
        "strong base significance for this landscape reading",
    ]


def test_build_badges_supports_spatial_and_detail_contexts() -> None:
    poi = make_poi()

    nearby_badges = build_badges(
        poi,
        spatial_mode="nearby",
        distance_m=90,
        travel_mode="walking",
    )
    detail_badges = build_badges(poi, include_source_badges=True)

    assert nearby_badges[:4] == [
        "near this location",
        "walkable",
        "featured",
        "officially corroborated",
    ]
    assert detail_badges == [
        "featured",
        "officially corroborated",
        "history",
        "infrastructure trace",
        "osm-ingested",
    ]


def test_build_why_it_matters_adds_rail_theme_reason() -> None:
    reasons = build_why_it_matters(
        make_poi(),
        requested_theme="rail",
        theme_match=True,
    )

    assert reasons[0] == "historical significance signal present"
    assert "reveals rail infrastructure or railyard corridor traces" in reasons


def test_build_badges_adds_rail_theme_badge() -> None:
    badges = build_badges(
        make_poi(),
        requested_theme="rail",
        theme_match=True,
    )

    assert "rail theme" in badges


def test_compute_category_context_penalizes_generic_scenic_park() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Cathedral Park",
            normalized_category="scenic",
            normalized_subcategory="trail_river_access",
            display_categories=["scenic"],
            raw_tag_summary_json={"name": "Cathedral Park", "leisure": "park"},
        ),
    )

    breakdown = compute_category_context_components(poi, requested_category="scenic")

    assert breakdown["scenic_specificity"] == -6.0


def test_compute_category_context_rewards_art_anchors() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Convergence Gallery",
            normalized_category="art",
            normalized_subcategory="gallery_art_space",
            display_categories=["art"],
            raw_tag_summary_json={"name": "Convergence Gallery", "tourism": "gallery"},
        ),
    )

    breakdown = compute_category_context_components(poi, requested_category="art")

    assert breakdown["art_anchor_bonus"] == 4.0


def test_compute_category_context_rewards_civic_hybrid_rail_depot() -> None:
    poi = cast(
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
        ),
    )

    breakdown = compute_category_context_components(poi, requested_category="civic")

    assert breakdown["civic_anchor_bonus"] == 10.0
