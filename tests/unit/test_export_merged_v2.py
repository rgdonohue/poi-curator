"""End-to-end test driving the real v2 export main() over a tiny temp seed.

Proves the Tudesque cluster (relation + two member ways + a proximate node)
collapses to one row, the solo church survives, and the merge manifest's
accounting matches the row delta. No DB and no real artifacts are touched:
module-level path constants are monkeypatched onto tmp_path.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import scripts.export_query_capable_pois_merged_v1 as exporter

# Header matches the columns the real build_export_row / export_category read
# via row.get(...). Extra columns are ignored by the script; the only column
# that must be present for a category to be allowed is primary_category
# ("history" is in ALLOWED_CATEGORIES). All other reads default cleanly.
SEED_HEADER = [
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
    "evidence_sources",
    "preferred_aliases",
    "active_themes",
    "record_origin",
    "source_basis",
    "evidence_strength",
    "description_status",
    "description_method",
    "description_review_status",
    "claim_basis",
    "risk_flags",
    "display_categories",
    "themes",
    "osm_id",
]


def _write_seed(path: Path) -> None:
    def row(**kw: str) -> dict[str, str]:
        base = {col: "" for col in SEED_HEADER}
        base.update(
            {
                "primary_category": "history",
                "display_priority": "50",
                "walk_affinity_hint": "0.55",
                "drive_affinity_hint": "0.9",
                "description_confidence_v1": "medium",
                "record_origin": "database",
            }
        )
        base.update(kw)
        return base

    rows = [
        row(
            poi_id="p-rel",
            dedupe_key="osm:relation/13422888",
            name="Tudesque House",
            lon="-105.93883405",
            lat="35.68407725",
            quality_score="80",
            claim_basis="historic_district",
        ),
        row(
            poi_id="p-e",
            dedupe_key="osm:way/461729209",
            name="Roque Tudesque House East",
            lon="-105.9387482642101",
            lat="35.684025653980406",
            quality_score="67.5",
            claim_basis="historic_district",
        ),
        row(
            poi_id="p-w",
            dedupe_key="osm:way/461729208",
            name="Roque Tudesque House West",
            lon="-105.93903457267577",
            lat="35.6841571533804",
            quality_score="67.5",
            claim_basis="historic_district",
        ),
        row(
            poi_id="p-node",
            dedupe_key="osm:node/6479254097",
            name="Roque Tudesque House",
            lon="-105.938944",
            lat="35.6841299",
            quality_score="62.5",
            claim_basis="state_register|historic_district",
        ),
        row(
            poi_id="solo",
            dedupe_key="osm:node/111",
            name="Cristo Rey Church",
            lon="-105.92",
            lat="35.69",
            quality_score="70",
            claim_basis="historic_district",
        ),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def _write_lineage(path: Path) -> None:
    path.write_text(
        "# extracted_at=2026-06-01T00:00:00Z source=poi_source_raw source_current_rows=5\n"
        "relation_record_id,member_record_ids\n"
        "relation/13422888,way/461729208|way/461729209\n",
        encoding="utf-8",
    )


def test_export_v2_collapses_tudesque(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = tmp_path / "seed.csv"
    context = tmp_path / "context.csv"  # absent -> empty contexts is fine
    lineage = tmp_path / "lineage.csv"
    out_v2 = tmp_path / "v2.csv"
    manifest = tmp_path / "manifest.json"
    _write_seed(seed)
    _write_lineage(lineage)

    monkeypatch.setattr(exporter, "LINEAGE_CSV", lineage)
    monkeypatch.setattr(exporter, "OUTPUT_CSV_V2", out_v2)
    monkeypatch.setattr(exporter, "MANIFEST_JSON", manifest)
    monkeypatch.setattr(
        "sys.argv", ["export", "--input", str(seed), "--context", str(context)]
    )

    assert exporter.main() == 0

    with out_v2.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        out_rows = list(reader)
        header = reader.fieldnames
    # v2 header is exactly v1 FIELDNAMES + the two audit columns; lineage helper
    # columns must NOT leak into the output.
    assert header == exporter.FIELDNAMES_V2
    assert header is not None
    assert "parent_relation_id" not in header
    assert "osm_member_refs" not in header

    names = {r["name"] for r in out_rows}
    # Tudesque collapses to 1 row (state-register display name) + the solo church = 2.
    assert len(out_rows) == 2
    assert "Roque Tudesque House" in names
    assert "Cristo Rey Church" in names

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["summary"]["clusters_collapsed"] == 1
    assert data["summary"]["rows_before"] - data["summary"]["rows_after"] == 3
    survivor = next(r for r in out_rows if r["name"] == "Roque Tudesque House")
    assert set(survivor["merged_from"].split("|")) == {
        "osm:way/461729208",
        "osm:way/461729209",
        "osm:node/6479254097",
    }
