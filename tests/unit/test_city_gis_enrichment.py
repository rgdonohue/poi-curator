from types import SimpleNamespace

from poi_curator_enrichment.city_gis import (
    CITY_GIS_LAYER_SPECS,
    CandidatePOI,
    CityGISFeature,
    match_point_feature_to_poi,
    name_similarity,
    poi_ids_within_polygon,
)
from poi_curator_enrichment.pipeline import summarize_evidence_signals
from shapely.geometry import Point, Polygon


def test_name_similarity_handles_possessive_variant() -> None:
    similarity = name_similarity("Palace of the Governor's", "Palace of the Governors")

    assert similarity >= 0.7


def test_match_point_feature_to_poi_matches_city_museum_record() -> None:
    museums_layer = next(
        layer for layer in CITY_GIS_LAYER_SPECS if layer.source_id == "city_gis_museums"
    )
    feature = CityGISFeature(
        layer=museums_layer,
        feature_id="10",
        name="Palace of the Governor's",
        label="Palace of the Governor's",
        geometry=Point(-105.93834, 35.68786),
        properties={"DEPARTMENT": "Palace of the Governor's"},
        source_url="https://example.test/10",
    )
    pois = [
        CandidatePOI(
            poi_id="palace",
            canonical_name="Palace of the Governors",
            normalized_category="history",
            display_categories=["history", "civic"],
            centroid=Point(-105.93835, 35.68787),
        ),
        CandidatePOI(
            poi_id="plaza",
            canonical_name="Santa Fe Plaza",
            normalized_category="civic",
            display_categories=["civic", "history"],
            centroid=Point(-105.93780, 35.68700),
        ),
    ]

    match = match_point_feature_to_poi(feature, pois)

    assert match is not None
    assert match.poi_id == "palace"
    assert match.confidence >= 0.7


def test_poi_ids_within_polygon_finds_anchor_boundary_membership() -> None:
    railyard_layer = next(
        layer for layer in CITY_GIS_LAYER_SPECS if layer.source_id == "city_gis_railyard_boundary"
    )
    polygon_feature = CityGISFeature(
        layer=railyard_layer,
        feature_id="1",
        name=None,
        label="The Railyard",
        geometry=Polygon(
            [
                (-105.95, 35.681),
                (-105.946, 35.681),
                (-105.946, 35.685),
                (-105.95, 35.685),
                (-105.95, 35.681),
            ]
        ),
        properties={},
        source_url="https://example.test/1",
    )
    pois = [
        CandidatePOI(
            poi_id="railyard",
            canonical_name="Santa Fe Railyard",
            normalized_category="civic",
            display_categories=["civic", "history"],
            centroid=Point(-105.9485, 35.6835),
        ),
        CandidatePOI(
            poi_id="plaza",
            canonical_name="Santa Fe Plaza",
            normalized_category="civic",
            display_categories=["civic", "history"],
            centroid=Point(-105.9378, 35.687),
        ),
    ]

    matched_ids = poi_ids_within_polygon(polygon_feature, pois)

    assert matched_ids == ["railyard"]


def test_summarize_evidence_signals_rolls_up_anchor_corroboration() -> None:
    evidence_rows = [
        SimpleNamespace(evidence_type="historic_building_status"),
        SimpleNamespace(evidence_type="district_membership"),
        SimpleNamespace(evidence_type="institution_membership"),
    ]

    summary = summarize_evidence_signals(evidence_rows)  # type: ignore[arg-type]

    assert summary.has_official_heritage_match is True
    assert summary.official_corroboration_score == 1.0
    assert summary.district_membership_score == 1.0
    assert summary.institutional_identity_score == 0.75
