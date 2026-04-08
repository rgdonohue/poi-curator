from dataclasses import dataclass
from typing import Any

from poi_curator_domain.categories import (
    ClassificationResult,
    classify_osm_tags,
)
from poi_curator_domain.descriptions import DESCRIPTION_TEMPLATES, is_low_quality_description
from poi_curator_domain.regions import RegionSpec
from poi_curator_domain.text import slugify
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class NormalizedPOI:
    source_record_id: str
    canonical_name: str
    slug: str
    geom: BaseGeometry
    centroid: Point
    city: str
    region: str
    country: str
    normalized_category: str
    normalized_subcategory: str
    display_categories: list[str]
    short_description: str
    raw_tag_summary: dict[str, str]
    historical_flag: bool
    cultural_flag: bool
    scenic_flag: bool
    infrastructure_flag: bool
    food_identity_flag: bool
    walk_affinity_hint: float
    drive_affinity_hint: float
    base_significance_score: float
    quality_score: float
    matched_rule_id: str
    matched_rule_tags: dict[str, str]


@dataclass(frozen=True)
class NormalizationAuditRecord:
    source_record_id: str
    name: str | None
    status: str
    matched_rule_id: str | None
    internal_type: str | None
    public_category: str | None
    display_categories: list[str]
    key_tags: dict[str, str]
    matched_rule_tags: dict[str, str]


def source_record_id_for_element(element: dict[str, Any]) -> str:
    return f"{element['type']}/{element['id']}"


def normalize_osm_element(
    element: dict[str, Any],
    region: RegionSpec,
) -> NormalizedPOI | None:
    normalized, _ = normalize_osm_element_with_audit(element, region)
    return normalized


def normalize_osm_element_with_audit(
    element: dict[str, Any],
    region: RegionSpec,
) -> tuple[NormalizedPOI | None, NormalizationAuditRecord]:
    tags = {
        key: str(value)
        for key, value in element.get("tags", {}).items()
        if value is not None
    }
    source_record_id = source_record_id_for_element(element)
    canonical_name = tags.get("name")
    if canonical_name is None:
        return None, NormalizationAuditRecord(
            source_record_id=source_record_id,
            name=None,
            status="skipped_missing_name",
            matched_rule_id=None,
            internal_type=None,
            public_category=None,
            display_categories=[],
            key_tags=summarize_tags(tags),
            matched_rule_tags={},
        )

    classification = classify_osm_tags(tags)
    if classification is None:
        return None, NormalizationAuditRecord(
            source_record_id=source_record_id,
            name=canonical_name,
            status="skipped_unclassified",
            matched_rule_id=None,
            internal_type=None,
            public_category=None,
            display_categories=[],
            key_tags=summarize_tags(tags),
            matched_rule_tags={},
        )

    geom = geometry_from_overpass_element(element)
    centroid_geom = geom.centroid
    centroid = (
        centroid_geom
        if isinstance(centroid_geom, Point)
        else Point(centroid_geom.x, centroid_geom.y)
    )
    display_categories = apply_name_specific_category_overrides(
        canonical_name,
        display_categories_for_classification(tags, classification),
    )

    normalized = NormalizedPOI(
        source_record_id=source_record_id,
        canonical_name=canonical_name,
        slug=build_slug(canonical_name, source_record_id),
        geom=geom,
        centroid=centroid,
        city=normalize_city(tags.get("addr:city"), region),
        region=region.region,
        country=region.country,
        normalized_category=classification.public_category,
        normalized_subcategory=classification.internal_type,
        display_categories=display_categories,
        short_description=build_short_description(classification.internal_type, tags),
        raw_tag_summary=summarize_tags(tags),
        historical_flag="history" in display_categories,
        cultural_flag="culture" in display_categories,
        scenic_flag="scenic" in display_categories,
        infrastructure_flag="civic" in display_categories,
        food_identity_flag="food" in display_categories,
        walk_affinity_hint=walk_affinity_for_internal_type(classification.internal_type),
        drive_affinity_hint=drive_affinity_for_internal_type(classification.internal_type),
        base_significance_score=base_significance_for_tags(classification.internal_type, tags),
        quality_score=quality_score_for_tags(tags),
        matched_rule_id=classification.matched_rule_id,
        matched_rule_tags=classification.matched_rule_tags,
    )
    audit = NormalizationAuditRecord(
        source_record_id=source_record_id,
        name=canonical_name,
        status="classified",
        matched_rule_id=classification.matched_rule_id,
        internal_type=classification.internal_type,
        public_category=classification.public_category,
        display_categories=display_categories,
        key_tags=summarize_tags(tags),
        matched_rule_tags=classification.matched_rule_tags,
    )
    return normalized, audit


def geometry_from_overpass_element(element: dict[str, Any]) -> BaseGeometry:
    if "lat" in element and "lon" in element:
        return Point(float(element["lon"]), float(element["lat"]))

    if "geometry" in element:
        coordinates = [
            (float(point["lon"]), float(point["lat"]))
            for point in element["geometry"]
        ]
        if len(coordinates) >= 4 and coordinates[0] == coordinates[-1]:
            return Polygon(coordinates)
        if len(coordinates) >= 2:
            return LineString(coordinates)
        if coordinates:
            lon, lat = coordinates[0]
            return Point(lon, lat)

    if "center" in element:
        center = element["center"]
        return Point(float(center["lon"]), float(center["lat"]))

    if "bounds" in element:
        bounds = element["bounds"]
        polygon = {
            "type": "Polygon",
            "coordinates": [[
                [bounds["minlon"], bounds["minlat"]],
                [bounds["minlon"], bounds["maxlat"]],
                [bounds["maxlon"], bounds["maxlat"]],
                [bounds["maxlon"], bounds["minlat"]],
                [bounds["minlon"], bounds["minlat"]],
            ]],
        }
        return shape(polygon)

    raise ValueError(
        "Unsupported Overpass geometry for element "
        f"{source_record_id_for_element(element)}"
    )


