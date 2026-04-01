from pathlib import Path

import typer
from poi_curator_domain.db import get_session_factory

from poi_curator_scoring.backend import get_database_scoring_backend
from poi_curator_scoring.evaluation import (
    evaluate_route_fixtures,
    load_route_fixtures,
    write_evaluation_report,
)

app = typer.Typer(help="POI Curator scoring and route evaluation tools.")

FIXTURES_OPTION = typer.Option(
    ...,
    exists=True,
    file_okay=True,
    dir_okay=False,
    help="Route fixture file (.json).",
)
OUTPUT_OPTION = typer.Option(
    None,
    file_okay=True,
    dir_okay=False,
    help="Optional report output path (.json or .md).",
)


@app.callback()
def main() -> None:
    """Expose a command group even when only one subcommand exists."""


@app.command("routes")
def evaluate_routes(
    fixtures: Path = FIXTURES_OPTION,
    output: Path | None = OUTPUT_OPTION,
) -> None:
    backend = get_database_scoring_backend()
    route_fixtures = load_route_fixtures(fixtures)

    session_factory = get_session_factory()
    with session_factory() as session:
        summary = evaluate_route_fixtures(backend, session, route_fixtures)

    typer.echo(f"fixtures={summary.fixture_count}")
    typer.echo(f"passed={summary.passed_count}")
    typer.echo(f"failed={summary.failed_count}")
    if output is not None:
        write_evaluation_report(output, summary)
        typer.echo(f"report={output}")
