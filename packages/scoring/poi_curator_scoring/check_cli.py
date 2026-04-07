from __future__ import annotations

from getpass import getuser
from pathlib import Path

import orjson
import typer
from poi_curator_domain.db import get_session_factory

from poi_curator_scoring.backend import get_database_scoring_backend
from poi_curator_scoring.checks import (
    DEFAULT_FIXTURES_PATH,
    DEFAULT_REVIEW_DIR,
    CheckReport,
    CheckRun,
    build_inline_nearby_case,
    build_inline_route_case,
    build_report,
    build_review_artifact,
    load_named_cases,
    render_terminal_run,
    run_check_case,
    write_report_files,
    write_review_files,
)
from poi_curator_scoring.evaluation import EvaluationCase

app = typer.Typer(help="POI Curator CLI field checks and human review capture.")
DEFAULT_REVIEWER = getuser()

FIXTURES_OPTION = typer.Option(
    DEFAULT_FIXTURES_PATH,
    "--fixtures",
    exists=True,
    file_okay=True,
    dir_okay=False,
    help="Evaluation fixture file (.json).",
)
JSON_OUT_OPTION = typer.Option(
    None,
    "--json-out",
    file_okay=True,
    dir_okay=False,
    help="Optional JSON report output path.",
)
MD_OUT_OPTION = typer.Option(
    None,
    "--md-out",
    file_okay=True,
    dir_okay=False,
    help="Optional Markdown report output path.",
)
VERBOSE_OPTION = typer.Option(
    False,
    "--verbose",
    help="Show fuller score breakdowns in terminal and markdown output.",
)
RAW_OPTION = typer.Option(
    False,
    "--raw",
    help="Print the full structured run payload as JSON after the summary.",
)
ROUTE_COORD_OPTION = typer.Option(
    ...,
    "--route-coord",
    help="Repeatable lon,lat coordinate for the route line.",
)
BATCH_ID_OPTION = typer.Option(
    None,
    "--id",
    help="Optional saved case id to include.",
)
REVIEWER_OPTION = typer.Option(
    DEFAULT_REVIEWER,
    "--reviewer",
    help="Reviewer name.",
)
REVIEW_DIR_OPTION = typer.Option(
    DEFAULT_REVIEW_DIR,
    "--review-dir",
    file_okay=False,
    dir_okay=True,
    help="Directory for default review artifacts.",
)


@app.callback()
def main() -> None:
    """Expose a command group for field checks."""


@app.command("nearby")
def nearby(
    lat: float = typer.Option(..., "--lat", help="Center latitude."),
    lon: float = typer.Option(..., "--lon", help="Center longitude."),
    radius_meters: int = typer.Option(..., "--radius-meters", min=1, help="Search radius."),
    category: str = typer.Option(..., "--category", help="Requested category."),
    travel_mode: str = typer.Option("walking", "--travel-mode", help="Travel mode."),
    theme: str | None = typer.Option(None, "--theme", help="Optional active theme slug."),
    region_hint: str | None = typer.Option(None, "--region-hint", help="Optional region hint."),
    limit: int = typer.Option(5, "--limit", min=1, max=20, help="Result limit."),
    label: str | None = typer.Option(None, "--label", help="Optional label for the run."),
    json_out: Path | None = JSON_OUT_OPTION,
    md_out: Path | None = MD_OUT_OPTION,
    verbose: bool = VERBOSE_OPTION,
    raw: bool = RAW_OPTION,
) -> None:
    case = build_inline_nearby_case(
        lat=lat,
        lon=lon,
        radius_meters=radius_meters,
        category=category,
        travel_mode=travel_mode,
        theme=theme,
        region_hint=region_hint,
        limit=limit,
        label=label,
    )
    run = _execute_single_case(case=case, expectation_based=False)
    _emit_run(run, fixtures_path=None, json_out=json_out, md_out=md_out, verbose=verbose, raw=raw)


@app.command("route")
def route(
    route_coord: list[str] = ROUTE_COORD_OPTION,
    category: str = typer.Option(..., "--category", help="Requested category."),
    travel_mode: str = typer.Option("walking", "--travel-mode", help="Travel mode."),
    theme: str | None = typer.Option(None, "--theme", help="Optional active theme slug."),
    region_hint: str | None = typer.Option(None, "--region-hint", help="Optional region hint."),
    limit: int = typer.Option(5, "--limit", min=1, max=20, help="Result limit."),
    max_detour_meters: int = typer.Option(
        ...,
        "--max-detour-meters",
        min=1,
        help="Maximum detour budget in meters.",
    ),
    max_extra_minutes: int = typer.Option(
        ...,
        "--max-extra-minutes",
        min=1,
        help="Maximum extra minutes budget.",
    ),
    origin_name: str = typer.Option("Start", "--origin-name", help="Origin label."),
    destination_name: str = typer.Option("End", "--destination-name", help="Destination label."),
    label: str | None = typer.Option(None, "--label", help="Optional label for the run."),
    json_out: Path | None = JSON_OUT_OPTION,
    md_out: Path | None = MD_OUT_OPTION,
    verbose: bool = VERBOSE_OPTION,
    raw: bool = RAW_OPTION,
) -> None:
    coordinates = [_parse_lon_lat(value) for value in route_coord]
    if len(coordinates) < 2:
        raise typer.BadParameter("Provide at least two --route-coord values.")

    case = build_inline_route_case(
        coordinates=coordinates,
        category=category,
        travel_mode=travel_mode,
        theme=theme,
        region_hint=region_hint,
        limit=limit,
        max_detour_meters=max_detour_meters,
        max_extra_minutes=max_extra_minutes,
        origin_name=origin_name,
        destination_name=destination_name,
        label=label,
    )
    run = _execute_single_case(case=case, expectation_based=False)
    _emit_run(run, fixtures_path=None, json_out=json_out, md_out=md_out, verbose=verbose, raw=raw)