def build_slug(name: str, source_record_id: str) -> str:
    element_type, element_id = source_record_id.split("/", maxsplit=1)
    return slugify(f"{name}-{element_type}-{element_id}")


def normalize_city(tag_city: str | None, region: RegionSpec) -> str:
    if tag_city is None:
        return region.city
    return slugify(tag_city)


def summarize_tags(tags: dict[str, str]) -> dict[str, str]:
    keep_keys = {
        "name",
        "historic",
        "tourism",
        "artwork_type",
        "amenity",
        "place",
        "railway",
        "waterway",
        "highway",
        "leisure",
        "natural",
        "man_made",
        "wikidata",
        "wikipedia",
    }
    return {key: value for key, value in tags.items() if key in keep_keys}


def display_categories_for_classification(
    tags: dict[str, str],
    classification: ClassificationResult,
) -> list[str]:
    categories = {classification.public_category}
    internal_type = classification.internal_type

    if "historic" in tags or internal_type in {"historic_site", "historic_district", "museum"}:
        categories.add("history")
    if internal_type in {
        "ritual_religious_site",
        "performance_cultural_venue",
        "neighborhood_corridor",
        "market_food_identity",
    }:
        categories.add("culture")
    if (
        any(key in tags for key in ("place", "amenity"))
        and classification.public_category != "food"
    ):
        categories.add("culture")
    if internal_type in {"mural_public_art", "gallery_art_space"}:
        categories.add("art")
    if (
        tags.get("tourism") == "artwork"
        and classification.internal_type == "infrastructure_landmark"
        and "acequia" in tags.get("name", "").casefold()
    ):
        categories.add("art")
    if internal_type in {"overlook_vista", "trail_river_access", "landscape_feature"}:
        categories.add("scenic")
    if tags.get("tourism") == "viewpoint":
        categories.add("scenic")
    if internal_type in {"civic_space_plaza", "infrastructure_landmark"}:
        categories.add("civic")
    if any(key in tags for key in ("man_made", "railway")) or tags.get("highway") == "pedestrian":
        categories.add("civic")
    if tags.get("historic") == "railway_station":
        categories.add("civic")
    if internal_type == "market_food_identity" or tags.get("amenity") == "marketplace":
        categories.add("food")
    ordered = [
        classification.public_category,
        "history",
        "culture",
        "art",
        "scenic",
        "food",
        "civic",
    ]
    seen: set[str] = set()
    result: list[str] = []
    for category in ordered:
        if category in categories and category not in seen:
            result.append(category)
            seen.add(category)
    return result


def apply_name_specific_category_overrides(
    canonical_name: str,
    display_categories: list[str],
) -> list[str]:
    name = canonical_name.casefold()
    if name not in {"the santa fe plaza", "santa fe plaza"}:
        return display_categories
    if "history" in display_categories:
        return display_categories

    result = list(display_categories)
    insert_at = 1 if result else 0
    result.insert(insert_at, "history")
    return result


def build_short_description(internal_type: str, tags: dict[str, str]) -> str:
    if description := tags.get("description"):
        normalized = description[:220].strip()
        if not is_low_quality_description(normalized):
            return normalized

    return DESCRIPTION_TEMPLATES[internal_type]


def walk_affinity_for_internal_type(internal_type: str) -> float:
    high = {"mural_public_art", "gallery_art_space", "neighborhood_corridor", "civic_space_plaza"}
    medium = {"historic_district", "museum", "performance_cultural_venue", "trail_river_access"}
    if internal_type in high:
        return 0.9
    if internal_type in medium:
        return 0.75
    return 0.55


def drive_affinity_for_internal_type(internal_type: str) -> float:
    high = {"overlook_vista", "historic_site", "infrastructure_landmark", "landscape_feature"}
    medium = {"museum", "historic_district", "civic_space_plaza", "market_food_identity"}
    if internal_type in high:
        return 0.9
    if internal_type in medium:
        return 0.75
    return 0.6


def base_significance_for_tags(internal_type: str, tags: dict[str, str]) -> float:
    base_scores = {
        "historic_site": 68.0,
        "historic_district": 72.0,
        "museum": 64.0,
        "monument_memorial": 62.0,
        "mural_public_art": 58.0,
        "gallery_art_space": 56.0,
        "performance_cultural_venue": 56.0,
        "neighborhood_corridor": 60.0,
        "overlook_vista": 60.0,
        "trail_river_access": 52.0,
        "civic_space_plaza": 66.0,
        "infrastructure_landmark": 64.0,
        "market_food_identity": 55.0,
        "ritual_religious_site": 58.0,
        "landscape_feature": 57.0,
    }
    score = base_scores[internal_type]
    if "wikidata" in tags:
        score += 4.0
    if "wikipedia" in tags:
        score += 3.0
    if tags.get("historic") in {"yes", "monument", "memorial"}:
        score += 2.0
    return score


def quality_score_for_tags(tags: dict[str, str]) -> float:
    score = 40.0
    score += min(len(tags), 12) * 2.5
    if "name" in tags:
        score += 10.0
    if "wikidata" in tags:
        score += 5.0
    if "wikipedia" in tags:
        score += 5.0
    return min(score, 95.0)
