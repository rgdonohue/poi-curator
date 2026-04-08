from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from poi_curator_domain.db import POI
from poi_curator_domain.themes import theme_badge_label, theme_explanation_reason


@dataclass(frozen=True)
class ScoringWeights:
    significance: float = 30.0
    quality: float = 10.0
    mode_affinity: float = 8.0
    official_corroboration: float = 8.0
    district_membership: float = 5.0
    institutional_identity: float = 4.0
    genericity_penalty: float = 10.0


DEFAULT_SCORING_WEIGHTS = ScoringWeights()

CategoryMatchResult = Literal["primary", "secondary", "mixed"]
SpatialExplanationMode = Literal["route", "nearby"]


def compute_non_spatial_score_components(
    poi: POI,
    *,
    travel_mode: str,
    weights: ScoringWeights = DEFAULT_SCORING_WEIGHTS,
) -> dict[str, float]:
    affinity_hint = (
        poi.drive_affinity_hint if travel_mode == "driving" else poi.walk_affinity_hint
    )
    editorial_boost = float(poi.editorial.editorial_boost) if poi.editorial is not None else 0.0
    official_corroboration = 0.0
    district_membership = 0.0
    institutional_identity = 0.0
    penalties = 0.0

    if poi.signals is not None:
        official_corroboration = round(
            float(getattr(poi.signals, "official_corroboration_score", 0.0))
            * weights.official_corroboration,
            2,
        )
        district_membership = round(
            float(getattr(poi.signals, "district_membership_score", 0.0))
            * weights.district_membership,
            2,
        )
        institutional_identity = round(
            float(getattr(poi.signals, "institutional_identity_score", 0.0))
            * weights.institutional_identity,
            2,
        )
        penalties = round(
            float(getattr(poi.signals, "genericity_penalty", 0.0)) * weights.genericity_penalty,
            2,
        )

    return {
        "significance": round((poi.base_significance_score / 100.0) * weights.significance, 2),
        "quality": round((poi.quality_score / 100.0) * weights.quality, 2),
        "mode_affinity": round(affinity_hint * weights.mode_affinity, 2),
        "official_corroboration": official_corroboration,
        "district_membership": district_membership,
        "institutional_identity": institutional_identity,
        "editorial_boost": editorial_boost,
        "penalties": -penalties,
    }


def compute_category_context_components(
    poi: POI,
    *,
    requested_category: str,
) -> dict[str, float]:
    raw_tags = dict(getattr(poi, "raw_tag_summary_json", {}) or {})
    name = str(getattr(poi, "canonical_name", "")).lower()
    normalized_subcategory = str(getattr(poi, "normalized_subcategory", ""))
    display_categories = list(getattr(poi, "display_categories", []) or [])

    scenic_specificity = 0.0
    art_anchor_bonus = 0.0
    civic_anchor_bonus = 0.0
    civic_fragment_penalty = 0.0
    history_anchor_bonus = 0.0

    if requested_category == "scenic":
        if poi.normalized_category != "scenic" and "scenic" in display_categories:
            scenic_specificity = -8.0
        elif normalized_subcategory == "overlook_vista":
            scenic_specificity = 4.0
        elif normalized_subcategory == "landscape_feature":
            scenic_specificity = 3.0
        elif normalized_subcategory == "trail_river_access":
            if (
                raw_tags.get("tourism") == "viewpoint"
                or "natural" in raw_tags
                or "waterway" in raw_tags
            ):
                scenic_specificity = 1.5
            else:
                scenic_specificity = -6.0

    if requested_category == "art" and poi.normalized_category == "art":
        if normalized_subcategory == "gallery_art_space":
            art_anchor_bonus += 3.0
        elif normalized_subcategory == "mural_public_art":
            art_anchor_bonus += 4.0
        if any(token in name for token in ("canyon", "gallery", "art", "studio")):
            art_anchor_bonus += 1.0

    if requested_category == "civic":
        if (
            poi.normalized_category == "history"
            and "civic" in display_categories
            and (
                raw_tags.get("historic") == "railway_station"
                or any(
                    token in name
                    for token in ("rail", "railway", "depot", "railyard", "acequia")
                )
            )
        ):
            civic_anchor_bonus = 10.0
        if (
            poi.normalized_category == "civic"
            and normalized_subcategory == "infrastructure_landmark"
            and any(token in name for token in ("bridge", "grid vent", "tunnel vent"))
        ):
            civic_fragment_penalty = -5.0

    if requested_category == "history" and _is_history_anchor(poi):
        history_anchor_bonus = 6.0

    return {
        "scenic_specificity": scenic_specificity,
        "art_anchor_bonus": art_anchor_bonus,
        "civic_anchor_bonus": civic_anchor_bonus,
        "civic_fragment_penalty": civic_fragment_penalty,
        "history_anchor_bonus": history_anchor_bonus,
    }


