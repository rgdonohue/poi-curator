#!/usr/bin/env python3
"""Build evidence packets and prompt payloads for POI description enrichment."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATEGORY_DESCRIPTIONS = {
    "history": "Places that reveal settlement, memory, and historical change.",
    "culture": "Places that express living identity, ritual, corridor life, and community meaning.",
    "art": "Murals, public art, and creative places with strong local voice.",
    "scenic": "Landscape features, overlooks, and visually legible terrain.",
    "food": "Identity-bearing food places only. Generic commerce should be down-ranked.",
    "civic": "Plazas, rail yards, irrigation works, and other civic or infrastructural traces.",
    "mixed": "Blend categories to see the strongest meaningful places regardless of type.",
}

THEME_DESCRIPTIONS = {
    "water": (
        "Places that reveal acequia infrastructure, canal traces, water corridors, "
        "and the civic landscape shaped by water."
    ),
    "rail": "Places that reveal rail infrastructure, labor, circulation, and adaptive reuse.",
    "public_memory": (
        "Places where public commemoration, civic-historic framing, and staged memory "
        "are legible in the landscape."
    ),
}

GENERIC_DESCRIPTION_TEMPLATES = {
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

EXTRACTOR_SYSTEM_PROMPT = """You extract only grounded facts from a POI evidence packet.

Rules:
- Use only the evidence packet.
- Do not infer unstated dates, events, people, communities, or significance claims.
- Separate hard facts from softer contextual cues.
- Prefer omission over speculation.

Return strict JSON with keys:
- supported_facts
- geographic_context
- historical_context
- cultural_context
- hard_constraints
- missing_information
- confidence
- risk_flags
"""

WRITER_SYSTEM_PROMPT = """You write historically truthful, culturally-geographic POI descriptions.

Rules:
- Use only facts and cues present in the evidence packet.
- If extracted facts are provided, treat them as the preferred factual basis.
- Prefer concrete spatial and historical readings over tourism copy.
- Do not invent dates, people, events, community claims, or causal stories.
- Avoid words such as iconic, charming, vibrant, must-see, hidden gem, picturesque.
- If the evidence is thin, say less and stay specific.
- Be careful with Indigenous, Hispano, colonial, religious, and memorial topics:
  avoid flattening or romanticizing.

Return strict JSON with keys:
- description_map
- description_card
- factual_basis
- claims_avoided
- confidence
- risk_flags
"""

CRITIC_SYSTEM_PROMPT = """You audit a POI description draft for historical truthfulness and
cultural-geographic discipline.

Rules:
- Reject unsupported factual claims.
- Flag romanticized, boosterish, or flattening language.
- Flag missing geographic specificity when the evidence packet supports it.
- Prefer cautious wording to speculative narrative.

