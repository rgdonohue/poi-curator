"""Console CLI for building and verifying the Detour v2 delivery.

Installed as ``poi-curator-export``. See docs/INTEGRATION_CONTRACT.md for the
contract this tooling serves. The verify command is a producer-side replica of
Detour's acceptance gate; the real PASS happens on Detour's receipt.
"""

from __future__ import annotations

from pathlib import Path

import typer

from poi_curator_editorial.detour_delivery import (
    DEFAULT_DISPOSITIONS,
    DEFAULT_OUT_CSV,
    DEFAULT_OUT_MANIFEST,
    DEFAULT_V1_CSV,
    DispositionError,
    build_delivery,
    verify_delivery,
)
from poi_curator_editorial.export_schema import ExportSchemaError

app = typer.Typer(
    name="poi-curator-export",
    help="Build and verify Detour delivery exports.",
    no_args_is_help=True,
)

V1_CSV_OPTION = typer.Option(DEFAULT_V1_CSV, help="Input v1 merged export CSV.")
DISPOSITIONS_OPTION = typer.Option(DEFAULT_DISPOSITIONS, help="Human-triaged dispositions JSON.")
OUT_DIR_OPTION = typer.Option(Path("."), help="Directory for the output CSV and manifest.")
CSV_OPTION = typer.Option(DEFAULT_OUT_CSV, "--csv", help="Delivery CSV to verify.")
MANIFEST_OPTION = typer.Option(
    DEFAULT_OUT_MANIFEST, "--manifest", help="Delivery merge manifest to verify."
)


@app.command("build-detour-v2")
def build_detour_v2(
    v1_csv: Path = V1_CSV_OPTION,
    dispositions: Path = DISPOSITIONS_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
) -> None:
    """Deterministically build the triaged Detour v2 delivery CSV + manifest."""
    out_csv = out_dir / DEFAULT_OUT_CSV.name
    out_manifest = out_dir / DEFAULT_OUT_MANIFEST.name
    try:
        manifest = build_delivery(
            v1_csv=v1_csv,
            dispositions_path=dispositions,
            out_csv=out_csv,
            out_manifest=out_manifest,
        )
    except DispositionError as exc:
        typer.echo(f"DISPOSITION ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except ExportSchemaError as exc:
        typer.echo(f"SCHEMA ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    summary = manifest["summary"]
    typer.echo(f"wrote {out_csv} and {out_manifest}")
    typer.echo(
        "rows_before={rows_before} rows_after={rows_after} "
        "clusters_collapsed={clusters_collapsed} "
        "clusters_left_colocated={clusters_left_colocated} "
        "review_candidates={review_candidates}".format(**summary)
    )
    failures = verify_delivery(out_csv, out_manifest)
    if failures:
        typer.echo("BUILD VERIFY FAIL — do not hand off", err=True)
        for failure in failures:
            typer.echo(f"  - {failure}", err=True)
        raise typer.Exit(code=1)
    typer.echo("build verify PASS (producer-side replica; Detour still verifies independently)")


@app.command("verify-detour-v2")
def verify_detour_v2(
    csv_path: Path = CSV_OPTION,
    manifest_path: Path = MANIFEST_OPTION,
) -> None:
    """Run the producer-side replica of Detour's acceptance gate."""
    failures = verify_delivery(csv_path, manifest_path)
    if failures:
        typer.echo("FAIL — not safe to promote")
        for failure in failures:
            typer.echo(f"  - {failure}")
        raise typer.Exit(code=1)
    typer.echo("PASS — safe to promote (producer-side replica; the real gate is Detour's)")


if __name__ == "__main__":
    app()
