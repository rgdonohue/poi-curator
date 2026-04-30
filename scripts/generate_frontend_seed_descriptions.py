#!/usr/bin/env python3
"""Generate grounded frontend descriptions for the merged POI seed CSV."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

INPUT_CSV = Path("reports/query_capable_pois_frontend_seed.csv")
CONTEXT_CSV = Path("reports/query_capable_pois_frontend_seed_context_v1.csv")
OUTPUT_CSV = Path("reports/query_capable_pois_frontend_seed_described_v1.csv")
SUMMARY_MD = Path("reports/query_capable_pois_frontend_seed_described_v1.md")

GENERIC_TEMPLATES = {
    "Historic site with strong local landscape context.",
    "Historic district that helps explain settlement patterns and continuity.",
    "Museum or interpretive site with clear historical context.",
    "Monument or memorial with strong public memory value.",
    "Public artwork that reads as part of the local cultural landscape.",
    "Art space with strong corridor-level cultural identity.",
    "Cultural venue that signals local performance and public life.",
    "Neighborhood corridor that expresses local identity at street level.",
    "Viewpoint with a strong terrain and settlement read.",
    "Landscape access point with ecological or scenic value.",
    "Civic space that helps explain the structure of public life.",
    "Infrastructure trace that reveals labor, circulation, or water systems.",
    "Identity-bearing market or food place with local distinctiveness.",
    "Ritual or religious site with strong cultural continuity.",
    "Landscape feature with clear scenic or ecological legibility.",
    "No editorial description yet.",
}


@dataclass(frozen=True)
class SeedRow:
    record_origin: str
    display_priority: str
    dedupe_key: str
    poi_id: str
    name: str
    city: str
    region: str
    country: str
    primary_source: str
    osm_id: str
    wikidata_id: str
    wikipedia_title: str
    primary_category: str
    display_categories: list[str]
    themes: list[str]
    review_status: str
    is_active: str
    short_description: str
    base_significance_score: str
    quality_score: str
    walk_affinity_hint: str
    drive_affinity_hint: str
    historical_flag: str
    cultural_flag: str
    scenic_flag: str
    infrastructure_flag: str
    food_identity_flag: str
    lon: str
    lat: str
    merge_note: str


def main() -> None:
    seed_rows = load_seed_rows(INPUT_CSV)
    db_rows = [row for row in seed_rows if row.record_origin == "database"]
    poi_by_id = load_poi_contexts(CONTEXT_CSV, {row.poi_id for row in db_rows})

    output_rows: list[dict[str, str]] = []
    confidence_counts: dict[str, int] = {}
    for row in seed_rows:
        poi = poi_by_id.get(row.poi_id)
        draft = build_description_draft(row, poi)
        confidence_counts[draft["description_confidence_v1"]] = (
            confidence_counts.get(draft["description_confidence_v1"], 0) + 1
        )
        output_rows.append({**row_to_dict(row), **draft})

    write_csv(OUTPUT_CSV, output_rows)
    write_summary(SUMMARY_MD, output_rows, confidence_counts)
    print(OUTPUT_CSV)
    print(f"rows={len(output_rows)}")


def load_seed_rows(path: Path) -> list[SeedRow]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return [
            SeedRow(
                record_origin=row["record_origin"],
                display_priority=row["display_priority"],
                dedupe_key=row["dedupe_key"],
                poi_id=row["poi_id"],
                name=row["name"],
                city=row["city"],
                region=row["region"],
                country=row["country"],
                primary_source=row["primary_source"],
                osm_id=row["osm_id"],
                wikidata_id=row["wikidata_id"],
                wikipedia_title=row["wikipedia_title"],
                primary_category=row["primary_category"],
                display_categories=split_pipe(row["display_categories"]),
                themes=split_pipe(row["themes"]),
                review_status=row["review_status"],
                is_active=row["is_active"],
                short_description=row["short_description"],
                base_significance_score=row["base_significance_score"],
                quality_score=row["quality_score"],
                walk_affinity_hint=row["walk_affinity_hint"],
                drive_affinity_hint=row["drive_affinity_hint"],
                historical_flag=row["historical_flag"],
                cultural_flag=row["cultural_flag"],
                scenic_flag=row["scenic_flag"],
                infrastructure_flag=row["infrastructure_flag"],
                food_identity_flag=row["food_identity_flag"],
                lon=row["lon"],
                lat=row["lat"],
                merge_note=row["merge_note"],
            )
            for row in csv.DictReader(csv_file)
        ]


def load_poi_contexts(path: Path, poi_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not poi_ids or not path.exists():
        return {}
    contexts: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            poi_id = row["poi_id"]
            if poi_id not in poi_ids:
                continue
            contexts[poi_id] = {
                "normalized_subcategory": row.get("normalized_subcategory", ""),
                "raw_tags": json.loads(row["raw_tags_json"]) if row.get("raw_tags_json") else {},
                "evidence_sources": set(split_pipe(row.get("evidence_sources", ""))),
                "evidence_labels": parse_evidence_label_pairs(row.get("evidence_label_pairs", "")),
                "preferred_aliases": split_pipe(row.get("preferred_aliases", "")),
                "active_themes": set(split_pipe(row.get("active_themes", ""))),
            }
    return contexts


def build_description_draft(row: SeedRow, poi: dict[str, Any] | None) -> dict[str, str]:
    current_tags = latest_tags(poi)
    evidence_sources = source_ids(poi)
    evidence_labels = labels_by_source(poi)
    active_themes = sorted(set(row.themes) | query_active_themes(poi))
    subcategory = (
        poi.get("normalized_subcategory") if poi is not None else infer_overlay_subcategory(row)
    )
    type_phrase = infer_type_phrase(row.name, subcategory, current_tags)
    context_phrase = infer_context_phrase(row, evidence_sources, active_themes, current_tags)
    evidence_phrase = infer_evidence_phrase(row, evidence_sources, evidence_labels)
    specific_phrase = infer_specific_phrase(row, poi, current_tags)
    reading_phrase = infer_reading_phrase(row, subcategory, active_themes, current_tags)
    map_description = build_map_description(
        type_phrase=type_phrase,
        city=row.city,
        context_phrase=context_phrase,
        evidence_phrase=evidence_phrase,
        reading_phrase=reading_phrase,
    )
    card_description = build_card_description(
        type_phrase=type_phrase,
        city=row.city,
        context_phrase=context_phrase,
        evidence_phrase=evidence_phrase,
        specific_phrase=specific_phrase,
        reading_phrase=reading_phrase,
        row=row,
    )
    confidence = infer_confidence(row, evidence_sources, current_tags, specific_phrase)
    basis = description_basis(evidence_sources, active_themes, current_tags, specific_phrase, row)
    claim_basis = basis or "category_fallback"
    source_basis = build_source_basis(row, evidence_sources)
    evidence_strength = infer_evidence_strength(
        row,
        evidence_sources,
        current_tags,
        specific_phrase,
    )
    risk_flags = build_description_risk_flags(
        row,
        confidence=confidence,
        evidence_strength=evidence_strength,
        claim_basis=claim_basis,
    )
    return {
        "description_map_v1": map_description,
        "description_card_v1": card_description,
        "frontend_description_v1": card_description,
        "description_confidence_v1": confidence,
        "description_basis_v1": basis,
        "description_themes_v1": "|".join(active_themes),
        "description_subcategory_v1": subcategory,
        "description_method_v1": "deterministic_evidence_weighted_v1",
        "source_basis": source_basis,
        "evidence_strength": evidence_strength,
        "description_status": "generated_draft",
        "description_method": "deterministic_draft",
        "description_review_status": "unreviewed",
        "claim_basis": claim_basis,
        "risk_flags": "|".join(risk_flags),
    }


def latest_tags(poi: dict[str, Any] | None) -> dict[str, str]:
    if poi is None:
        return {}
    return {
        str(key): str(value)
        for key, value in (poi.get("raw_tags") or {}).items()
        if value is not None
    }


def source_ids(poi: dict[str, Any] | None) -> set[str]:
    if poi is None:
        return set()
    return set(poi.get("evidence_sources", set()))


def labels_by_source(poi: dict[str, Any] | None) -> dict[str, list[str]]:
    if poi is None:
        return {}
    return dict(poi.get("evidence_labels", {}))


def query_active_themes(poi: dict[str, Any] | None) -> set[str]:
    if poi is None:
        return set()
    return set(poi.get("active_themes", set()))


def infer_overlay_subcategory(row: SeedRow) -> str:
    name = row.name.casefold()
    if "plaza" in name:
        return "civic_space_plaza"
    if row.primary_category == "art":
        return "gallery_art_space"
    if row.primary_category == "history":
        return "historic_site"
    if row.primary_category == "culture":
        if "corridor" in name or "district" in name or "road" in name:
            return "neighborhood_corridor"
        return "performance_cultural_venue"
    if row.primary_category == "scenic":
        return "overlook_vista"
    if row.primary_category == "civic":
        return "infrastructure_landmark" if "rail" in name else "civic_space_plaza"
    return "historic_site"


def infer_type_phrase(name: str, subcategory: str, tags: dict[str, str]) -> str:
    lowered = name.casefold()
    tourism = tags.get("tourism", "")
    building = tags.get("building", "")
    amenity = tags.get("amenity", "")
    historic = tags.get("historic", "")
    man_made = tags.get("man_made", "")
    leisure = tags.get("leisure", "")
    natural = tags.get("natural", "")
    artwork_type = tags.get("artwork_type", "")
    place = tags.get("place", "")
    highway = tags.get("highway", "")

    if tourism == "gallery":
        return "gallery" if "gallery" in lowered else "gallery or art space"
    if tourism == "museum":
        if building in {"chapel", "church"} or any(
            token in lowered for token in ("chapel", "church", "mission", "cathedral")
        ):
            return "chapel building now interpreted as a museum"
        if historic == "castle" and tags.get("castle_type") == "palace":
            return "historic palace museum"
        if tags.get("museum") == "history":
            return "history museum"
        if tags.get("museum") == "art":
            return "art museum or exhibition venue"
        return "museum"
    if tourism == "artwork":
        if artwork_type == "mural":
            return "mural"
        if artwork_type == "statue":
            return "public statue"
        return "public artwork"
    if tourism == "viewpoint" or subcategory == "overlook_vista":
        return "viewpoint" if "hill" not in lowered else "hilltop viewpoint"
    if amenity == "theatre":
        if "cinema" in lowered:
            return "cinema and performance venue"
        return "performance venue"
    if amenity == "marketplace":
        return "marketplace"
    if amenity == "place_of_worship":
        if building in {"chapel", "church"}:
            return "church or chapel"
        return "place of worship"
    if leisure == "park":
        return "park"
    if natural == "peak":
        return "mountain peak"
    if place == "neighbourhood":
        return "residential neighborhood"
    if highway == "pedestrian" and "alley" in lowered:
        return "pedestrian alley"
    if man_made == "cross":
        return "cross landmark"
    if man_made == "tower":
        return "tower landmark"
    if man_made == "bridge":
        return "bridge crossing"

    if subcategory == "historic_site":
        if "house" in lowered:
            return "historic house"
        if any(token in lowered for token in ("chapel", "church", "mission", "cathedral")):
            return "historic chapel or church"
        if "fort" in lowered:
            return "fort site"
        if "bridge" in lowered:
            return "historic bridge"
        if "trail" in lowered:
            return "historic trail corridor"
        if "school" in lowered:
            return "historic school building"
        if "avenue" in lowered or "street" in lowered or "road" in lowered:
            return "historic street trace"
        if "ruins" in lowered:
            return "ruin site"
        return "historic site"
    if subcategory == "museum":
        return "house museum" if "house" in lowered else "museum"
    if subcategory == "monument_memorial":
        return "monument or memorial"
    if subcategory == "gallery_art_space":
        return "gallery or art space"
    if subcategory == "mural_public_art":
        return "public artwork"
    if subcategory == "performance_cultural_venue":
        return "performance or cultural venue"
    if subcategory == "ritual_religious_site":
        if any(token in lowered for token in ("chapel", "church", "mission", "cathedral")):
            return "religious site"
        return "place of worship"
    if subcategory == "neighborhood_corridor":
        return "neighborhood corridor"
    if subcategory == "civic_space_plaza":
        return "plaza and civic core"
    if subcategory == "infrastructure_landmark":
        if "bridge" in lowered:
            return "bridge and circulation trace"
        if any(token in lowered for token in ("acequia", "canal", "ditch")) or "waterway" in tags:
            return "water infrastructure trace"
        if any(token in lowered for token in ("rail", "railyard", "depot", "station")):
            return "rail infrastructure trace"
        return "civic infrastructure trace"
    if subcategory == "market_food_identity":
        return "identity-bearing market"
    if subcategory == "trail_river_access":
        return "park and landscape access point" if "park" in lowered else "landscape access point"
    if subcategory == "landscape_feature":
        return "landscape feature"
    if subcategory == "overlook_vista":
        return "overlook"
    return "place"


def infer_context_phrase(
    row: SeedRow,
    evidence_sources: set[str],
    active_themes: list[str],
    tags: dict[str, str],
) -> str:
    city = humanize_slug(row.city)
    street = clean_tag_text(tags.get("addr:street"))
    if "city_gis_plaza_park" in evidence_sources:
        return f"at {city}'s Plaza civic core"
    if "city_gis_railyard_boundary" in evidence_sources:
        return f"in the Railyard corridor in {city}"
    if street and row.city == "santa-fe" and "city_gis_historic_districts" in evidence_sources:
        return f"on {street} within Santa Fe's mapped historic district fabric"
    if street and row.city == "santa-fe":
        return f"on {street} in Santa Fe"
    if street:
        return f"on {street} in {city}"
    if "city_gis_plaza_park" in evidence_sources:
        return f"at {city}'s Plaza civic core"
    if "water" in active_themes:
        return f"along a water-shaped civic corridor in {city}"
    if "rail" in active_themes:
        return f"within a rail-marked corridor in {city}"
    if "city_gis_historic_districts" in evidence_sources:
        if row.city == "santa-fe":
            return "within Santa Fe's mapped historic district fabric"
        return f"within a mapped historic district in {city}"
    return f"in {city}"


def infer_evidence_phrase(
    row: SeedRow,
    evidence_sources: set[str],
    evidence_labels: dict[str, list[str]],
) -> str:
    if row.record_origin == "fixture_overlay":
        return "This draft is grounded in the curated fixture record rather than a database POI."
    if {"nrhp_listed_properties", "nm_hpd_register_workbook"} <= evidence_sources:
        return "State and national register records both support its historic standing."
    if "nrhp_listed_properties" in evidence_sources:
        return "National register records support its historic standing."
    if "nm_hpd_register_workbook" in evidence_sources:
        return "State register records support its historic standing."
    if "city_gis_historic_building_status" in evidence_sources:
        labels = "|".join(evidence_labels.get("city_gis_historic_building_status", []))
        if "Significant" in labels:
            return "City historic-building data marks it as significant."
        return "City historic-building data tracks it as part of the historic fabric."
    if "city_gis_historic_districts" in evidence_sources:
        return "City mapping places it within a historic district."
    if "city_gis_museums" in evidence_sources:
        return "City mapping also treats it as a museum."
    if "city_gis_place_of_worship" in evidence_sources:
        return "City mapping treats it as a place of worship."
    if "city_gis_public_art" in evidence_sources:
        return "City mapping treats it as public art."
    if "city_gis_plaza_park" in evidence_sources:
        return "City mapping places it inside Plaza Park."
    if "city_gis_railyard_boundary" in evidence_sources:
        return "City mapping places it inside the Railyard boundary."
    return ""


def infer_specific_phrase(row: SeedRow, poi: dict[str, Any] | None, tags: dict[str, str]) -> str:
    if row.record_origin == "fixture_overlay":
        fixture_phrase = infer_fixture_overlay_phrase(row)
        if fixture_phrase:
            return fixture_phrase
        return ""
    if poi is not None:
        preferred_alias = next(iter(poi.get("preferred_aliases", [])), None)
        if preferred_alias and preferred_alias.casefold() != row.name.casefold():
            return f"It is also widely identified as {preferred_alias}."
    description = clean_tag_text(tags.get("description"))
    if description:
        return f"The current source description notes that it is {description}."
    if tags.get("historic") == "memorial":
        memorial_year = clean_tag_text(tags.get("year_of_construction") or tags.get("start_date"))
        if memorial_year:
            return f"The source record dates the memorial to {memorial_year}."
        return "The source record identifies it specifically as a memorial."
    if tags.get("historic") == "house":
        return "The source record identifies it specifically as a historic house."
    if tags.get("tourism") == "museum" and tags.get("building") in {"chapel", "church"}:
        return "Current tags describe a church or chapel building now visited as a museum."
    if tags.get("tourism") == "museum" and tags.get("museum") == "history":
        return "Current tags classify it specifically as a history museum."
    if tags.get("tourism") == "museum" and tags.get("museum") == "art":
        return "Current tags classify it as an art museum or exhibition venue."
    if tags.get("historic") == "castle" and tags.get("castle_type") == "palace":
        return "Current tags describe a palace-form historic building."
    if tags.get("artwork_type") == "mural":
        return "The source record identifies the work as a mural."
    if tags.get("artwork_type") == "statue":
        return "The source record identifies the work as a statue."
    if tags.get("man_made") == "cross":
        material = clean_tag_text(tags.get("material"))
        if material:
            return f"The source record identifies a {material} cross landmark."
        return "The source record identifies a cross landmark."
    if tags.get("man_made") == "tower":
        tower_type = clean_tag_text(tags.get("tower:type"))
        if tower_type:
            return f"The source record identifies a tower used as a {tower_type}."
        return "The source record identifies a tower landmark."
    if tags.get("man_made") == "bridge":
        return "The source record identifies a bridge crossing."
    if tags.get("amenity") == "theatre" or "cinema" in row.name.casefold():
        return "The current record treats it as a theater or cinema venue."
    if tags.get("amenity") == "marketplace":
        return "The current record treats it as a marketplace rather than a single shop."
    if tags.get("place") == "neighbourhood":
        return "The current record treats it as a named neighborhood rather than a single building."
    if tags.get("natural") == "peak":
        return "The current record identifies it as a named peak."
    if tags.get("leisure") == "park":
        return "The current record treats it as a park or open-space resource."
    if tags.get("highway") == "pedestrian":
        return "The current record maps it as a pedestrian passage."
    old_name = clean_tag_text(tags.get("old_name"))
    if old_name:
        return f"The current source record preserves the older name {old_name}."
    if tags.get("artist_name") and row.primary_category == "art":
        return f"The source record credits the work to {tags['artist_name']}."
    if tags.get("was:industrial"):
        return (
            "The source record also points to earlier industrial use as a "
            f"{tags['was:industrial']}."
        )
    return ""


def infer_reading_phrase(
    row: SeedRow,
    subcategory: str,
    active_themes: list[str],
    tags: dict[str, str],
) -> str:
    name = row.name.casefold()
    if tags.get("tourism") == "gallery":
        if clean_tag_text(tags.get("addr:street")) == "Canyon Road":
            return "the gallery corridor that gives Canyon Road its cumulative cultural density"
        return "the commercial and cultural density created by clustered gallery space"
    if tags.get("tourism") == "museum":
        if tags.get("building") in {"chapel", "church"}:
            return "how sacred architecture gets re-read through preservation and visitation"
        return "how domestic, civic, or interpretive history has been staged for public reading"
    if tags.get("amenity") == "theatre" or "cinema" in name:
        return "performance, film culture, and public life at street level"
    if tags.get("leisure") == "park":
        return "everyday open space, terrain, and neighborhood use on the ground"
    if tags.get("natural") == "peak" or tags.get("tourism") == "viewpoint":
        return "topography, basin settlement, and long views across the city"
    if tags.get("place") == "neighbourhood":
        return "residential settlement pattern and neighborhood-scale identity"
    if tags.get("historic") == "memorial" or subcategory == "monument_memorial":
        return "public memory and commemorative framing in the landscape"
    if tags.get("man_made") in {"tower", "cross"}:
        return "vantage, circulation, and symbolic marking in the built landscape"
    if tags.get("highway") == "pedestrian":
        return "how small passages and pedestrian shortcuts structure downtown movement"
    if "water" in active_themes:
        return "how water management shaped movement, settlement, and civic space"
    if "rail" in active_themes:
        return "labor, circulation, and later adaptive reuse in the rail landscape"
    if subcategory == "historic_site":
        if "house" in name:
            return "domestic architecture and older settlement patterns"
        if any(token in name for token in ("chapel", "church", "mission", "cathedral")):
            return "religious presence within the older built landscape"
        if "fort" in name:
            return "military vantage and territorial framing"
        if "bridge" in name:
            return "how circulation and drainage crossings were built into the city"
        if "trail" in name:
            return "regional movement and route-making rather than a single isolated monument"
        if "school" in name:
            return "institutional change and adaptive reuse in the urban fabric"
        return "older civic and settlement layers in the built environment"
    if subcategory == "museum":
        return "how domestic, civic, or interpretive history has been staged for public reading"
    if subcategory == "monument_memorial":
        return "public memory and commemorative framing in the landscape"
    if subcategory == "gallery_art_space":
        return "the cumulative gallery fabric that gives the street its cultural density"
    if subcategory == "mural_public_art":
        return "how visual culture enters the everyday civic landscape"
    if subcategory == "performance_cultural_venue":
        return "public life and cultural activity at street level"
    if subcategory == "ritual_religious_site":
        return "religious presence in the local built landscape"
    if subcategory == "neighborhood_corridor":
        return "settlement pattern, street sequence, and district-scale identity"
    if subcategory == "civic_space_plaza":
        return "public life, ceremony, and the urban structure of the city center"
    if subcategory == "infrastructure_landmark":
        if "bridge" in name:
            return "movement, crossing, and the physical shaping of circulation"
        return "the infrastructural systems that organized movement and public space"
    if subcategory == "market_food_identity":
        return "local trade and public life rather than generic retail"
    if subcategory == "trail_river_access":
        return "terrain, drainage, and everyday open space on the ground"
    if subcategory == "landscape_feature":
        return "terrain and ecological legibility rather than destination hype"
    if subcategory == "overlook_vista":
        return "topography, urban form, and historical framing in one view"
    return "the place as part of a broader cultural-geographic landscape"


def build_map_description(
    *,
    type_phrase: str,
    city: str,
    context_phrase: str,
    evidence_phrase: str,
    reading_phrase: str,
) -> str:
    evidence_clause = shorten_evidence_for_map(evidence_phrase)
    if (
        "historic district" in context_phrase
        and evidence_clause == "within a mapped historic district"
    ):
        evidence_clause = ""
    if "Railyard" in context_phrase and evidence_clause == "inside the Railyard boundary":
        evidence_clause = ""
    if "Plaza" in context_phrase and evidence_clause == "inside Plaza Park":
        evidence_clause = ""
    parts = [
        f"{indefinite_article(type_phrase).capitalize()} {type_phrase} {context_phrase}",
        evidence_clause,
        f"useful for reading {reading_phrase}",
    ]
    text = join_clauses(parts)
    return finalize_sentence(text)


def build_card_description(
    *,
    type_phrase: str,
    city: str,
    context_phrase: str,
    evidence_phrase: str,
    specific_phrase: str,
    reading_phrase: str,
    row: SeedRow,
) -> str:
    city_label = humanize_slug(city)
    opening = f"{indefinite_article(type_phrase).capitalize()} {type_phrase} {context_phrase}."
    body = f"It is most useful for reading {reading_phrase}."
    parts = [opening, evidence_phrase, specific_phrase, body]
    text = " ".join(part for part in parts if part).strip()
    if count_words(text) < 35:
        text = " ".join(
            part
            for part in [
                text,
                (
                    "The point here is less a generic stop than a grounded way "
                    f"to read {city_label}'s landscape."
                ),
            ]
            if part
        )
    return finalize_sentence(text)


def shorten_evidence_for_map(evidence_phrase: str) -> str:
    if not evidence_phrase:
        return ""
    replacements = {
        "This draft is grounded in the curated fixture record rather than a database POI.": "",
        "State and national register records both support its historic standing.": (
            "with state and national register support"
        ),
        "National register records support its historic standing.": (
            "with national register support"
        ),
        "State register records support its historic standing.": "with state register support",
        "City mapping places it within a historic district.": "within a mapped historic district",
        "City mapping places it inside Plaza Park.": "inside Plaza Park",
        "City mapping places it inside the Railyard boundary.": "inside the Railyard boundary",
        "City mapping also treats it as a museum.": "also mapped as a museum",
        "City mapping treats it as a place of worship.": "also mapped as a place of worship",
        "City mapping treats it as public art.": "also mapped as public art",
        "City historic-building data marks it as significant.": (
            "with city historic-building support"
        ),
        "City historic-building data tracks it as part of the historic fabric.": (
            "with city historic-building support"
        ),
    }
    return replacements.get(evidence_phrase, evidence_phrase.rstrip("."))


def infer_confidence(
    row: SeedRow,
    evidence_sources: set[str],
    tags: dict[str, str],
    specific_phrase: str,
) -> str:
    score = 0
    if {"nrhp_listed_properties", "nm_hpd_register_workbook"} <= evidence_sources:
        score += 3
    elif evidence_sources & {"nrhp_listed_properties", "nm_hpd_register_workbook"}:
        score += 2
    elif evidence_sources:
        score += 1
    if row.wikidata_id or row.wikipedia_title:
        score += 1
    if specific_phrase:
        score += 1
    if tags.get("description") and clean_tag_text(tags.get("description")):
        score += 1
    if row.record_origin == "fixture_overlay":
        score -= 1
    if row.name in {"", "?"}:
        score -= 2
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def infer_evidence_strength(
    row: SeedRow,
    evidence_sources: set[str],
    tags: dict[str, str],
    specific_phrase: str,
) -> str:
    strength_score = 0
    if row.record_origin == "fixture_overlay":
        strength_score -= 1
    if {"nrhp_listed_properties", "nm_hpd_register_workbook"} <= evidence_sources:
        strength_score += 3
    elif evidence_sources & {"nrhp_listed_properties", "nm_hpd_register_workbook"}:
        strength_score += 2
    elif evidence_sources:
        strength_score += 1
    if row.wikidata_id or row.wikipedia_title:
        strength_score += 1
    if tags.get("description") or tags.get("old_name") or tags.get("artist_name"):
        strength_score += 1
    if specific_phrase:
        strength_score += 1
    if row.name in {"", "?"}:
        strength_score -= 2
    if strength_score >= 4:
        return "high"
    if strength_score >= 2:
        return "medium"
    return "low"


def description_basis(
    evidence_sources: set[str],
    active_themes: list[str],
    tags: dict[str, str],
    specific_phrase: str,
    row: SeedRow,
) -> str:
    basis: list[str] = []
    if row.record_origin == "fixture_overlay":
        basis.append("fixture_overlay")
    if "nrhp_listed_properties" in evidence_sources:
        basis.append("nrhp")
    if "nm_hpd_register_workbook" in evidence_sources:
        basis.append("state_register")
    if "city_gis_historic_districts" in evidence_sources:
        basis.append("historic_district")
    if "city_gis_historic_building_status" in evidence_sources:
        basis.append("historic_building_status")
    if "city_gis_museums" in evidence_sources:
        basis.append("museum_layer")
    if "city_gis_place_of_worship" in evidence_sources:
        basis.append("place_of_worship_layer")
    if "city_gis_public_art" in evidence_sources:
        basis.append("public_art_layer")
    if "city_gis_plaza_park" in evidence_sources:
        basis.append("plaza_boundary")
    if "city_gis_railyard_boundary" in evidence_sources:
        basis.append("railyard_boundary")
    if active_themes:
        basis.extend(f"theme:{theme}" for theme in active_themes)
    if tags.get("description"):
        basis.append("source_description_tag")
    if tags.get("old_name"):
        basis.append("source_old_name")
    if tags.get("artist_name"):
        basis.append("source_artist")
    if tags.get("was:industrial"):
        basis.append("source_former_use")
    if row.wikidata_id:
        basis.append("wikidata_id")
    if row.wikipedia_title:
        basis.append("wikipedia_title")
    if specific_phrase and not basis:
        basis.append("source_specific_text")
    return "|".join(dict.fromkeys(basis))


def build_source_basis(row: SeedRow, evidence_sources: set[str]) -> str:
    basis = [row.primary_source] if row.primary_source else []
    basis.extend(sorted(evidence_sources))
    if row.wikidata_id:
        basis.append("wikidata_id")
    if row.wikipedia_title:
        basis.append("wikipedia_title")
    return "|".join(dict.fromkeys(basis))


def build_description_risk_flags(
    row: SeedRow,
    *,
    confidence: str,
    evidence_strength: str,
    claim_basis: str,
) -> list[str]:
    flags: list[str] = []
    if row.record_origin == "fixture_overlay":
        flags.append("synthetic_fixture")
    if row.name in {"", "?"}:
        flags.append("missing_name")
    if confidence == "low":
        flags.append("low_confidence")
    if evidence_strength == "low":
        flags.append("low_evidence")
    if claim_basis == "category_fallback":
        flags.append("category_fallback")
    if row.primary_category in {"culture", "history", "civic"}:
        flags.append(f"{row.primary_category}_sensitivity")
    return flags


def clean_tag_text(value: str | None) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    if not text or text in GENERIC_TEMPLATES:
        return ""
    return text.rstrip(".")


def humanize_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", "-").split("-") if part)


def join_clauses(parts: list[str]) -> str:
    return ", ".join(part.strip().rstrip(".") for part in parts if part and part.strip())


def finalize_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" ,")
    if not cleaned.endswith("."):
        cleaned += "."
    return cleaned


def count_words(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def indefinite_article(phrase: str) -> str:
    return "an" if phrase[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def split_pipe(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split("|")) if item]


def parse_evidence_label_pairs(value: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in split_pipe(value):
        source_id, _, label = item.partition("::")
        if source_id and label:
            grouped.setdefault(source_id, []).append(label)
    return grouped


def infer_fixture_overlay_phrase(row: SeedRow) -> str:
    lowered = row.name.casefold()
    if "plaza" in lowered:
        return (
            "The fixture keeps the city's central plaza and long-running civic "
            "gathering ground in the frontend seed."
        )
    if "railyard" in lowered:
        return (
            "The fixture marks an arts-facing district tied to the former rail yard "
            "and its later reuse."
        )
    if "canyon road" in lowered:
        return "The fixture keeps Santa Fe's gallery corridor on Canyon Road in the seed set."
    if "acequia" in lowered:
        return (
            "The fixture preserves a point tied to the Acequia Madre landscape "
            "rather than dropping that corridor entirely."
        )
    if "cross of the martyrs" in lowered:
        return (
            "The fixture keeps a well-known overlook and commemorative landmark "
            "even though it is not yet matched as a canonical POI."
        )
    return ""


def row_to_dict(row: SeedRow) -> dict[str, str]:
    return {
        "record_origin": row.record_origin,
        "display_priority": row.display_priority,
        "dedupe_key": row.dedupe_key,
        "poi_id": row.poi_id,
        "name": row.name,
        "city": row.city,
        "region": row.region,
        "country": row.country,
        "primary_source": row.primary_source,
        "osm_id": row.osm_id,
        "wikidata_id": row.wikidata_id,
        "wikipedia_title": row.wikipedia_title,
        "primary_category": row.primary_category,
        "display_categories": "|".join(row.display_categories),
        "themes": "|".join(row.themes),
        "review_status": row.review_status,
        "is_active": row.is_active,
        "short_description": row.short_description,
        "base_significance_score": row.base_significance_score,
        "quality_score": row.quality_score,
        "walk_affinity_hint": row.walk_affinity_hint,
        "drive_affinity_hint": row.drive_affinity_hint,
        "historical_flag": row.historical_flag,
        "cultural_flag": row.cultural_flag,
        "scenic_flag": row.scenic_flag,
        "infrastructure_flag": row.infrastructure_flag,
        "food_identity_flag": row.food_identity_flag,
        "lon": row.lon,
        "lat": row.lat,
        "merge_note": row.merge_note,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    path: Path, rows: list[dict[str, str]], confidence_counts: dict[str, int]
) -> None:
    examples = rows[:8]
    by_origin: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        by_origin[row["record_origin"]] = by_origin.get(row["record_origin"], 0) + 1
        status = row["description_status"]
        by_status[status] = by_status.get(status, 0) + 1
    lines = [
        "# Frontend Descriptions V1",
        "",
        f"- Rows: {len(rows)}",
        f"- Confidence counts: {json.dumps(confidence_counts, sort_keys=True)}",
        f"- Record origins: {json.dumps(by_origin, sort_keys=True)}",
        f"- Description statuses: {json.dumps(by_status, sort_keys=True)}",
        "",
        (
            "This file is a deterministic evidence-weighted description pass for "
            "the merged frontend seed."
        ),
        (
            "It prefers register and city-GIS evidence when present, then specific "
            "source tags, then cautious category-level fallback language."
        ),
        "Every generated description here is a draft, not canonical POI copy.",
        "",
        "Example rows:",
    ]
    for row in examples:
        lines.extend(
            [
                f"## {row['name']}",
                f"- Origin: {row['record_origin']}",
                f"- Basis: {row['description_basis_v1']}",
                f"- Claim basis: {row['claim_basis']}",
                f"- Review status: {row['description_review_status']}",
                f"- Map: {row['description_map_v1']}",
                f"- Card: {row['description_card_v1']}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
