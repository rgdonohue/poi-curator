from __future__ import annotations

from typing import Any

LOW_SIGNAL_SUBSTRINGS = (
    "survey",
    "resurvey",
    "confirm former",
    "fixme",
    "todo",
    "verify",
    "needs review",
    "not resurveyed",
    "check elevation",
)

DESCRIPTION_TEMPLATES = {
    "historic_site": "Historic site with strong local landscape context.",
    "historic_district": (
        "Historic district that helps explain settlement patterns and continuity."
    ),
    "museum": "Museum or interpretive site with clear historical context.",
    "monument_memorial": "Monument or memorial with strong public memory value.",
    "mural_public_art": "Public artwork that reads as part of the local cultural landscape.",
    "gallery_art_space": "Art space with strong corridor-level cultural identity.",
    "performance_cultural_venue": (
        "Cultural venue that signals local performance and public life."
    ),
    "neighborhood_corridor": (
        "Neighborhood corridor that expresses local identity at street level."
    ),
    "overlook_vista": "Viewpoint with a strong terrain and settlement read.",
    "trail_river_access": "Landscape access point with ecological or scenic value.",
    "civic_space_plaza": "Civic space that helps explain the structure of public life.",
    "infrastructure_landmark": (
        "Infrastructure trace that reveals labor, circulation, or water systems."
    ),
    "market_food_identity": "Identity-bearing market or food place with local distinctiveness.",
    "ritual_religious_site": "Ritual or religious site with strong cultural continuity.",
    "landscape_feature": "Landscape feature with clear scenic or ecological legibility.",
}


def is_low_quality_description(description: str | None) -> bool:
    if description is None:
        return True
    normalized = " ".join(description.strip().split())
    if len(normalized) < 20:
        return True
    lowered = normalized.lower()
    if any(fragment in lowered for fragment in LOW_SIGNAL_SUBSTRINGS):
        return True
    if normalized.count(",") >= 3 and len(normalized.split()) <= 8:
        return True
    return False


def fallback_short_description(normalized_subcategory: str | None) -> str:
    if normalized_subcategory is None:
        return "No editorial description yet."
    return DESCRIPTION_TEMPLATES[normalized_subcategory]


def choose_short_description(
    *,
    normalized_subcategory: str | None,
    editorial_override: str | None = None,
    stored_description: str | None = None,
) -> str:
    if editorial_override and not is_low_quality_description(editorial_override):
        return editorial_override
    if stored_description and not is_low_quality_description(stored_description):
        return stored_description
    return fallback_short_description(normalized_subcategory)


def description_quality_score(description: str | None, normalized_subcategory: str | None) -> float:
    chosen = choose_short_description(
        normalized_subcategory=normalized_subcategory,
        stored_description=description,
    )
    if chosen == "No editorial description yet.":
        return 0.0
    return min(float(len(chosen)) / 20.0, 10.0)


def choose_short_description_for_poi(poi: Any) -> str:
    editorial_override = None
    if getattr(poi, "editorial", None) is not None:
        editorial_override = getattr(poi.editorial, "editorial_description_override", None)
    return choose_short_description(
        normalized_subcategory=getattr(poi, "normalized_subcategory", None),
        editorial_override=editorial_override,
        stored_description=getattr(poi, "short_description", None),
    )
