"""Contract/golden tests for the Detour delivery build + verify path.

Covers, without PostGIS:

- the committed repo-root delivery passes the producer-side gate replica
  (including its legacy schema_version 1 manifest);
- the build reproduces the committed delivery CSV byte-for-byte from the
  committed v1 export + dispositions file, with a content-equivalent
  schema_version 2 manifest;
- a small synthetic fixture (clearly labeled test_fixture rows) proves the
  build is deterministic and exercises every disposition kind;
- dispositions referencing missing dedupe_keys fail loudly;
- schema validation refuses to write a non-compliant delivery.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from poi_curator_editorial.detour_delivery import (
    DispositionError,
    build_delivery,
    verify_delivery,
)
from poi_curator_editorial.export_cli import app as export_app
from poi_curator_editorial.export_schema import ExportSchemaError
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "detour_delivery"

COMMITTED_CSV = REPO_ROOT / "query_capable_pois_merged_v2.csv"
COMMITTED_MANIFEST = REPO_ROOT / "query_capable_pois_merged_v2_merge_manifest.json"
COMMITTED_V1_CSV = REPO_ROOT / "reports" / "query_capable_pois_merged_v1.csv"
COMMITTED_DISPOSITIONS = REPO_ROOT / "data" / "detour_v2_dispositions.json"


def normalized_input_paths(manifest: dict[str, Any]) -> dict[str, Any]:
    """Reduce inputs.*.path to basenames so golden comparison is machine-independent."""
    result = json.loads(json.dumps(manifest))
    for artifact in result.get("inputs", {}).values():
        artifact["path"] = Path(artifact["path"]).name
    return result


def test_verify_passes_on_committed_root_delivery() -> None:
    failures = verify_delivery(COMMITTED_CSV, COMMITTED_MANIFEST)

    assert failures == []


def test_committed_manifest_is_legacy_schema_version_1() -> None:
    manifest = json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1


def test_build_reproduces_committed_delivery(tmp_path: Path) -> None:
    out_csv = tmp_path / "query_capable_pois_merged_v2.csv"
    out_manifest = tmp_path / "query_capable_pois_merged_v2_merge_manifest.json"

    manifest = build_delivery(
        v1_csv=COMMITTED_V1_CSV,
        dispositions_path=COMMITTED_DISPOSITIONS,
        out_csv=out_csv,
        out_manifest=out_manifest,
    )

    assert out_csv.read_bytes() == COMMITTED_CSV.read_bytes()
    # The rebuilt manifest is schema_version 2 with input provenance; its
    # content must match the committed legacy manifest exactly once the new
    # envelope fields are removed.
    committed = json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8"))
    rebuilt = json.loads(json.dumps(manifest))
    assert rebuilt.pop("schema_version") == 2
    assert rebuilt.pop("contract") == "detour-export"
    inputs = rebuilt.pop("inputs")
    assert set(inputs) == {"v1_csv", "dispositions"}
    assert committed.pop("schema_version") == 1
    assert rebuilt == committed
    assert verify_delivery(out_csv, out_manifest) == []


def test_golden_fixture_build_matches_expected_and_is_deterministic(tmp_path: Path) -> None:
    outputs: list[tuple[bytes, dict[str, Any]]] = []
    for run in ("first", "second"):
        out_csv = tmp_path / run / "v2.csv"
        out_manifest = tmp_path / run / "manifest.json"
        build_delivery(
            v1_csv=FIXTURES / "v1_small.csv",
            dispositions_path=FIXTURES / "dispositions_small.json",
            out_csv=out_csv,
            out_manifest=out_manifest,
        )
        outputs.append(
            (out_csv.read_bytes(), json.loads(out_manifest.read_text(encoding="utf-8")))
        )

    assert outputs[0][0] == outputs[1][0], "CSV output must be deterministic"
    assert outputs[0][1] == outputs[1][1], "manifest output must be deterministic"

    assert outputs[0][0] == (FIXTURES / "expected_v2.csv").read_bytes()
    expected = json.loads((FIXTURES / "expected_manifest.json").read_text(encoding="utf-8"))
    assert normalized_input_paths(outputs[0][1]) == normalized_input_paths(expected)

    summary = outputs[0][1]["summary"]
    assert summary == {
        "rows_before": 7,
        "rows_after": 5,
        "clusters_collapsed": 1,
        "clusters_left_colocated": 1,
        "review_candidates": 1,
    }
    dispositions = sorted(entry["disposition"] for entry in outputs[0][1]["clusters"])
    assert dispositions == ["collapsed", "left_colocated", "review_candidate"]
    assert [entry["dedupe_key"] for entry in outputs[0][1]["excluded_rows"]] == [
        "osm:relation/5"
    ]


def test_golden_fixture_verify_passes(tmp_path: Path) -> None:
    out_csv = tmp_path / "v2.csv"
    out_manifest = tmp_path / "manifest.json"
    build_delivery(
        v1_csv=FIXTURES / "v1_small.csv",
        dispositions_path=FIXTURES / "dispositions_small.json",
        out_csv=out_csv,
        out_manifest=out_manifest,
    )

    assert verify_delivery(out_csv, out_manifest) == []


def build_small_fixture(out_csv: Path, out_manifest: Path, *, overwrite: bool = False) -> None:
    build_delivery(
        v1_csv=FIXTURES / "v1_small.csv",
        dispositions_path=FIXTURES / "dispositions_small.json",
        out_csv=out_csv,
        out_manifest=out_manifest,
        overwrite=overwrite,
    )


def test_build_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    out_csv = tmp_path / "v2.csv"
    out_manifest = tmp_path / "manifest.json"
    build_small_fixture(out_csv, out_manifest)
    first_csv = out_csv.read_bytes()
    first_manifest = out_manifest.read_bytes()

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        build_small_fixture(out_csv, out_manifest)
    assert out_csv.read_bytes() == first_csv, "refused build must not touch outputs"
    assert out_manifest.read_bytes() == first_manifest

    build_small_fixture(out_csv, out_manifest, overwrite=True)
    assert out_csv.read_bytes() == first_csv, "forced rebuild stays deterministic"
    assert out_manifest.read_bytes() == first_manifest


def test_cli_casual_build_does_not_overwrite_existing_delivery(tmp_path: Path) -> None:
    # Simulate the repo-root situation: the out-dir already holds a committed
    # delivery pair. A casual build must refuse (exit 4) and leave it intact.
    sentinel_csv = tmp_path / "query_capable_pois_merged_v2.csv"
    sentinel_manifest = tmp_path / "query_capable_pois_merged_v2_merge_manifest.json"
    sentinel_csv.write_text("committed delivery placeholder", encoding="utf-8")
    sentinel_manifest.write_text("{}", encoding="utf-8")
    runner = CliRunner()
    base_args = [
        "build-detour-v2",
        "--v1-csv",
        str(FIXTURES / "v1_small.csv"),
        "--dispositions",
        str(FIXTURES / "dispositions_small.json"),
        "--out-dir",
        str(tmp_path),
    ]

    result = runner.invoke(export_app, base_args)

    assert result.exit_code == 4
    assert sentinel_csv.read_text(encoding="utf-8") == "committed delivery placeholder"
    assert sentinel_manifest.read_text(encoding="utf-8") == "{}"

    forced = runner.invoke(export_app, [*base_args, "--force"])

    assert forced.exit_code == 0
    assert sentinel_csv.read_bytes() == (FIXTURES / "expected_v2.csv").read_bytes()


def test_disposition_with_missing_dedupe_key_fails_loudly(tmp_path: Path) -> None:
    dispositions = json.loads(
        (FIXTURES / "dispositions_small.json").read_text(encoding="utf-8")
    )
    dispositions["collapses"][0]["members"][0] = "osm:relation/999999"
    broken = tmp_path / "broken_dispositions.json"
    broken.write_text(json.dumps(dispositions), encoding="utf-8")
    out_csv = tmp_path / "v2.csv"

    with pytest.raises(DispositionError, match="osm:relation/999999"):
        build_delivery(
            v1_csv=FIXTURES / "v1_small.csv",
            dispositions_path=broken,
            out_csv=out_csv,
            out_manifest=tmp_path / "manifest.json",
        )
    assert not out_csv.exists(), "a failed build must not emit artifacts"


def test_schema_violation_refuses_to_write(tmp_path: Path) -> None:
    # Dropping the out-of-bbox exclusion leaves a row outside the Santa Fe
    # bbox, which the versioned row schema must refuse to write.
    dispositions = json.loads(
        (FIXTURES / "dispositions_small.json").read_text(encoding="utf-8")
    )
    dispositions["excluded_rows"] = []
    broken = tmp_path / "no_exclusion_dispositions.json"
    broken.write_text(json.dumps(dispositions), encoding="utf-8")
    out_csv = tmp_path / "v2.csv"

    with pytest.raises(ExportSchemaError, match="bbox"):
        build_delivery(
            v1_csv=FIXTURES / "v1_small.csv",
            dispositions_path=broken,
            out_csv=out_csv,
            out_manifest=tmp_path / "manifest.json",
        )
    assert not out_csv.exists(), "a failed build must not emit artifacts"