Return strict JSON with keys:
- verdict
- issues
- suggested_rewrite_notes
- confidence
"""


@dataclass(frozen=True)
class SeedRecord:
    record_origin: str
    display_priority: int
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
    is_active: bool
    short_description: str
    base_significance_score: float | None
    quality_score: float | None
    walk_affinity_hint: float | None
    drive_affinity_hint: float | None
    historical_flag: bool | None
    cultural_flag: bool | None
    scenic_flag: bool | None
    infrastructure_flag: bool | None
    food_identity_flag: bool | None
    lon: float | None
    lat: float | None
    merge_note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build evidence packets and prompt payloads for POI description enrichment.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/query_capable_pois_frontend_seed.csv"),
        help="Frontend seed CSV to transform.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/description_enrichment/frontend_seed_v1"),
        help="Output directory for evidence packets and prompts.",
    )
    parser.add_argument(
        "--pilot-size",
        type=int,
        default=20,
        help="How many high-priority rows to include in the pilot selection.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_seed_records(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    evidence_packets = [build_evidence_packet(row) for row in rows]
    pilot_packets = select_pilot_packets(evidence_packets, args.pilot_size)
    pilot_ids = {packet["record_id"] for packet in pilot_packets}

    write_jsonl(args.output_dir / "evidence_packets.jsonl", evidence_packets)
    write_jsonl(args.output_dir / "pilot_evidence_packets.jsonl", pilot_packets)
    write_jsonl(
        args.output_dir / "extractor_tasks.jsonl",
        [build_extractor_task(packet) for packet in evidence_packets],
    )
    write_jsonl(
        args.output_dir / "pilot_extractor_tasks.jsonl",
        [
            build_extractor_task(packet)
            for packet in evidence_packets
            if packet["record_id"] in pilot_ids
        ],
    )
    write_jsonl(
        args.output_dir / "writer_tasks.jsonl",
        [build_writer_task(packet) for packet in evidence_packets],
    )
    write_jsonl(
        args.output_dir / "pilot_writer_tasks.jsonl",
        [
            build_writer_task(packet)
            for packet in evidence_packets
            if packet["record_id"] in pilot_ids
        ],
    )
    write_jsonl(
        args.output_dir / "critic_tasks.jsonl",
        [build_critic_task(packet) for packet in evidence_packets],
    )
    write_jsonl(
        args.output_dir / "pilot_critic_tasks.jsonl",
        [
            build_critic_task(packet)
            for packet in evidence_packets
            if packet["record_id"] in pilot_ids
        ],
    )
    write_csv(
        args.output_dir / "pilot_selection.csv",
        [flatten_packet(packet) for packet in pilot_packets],
    )
    write_json(
        args.output_dir / "schemas" / "extractor_output_template.json", extractor_output_template()
    )
    write_json(
        args.output_dir / "schemas" / "writer_output_template.json", writer_output_template()
    )
    write_json(
        args.output_dir / "schemas" / "critic_output_template.json", critic_output_template()
    )
    write_jsonl(
        args.output_dir / "starter_extractor_results.jsonl",
        [extractor_output_template(record_id=packet["record_id"]) for packet in pilot_packets],
    )
    write_jsonl(
        args.output_dir / "starter_writer_results.jsonl",
        [writer_output_template(record_id=packet["record_id"]) for packet in pilot_packets],
    )
    write_jsonl(
        args.output_dir / "starter_critic_results.jsonl",
        [critic_output_template(record_id=packet["record_id"]) for packet in pilot_packets],
    )
    write_summary(args.output_dir / "README.md", evidence_packets, args.pilot_size)

    print(args.output_dir)
    print(f"records={len(evidence_packets)}")
    print(f"pilot_records={min(args.pilot_size, len(evidence_packets))}")


def load_seed_records(path: Path) -> list[SeedRecord]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        return [parse_seed_row(row) for row in reader]


def parse_seed_row(row: dict[str, str]) -> SeedRecord:
    return SeedRecord(
        record_origin=row.get("record_origin", ""),
        display_priority=parse_int(row.get("display_priority")),
        dedupe_key=row.get("dedupe_key", ""),
        poi_id=row.get("poi_id", ""),
        name=row.get("name", "").strip(),
        city=row.get("city", "").strip(),
        region=row.get("region", "").strip(),
        country=row.get("country", "").strip(),
        primary_source=row.get("primary_source", "").strip(),
        osm_id=row.get("osm_id", "").strip(),
        wikidata_id=row.get("wikidata_id", "").strip(),
        wikipedia_title=row.get("wikipedia_title", "").strip(),
        primary_category=row.get("primary_category", "").strip(),
        display_categories=split_pipe(row.get("display_categories", "")),
        themes=split_pipe(row.get("themes", "")),
        review_status=row.get("review_status", "").strip(),
        is_active=parse_bool(row.get("is_active")),
        short_description=row.get("short_description", "").strip(),
        base_significance_score=parse_optional_float(row.get("base_significance_score")),
        quality_score=parse_optional_float(row.get("quality_score")),
        walk_affinity_hint=parse_optional_float(row.get("walk_affinity_hint")),
        drive_affinity_hint=parse_optional_float(row.get("drive_affinity_hint")),
        historical_flag=parse_optional_bool(row.get("historical_flag")),
        cultural_flag=parse_optional_bool(row.get("cultural_flag")),
        scenic_flag=parse_optional_bool(row.get("scenic_flag")),
        infrastructure_flag=parse_optional_bool(row.get("infrastructure_flag")),
        food_identity_flag=parse_optional_bool(row.get("food_identity_flag")),
        lon=parse_optional_float(row.get("lon")),
        lat=parse_optional_float(row.get("lat")),
        merge_note=row.get("merge_note", "").strip(),
    )


def build_evidence_packet(row: SeedRecord) -> dict[str, Any]:
    archetype = infer_archetype(row)
    generic_description = row.short_description in GENERIC_DESCRIPTION_TEMPLATES
    factual_cues = build_factual_cues(row, archetype)
    risk_flags = build_risk_flags(row, generic_description)
    evidence_strength = estimate_evidence_strength(row, risk_flags)

    return {
        "record_id": row.poi_id or row.dedupe_key,
        "poi_id": row.poi_id,
        "name": row.name,
        "location": {
            "city": row.city,
            "region": row.region,
            "country": row.country,
            "coordinates": {
                "lon": row.lon,
                "lat": row.lat,
            },
        },
        "record_origin": row.record_origin,
        "display_priority": row.display_priority,
        "dedupe_key": row.dedupe_key,
        "primary_source": row.primary_source,
        "source_identifiers": {
            "osm_id": row.osm_id or None,
            "wikidata_id": row.wikidata_id or None,
            "wikipedia_title": row.wikipedia_title or None,
        },
        "classification": {
            "primary_category": row.primary_category,
            "display_categories": row.display_categories,
            "category_descriptions": {
                category: CATEGORY_DESCRIPTIONS.get(category, "")
                for category in row.display_categories
            },
            "themes": row.themes,
            "theme_descriptions": {
                theme: THEME_DESCRIPTIONS.get(theme, "") for theme in row.themes
            },
            "archetype": archetype,
        },
        "existing_copy": {
            "short_description": row.short_description or None,
            "is_generic_template": generic_description,
            "quality_score": row.quality_score,
        },
        "signals": {
            "review_status": row.review_status or None,
            "base_significance_score": row.base_significance_score,
            "walk_affinity_hint": row.walk_affinity_hint,
            "drive_affinity_hint": row.drive_affinity_hint,
            "historical_flag": row.historical_flag,
            "cultural_flag": row.cultural_flag,
            "scenic_flag": row.scenic_flag,
            "infrastructure_flag": row.infrastructure_flag,
            "food_identity_flag": row.food_identity_flag,
            "evidence_strength": evidence_strength,
        },
        "factual_cues": factual_cues,
        "writing_constraints": build_writing_constraints(row),
        "risk_flags": risk_flags,
        "merge_note": row.merge_note or None,
    }


def build_extractor_task(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": packet["record_id"],
        "pass_name": "extractor_v1",
        "system_prompt": EXTRACTOR_SYSTEM_PROMPT,
        "user_prompt": build_extractor_user_prompt(packet),
        "evidence_packet": packet,
    }


def extractor_output_template(record_id: str | None = None) -> dict[str, Any]:
    return {
        "record_id": record_id or "<record_id>",
        "supported_facts": [],
        "geographic_context": [],
        "historical_context": [],
        "cultural_context": [],
        "hard_constraints": [],
        "missing_information": [],
        "confidence": "",
        "risk_flags": [],
    }


def build_writer_task(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": packet["record_id"],
        "pass_name": "writer_v1",
        "system_prompt": WRITER_SYSTEM_PROMPT,
        "user_prompt": build_writer_user_prompt(packet),
        "evidence_packet": packet,
        "extracted_facts_placeholder": "{{extractor_output_json}}",
    }


def writer_output_template(record_id: str | None = None) -> dict[str, Any]:
    return {
        "record_id": record_id or "<record_id>",
        "description_map": "",
        "description_card": "",
        "factual_basis": [],
        "claims_avoided": [],
        "confidence": "",
        "risk_flags": [],
    }


def build_critic_task(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": packet["record_id"],
        "pass_name": "critic_v1",
        "system_prompt": CRITIC_SYSTEM_PROMPT,
        "user_prompt": build_critic_user_prompt(packet),
        "evidence_packet": packet,
        "draft_placeholder": "{{writer_output_json}}",
    }


def critic_output_template(record_id: str | None = None) -> dict[str, Any]:
    return {
        "record_id": record_id or "<record_id>",
        "verdict": "",
        "issues": [],
        "suggested_rewrite_notes": [],
        "confidence": "",
    }


def build_writer_user_prompt(packet: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Write two descriptions for this POI.",
            "",
            "Requirements:",
            "- `description_map`: 18 to 30 words.",
            "- `description_card`: 35 to 65 words.",
            (
                "- Use only supported facts and cues from the evidence packet "
                "and extracted facts JSON."
            ),
            "- Favor spatial, historical, and cultural-geographic specificity.",
            "- Avoid promotional language and unsupported claims.",
            "",
            "Extracted facts JSON:",
            "{{extractor_output_json}}",
            "",
            "Evidence packet JSON:",
            json.dumps(packet, ensure_ascii=True, indent=2, sort_keys=True),
        ]
    )


def build_extractor_user_prompt(packet: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Extract grounded facts from this POI evidence packet.",
            "",
            "Focus on:",
            "- identity facts",
            "- geographic context",
            "- historical or cultural context that is explicitly supported",
            "- hard constraints for a cautious writer",
            "",
            "Evidence packet JSON:",
            json.dumps(packet, ensure_ascii=True, indent=2, sort_keys=True),
        ]
    )


def build_critic_user_prompt(packet: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Audit the draft description JSON for this POI.",
            "",
            "Check for:",
            "- unsupported facts",
            "- romanticized or generic language",
            "- flattening of local histories or communities",
            "- missed geographic specificity supported by the evidence",
            "",
            "Extracted facts JSON:",
            "{{extractor_output_json}}",
            "",
            "Evidence packet JSON:",
            json.dumps(packet, ensure_ascii=True, indent=2, sort_keys=True),
            "",
            "Draft JSON to audit:",
            "{{writer_output_json}}",
        ]
    )


def build_factual_cues(row: SeedRecord, archetype: str) -> list[str]:
    cues: list[str] = []
    if row.city:
        cues.append(f"Located in {row.city}.")
    if row.region:
        cues.append(f"Region context: {row.region}.")
    if row.primary_category:
        cues.append(
            f"Primary category is {row.primary_category}: "
            f"{CATEGORY_DESCRIPTIONS.get(row.primary_category, '')}"
        )
    if row.themes:
        for theme in row.themes:
            description = THEME_DESCRIPTIONS.get(theme)
            if description:
                cues.append(f"Theme cue `{theme}`: {description}")
    if archetype != "general_poi":
        cues.append(f"Likely archetype: {archetype.replace('_', ' ')}.")
    if row.primary_source == "osm_overpass":
        cues.append(
            "Canonical record comes from OSM ingest and may still carry generic "
            "machine-generated text."
        )
    if row.wikidata_id:
        cues.append(
            "Has a Wikidata identifier, so identity claims can be checked against "
            "structured knowledge."
        )
    if row.wikipedia_title:
        cues.append("Has a Wikipedia title, which may support cautious summary context.")
    if row.record_origin == "fixture_overlay":
        cues.append("This row is a fixture overlay, not a database-native POI.")
    if row.merge_note:
        cues.append(row.merge_note)
    if row.historical_flag:
        cues.append("Historical signal flag is set.")
    if row.cultural_flag:
        cues.append("Cultural continuity signal flag is set.")
    if row.scenic_flag:
        cues.append("Scenic or terrain-read signal flag is set.")
    if row.infrastructure_flag:
        cues.append("Infrastructure signal flag is set.")
    if row.food_identity_flag:
        cues.append("Food identity signal flag is set.")
    return cues


def build_risk_flags(row: SeedRecord, generic_description: bool) -> list[str]:
    flags: list[str] = []
    if row.name in {"", "?"}:
        flags.append("name_missing_or_placeholder")
    if generic_description:
        flags.append("generic_existing_description")
    if row.review_status == "needs_review":
        flags.append("needs_editorial_review")
    if row.record_origin == "fixture_overlay":
        flags.append("fixture_overlay")
    if not row.wikidata_id and not row.wikipedia_title:
        flags.append("no_identity_enrichment")
    if row.primary_source == "osm_overpass":
        flags.append("osm_only_identity_risk")
    if row.primary_category in {"history", "culture", "civic"}:
        flags.append("historical_or_cultural_sensitivity")
    if "water" in row.themes or "rail" in row.themes:
        flags.append("theme_specific_claims_must_be_grounded")
    return flags


def build_writing_constraints(row: SeedRecord) -> list[str]:
    constraints = [
        "Do not invent dates, people, ownership histories, or named communities.",
        "Do not use tourism cliches or marketing language.",
        (
            "Prefer phrases like `reflects`, `suggests`, or `is associated with` "
            "when certainty is limited."
        ),
        "If the evidence is thin, keep the description short and concrete.",
    ]
    if row.primary_category == "history":
        constraints.append(
            "Treat historical claims conservatively unless explicit evidence supports them."
        )
    if row.primary_category == "culture":
        constraints.append(
            "Avoid speaking for a living community unless the evidence packet clearly "
            "supports the claim."
        )
    if row.primary_category == "civic":
        constraints.append(
            "Describe infrastructural and public-life functions clearly without "
            "overclaiming historical importance."
        )
    return constraints


def estimate_evidence_strength(row: SeedRecord, risk_flags: list[str]) -> str:
    score = 0
    if row.wikidata_id:
        score += 2
    if row.wikipedia_title:
        score += 1
    if row.base_significance_score is not None and row.base_significance_score >= 70:
        score += 1
    if row.quality_score is not None and row.quality_score >= 80:
        score += 1
    if row.record_origin == "database":
        score += 1
    score -= sum(
        1
        for flag in risk_flags
        if flag in {"name_missing_or_placeholder", "fixture_overlay", "osm_only_identity_risk"}
    )
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def infer_archetype(row: SeedRecord) -> str:
    name = row.name.casefold()
    theme_set = set(row.themes)
    if "water" in theme_set or any(
        token in name for token in ("acequia", "canal", "ditch", "river")
    ):
        return "water_corridor"
    if "rail" in theme_set or any(
        token in name for token in ("rail", "railyard", "depot", "station")
    ):
        return "rail_corridor"
    if any(
        token in name for token in ("church", "chapel", "mission", "catholic", "worship", "temple")
    ):
        return "ritual_religious_site"
    if any(token in name for token in ("plaza", "square")):
        return "civic_core"
    if any(token in name for token in ("district", "neighborhood", "neighbourhood", "barrio")):
        return "district_or_corridor"
    if any(token in name for token in ("overlook", "vista", "peak", "hill", "cross")):
        return "overlook_landscape"
    if row.primary_category == "art":
        return "art_site"
    if row.primary_category == "history":
        return "historic_site"
    if row.primary_category == "scenic":
        return "landscape_site"
    if row.primary_category == "civic":
        return "civic_infrastructure_site"
    return "general_poi"


def select_pilot_packets(
    packets: list[dict[str, Any]],
    pilot_size: int,
) -> list[dict[str, Any]]:
    def sort_key(packet: dict[str, Any]) -> tuple[int, float, str]:
        signals = packet["signals"]
        significance = signals.get("base_significance_score") or 0.0
        return (
            int(packet["display_priority"]),
            float(significance),
            str(packet["name"]).lower(),
        )

    return sorted(packets, key=sort_key, reverse=True)[:pilot_size]


def flatten_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": packet["record_id"],
        "name": packet["name"],
        "city": packet["location"]["city"],
        "record_origin": packet["record_origin"],
        "primary_category": packet["classification"]["primary_category"],
        "themes": "|".join(packet["classification"]["themes"]),
        "archetype": packet["classification"]["archetype"],
        "evidence_strength": packet["signals"]["evidence_strength"],
        "risk_flags": "|".join(packet["risk_flags"]),
        "short_description": packet["existing_copy"]["short_description"] or "",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            output_file.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_summary(path: Path, packets: list[dict[str, Any]], pilot_size: int) -> None:
    by_origin: dict[str, int] = {}
    by_strength: dict[str, int] = {}
    for packet in packets:
        by_origin[packet["record_origin"]] = by_origin.get(packet["record_origin"], 0) + 1
        strength = packet["signals"]["evidence_strength"]
        by_strength[strength] = by_strength.get(strength, 0) + 1

    lines = [
        "# Description Enrichment Batch",
        "",
        f"- Records: {len(packets)}",
        f"- Pilot selection size: {min(pilot_size, len(packets))}",
        f"- Origins: {json.dumps(by_origin, sort_keys=True)}",
        f"- Evidence strength counts: {json.dumps(by_strength, sort_keys=True)}",
        "",
        "Artifacts:",
        "- `evidence_packets.jsonl`: grounded evidence packet for each seed row",
        "- `pilot_evidence_packets.jsonl`: pilot-only evidence packets",
        "- `extractor_tasks.jsonl`: batch-ready fact extraction prompts",
        "- `pilot_extractor_tasks.jsonl`: pilot-only extractor prompts",
        "- `writer_tasks.jsonl`: batch-ready writer prompts",
        "- `pilot_writer_tasks.jsonl`: pilot-only writer prompts",
        "- `critic_tasks.jsonl`: batch-ready critic prompts with a writer output placeholder",
        "- `pilot_critic_tasks.jsonl`: pilot-only critic prompts",
        "- `pilot_selection.csv`: high-priority rows to review first",
        "- `schemas/*.json`: output templates for each pass",
        "- `starter_*_results.jsonl`: empty starter files keyed to the pilot rows",
        "",
        "Recommended pass order:",
        "1. Run extractor on the pilot selection first.",
        "2. Run writer using the extractor outputs.",
        "3. Run critic on the writer outputs.",
        "4. Review flagged rows manually before scaling to the full set.",
        "5. Only after the pilot looks good, run the full batch.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_pipe(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split("|")) if item]


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "t", "1", "yes"}


def parse_optional_bool(value: str | None) -> bool | None:
    stripped = (value or "").strip()
    if not stripped:
        return None
    return parse_bool(stripped)


def parse_optional_float(value: str | None) -> float | None:
    stripped = (value or "").strip()
    if not stripped:
        return None
    return float(stripped)


def parse_int(value: str | None) -> int:
    stripped = (value or "").strip()
    return int(stripped) if stripped else 0


if __name__ == "__main__":
    main()
