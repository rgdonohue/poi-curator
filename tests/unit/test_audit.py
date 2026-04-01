import csv
from pathlib import Path

import orjson
from poi_curator_domain.regions import get_region
from poi_curator_ingestion.audit import build_audit_records, write_audit_records


def test_build_audit_records_contains_rule_diagnostics() -> None:
    fixture = orjson.loads(Path("data/fixtures/overpass_santa_fe_sample.json").read_bytes())

    records = build_audit_records(fixture["elements"], get_region("santa-fe"))

    overlook = next(record for record in records if record.source_record_id == "node/1003")
    assert overlook.status == "classified"
    assert overlook.matched_rule_id == "viewpoint"
    assert overlook.public_category == "scenic"


def test_write_audit_records_csv(tmp_path: Path) -> None:
    fixture = orjson.loads(Path("data/fixtures/overpass_santa_fe_sample.json").read_bytes())
    output_path = tmp_path / "audit.csv"

    records = build_audit_records(fixture["elements"], get_region("santa-fe"))
    write_audit_records(output_path, records)

    rows = list(csv.DictReader(output_path.open()))
    assert len(rows) == len(fixture["elements"])
    assert any(row["matched_rule_id"] == "viewpoint" for row in rows)
