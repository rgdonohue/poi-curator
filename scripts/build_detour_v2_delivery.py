#!/usr/bin/env python3
"""Compatibility shim: the triaged Detour v2 delivery build moved into the
``poi_curator_editorial.detour_delivery`` package and the ``poi-curator-export
build-detour-v2`` console command.

The human-triaged dispositions formerly hardcoded here now live in
``data/detour_v2_dispositions.json``. This shim preserves the old invocation
(``python scripts/build_detour_v2_delivery.py``) and still targets the repo
root, but it now refuses to overwrite the committed delivery pair unless
``--force`` is passed — cutting a new root delivery is an explicit action.
Note the manifest is now stamped ``schema_version: 2`` with input provenance;
the committed delivery predates that and remains legacy ``schema_version: 1``.
See docs/INTEGRATION_CONTRACT.md.
"""

from __future__ import annotations

import argparse

from poi_curator_editorial.detour_delivery import (
    DEFAULT_OUT_CSV,
    DEFAULT_OUT_MANIFEST,
    build_delivery,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the repo-root Detour v2 delivery (explicit action).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the existing repo-root delivery pair.",
    )
    args = parser.parse_args()
    try:
        manifest = build_delivery(overwrite=args.force)
    except FileExistsError as exc:
        print(f"REFUSED: {exc}")
        return 4
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
