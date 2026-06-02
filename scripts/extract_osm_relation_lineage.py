#!/usr/bin/env python3
"""Extract OSM relation->member lineage from poi_source_raw into a committed CSV.

Run once when the corpus is (re)ingested. Output feeds the export-time
same-feature canonicalization, which stays pure-CSV.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUTPUT_CSV = Path("reports/osm_relation_lineage.csv")
OSM_SOURCE_NAME = "osm_overpass"
LINEAGE_FIELDNAMES = ["relation_record_id", "member_record_ids"]


def relation_lineage_from_elements(
    elements: list[dict[str, Any]],
) -> list[tuple[str, list[str]]]:
    lineage: list[tuple[str, list[str]]] = []
    for element in elements:
        if element.get("type") != "relation":
            continue
        members = element.get("members") or []
        member_ids = [
            f"{member['type']}/{member['ref']}"
            for member in members
            if member.get("type") and member.get("ref") is not None
        ]
        if not member_ids:
            continue
        lineage.append((f"relation/{element['id']}", member_ids))
    lineage.sort(key=lambda item: item[0])
    return lineage


def write_lineage_csv(
    path: Path, lineage: list[tuple[str, list[str]]], *, source_row_count: int
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(
            f"# extracted_at={stamp} source=poi_source_raw "
            f"source_current_rows={source_row_count}\n"
        )
        writer = csv.writer(handle)
        writer.writerow(LINEAGE_FIELDNAMES)
        for relation_id, member_ids in lineage:
            writer.writerow([relation_id, "|".join(member_ids)])


def main() -> int:
    from poi_curator_domain.db import POISourceRaw, get_session_factory
    from sqlalchemy import select

    session_factory = get_session_factory()
    with session_factory() as session:
        rows = list(
            session.scalars(
                select(POISourceRaw).where(
                    POISourceRaw.source_name == OSM_SOURCE_NAME,
                    POISourceRaw.is_current.is_(True),
                )
            )
        )
        elements = [row.raw_payload_json for row in rows]
    lineage = relation_lineage_from_elements(elements)
    write_lineage_csv(OUTPUT_CSV, lineage, source_row_count=len(elements))
    print(f"wrote {OUTPUT_CSV}")
    print(f"relations_with_members={len(lineage)} source_current_rows={len(elements)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
