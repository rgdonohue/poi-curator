from pathlib import Path

import typer
from poi_curator_domain.db import get_session_factory
from poi_curator_domain.regions import get_region

from poi_curator_ingestion.audit import build_audit_records, write_audit_records
from poi_curator_ingestion.overpass import (
    fetch_overpass_elements,
    load_overpass_elements_from_file,
)
from poi_curator_ingestion.pipeline import (
    ingest_osm_elements,
    refresh_osm_region_from_current_raw,
    reset_osm_region,
)

app = typer.Typer(help="POI Curator ingestion jobs.")

REGION_OPTION = typer.Option(..., help="Region slug to ingest.")
INPUT_FILE_OPTION = typer.Option(
    None,
    exists=True,
    file_okay=True,
    dir_okay=False,
    help="Optional Overpass JSON fixture file.",
)
AUDIT_OUTPUT_OPTION = typer.Option(
    None,
    file_okay=True,
    dir_okay=False,
    help="Optional audit export path (.json or .csv).",
)
REQUIRED_AUDIT_OUTPUT_OPTION = typer.Option(
    ...,
    file_okay=True,
    dir_okay=False,
    help="Audit export path (.json or .csv).",
)
YES_OPTION = typer.Option(
    False,
    "--yes",
    help="Confirm destructive region reset before rebuilding live OSM data.",
)


@app.command("osm")
def ingest_osm(
    region: str = REGION_OPTION,
    input_file: Path | None = INPUT_FILE_OPTION,
    audit_output: Path | None = AUDIT_OUTPUT_OPTION,
) -> None:
    region_spec = get_region(region)
    elements = (
        load_overpass_elements_from_file(input_file)
        if input_file is not None
        else fetch_overpass_elements(region_spec)
    )
    if audit_output is not None:
        write_audit_records(audit_output, build_audit_records(elements, region_spec))

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = ingest_osm_elements(session, region_spec, elements)

    typer.echo(
        "\n".join(
            [
                f"region={summary.region}",
                f"fetched={summary.fetched_count}",
                f"raw_inserted={summary.raw_inserted}",
                f"raw_updated={summary.raw_updated}",
                f"canonical_inserted={summary.canonical_inserted}",
                f"canonical_updated={summary.canonical_updated}",
                f"skipped={summary.skipped_without_name_or_type}",
                f"ingest_run_id={summary.ingest_run_id}",
            ]
        )
    )


@app.command("audit-osm")
def audit_osm(
    region: str = REGION_OPTION,
    input_file: Path | None = INPUT_FILE_OPTION,
    audit_output: Path = REQUIRED_AUDIT_OUTPUT_OPTION,
) -> None:
    region_spec = get_region(region)
    elements = (
        load_overpass_elements_from_file(input_file)
        if input_file is not None
        else fetch_overpass_elements(region_spec)
    )
    records = build_audit_records(elements, region_spec)
    write_audit_records(audit_output, records)
    typer.echo(f"audit_records={len(records)}")
    typer.echo(f"audit_output={audit_output}")


@app.command("rebuild-osm")
def rebuild_osm(
    region: str = REGION_OPTION,
    input_file: Path | None = INPUT_FILE_OPTION,
    audit_output: Path | None = AUDIT_OUTPUT_OPTION,
    yes: bool = YES_OPTION,
) -> None:
    if not yes:
        raise typer.BadParameter("Pass --yes to confirm region-scoped OSM rebuild.")

    region_spec = get_region(region)
    session_factory = get_session_factory()
    with session_factory() as session:
        reset_summary = reset_osm_region(session, region_spec)

    typer.echo(
        "\n".join(
            [
                f"reset_region={reset_summary.region}",
                f"reset_poi_deleted={reset_summary.poi_deleted}",
                f"reset_raw_deleted={reset_summary.raw_deleted}",
                f"reset_ingest_runs_deleted={reset_summary.ingest_runs_deleted}",
            ]
        )
    )

    ingest_osm(
        region=region,
        input_file=input_file,
        audit_output=audit_output,
    )


@app.command("refresh-osm")
def refresh_osm(region: str = REGION_OPTION) -> None:
    region_spec = get_region(region)
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = refresh_osm_region_from_current_raw(session, region_spec)

    typer.echo(
        "\n".join(
            [
                f"region={summary.region}",
                f"canonical_inserted={summary.canonical_inserted}",
                f"canonical_updated={summary.canonical_updated}",
                f"skipped={summary.skipped_without_name_or_type}",
            ]
        )
    )


@app.command("heritage")
def ingest_heritage(region: str = typer.Option(..., help="Region slug to ingest.")) -> None:
    typer.echo(
        "[scaffold] Heritage overlay job placeholder. "
        f"Implement NRHP/SHPO import for region={region}."
    )