def compute_theme_context_components(
    poi: POI,
    *,
    requested_category: str,
    requested_theme: str | None,
) -> dict[str, float]:
    rail_anchor_bonus = 0.0
    rail_trace_guardrail = 0.0

    if requested_theme == "rail" and requested_category == "mixed":
        if _is_rail_anchor(poi):
            rail_anchor_bonus = 4.0
        elif _is_rule_only_rail_trace(poi):
            rail_trace_guardrail = -3.0

    return {
        "rail_anchor_bonus": rail_anchor_bonus,
        "rail_trace_guardrail": rail_trace_guardrail,
    }


def compute_point_theme_context_components(
    poi: POI,
    *,
    requested_category: str,
    requested_theme: str | None,
) -> dict[str, float]:
    nearby_rail_anchor_prominence = 0.0

    if requested_theme == "rail" and requested_category == "mixed" and _is_rail_anchor(poi):
        nearby_rail_anchor_prominence = 8.0

    return {
        "nearby_rail_anchor_prominence": nearby_rail_anchor_prominence,
    }


def build_why_it_matters(
    poi: POI,
    *,
    score_breakdown: Mapping[str, float] | None = None,
    category_match: CategoryMatchResult | None = None,
    spatial_mode: SpatialExplanationMode | None = None,
    include_editorial_reason: bool = False,
    requested_theme: str | None = None,
    theme_match: bool = False,
) -> list[str]:
    reasons: list[str] = []

    if score_breakdown is not None and spatial_mode is not None:
        if category_match == "primary":
            reasons.append("strong primary match for the requested category")
        elif category_match == "secondary":
            secondary_reason = (
                "secondary category match supported by route fit"
                if spatial_mode == "route"
                else "secondary category match supported by proximity"
            )
            reasons.append(secondary_reason)

        fit_keys: tuple[str, ...] = ("route_proximity", "detour_fit", "budget_fit")
        fit_threshold = 22.0
        fit_reason = "close to the route with manageable detour burden"
        if spatial_mode == "nearby":
            fit_keys = ("point_proximity", "radius_fit")
            fit_reason = "very close to the pinned location"

        fit_total = sum(float(score_breakdown.get(key, 0.0)) for key in fit_keys)
        if fit_total >= fit_threshold:
            reasons.append(fit_reason)
        if theme_match:
            theme_reason = theme_explanation_reason(requested_theme)
            if theme_reason is not None:
                reasons.append(theme_reason)

        if float(score_breakdown.get("significance", 0.0)) >= 18:
            reasons.append("strong base significance for this landscape reading")
        if float(score_breakdown.get("official_corroboration", 0.0)) >= 4:
            reasons.append("corroborated by official city or heritage sources")
        elif float(score_breakdown.get("district_membership", 0.0)) >= 3:
            reasons.append("sits inside a named civic or historic district")
        elif float(score_breakdown.get("institutional_identity", 0.0)) >= 2.5:
            reasons.append("recognized by public cultural institution data")
        if poi.signals is not None and bool(getattr(poi.signals, "has_wikidata", False)):
            reasons.append("linked identity from structured public data")
        if poi.infrastructure_flag:
            reasons.append("reveals civic or infrastructural traces")
        elif poi.cultural_flag:
            reasons.append("strong local identity and cultural legibility")
        elif poi.scenic_flag:
            reasons.append("offers a clear terrain or landscape read")
        elif poi.historical_flag:
            reasons.append("anchors local historical context")
        if (
            include_editorial_reason
            and poi.editorial is not None
            and poi.editorial.editorial_boost > 0
        ):
            reasons.append("editorially boosted candidate")
        if reasons:
            return reasons[:3]
        if spatial_mode == "route":
            return ["route-plausible candidate with meaningful local signal"]
        return ["nearby candidate with meaningful local signal"]

    if poi.historical_flag:
        reasons.append("historical significance signal present")
    if theme_match:
        theme_reason = theme_explanation_reason(requested_theme)
        if theme_reason is not None:
            reasons.append(theme_reason)
    if poi.cultural_flag:
        reasons.append("strong local identity or cultural context")
    if poi.infrastructure_flag:
        reasons.append("reveals civic or infrastructural traces")
    if poi.signals is not None and poi.signals.official_corroboration_score >= 0.7:
        reasons.append("corroborated by official city or heritage sources")
    if poi.signals is not None and poi.signals.has_wikidata:
        reasons.append("structured external identity match")
    return reasons[:3] or ["candidate requires editorial review"]


