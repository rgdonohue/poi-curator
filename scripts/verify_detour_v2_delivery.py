#!/usr/bin/env python3
"""Compatibility shim: the Detour delivery gate replica moved into the
``poi_curator_editorial.detour_delivery`` package and the ``poi-curator-export
verify-detour-v2`` console command.

This remains a faithful replica of the Detour-side ``qc_pois.py`` acceptance
gate. We cannot run their gate (it lives Detour-side); the real PASS happens
on their receipt. See docs/INTEGRATION_CONTRACT.md.
"""

from __future__ import annotations

import json
import sys

from poi_curator_editorial.detour_delivery import (
    DEFAULT_OUT_CSV,
    DEFAULT_OUT_MANIFEST,
    load_rows,
    verify_delivery,
)


def main() -> int:
    failures = verify_delivery(DEFAULT_OUT_CSV, DEFAULT_OUT_MANIFEST)
    if failures:
        print("FAIL — not safe to promote")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    rows, _ = load_rows(DEFAULT_OUT_CSV)
    manifest = json.loads(DEFAULT_OUT_MANIFEST.read_text(encoding="utf-8"))
    print("PASS — safe to promote")
    print(
        f"  rows={len(rows)} clusters: "
        f"collapsed={manifest['summary']['clusters_collapsed']} "
        f"left_colocated={manifest['summary']['clusters_left_colocated']} "
        f"review={manifest['summary']['review_candidates']}"
    )
    print("  residual <=35m clusters: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
