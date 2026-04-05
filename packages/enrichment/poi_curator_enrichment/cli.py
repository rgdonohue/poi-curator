import typer
from poi_curator_domain.db import get_session_factory

from poi_curator_enrichment.pipeline import (
    enrich_region_from_city_gis,
    enrich_region_from_nm_state_register,
    enrich_region_from_nrhp,
    enrich_region_from_wikidata,
)

app = typer.Typer(help="POI Curator enrichment jobs.")


@app.command("wikidata")
def enrich_wikidata(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = enrich_region_from_wikidata(session, region)

    typer.echo(
        "\n".join(
            [
                f"region={summary.region}",
                f"candidates={summary.candidate_count}",
                f"enriched={summary.enriched_count}",
                f"skipped_without_wikidata_id={summary.skipped_without_wikidata_id}",
                f"fetch_errors={summary.fetch_error_count}",
            ]
        )
    )


@app.command("wikipedia")
def enrich_wikipedia(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    typer.echo(
        "[scaffold] Wikipedia enrichment placeholder. "
        f"Implement extract hydration for region={region}."
    )


@app.command("city-gis")
def enrich_city_gis(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = enrich_region_from_city_gis(session, region)

    typer.echo(
        "\n".join(
            [
                f"region={summary.region}",
                f"features={summary.feature_count}",
                f"evidence_created={summary.evidence_created}",
                f"unmatched_features={summary.unmatched_feature_count}",
                f"impacted_pois={summary.impacted_poi_count}",
            ]
        )
    )


@app.command("nrhp")
def enrich_nrhp(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = enrich_region_from_nrhp(session, region)

    typer.echo(
        "\n".join(
            [
                f"region={summary.region}",
                f"candidate_rows={summary.candidate_row_count}",
                f"evidence_created={summary.evidence_created}",
                f"unmatched_rows={summary.unmatched_row_count}",
                f"impacted_pois={summary.impacted_poi_count}",
            ]
        )
    )


@app.command("state-register")
def enrich_state_register(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = enrich_region_from_nm_state_register(session, region)

    typer.echo(
        "\n".join(
            [
                f"region={summary.region}",
                f"candidate_rows={summary.candidate_row_count}",
                f"evidence_created={summary.evidence_created}",
                f"unmatched_rows={summary.unmatched_row_count}",
                f"impacted_pois={summary.impacted_poi_count}",
            ]
        )
    )