def build_badges(
    poi: POI,
    *,
    spatial_mode: SpatialExplanationMode | None = None,
    distance_m: int | None = None,
    estimated_detour_m: int | None = None,
    travel_mode: str | None = None,
    include_source_badges: bool = False,
    requested_theme: str | None = None,
    theme_match: bool = False,
) -> list[str]:
    badges: list[str] = []

    if spatial_mode == "route":
        if distance_m is not None and distance_m <= 150:
            badges.append("near this route")
        if estimated_detour_m is not None and estimated_detour_m <= 500:
            badges.append("within budget")
    elif spatial_mode == "nearby":
        if distance_m is not None and distance_m <= 100:
            badges.append("near this location")
        if travel_mode == "walking" and distance_m is not None and distance_m <= 400:
            badges.append("walkable")
        if travel_mode == "driving" and distance_m is not None and distance_m <= 1200:
            badges.append("short drive")

    if poi.editorial is not None and poi.editorial.editorial_status == "featured":
        badges.append("featured")
    if poi.signals is not None and float(
        getattr(poi.signals, "official_corroboration_score", 0.0)
    ) >= 0.7:
        badges.append("officially corroborated")
    if theme_match:
        theme_badge = theme_badge_label(requested_theme)
        if theme_badge is not None:
            badges.append(theme_badge)

    if spatial_mode is None:
        if poi.historical_flag:
            badges.append("history")
        if poi.scenic_flag:
            badges.append("scenic")
        if poi.infrastructure_flag:
            badges.append("infrastructure trace")
        if include_source_badges and poi.primary_source == "osm_overpass":
            badges.append("osm-ingested")
        return badges

    if poi.infrastructure_flag:
        badges.append("infrastructure trace")
    elif poi.scenic_flag:
        badges.append("scenic")
    elif poi.cultural_flag:
        badges.append("cultural signal")
    elif poi.historical_flag:
        badges.append("history")
    return badges


def _is_rail_anchor(poi: POI) -> bool:
    raw_tags = dict(getattr(poi, "raw_tag_summary_json", {}) or {})
    name = str(getattr(poi, "canonical_name", "") or "").casefold()
    normalized_subcategory = str(getattr(poi, "normalized_subcategory", "") or "")

    if raw_tags.get("historic") == "railway_station":
        return True
    if raw_tags.get("railway") in {"station", "yard"}:
        return True
    if "depot" in name or "station" in name:
        return True
    if (
        "railyard" in name or "rail yard" in name
    ) and normalized_subcategory in {"historic_district", "infrastructure_landmark"}:
        return True
    return False


def _is_history_anchor(poi: POI) -> bool:
    raw_tags = dict(getattr(poi, "raw_tag_summary_json", {}) or {})
    name = str(getattr(poi, "canonical_name", "") or "").casefold()
    normalized_subcategory = str(getattr(poi, "normalized_subcategory", "") or "")
    display_categories = list(getattr(poi, "display_categories", []) or [])

    if (
        "history" not in display_categories
        and getattr(poi, "normalized_category", None) != "history"
    ):
        return False
    if name in {
        "palace of the governors",
        "the santa fe plaza",
        "santa fe plaza",
        "de vargas street house",
    }:
        return True
    if (
        name == "san miguel"
        and normalized_subcategory == "ritual_religious_site"
        and raw_tags.get("historic") in {"building", "church"}
    ):
        return True
    return False


def _is_rule_only_rail_trace(poi: POI) -> bool:
    normalized_subcategory = str(getattr(poi, "normalized_subcategory", "") or "")
    if normalized_subcategory not in {"infrastructure_landmark", "trail_river_access"}:
        return False
    if _is_rail_anchor(poi):
        return False

    rail_membership = next(
        (
            membership
            for membership in getattr(poi, "theme_memberships", []) or []
            if getattr(membership, "theme_slug", None) == "rail"
        ),
        None,
    )
    if rail_membership is None:
        return False
    if getattr(rail_membership, "assignment_basis", None) != "rule":
        return False
    return len(getattr(rail_membership, "evidence_links", []) or []) == 0
