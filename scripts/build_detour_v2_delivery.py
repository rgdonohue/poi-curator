#!/usr/bin/env python3
"""Compatibility shim: the triaged Detour v2 delivery build moved into the
``poi_curator_editorial.detour_delivery`` package and the ``poi-curator-export
build-detour-v2`` console command.

The human-triaged dispositions formerly hardcoded here now live in
``data/detour_v2_dispositions.json``. This shim preserves the old invocation
(``python scripts/build_detour_v2_delivery.py``) and still writes the delivery
pair to the repo root. Note the manifest is now stamped ``schema_version: 2``
with input provenance; the committed delivery predates that and remains
legacy ``schema_version: 1``. See docs/INTEGRATION_CONTRACT.md.
"""

from __future__ import annotations

from poi_curator_editorial.detour_delivery import (
    DEFAULT_OUT_CSV,
    DEFAULT_OUT_MANIFEST,
    build_delivery,
)


def main() -> int:
    manifest = build_delivery()
    summary = manifest["summary"]
    print(f"wrote {DEFAULT_OUT_CSV} and {DEFAULT_OUT_MANIFEST}")
    print(
        "rows_before={rows_before} rows_after={rows_after} "
        "clusters_collapsed={clusters_collapsed} "
        "clusters_left_colocated={clusters_left_colocated} "
        "review_candidates={review_candidates}".format(**summary)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
