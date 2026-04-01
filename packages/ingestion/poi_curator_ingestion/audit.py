import csv
from pathlib import Path

import orjson
from poi_curator_domain.regions import RegionSpec

from poi_curator_ingestion.normalize import (
    NormalizationAuditRecord,
    normalize_osm_element_with_audit,
)


def build_audit_records(
    elements: list[dict],
    region: RegionSpec,
) -> list[NormalizationAuditRecord]:
    return [
        normalize_osm_element_with_audit(element, region)[1]
        for element in elements
    ]


def write_audit_records(path: Path, records: list[NormalizationAuditRecord]) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        write_audit_csv(path, records)
        return
    write_audit_json(path, records)


def write_audit_json(path: Path, records: list[NormalizationAuditRecord]) -> None:
    payload = [
        {
            "source_record_id": record.source_record_id,
            "name": record.name,
            "status": record.status,
            "matched_rule_id": record.matched_rule_id,
            "internal_type": record.internal_type,
            "public_category": record.public_category,
            "display_categories": record.display_categories,
            "key_tags": record.key_tags,
            "matched_rule_tags": record.matched_rule_tags,
        }
        for record in records
    ]
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))


def write_audit_csv(path: Path, records: list[NormalizationAuditRecord]) -> None:
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "source_record_id",
                "name",
                "status",
                "matched_rule_id",
                "internal_type",
                "public_category",
                "display_categories",
                "key_tags",
                "matched_rule_tags",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "source_record_id": record.source_record_id,
                    "name": record.name,
                    "status": record.status,
                    "matched_rule_id": record.matched_rule_id,
                    "internal_type": record.internal_type,
                    "public_category": record.public_category,
                    "display_categories": "|".join(record.display_categories),
                    "key_tags": orjson.dumps(record.key_tags).decode("utf-8"),
                    "matched_rule_tags": orjson.dumps(record.matched_rule_tags).decode("utf-8"),
                }
            )
