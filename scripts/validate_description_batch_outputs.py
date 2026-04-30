#!/usr/bin/env python3
"""Validate extractor, writer, and critic JSONL outputs before review merge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate description batch JSONL outputs.",
    )
    parser.add_argument("--kind", choices=["extractor", "writer", "critic"], required=True)
    parser.add_argument("--input", type=Path, required=True, help="JSONL output file to validate.")
    parser.add_argument(
        "--expected-record-ids",
        type=Path,
        default=None,
        help="Optional CSV or JSONL file used to verify record_id coverage.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_jsonl(args.input)
    expected_ids = load_expected_ids(args.expected_record_ids) if args.expected_record_ids else None

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        record_id = str(row.get("record_id") or "")
        if not record_id:
            errors.append(f"line {index}: missing record_id")
            continue
        if record_id in seen_ids:
            errors.append(f"line {index}: duplicate record_id {record_id}")
        seen_ids.add(record_id)
        errors.extend(validate_row(args.kind, row, index))

    if expected_ids is not None:
        missing = sorted(expected_ids - seen_ids)
        unexpected = sorted(seen_ids - expected_ids)
        if missing:
            errors.append(
                f"missing record_ids: {', '.join(missing[:10])}"
                + (" ..." if len(missing) > 10 else "")
            )
        if unexpected:
            errors.append(
                f"unexpected record_ids: {', '.join(unexpected[:10])}"
                + (" ..." if len(unexpected) > 10 else "")
            )

    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    print(f"validated={len(rows)} kind={args.kind}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def load_expected_ids(path: Path) -> set[str]:
    if path.suffix.lower() == ".csv":
        import csv

        with path.open(newline="", encoding="utf-8") as csv_file:
            return {row["record_id"] for row in csv.DictReader(csv_file)}
    return {str(row.get("record_id") or "") for row in load_jsonl(path) if row.get("record_id")}


def validate_row(kind: str, row: dict[str, Any], line_number: int) -> list[str]:
    if kind == "extractor":
        return validate_extractor(row, line_number)
    if kind == "writer":
        return validate_writer(row, line_number)
    return validate_critic(row, line_number)


def validate_extractor(row: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    errors.extend(require_list(row, line_number, "supported_facts"))
    errors.extend(require_list(row, line_number, "geographic_context"))
    errors.extend(require_list(row, line_number, "historical_context"))
    errors.extend(require_list(row, line_number, "cultural_context"))
    errors.extend(require_list(row, line_number, "hard_constraints"))
    errors.extend(require_list(row, line_number, "missing_information"))
    errors.extend(require_confidence(row, line_number))
    errors.extend(require_list(row, line_number, "risk_flags"))
    return errors


def validate_writer(row: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    errors.extend(require_string(row, line_number, "description_map"))
    errors.extend(require_string(row, line_number, "description_card"))
    errors.extend(require_list(row, line_number, "factual_basis"))
    errors.extend(require_list(row, line_number, "claims_avoided"))
    errors.extend(require_confidence(row, line_number))
    errors.extend(require_list(row, line_number, "risk_flags"))

    description_map = str(row.get("description_map") or "").strip()
    description_card = str(row.get("description_card") or "").strip()
    map_words = count_words(description_map)
    card_words = count_words(description_card)
    if description_map and not 18 <= map_words <= 30:
        errors.append(f"line {line_number}: description_map should be 18-30 words, got {map_words}")
    if description_card and not 35 <= card_words <= 65:
        errors.append(
            f"line {line_number}: description_card should be 35-65 words, got {card_words}"
        )
    return errors


def validate_critic(row: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    errors.extend(require_string(row, line_number, "verdict"))
    errors.extend(require_list(row, line_number, "issues"))
    errors.extend(require_list(row, line_number, "suggested_rewrite_notes"))
    errors.extend(require_confidence(row, line_number))
    verdict = str(row.get("verdict") or "").strip().lower()
    if verdict and verdict not in {"accept", "review", "reject", "blocked"}:
        errors.append(f"line {line_number}: invalid verdict {verdict}")
    return errors


def require_string(row: dict[str, Any], line_number: int, key: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, str):
        return [f"line {line_number}: {key} must be a string"]
    if not value.strip():
        return [f"line {line_number}: {key} must be non-empty"]
    return []


def require_list(row: dict[str, Any], line_number: int, key: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, list):
        return [f"line {line_number}: {key} must be a list"]
    if any(not isinstance(item, str) for item in value):
        return [f"line {line_number}: {key} must contain only strings"]
    return []


def require_confidence(row: dict[str, Any], line_number: int) -> list[str]:
    value = row.get("confidence")
    if not isinstance(value, str) or value.strip().lower() not in {"low", "medium", "high"}:
        return [f"line {line_number}: confidence must be one of low, medium, high"]
    return []


def count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


if __name__ == "__main__":
    main()
