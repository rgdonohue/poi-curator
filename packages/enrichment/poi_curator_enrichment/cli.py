import typer

app = typer.Typer(help="POI Curator enrichment jobs.")


@app.command("wikidata")
def enrich_wikidata(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    typer.echo(
        f"[scaffold] Wikidata enrichment placeholder. Implement entity linking for region={region}."
    )


@app.command("wikipedia")
def enrich_wikipedia(region: str = typer.Option(..., help="Region slug to enrich.")) -> None:
    typer.echo(
        "[scaffold] Wikipedia enrichment placeholder. "
        f"Implement extract hydration for region={region}."
    )