@app.command("case")
def case(
    id: str = typer.Option(..., "--id", help="Saved case id."),
    fixtures: Path = FIXTURES_OPTION,
    json_out: Path | None = JSON_OUT_OPTION,
    md_out: Path | None = MD_OUT_OPTION,
    verbose: bool = VERBOSE_OPTION,
    raw: bool = RAW_OPTION,
) -> None:
    cases = _load_cases_or_exit(fixtures, [id])
    run = _execute_single_case(case=cases[0], expectation_based=True)
    _emit_run(
        run,
        fixtures_path=fixtures,
        json_out=json_out,
        md_out=md_out,
        verbose=verbose,
        raw=raw,
    )


@app.command("batch")
def batch(
    fixtures: Path = FIXTURES_OPTION,
    id: list[str] | None = BATCH_ID_OPTION,
    json_out: Path | None = JSON_OUT_OPTION,
    md_out: Path | None = MD_OUT_OPTION,
    verbose: bool = VERBOSE_OPTION,
    raw: bool = RAW_OPTION,
) -> None:
    cases = _load_cases_or_exit(fixtures, id or None)
    runs = _execute_cases(cases=cases, expectation_based=True)
    report = build_report(runs, fixtures_path=fixtures)

    for index, run in enumerate(runs):
        if index:
            typer.echo("")
        typer.echo(render_terminal_run(run, verbose=verbose))

    _write_report_outputs(report, json_out=json_out, md_out=md_out, verbose=verbose)
    if raw:
        typer.echo(_json_dump(report.model_dump(mode="json")))


@app.command("review")
def review(
    id: str = typer.Option(..., "--id", help="Saved case id to run and review."),
    verdict: str = typer.Option(..., "--verdict", help="Human review verdict."),
    note: str | None = typer.Option(None, "--note", help="Optional human note."),
    reviewer: str = REVIEWER_OPTION,
    fixtures: Path = FIXTURES_OPTION,
    review_dir: Path = REVIEW_DIR_OPTION,
    json_out: Path | None = JSON_OUT_OPTION,
    md_out: Path | None = MD_OUT_OPTION,
    verbose: bool = VERBOSE_OPTION,
    raw: bool = RAW_OPTION,
) -> None:
    cases = _load_cases_or_exit(fixtures, [id])
    run = _execute_single_case(case=cases[0], expectation_based=True)
    review_artifact = build_review_artifact(
        run,
        verdict=verdict,
        reviewer=reviewer,
        note=note,
        fixtures_path=fixtures,
    )

    typer.echo(render_terminal_run(run, verbose=verbose))
    typer.echo("")
    typer.echo(f"reviewer={review_artifact.reviewer}")
    typer.echo(f"verdict={review_artifact.verdict}")
    if review_artifact.note:
        typer.echo(f"review_note={review_artifact.note}")

    for path in write_review_files(
        review_artifact,
        review_dir=review_dir,
        json_out=json_out,
        md_out=md_out,
    ):
        typer.echo(f"review_saved={path}")

    if raw:
        typer.echo(_json_dump(review_artifact.model_dump(mode="json")))


def _execute_single_case(*, case: EvaluationCase, expectation_based: bool) -> CheckRun:
    return _execute_cases(cases=[case], expectation_based=expectation_based)[0]


def _execute_cases(*, cases: list[EvaluationCase], expectation_based: bool) -> list[CheckRun]:
    backend = get_database_scoring_backend()
    session_factory = get_session_factory()
    with session_factory() as session:
        return [
            run_check_case(backend, session, case, expectation_based=expectation_based)
            for case in cases
        ]


def _emit_run(
    run: CheckRun,
    *,
    fixtures_path: Path | None,
    json_out: Path | None,
    md_out: Path | None,
    verbose: bool,
    raw: bool,
) -> None:
    typer.echo(render_terminal_run(run, verbose=verbose))
    report = build_report([run], fixtures_path=fixtures_path)
    _write_report_outputs(report, json_out=json_out, md_out=md_out, verbose=verbose)
    if raw:
        typer.echo(_json_dump(run.model_dump(mode="json")))


def _write_report_outputs(
    report: CheckReport,
    *,
    json_out: Path | None,
    md_out: Path | None,
    verbose: bool,
) -> None:
    for path in write_report_files(
        report,
        json_out=json_out,
        md_out=md_out,
        verbose_markdown=verbose,
    ):
        typer.echo(f"report={path}")


def _load_cases_or_exit(fixtures: Path, requested_ids: list[str] | None) -> list[EvaluationCase]:
    try:
        return load_named_cases(fixtures, requested_ids)
    except KeyError as exc:
        raise typer.BadParameter(
            f"Unknown case id(s) in {fixtures}: {exc.args[0]}"
        ) from exc


def _parse_lon_lat(value: str) -> tuple[float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid lon,lat pair: {value}")
    try:
        lon = float(parts[0])
        lat = float(parts[1])
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid lon,lat pair: {value}") from exc
    return lon, lat


def _json_dump(payload: object) -> str:
    return orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode("utf-8")
