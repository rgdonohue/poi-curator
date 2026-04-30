#!/usr/bin/env python3
"""Validate governance fields for frontend seed exports."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ALLOWED_RECORD_ORIGINS = {"database", "fixture_overlay", "manual_export", "test_fixture"}
ALLOWED_EVIDENCE_STRENGTHS = {"high", "medium", "low", "unknown"}
ALLOWED_DESCRIPTION_STATUSES = {
    "none",
    "source",
    "generated_draft",
    "editorial_approved",
}
ALLOWED_DESCRIPTION_METHODS = {
    "source_import",
    "deterministic_draft",
    "model_draft",
    "model_draft_batch",
    "editorial",
}
ALLOWED_DESCRIPTION_REVIEW_STATUSES = {
    "unreviewed",
    "needs_revision",
    "approved",
    "rejected",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate governance fields on a frontend seed CSV export.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/query_capable_pois_frontend_seed_described_v1.csv"),
        help="CSV export to validate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_csv(args.input)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"ok {args.input}")
    return 0


def validate_csv(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    return validate_rows(rows)


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    required_columns = {
        "record_origin",
        "source_basis",
        "evidence_strength",
        "description_status",
        "description_method",
        "description_review_status",
        "claim_basis",
        "risk_flags",
    }
    if not rows:
        return ["csv contains no rows"]

    missing_columns = sorted(required_columns - set(rows[0].keys()))
    if missing_columns:
        return [f"missing required columns: {', '.join(missing_columns)}"]

    for index, row in enumerate(rows, start=2):
        origin = row["record_origin"].strip()
        source_basis = row["source_basis"].strip()
        evidence_strength = row["evidence_strength"].strip()
        description_status = row["description_status"].strip()
        description_method = row["description_method"].strip()
        description_review_status = row["description_review_status"].strip()
        claim_basis = row["claim_basis"].strip()
        risk_flags = {
            part for part in (item.strip() for item in row["risk_flags"].split("|")) if part
        }

        if origin not in ALLOWED_RECORD_ORIGINS:
            errors.append(f"line {index}: invalid record_origin={origin!r}")
        if not source_basis:
            errors.append(f"line {index}: source_basis is required")
        if evidence_strength not in ALLOWED_EVIDENCE_STRENGTHS:
            errors.append(f"line {index}: invalid evidence_strength={evidence_strength!r}")
        if description_status not in ALLOWED_DESCRIPTION_STATUSES:
            errors.append(f"line {index}: invalid description_status={description_status!r}")
        if description_method not in ALLOWED_DESCRIPTION_METHODS:
            errors.append(f"line {index}: invalid description_method={description_method!r}")
        if description_review_status not in ALLOWED_DESCRIPTION_REVIEW_STATUSES:
            errors.append(
                f"line {index}: invalid description_review_status={description_review_status!r}"
            )
        if description_status == "generated_draft" and not claim_basis:
            errors.append(f"line {index}: generated_draft row is missing claim_basis")
        if origin == "fixture_overlay" and "synthetic_fixture" not in risk_flags:
            errors.append(
                f"line {index}: fixture_overlay row must include synthetic_fixture risk flag"
            )
        if description_status == "editorial_approved" and description_review_status != "approved":
            errors.append(
                f"line {index}: editorial_approved rows must have "
                "description_review_status=approved"
            )

    return errors


if __name__ == "__main__":
    sys.exit(main())
