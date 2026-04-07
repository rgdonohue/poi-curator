import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from poi_curator_domain.settings import get_settings

from poi_curator_api.api import api_router
from poi_curator_api.dependencies import lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    static_dir = Path(__file__).resolve().parent / "static"
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = FastAPI(
        title="POI Curator API",
        version="0.1.0",
        summary="Route-aware, culturally informed POI backend",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/v1")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {
            "service": "poi-curator",
            "docs_url": "/docs",
            "map_test_url": "/map-test",
            "environment": settings.env,
        }

    @app.get("/map-test", tags=["meta"])
    def map_test() -> FileResponse:
        return FileResponse(static_dir / "map-test" / "index.html")

    return app


app = create_app()


def serve() -> None:
    settings = get_settings()
    uvicorn.run(
        "poi_curator_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
