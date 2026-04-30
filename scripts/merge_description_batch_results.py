#!/usr/bin/env python3
"""Merge extractor, writer, and critic batch outputs into a review CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge description-enrichment batch outputs into a review CSV.",
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=Path("reports/description_enrichment/frontend_seed_v1"),
        help="Directory containing evidence packets and pilot selection.",
    )
    parser.add_argument(
        "--extractor-results",
        type=Path,
        required=True,
        help="JSONL file of extractor outputs keyed by record_id.",
    )
    parser.add_argument(
        "--writer-results",
        type=Path,
        required=True,
        help="JSONL file of writer outputs keyed by record_id.",
    )
    parser.add_argument(
        "--critic-results",
        type=Path,
        required=True,
        help="JSONL file of critic outputs keyed by record_id.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/description_enrichment/frontend_seed_v1/pilot_review.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--pilot-only",
        action="store_true",
        help="Restrict output to record_ids listed in pilot_selection.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evidence_packets = load_jsonl_by_record_id(args.batch_dir / "evidence_packets.jsonl")
    extractor_results = load_jsonl_by_record_id(args.extractor_results)
    writer_results = load_jsonl_by_record_id(args.writer_results)
    critic_results = load_jsonl_by_record_id(args.critic_results)

    allowed_ids: set[str] | None = None
    if args.pilot_only:
        allowed_ids = load_pilot_record_ids(args.batch_dir / "pilot_selection.csv")

    rows: list[dict[str, Any]] = []
    for record_id, packet in evidence_packets.items():
        if allowed_ids is not None and record_id not in allowed_ids:
            continue
        extractor = extractor_results.get(record_id, {})
        writer = writer_results.get(record_id, {})
        critic = critic_results.get(record_id, {})
        rows.append(
            build_review_row(
                record_id=record_id,
                packet=packet,
                extractor=extractor,
                writer=writer,
                critic=critic,
            )
        )

    rows.sort(key=lambda row: (row["record_origin"], row["name"].lower()))
    write_csv(args.output, rows)
    print(args.output)
    print(f"rows={len(rows)}")


def load_jsonl_by_record_id(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            record_id = str(payload.get("record_id") or payload.get("id") or "")
            if not record_id:
                continue
            records[record_id] = payload
    return records


def load_pilot_record_ids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return {row["record_id"] for row in csv.DictReader(csv_file)}


def build_review_row(
    *,
    record_id: str,
    packet: dict[str, Any],
    extractor: dict[str, Any],
    writer: dict[str, Any],
    critic: dict[str, Any],
) -> dict[str, Any]:
    location = packet.get("location", {})
    classification = packet.get("classification", {})
    signals = packet.get("signals", {})
    existing_copy = packet.get("existing_copy", {})

    description_map = string_or_json_value(writer.get("description_map"))
    description_card = string_or_json_value(writer.get("description_card"))
    critic_verdict = stringify(critic.get("verdict"))
    final_recommendation = ""
    if description_card and critic_verdict.lower() not in {"reject", "blocked"}:
        final_recommendation = description_card

    return {
        "record_id": record_id,
        "name": stringify(packet.get("name")),
        "city": stringify(location.get("city")),
        "region": stringify(location.get("region")),
        "record_origin": stringify(packet.get("record_origin")),
        "source_basis": stringify(packet.get("primary_source")),
        "primary_category": stringify(classification.get("primary_category")),
        "themes": pipe_join(classification.get("themes", [])),
        "archetype": stringify(classification.get("archetype")),
        "evidence_strength": stringify(signals.get("evidence_strength")),
        "risk_flags": pipe_join(packet.get("risk_flags", [])),
        "existing_short_description": stringify(existing_copy.get("short_description")),
        "extractor_supported_facts": json.dumps(
            extractor.get("supported_facts", []),
            ensure_ascii=True,
        ),
        "extractor_geographic_context": json.dumps(
            extractor.get("geographic_context", []),
            ensure_ascii=True,
        ),
        "extractor_historical_context": json.dumps(
            extractor.get("historical_context", []),
            ensure_ascii=True,
        ),
        "extractor_cultural_context": json.dumps(
            extractor.get("cultural_context", []),
            ensure_ascii=True,
        ),
        "extractor_hard_constraints": json.dumps(
            extractor.get("hard_constraints", []),
            ensure_ascii=True,
        ),
        "extractor_missing_information": json.dumps(
            extractor.get("missing_information", []),
            ensure_ascii=True,
        ),
        "extractor_confidence": stringify(extractor.get("confidence")),
        "writer_description_map": description_map,
        "writer_description_card": description_card,
        "writer_factual_basis": json.dumps(writer.get("factual_basis", []), ensure_ascii=True),
        "writer_claims_avoided": json.dumps(writer.get("claims_avoided", []), ensure_ascii=True),
        "writer_confidence": stringify(writer.get("confidence")),
        "writer_risk_flags": json.dumps(writer.get("risk_flags", []), ensure_ascii=True),
        "description_status": "generated_draft",
        "description_method": "model_draft_batch",
        "description_review_status": "unreviewed",
        "claim_basis": json.dumps(
            writer.get("factual_basis") or extractor.get("supported_facts", []),
            ensure_ascii=True,
        ),
        "critic_verdict": critic_verdict,
        "critic_issues": json.dumps(critic.get("issues", []), ensure_ascii=True),
        "critic_suggested_rewrite_notes": json.dumps(
            critic.get("suggested_rewrite_notes", []),
            ensure_ascii=True,
        ),
        "critic_confidence": stringify(critic.get("confidence")),
        "final_recommended_description": final_recommendation,
        "editorial_status": "",
        "editorial_notes": "",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pipe_join(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return "|".join(str(value) for value in values if value is not None and str(value))


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def string_or_json_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


if __name__ == "__main__":
    main()
