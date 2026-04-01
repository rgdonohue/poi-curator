from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from poi_curator_domain.schemas import (
    AdminIngestRunRequest,
    AdminIngestRunResponse,
    AdminIngestStatusResponse,
    AdminPOIItem,
    AdminPOIPatchRequest,
    AdminPOIPatchResponse,
)

from poi_curator_api.dependencies import DatabaseSession, ScoringBackendDep

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/poi", response_model=list[AdminPOIItem])
def admin_poi_queue(
    db: DatabaseSession,
    backend: ScoringBackendDep,
    status: str = Query(default="needs_review"),
    city: str | None = Query(default=None),
) -> list[AdminPOIItem]:
    return backend.get_admin_queue(db, status=status, city=city)


@router.patch("/poi/{poi_id}", response_model=AdminPOIPatchResponse)
def patch_admin_poi(
    poi_id: str,
    payload: AdminPOIPatchRequest,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> AdminPOIPatchResponse:
    poi = backend.get_poi_detail(db, poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail="POI not found")

    return AdminPOIPatchResponse(
        poi_id=poi_id,
        applied_changes=payload.model_dump(exclude_none=True),
        persisted=False,
        message="Scaffold response only. Persistence will be added with the editorial layer.",
    )


@router.post("/ingest/run", response_model=AdminIngestRunResponse)
def trigger_ingest(payload: AdminIngestRunRequest) -> AdminIngestRunResponse:
    started_at = datetime.now(UTC)
    return AdminIngestRunResponse(
        run_id="scaffold-run",
        source=payload.source,
        region=payload.region,
        status="queued",
        started_at=started_at,
    )


@router.get("/ingest/status", response_model=AdminIngestStatusResponse)
def ingest_status() -> AdminIngestStatusResponse:
    return AdminIngestStatusResponse(
        last_run_id="scaffold-run",
        status="idle",
        last_successful_run_at=None,
    )
