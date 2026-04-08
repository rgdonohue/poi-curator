from types import SimpleNamespace

import pytest
from shapely.geometry import LineString, Point, Polygon

from poi_curator_scoring.place_representation import build_place_representation


def test_line_geometry_builds_corridor_representation_from_query_encounter() -> None:
    poi = SimpleNamespace(
        normalized_subcategory="infrastructure_landmark",
        raw_tag_summary_json={"man_made": "canal"},
    )

    representation = build_place_representation(
        poi,
        LineString([(0.0, 0.0), (10.0, 0.0)]),
        query_geometry=Point(2.0, 3.0),
        fallback_point=Point(5.0, 0.0),
    )

    assert representation.extended_place is not None
    assert representation.extended_place.place_form == "corridor"
    assert representation.anchor_point.x == pytest.approx(2.0)
    assert representation.anchor_point.y == pytest.approx(0.0)
    assert representation.extended_place.encounter_anchors[0].is_primary is True
    assert representation.extended_place.encounter_anchors[0].coordinates == pytest.approx(
        [2.0, 0.0]
    )
    assert any(anchor.kind == "segment" for anchor in representation.extended_place.encounter_anchors[1:])


def test_polygon_geometry_builds_area_representation_with_center_anchor() -> None:
    poi = SimpleNamespace(
        normalized_subcategory="historic_district",
        raw_tag_summary_json={},
    )

    representation = build_place_representation(
        poi,
        Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)]),
        query_geometry=Point(12.0, 4.0),
        fallback_point=Point(5.0, 4.0),
    )

    assert representation.extended_place is not None
    assert representation.extended_place.place_form == "area"
    assert representation.anchor_point.x == pytest.approx(10.0)
    assert representation.anchor_point.y == pytest.approx(4.0)
    assert representation.extended_place.encounter_anchors[0].label == "primary encounter"
    assert representation.extended_place.encounter_anchors[1].label == "area center"
