import orjson
from poi_curator_domain.regions import get_region
from poi_curator_ingestion.normalize import normalize_osm_element, normalize_osm_element_with_audit


def test_normalize_fixture_element_into_canonical_poi() -> None:
    fixture = orjson.loads(
        open("data/fixtures/overpass_santa_fe_sample.json", "rb").read()
    )
    element = fixture["elements"][0]

    normalized = normalize_osm_element(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.canonical_name == "Santa Fe Plaza"
    assert normalized.normalized_category == "civic"
    assert normalized.normalized_subcategory == "civic_space_plaza"
    assert normalized.display_categories == ["civic", "history", "culture"]
    assert "history" in normalized.display_categories
    assert normalized.slug.startswith("santa-fe-plaza-way-")


def test_overlook_normalizes_to_scenic_primary_with_history_secondary() -> None:
    fixture = orjson.loads(
        open("data/fixtures/overpass_santa_fe_sample.json", "rb").read()
    )
    element = next(item for item in fixture["elements"] if item["id"] == 1003)

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "scenic"
    assert normalized.normalized_subcategory == "overlook_vista"
    assert normalized.display_categories == ["scenic", "history"]
    assert audit.matched_rule_id == "viewpoint"


def test_acequia_normalizes_to_civic_primary() -> None:
    fixture = orjson.loads(
        open("data/fixtures/overpass_santa_fe_sample.json", "rb").read()
    )
    element = next(item for item in fixture["elements"] if item["id"] == 1002)

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "civic"
    assert normalized.normalized_subcategory == "infrastructure_landmark"
    assert normalized.display_categories == ["civic", "history"]
    assert audit.matched_rule_id == "acequia_canal"


def test_barrio_can_be_culture_primary_with_history_secondary() -> None:
    fixture = orjson.loads(
        open("data/fixtures/overpass_santa_fe_sample.json", "rb").read()
    )
    element = next(item for item in fixture["elements"] if item["id"] == 1014)

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "culture"
    assert normalized.display_categories == ["culture", "history"]
    assert audit.matched_rule_id == "neighbourhood"


def test_marketplace_normalizes_to_food_primary() -> None:
    fixture = orjson.loads(
        open("data/fixtures/overpass_santa_fe_sample.json", "rb").read()
    )
    element = next(item for item in fixture["elements"] if item["id"] == 1008)

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "food"
    assert normalized.display_categories == ["food", "culture"]
    assert audit.matched_rule_id == "marketplace"


def test_historic_railway_station_gains_civic_secondary() -> None:
    element = {
        "type": "node",
        "id": 9999,
        "lat": 35.6815,
        "lon": -105.952,
        "tags": {
            "name": "Atchison, Topeka & Santa Fe Railway Depot",
            "historic": "railway_station",
        },
    }

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "history"
    assert normalized.display_categories == ["history", "civic"]
    assert audit.matched_rule_id == "historic_generic"


def test_acequia_named_mural_normalizes_to_civic_with_art_secondary() -> None:
    element = {
        "type": "node",
        "id": 10000,
        "lat": 35.6828,
        "lon": -105.9319,
        "tags": {
            "name": "Acequia Madre",
            "tourism": "artwork",
            "artwork_type": "mural",
        },
    }

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "civic"
    assert normalized.normalized_subcategory == "infrastructure_landmark"
    assert normalized.display_categories == ["civic", "art"]
    assert normalized.short_description == (
        "Infrastructure trace that reveals labor, circulation, or water systems."
    )
    assert audit.matched_rule_id == "acequia_named_artwork_override"


def test_waterway_trace_normalizes_to_civic_primary() -> None:
    element = {
        "type": "way",
        "id": 10001,
        "geometry": [
            {"lat": 35.6826, "lon": -105.9321},
            {"lat": 35.6829, "lon": -105.9318},
        ],
        "tags": {
            "name": "Acequia Trail Crossing",
            "waterway": "stream",
        },
    }

    normalized, audit = normalize_osm_element_with_audit(element, get_region("santa-fe"))

    assert normalized is not None
    assert normalized.normalized_category == "civic"
    assert normalized.normalized_subcategory == "infrastructure_landmark"
    assert normalized.display_categories == ["civic"]
    assert audit.matched_rule_id == "waterway_trace"
