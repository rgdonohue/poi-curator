import uvicorn
from fastapi import FastAPI
from poi_curator_domain.settings import get_settings

from poi_curator_api.api import api_router
from poi_curator_api.dependencies import lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="POI Curator API",
        version="0.1.0",
        summary="Route-aware, culturally informed POI backend",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/v1")

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {
            "service": "poi-curator",
            "docs_url": "/docs",
            "environment": settings.env,
        }

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
