from poi_curator_domain.categories import (
    classify_osm_tags,
    infer_internal_type_from_osm_tags,
    public_category_for_internal_type,
)


def test_infer_mural_internal_type() -> None:
    tags = {"tourism": "artwork", "artwork_type": "mural", "name": "Wall"}

    internal_type = infer_internal_type_from_osm_tags(tags)

    assert internal_type == "mural_public_art"
    assert public_category_for_internal_type(internal_type) == "art"


def test_acequia_named_mural_reads_as_infrastructure() -> None:
    tags = {"tourism": "artwork", "artwork_type": "mural", "name": "Acequia Madre"}

    classification = classify_osm_tags(tags)

    assert classification is not None
    assert classification.internal_type == "infrastructure_landmark"
    assert classification.public_category == "civic"
    assert classification.matched_rule_id == "acequia_named_artwork_override"


def test_waterway_trace_reads_as_infrastructure() -> None:
    tags = {"name": "Acequia Trail Crossing", "waterway": "stream"}

    classification = classify_osm_tags(tags)

    assert classification is not None
    assert classification.internal_type == "infrastructure_landmark"
    assert classification.public_category == "civic"
    assert classification.matched_rule_id == "waterway_trace"


def test_viewpoint_beats_historic_memorial_for_overlook() -> None:
    tags = {
        "name": "Cross of the Martyrs Overlook",
        "tourism": "viewpoint",
        "historic": "memorial",
    }

    classification = classify_osm_tags(tags)

    assert classification is not None
    assert classification.internal_type == "overlook_vista"
    assert classification.public_category == "scenic"
    assert classification.matched_rule_id == "viewpoint"


def test_railway_yard_beats_historic_generic_for_infrastructure() -> None:
    tags = {
        "name": "Santa Fe Rail Yard District",
        "railway": "yard",
        "historic": "industrial",
    }

    classification = classify_osm_tags(tags)

    assert classification is not None
    assert classification.internal_type == "infrastructure_landmark"
    assert classification.public_category == "civic"
    assert classification.matched_rule_id == "railway_trace"


def test_named_plaza_park_reads_as_civic_plaza() -> None:
    tags = {
        "name": "The Santa Fe Plaza",
        "leisure": "park",
        "operator:type": "government",
    }

    classification = classify_osm_tags(tags)

    assert classification is not None
    assert classification.internal_type == "civic_space_plaza"
    assert classification.public_category == "civic"
    assert classification.matched_rule_id == "park_named_plaza"
