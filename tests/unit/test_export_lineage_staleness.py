from pathlib import Path

import pytest

import scripts.export_query_capable_pois_merged_v1 as exporter


def test_warn_missing_lineage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seed = tmp_path / "seed.csv"
    seed.write_text("x\n", encoding="utf-8")
    exporter.warn_if_lineage_stale(tmp_path / "absent.csv", seed)
    out = capsys.readouterr().out
    assert "missing" in out


def test_no_false_positive_when_lineage_fresh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Lineage written AFTER seed -> not stale -> no warning at all.
    seed = tmp_path / "seed.csv"
    seed.write_text("x\n", encoding="utf-8")
    lineage = tmp_path / "lineage.csv"
    lineage.write_text("# stamp\nrelation_record_id,member_record_ids\n", encoding="utf-8")
    import os
    import time

    # ensure lineage mtime >= seed mtime
    now = time.time()
    os.utime(seed, (now - 10, now - 10))
    os.utime(lineage, (now, now))
    exporter.warn_if_lineage_stale(lineage, seed)
    out = capsys.readouterr().out
    assert out == ""  # no warnings on a fresh lineage


def test_warn_when_lineage_older_than_seed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed = tmp_path / "seed.csv"
    seed.write_text("x\n", encoding="utf-8")
    lineage = tmp_path / "lineage.csv"
    lineage.write_text("# stamp\nrelation_record_id,member_record_ids\n", encoding="utf-8")
    import os
    import time

    now = time.time()
    os.utime(lineage, (now - 100, now - 100))
    os.utime(seed, (now, now))
    exporter.warn_if_lineage_stale(lineage, seed)
    out = capsys.readouterr().out
    assert "older than seed" in out
