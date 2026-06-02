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
