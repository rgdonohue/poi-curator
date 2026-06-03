#!/usr/bin/env python3
"""Export the Detour startup POI CSV by flattening seed and context fields."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable
from pathlib import Path

INPUT_CSV = Path("reports/query_capable_pois_frontend_seed_described_v1.csv")
CONTEXT_CSV = Path("reports/query_capable_pois_frontend_seed_context_v1.csv")
OUTPUT_CSV_V2 = Path("reports/query_capable_pois_merged_v2.csv")
MANIFEST_JSON = Path("reports/query_capable_pois_merged_v2_merge_manifest.json")
LINEAGE_CSV = Path("reports/osm_relation_lineage.csv")
AUDIT_COLUMNS = ["merged_from", "merge_reason"]

ALLOWED_CATEGORIES = {"history", "art", "scenic", "culture", "civic"}
UNUSABLE_NAMES = {"", "?", "unknown", "unnamed", "n/a", "none", "null"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
MARKET_EXPORT_MIN_QUALITY = 80.0
CONFIDENCE_PROMOTION_BASIS = {
    "historic_building_status",
    "museum_layer",
    "place_of_worship_layer",
    "plaza_boundary",
    "public_art_layer",
    "railyard_boundary",
    "state_register",
    "nrhp",
}

DETOUR_REQUIRED_COLUMNS = [
    "poi_id",
    "dedupe_key",
    "name",
    "lon",
    "lat",
    "primary_category",
    "display_priority",
    "quality_score",
    "walk_affinity_hint",
    "drive_affinity_hint",
    "wikipedia_title",
    "short_description",
    "description_map_v1",
    "description_card_v1",
    "description_subcategory_v1",
    "description_confidence_v1",
    "description_basis_v1",
    "address",
]

DETOUR_OPTIONAL_COLUMNS = [
    "evidence_sources",
    "preferred_aliases",
    "active_themes",
]

GOVERNANCE_COLUMNS = [
    "record_origin",
    "source_basis",
    "evidence_strength",
    "description_status",
    "description_method",
    "description_review_status",
    "claim_basis",
    "risk_flags",
]

FIELDNAMES = DETOUR_REQUIRED_COLUMNS + DETOUR_OPTIONAL_COLUMNS + GOVERNANCE_COLUMNS
FIELDNAMES_V2 = FIELDNAMES + AUDIT_COLUMNS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build reports/query_capable_pois_merged_v1.csv for Detour.",
    )
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--context", type=Path, default=CONTEXT_CSV)
    return parser.parse_args()


def main() -> int:
    from poi_curator_editorial.feature_canonicalization import canonicalize

    args = parse_args()
    seed_rows = read_csv(args.input)
    contexts = load_contexts(args.context)
    rows = build_export_rows(seed_rows, contexts)

    parent_of, members_of, stamped_count = load_relation_lineage(LINEAGE_CSV)
    warn_if_lineage_stale(LINEAGE_CSV, args.input, stamped_count, len(seed_rows))
    attach_lineage_columns(rows, parent_of, members_of)

    merged_rows, manifest = canonicalize(rows)

    write_csv(OUTPUT_CSV_V2, merged_rows, fieldnames=FIELDNAMES_V2)
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    validate_rows(merged_rows)

    summary = manifest["summary"]
    print(f"wrote {OUTPUT_CSV_V2}")
    print(f"wrote {MANIFEST_JSON}")
    print(
        "rows_before={rows_before} rows_after={rows_after} "
        "clusters_collapsed={clusters_collapsed} "
        "clusters_left_colocated={clusters_left_colocated} "
        "review_candidates={review_candidates}".format(**summary)
    )
    return 0


def load_relation_lineage(path: Path) -> tuple[dict[str, str], dict[str, str], int]:
    """Return (member_dedupe_key -> parent_relation_dedupe_key,
    relation_dedupe_key -> piped member dedupe_keys, stamped_source_row_count)."""
    parent_of: dict[str, str] = {}
    members_of: dict[str, str] = {}
    stamped_count = -1
    if not path.exists():
        return parent_of, members_of, stamped_count
    with path.open(newline="", encoding="utf-8") as handle:
        first = handle.readline()
        if first.startswith("#"):
            for field in first.lstrip("#").split():
                if field.startswith("source_current_rows="):
                    try:
                        stamped_count = int(field.split("=", 1)[1])
                    except ValueError:
                        stamped_count = -1
        else:
            handle.seek(0)
        for row in csv.DictReader(handle):
            relation_key = f"osm:{row['relation_record_id']}"
            member_keys = [
                f"osm:{member}" for member in row["member_record_ids"].split("|") if member
            ]
            members_of[relation_key] = "|".join(member_keys)
            for member_key in member_keys:
                parent_of[member_key] = relation_key
    return parent_of, members_of, stamped_count


def warn_if_lineage_stale(
    lineage_path: Path, seed_path: Path, stamped_count: int, seed_row_count: int
) -> None:
    if not lineage_path.exists():
        print(f"WARNING: lineage artifact {lineage_path} missing; no relation merges applied")
        return
    # Best-effort heuristic: mtimes reflect checkout order, can false-positive after git ops.
    if seed_path.exists() and lineage_path.stat().st_mtime < seed_path.stat().st_mtime:
        print(
            f"WARNING: lineage artifact {lineage_path} is older than seed {seed_path}; "
            "re-run scripts/extract_osm_relation_lineage.py"
        )
    if 0 <= stamped_count and abs(stamped_count - seed_row_count) > seed_row_count:
        print(
            f"WARNING: lineage source_current_rows={stamped_count} differs sharply from "
            f"seed rows={seed_row_count}; lineage may be stale"
        )


def attach_lineage_columns(
    rows: list[dict[str, str]],
    parent_of: dict[str, str],
    members_of: dict[str, str],
) -> None:
    for row in rows:
        key = row["dedupe_key"]
        row["parent_relation_id"] = parent_of.get(key, "")
        row["osm_member_refs"] = members_of.get(key, "")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return [
            {key: value if value is not None else "" for key, value in row.items()}
            for row in csv.DictReader(csv_file)
        ]


def load_contexts(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}

    contexts: dict[str, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            poi_id = clean(row.get("poi_id", ""))
            if not poi_id:
                continue
            contexts[poi_id] = {
                "normalized_subcategory": clean(row.get("normalized_subcategory", "")),
                "raw_tags": parse_tags(row.get("raw_tags_json", "")),
                "evidence_sources": clean(row.get("evidence_sources", "")),
                "preferred_aliases": clean(row.get("preferred_aliases", "")),
                "active_themes": clean(row.get("active_themes", "")),
            }
    return contexts


def parse_tags(value: str) -> dict[str, str]:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) for key, item in parsed.items() if item is not None}


def build_export_rows(
    seed_rows: Iterable[dict[str, str]],
    contexts: dict[str, dict[str, object]],
) -> list[dict[str, str]]:
    best_by_dedupe_key: dict[str, dict[str, str]] = {}
    for source_row in seed_rows:
        category = export_category(source_row)
        name = clean(source_row.get("name", ""))
        if (
            not category
            or name.casefold() in UNUSABLE_NAMES
            or is_synthetic_row(source_row)
        ):
            continue

        row = build_export_row(
            source_row,
            contexts.get(clean(source_row.get("poi_id", "")), {}),
            category,
        )
        dedupe_key = row["dedupe_key"] or row["poi_id"]
        current = best_by_dedupe_key.get(dedupe_key)
        if current is None or row_quality(row) > row_quality(current):
            best_by_dedupe_key[dedupe_key] = row

    return sorted(
        best_by_dedupe_key.values(),
        key=lambda row: (
            -row_quality(row),
            row["primary_category"],
            row["name"].casefold(),
            row["poi_id"],
        ),
    )


def build_export_row(
    source_row: dict[str, str],
    context: dict[str, object],
    primary_category: str,
) -> dict[str, str]:
    tags = context.get("raw_tags", {})
    if not isinstance(tags, dict):
        tags = {}

    active_themes = merge_pipe_values(
        source_row.get("themes", ""),
        source_row.get("description_themes_v1", ""),
        str(context.get("active_themes", "")),
    )
    description_subcategory = first_non_empty(
        source_row.get("description_subcategory_v1", ""),
        str(context.get("normalized_subcategory", "")),
    )
    evidence_sources = str(context.get("evidence_sources", ""))

    poi_id = clean(source_row.get("poi_id", ""))
    dedupe_key = clean(source_row.get("dedupe_key", "")) or poi_id

    export_row = {
        "poi_id": poi_id,
        "dedupe_key": dedupe_key,
        "name": clean(source_row.get("name", "")),
        "lon": clean(source_row.get("lon", "")),
        "lat": clean(source_row.get("lat", "")),
        "primary_category": primary_category,
        "display_priority": integer_or_default(source_row.get("display_priority", ""), 50),
        "quality_score": float_or_default(source_row.get("quality_score", ""), 50.0),
        "walk_affinity_hint": float_or_default(source_row.get("walk_affinity_hint", ""), 0.5),
        "drive_affinity_hint": float_or_default(source_row.get("drive_affinity_hint", ""), 0.5),
        "wikipedia_title": clean(source_row.get("wikipedia_title", "")),
        "short_description": clean(source_row.get("short_description", "")),
        "description_map_v1": clean(source_row.get("description_map_v1", "")),
        "description_card_v1": clean(source_row.get("description_card_v1", "")),
        "description_subcategory_v1": clean(description_subcategory),
        "description_confidence_v1": export_confidence(source_row),
        "description_basis_v1": clean(source_row.get("description_basis_v1", "")),
        "address": address_from_tags(tags),
        "evidence_sources": clean(evidence_sources),
        "preferred_aliases": clean(str(context.get("preferred_aliases", ""))),
        "active_themes": active_themes,
        "record_origin": clean(source_row.get("record_origin", "")),
        "source_basis": clean(source_row.get("source_basis", "")),
        "evidence_strength": clean(source_row.get("evidence_strength", "")),
        "description_status": clean(source_row.get("description_status", "")),
        "description_method": clean(source_row.get("description_method", "")),
        "description_review_status": clean(source_row.get("description_review_status", "")),
        "claim_basis": clean(source_row.get("claim_basis", "")),
        "risk_flags": clean(source_row.get("risk_flags", "")),
    }
    apply_market_description_overrides(export_row, tags)
    return export_row


def address_from_tags(tags: dict[str, str]) -> str:
    street = clean(tags.get("addr:street", ""))
    house_number = clean(tags.get("addr:housenumber", ""))
    if house_number and street:
        return f"{house_number} {street}"
    return street


def apply_market_description_overrides(row: dict[str, str], tags: dict[str, str]) -> None:
    if row["description_subcategory_v1"] != "market_food_identity":
        return
    if row["primary_category"] != "culture":
        return
    if "railyard_boundary" not in set(split_pipe(row["description_basis_v1"])):
        return

    address_clause = f" at {row['address']}" if row["address"] else ""
    row["description_map_v1"] = (
        f"A marketplace in Santa Fe's Railyard corridor{address_clause}, useful for reading "
        "local trade, art, food systems, and public life."
    )

    if row["name"] == "Santa Fe Farmers Market":
        row["description_card_v1"] = (
            f"{row['name']} is a marketplace in Santa Fe's Railyard corridor{address_clause}. "
            "The source record lists Saturday morning hours year-round, with additional seasonal "
            "market days. It is useful for reading local food systems, regional trade, and public "
            "life around the Railyard."
        )
        return

    if row["name"] == "Santa Fe Artists Market":
        row["description_card_v1"] = (
            f"{row['name']} is a marketplace in Santa Fe's Railyard corridor{address_clause}. "
            "The source record identifies local juried artists working across pottery, jewelry, "
            "painting, photography, sculpture, furniture, textiles, and other fine art and craft. "
            "It is useful for reading the Railyard as a public arts and market district."
        )
        return

    description = clean(tags.get("description", ""))
    if description:
        row["description_card_v1"] = (
            f"{row['name']} is a marketplace in Santa Fe's Railyard corridor{address_clause}. "
            f"The source record describes it as {description.rstrip('.')}. "
            "It is useful for reading local trade and public life around the Railyard."
        )


def export_category(row: dict[str, str]) -> str:
    category = clean(row.get("primary_category", ""))
    if category in ALLOWED_CATEGORIES:
        return category
    if category != "food":
        return ""

    display_categories = set(split_pipe(row.get("display_categories", "")))
    basis = set(split_pipe(row.get("description_basis_v1", "")))
    subcategory = clean(row.get("description_subcategory_v1", ""))
    if (
        subcategory == "market_food_identity"
        and "culture" in display_categories
        and "railyard_boundary" in basis
        and row_quality(row) >= MARKET_EXPORT_MIN_QUALITY
    ):
        return "culture"
    return ""


def export_confidence(row: dict[str, str]) -> str:
    confidence = confidence_or_default(row.get("description_confidence_v1", ""))
    basis = set(split_pipe(row.get("description_basis_v1", "")))
    if confidence == "low" and basis & CONFIDENCE_PROMOTION_BASIS:
        return "medium"
    return confidence


def is_synthetic_row(row: dict[str, str]) -> bool:
    if clean(row.get("record_origin", "")).casefold() == "test_fixture":
        return True
    if clean(row.get("primary_source", "")).casefold() == "test":
        return True
    if clean(row.get("source_basis", "")).casefold() == "test":
        return True
    if clean(row.get("city", "")).casefold().startswith("test-"):
        return True
    if clean(row.get("region", "")).casefold().startswith("test-"):
        return True
    return clean(row.get("dedupe_key", "")).casefold().startswith("name_city:editorial-test-")


def merge_pipe_values(*values: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in split_pipe(value):
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return "|".join(merged)


def split_pipe(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split("|")) if item]


def first_non_empty(*values: str) -> str:
    for value in values:
        cleaned = clean(value)
        if cleaned:
            return cleaned
    return ""


def confidence_or_default(value: str) -> str:
    cleaned = clean(value).casefold()
    return cleaned if cleaned in CONFIDENCE_VALUES else "low"


def integer_or_default(value: str, default: int) -> str:
    try:
        return str(int(float(str(value).strip())))
    except ValueError:
        return str(default)


def float_or_default(value: str, default: float) -> str:
    try:
        return f"{float(str(value).strip()):g}"
    except ValueError:
        return f"{default:g}"


def row_quality(row: dict[str, str]) -> float:
    try:
        return float(row.get("quality_score", ""))
    except ValueError:
        return 0.0


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def write_csv(
    path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file, fieldnames=fieldnames or FIELDNAMES, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("export has no rows")

    seen_dedupe_keys: set[str] = set()
    for index, row in enumerate(rows, start=2):
        missing = [field for field in FIELDNAMES if row.get(field) is None]
        if missing:
            raise ValueError(f"line {index}: missing columns: {', '.join(missing)}")
        for required_field in ["poi_id", "dedupe_key", "name", "lon", "lat"]:
            if not row[required_field].strip():
                raise ValueError(f"line {index}: {required_field} is required")
        if row["primary_category"] not in ALLOWED_CATEGORIES:
            raise ValueError(f"line {index}: invalid category {row['primary_category']!r}")
        if row["name"].casefold() in UNUSABLE_NAMES:
            raise ValueError(f"line {index}: unusable name {row['name']!r}")
        if row["description_confidence_v1"] not in CONFIDENCE_VALUES:
            raise ValueError(
                f"line {index}: invalid confidence {row['description_confidence_v1']!r}",
            )
        for numeric_field in [
            "lon",
            "lat",
            "quality_score",
            "walk_affinity_hint",
            "drive_affinity_hint",
        ]:
            float(row[numeric_field])
        int(row["display_priority"])

        dedupe_key = row["dedupe_key"] or row["poi_id"]
        if dedupe_key in seen_dedupe_keys:
            raise ValueError(f"line {index}: duplicate dedupe_key {dedupe_key!r}")
        seen_dedupe_keys.add(dedupe_key)


if __name__ == "__main__":
    raise SystemExit(main())
