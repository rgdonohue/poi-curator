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

import httpx

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
        relation_id = element.get("id")
        if relation_id is None:
            continue
        lineage.append((f"relation/{relation_id}", member_ids))
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


def relation_ids_from_raw(raw_payloads: list[dict[str, Any]]) -> list[int]:
    """Return sorted unique ids of payloads whose type is "relation"."""
    ids = {
        payload["id"]
        for payload in raw_payloads
        if payload.get("type") == "relation" and payload.get("id") is not None
    }
    return sorted(ids)


def fetch_relation_members(relation_ids: list[int]) -> list[dict[str, Any]]:
    """Fetch relations (with members) live from Overpass via ``out geom;``.

    The ingest corpus was queried with ``out ... center ...`` which drops the
    members list, so member lineage cannot come from ``poi_source_raw``. We read
    which relations exist from the DB and re-fetch their members here.
    """
    if not relation_ids:
        return []

    from poi_curator_domain.settings import get_settings

    settings = get_settings()
    ids = ",".join(map(str, relation_ids))
    query = f"[out:json][timeout:120];rel(id:{ids});out geom;"

    endpoints = [settings.overpass_url]
    if settings.overpass_fallback_url not in endpoints:
        endpoints.append(settings.overpass_fallback_url)

    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            with httpx.Client(
                timeout=max(120, settings.overpass_timeout_seconds)
            ) as client:
                response = client.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": "poi-curator/0.1.0"},
                )
                response.raise_for_status()
                payload = response.json()
            return list(payload.get("elements", []))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


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
        payloads = [row.raw_payload_json for row in rows]
    relation_ids = relation_ids_from_raw(payloads)
    elements = fetch_relation_members(relation_ids)
    lineage = relation_lineage_from_elements(elements)
    write_lineage_csv(OUTPUT_CSV, lineage, source_row_count=len(payloads))
    print(f"wrote {OUTPUT_CSV}")
    print(
        f"relations_queried={len(relation_ids)} "
        f"relations_with_members={len(lineage)} source_current_rows={len(payloads)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
