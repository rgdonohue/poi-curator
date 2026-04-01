from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from poi_curator_domain.db import dispose_engine, get_db_session, get_engine
from poi_curator_scoring.backend import ScoringBackend, get_default_scoring_backend
from sqlalchemy.orm import Session

DatabaseSession = Annotated[Session, Depends(get_db_session)]
ScoringBackendDep = Annotated[ScoringBackend, Depends(get_default_scoring_backend)]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_engine()
    try:
        yield
    finally:
        dispose_engine()
