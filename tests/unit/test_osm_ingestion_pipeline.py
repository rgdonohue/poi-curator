from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from poi_curator_ingestion.normalize import NormalizedPOI
from poi_curator_ingestion.pipeline import update_existing_poi_from_osm
from shapely.geometry import Point


def test_osm_upsert_does_not_overwrite_reviewed_canonical_field() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Reviewed Plaza",
            slug="reviewed-plaza-node-1",
            geom=None,
            centroid=None,
            city="santa-fe",
            region="New Mexico",
            country="US",
            normalized_category="Culture & History",
            normalized_subcategory="civic_space_plaza",
            display_categories=["culture"],
            short_description="Reviewed description",
            raw_tag_summary_json={},
            historical_flag=True,
            cultural_flag=True,
            scenic_flag=False,
            infrastructure_flag=False,
            food_identity_flag=False,
            walk_affinity_hint=0.7,
            drive_affinity_hint=0.4,
            base_significance_score=6.0,
            quality_score=70.0,
            updated_at=datetime.now(UTC),
            editorial=SimpleNamespace(
                editorial_status="approved",
                editorial_title_override=None,
                editorial_description_override=None,
                editorial_category_override=None,
            ),
        ),
    )
    normalized = NormalizedPOI(
        source_record_id="node/1",
        canonical_name="OSM Plaza",
        slug="osm-plaza-node-1",
        geom=Point(-105.94, 35.68),
        centroid=Point(-105.94, 35.68),
        city="santa-fe",
        region="New Mexico",
        country="US",
        normalized_category="Food & Drink",
        normalized_subcategory="restaurant",
        display_categories=["food"],
        short_description="Incoming OSM description",
        raw_tag_summary={"name": "OSM Plaza"},
        historical_flag=False,
        cultural_flag=False,
        scenic_flag=False,
        infrastructure_flag=False,
        food_identity_flag=True,
        walk_affinity_hint=0.5,
        drive_affinity_hint=0.6,
        base_significance_score=4.0,
        quality_score=50.0,
        matched_rule_id="amenity_restaurant",
        matched_rule_tags={"amenity": "restaurant"},
    )

    conflicts = update_existing_poi_from_osm(poi, normalized)

    assert poi.canonical_name == "Reviewed Plaza"
    assert poi.normalized_category == "Culture & History"
    assert poi.short_description == "Reviewed description"
    assert poi.raw_tag_summary_json == {"name": "OSM Plaza"}
    assert {conflict.field_name for conflict in conflicts} >= {
        "canonical_name",
        "normalized_category",
        "short_description",
    }
