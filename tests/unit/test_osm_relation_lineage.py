from pathlib import Path
from typing import Any

import pytest

from scripts.extract_osm_relation_lineage import (
    LINEAGE_FIELDNAMES,
    relation_lineage_from_elements,
)


def test_relation_lineage_extracts_member_refs() -> None:
    elements = [
        {
            "type": "relation",
            "id": 13422888,
            "tags": {"name": "Tudesque House"},
            "members": [
                {"type": "way", "ref": 461729208, "role": "outer"},
                {"type": "way", "ref": 461729209, "role": "outer"},
            ],
        },
        {"type": "way", "id": 461729208, "tags": {}},
        {"type": "node", "id": 1, "tags": {}},
    ]
    lineage = relation_lineage_from_elements(elements)
    assert lineage == [("relation/13422888", ["way/461729208", "way/461729209"])]


def test_relation_without_members_is_skipped() -> None:
    elements = [{"type": "relation", "id": 7, "tags": {}, "members": []}]
    assert relation_lineage_from_elements(elements) == []


def test_lineage_fieldnames_shape() -> None:
    assert LINEAGE_FIELDNAMES == ["relation_record_id", "member_record_ids"]


def test_write_lineage_csv_byte_layout(tmp_path: Path) -> None:
    from scripts.extract_osm_relation_lineage import write_lineage_csv

    out = tmp_path / "lineage.csv"
    write_lineage_csv(
        out,
        [("relation/13422888", ["way/461729208", "way/461729209"])],
        source_row_count=42,
    )
    lines = out.read_text(encoding="utf-8").splitlines()
    # Line 1: provenance comment the export consumer must skip.
    assert lines[0].startswith("# extracted_at=")
    assert "source=poi_source_raw" in lines[0]
    assert "source_current_rows=42" in lines[0]
    # Line 2: the CSV header, exactly the fieldnames.
    assert lines[1] == "relation_record_id,member_record_ids"
    # Line 3: a data row, members pipe-joined.
    assert lines[2] == "relation/13422888,way/461729208|way/461729209"


def test_write_lineage_csv_empty_is_header_only(tmp_path: Path) -> None:
    from scripts.extract_osm_relation_lineage import write_lineage_csv

    out = tmp_path / "empty.csv"
    write_lineage_csv(out, [], source_row_count=0)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("#")
    assert lines[1] == "relation_record_id,member_record_ids"
    assert len(lines) == 2  # header comment + csv header, no data rows


def test_relation_lineage_sorted_and_guards_members() -> None:
    from scripts.extract_osm_relation_lineage import relation_lineage_from_elements

    elements: list[dict[str, Any]] = [
        {"type": "relation", "id": 200, "members": [{"type": "way", "ref": 2}]},
        {"type": "relation", "id": 100, "members": [
            {"type": "way", "ref": 1},
            {"type": "way"},  # malformed: no ref -> dropped
            {"ref": 9},       # malformed: no type -> dropped
        ]},
        {"type": "relation", "members": [{"type": "way", "ref": 5}]},  # no id -> skipped
    ]
    lineage = relation_lineage_from_elements(elements)
    # Sorted by relation_record_id ("relation/100" < "relation/200"); malformed
    # members dropped; id-less relation skipped.
    assert lineage == [
        ("relation/100", ["way/1"]),
        ("relation/200", ["way/2"]),
    ]


def test_relation_ids_from_raw_returns_sorted_unique_relation_ids() -> None:
    from scripts.extract_osm_relation_lineage import relation_ids_from_raw
    payloads = [
        {"type": "relation", "id": 200},
        {"type": "way", "id": 5},
        {"type": "relation", "id": 100},
        {"type": "node", "id": 9},
        {"type": "relation", "id": 200},  # dup
    ]
    assert relation_ids_from_raw(payloads) == [100, 200]


def test_relation_ids_from_raw_empty() -> None:
    from scripts.extract_osm_relation_lineage import relation_ids_from_raw
    assert relation_ids_from_raw([{"type": "way", "id": 1}]) == []


def test_fetch_relation_members_empty_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No ids -> no network call, returns [].
    import scripts.extract_osm_relation_lineage as ext

    def _boom(*a: Any, **k: Any) -> Any:  # pragma: no cover
        raise AssertionError("network should not be called for empty ids")

    monkeypatch.setattr(ext.httpx, "post", _boom)
    assert ext.fetch_relation_members([]) == []
