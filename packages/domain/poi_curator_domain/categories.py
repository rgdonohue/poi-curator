from dataclasses import dataclass

from pydantic import BaseModel


class CategoryResponse(BaseModel):
    slug: str
    label: str
    description: str


PUBLIC_CATEGORIES: list[CategoryResponse] = [
    CategoryResponse(
        slug="history",
        label="History",
        description="Places that reveal settlement, memory, and historical change.",
    ),
    CategoryResponse(
        slug="culture",
        label="Culture",
        description=(
            "Places that express living identity, ritual, corridor life, and community meaning."
        ),
    ),
    CategoryResponse(
        slug="art",
        label="Art",
        description="Murals, public art, and creative places with strong local voice.",
    ),
    CategoryResponse(
        slug="scenic",
        label="Scenic",
        description="Landscape features, overlooks, and visually legible terrain.",
    ),
    CategoryResponse(
        slug="food",
        label="Food",
        description="Identity-bearing food places only. Generic commerce should be down-ranked.",
    ),
    CategoryResponse(
        slug="civic",
        label="Civic / Infrastructure",
        description=(
            "Plazas, rail yards, irrigation works, and other civic or infrastructural traces."
        ),
    ),
]


INTERNAL_TYPES: list[str] = [
    "historic_site",
    "historic_district",
    "museum",
    "monument_memorial",
    "mural_public_art",
    "gallery_art_space",
    "performance_cultural_venue",
    "neighborhood_corridor",
    "overlook_vista",
    "trail_river_access",
    "civic_space_plaza",
    "infrastructure_landmark",
    "market_food_identity",
    "ritual_religious_site",
    "landscape_feature",
]


INTERNAL_TYPE_TO_PUBLIC_CATEGORY: dict[str, str] = {
    "historic_site": "history",
    "historic_district": "history",
    "museum": "history",
    "monument_memorial": "history",
    "mural_public_art": "art",
    "gallery_art_space": "art",
    "performance_cultural_venue": "culture",
    "neighborhood_corridor": "culture",
    "overlook_vista": "scenic",
    "trail_river_access": "scenic",
    "civic_space_plaza": "civic",
    "infrastructure_landmark": "civic",
    "market_food_identity": "food",
    "ritual_religious_site": "culture",
    "landscape_feature": "scenic",
}


@dataclass(frozen=True)
class OSMTagRule:
    rule_id: str
    internal_type: str
    required_tags: dict[str, str]


@dataclass(frozen=True)
class ClassificationResult:
    internal_type: str
    public_category: str
    matched_rule_id: str
    matched_rule_tags: dict[str, str]


OSM_TAG_RULES: list[OSMTagRule] = [
    OSMTagRule("marketplace", "market_food_identity", {"amenity": "marketplace"}),
    OSMTagRule("plaza_square", "civic_space_plaza", {"place": "square"}),
    OSMTagRule("pedestrian_plaza", "civic_space_plaza", {"highway": "pedestrian"}),
    OSMTagRule("viewpoint", "overlook_vista", {"tourism": "viewpoint"}),
    OSMTagRule("acequia_canal", "infrastructure_landmark", {"man_made": "canal"}),
    OSMTagRule("railway_trace", "infrastructure_landmark", {"railway": "*"}),
    OSMTagRule("man_made_infrastructure", "infrastructure_landmark", {"man_made": "*"}),
    OSMTagRule(
        "mural_artwork",
        "mural_public_art",
        {"tourism": "artwork", "artwork_type": "mural"},
    ),
    OSMTagRule(
        "memorial_artwork",
        "monument_memorial",
        {"tourism": "artwork", "artwork_type": "statue"},
    ),
    OSMTagRule("gallery", "gallery_art_space", {"tourism": "gallery"}),
    OSMTagRule("museum", "museum", {"tourism": "museum"}),
    OSMTagRule("theatre", "performance_cultural_venue", {"amenity": "theatre"}),
    OSMTagRule("place_of_worship", "ritual_religious_site", {"amenity": "place_of_worship"}),
    OSMTagRule("park", "trail_river_access", {"leisure": "park"}),
    OSMTagRule("natural_feature", "landscape_feature", {"natural": "*"}),
    OSMTagRule("neighbourhood", "neighborhood_corridor", {"place": "neighbourhood"}),
    OSMTagRule("historic_district", "historic_district", {"historic": "district"}),
    OSMTagRule("historic_memorial", "monument_memorial", {"historic": "memorial"}),
    OSMTagRule("historic_monument", "monument_memorial", {"historic": "monument"}),
    OSMTagRule("historic_generic", "historic_site", {"historic": "*"}),
]


def public_category_for_internal_type(internal_type: str) -> str:
    return INTERNAL_TYPE_TO_PUBLIC_CATEGORY[internal_type]


def classify_osm_tags(tags: dict[str, str]) -> ClassificationResult | None:
    if tags.get("leisure") == "park" and "plaza" in tags.get("name", "").lower():
        return ClassificationResult(
            internal_type="civic_space_plaza",
            public_category="civic",
            matched_rule_id="park_named_plaza",
            matched_rule_tags={"leisure": "park", "name_contains": "plaza"},
        )
    matched_rule = match_osm_rule(tags)
    if matched_rule is None:
        return None
    return ClassificationResult(
        internal_type=matched_rule.internal_type,
        public_category=public_category_for_internal_type(matched_rule.internal_type),
        matched_rule_id=matched_rule.rule_id,
        matched_rule_tags=matched_rule.required_tags,
    )


def infer_internal_type_from_osm_tags(tags: dict[str, str]) -> str | None:
    result = classify_osm_tags(tags)
    return result.internal_type if result is not None else None


def match_osm_rule(tags: dict[str, str]) -> OSMTagRule | None:
    for rule in OSM_TAG_RULES:
        if _matches_required_tags(tags, rule.required_tags):
            return rule
    return None


def _matches_required_tags(tags: dict[str, str], required_tags: dict[str, str]) -> bool:
    for key, expected_value in required_tags.items():
        actual_value = tags.get(key)
        if actual_value is None:
            return False
        if expected_value != "*" and actual_value != expected_value:
            return False
    return True
