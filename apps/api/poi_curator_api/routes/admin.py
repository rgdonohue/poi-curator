from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from poi_curator_domain.query_logging import list_query_logs
from poi_curator_domain.schemas import (
    AdminAliasFromDiagnosticRequest,
    AdminAliasMutationResponse,
    AdminCreateAliasRequest,
    AdminIngestRunRequest,
    AdminIngestRunResponse,
    AdminIngestStatusResponse,
    AdminMatchDiagnosticItem,
    AdminPOIEvidenceResponse,
    AdminPOIItem,
    AdminPOIPatchRequest,
    AdminPOIPatchResponse,
    AdminResolveDiagnosticRequest,
    AdminSuppressDiagnosticRequest,
    AdminThemeMembershipDetailResponse,
    AdminThemeMembershipQueueItem,
    AdminThemeReviewRequest,
    AdminThemeReviewResponse,
    AdminThemeSummaryItem,
    QueryLogListResponse,
)
from poi_curator_domain.settings import get_settings
from poi_curator_editorial import service as editorial_service

from poi_curator_api.dependencies import DatabaseSession, ScoringBackendDep

OPTIONAL_DATETIME_QUERY = Query(default=None)


def require_admin_api_key(
    admin_key: str | None = Header(default=None, alias="X-POI-Curator-Admin-Key"),
) -> None:
    expected_key = get_settings().admin_key
    if expected_key is None or not expected_key or admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key.")


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)


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
) -> AdminPOIPatchResponse:
    response = editorial_service.patch_admin_poi(db, poi_id, payload)
    if response is None:
        raise HTTPException(status_code=404, detail="POI not found")
    return response


@router.get("/themes", response_model=list[AdminThemeSummaryItem])
def admin_theme_summaries(
    db: DatabaseSession,
    backend: ScoringBackendDep,
    city: str | None = Query(default=None),
) -> list[AdminThemeSummaryItem]:
    return backend.get_admin_theme_summaries(db, city=city)


@router.get("/theme-memberships", response_model=list[AdminThemeMembershipQueueItem])
def admin_theme_memberships(
    db: DatabaseSession,
    backend: ScoringBackendDep,
    theme_slug: str | None = Query(default=None),
    city: str | None = Query(default=None),
    automated_status: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
    editorial_decision: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AdminThemeMembershipQueueItem]:
    return backend.get_admin_theme_memberships(
        db,
        theme_slug=theme_slug,
        city=city,
        automated_status=automated_status,
        review_state=review_state,
        editorial_decision=editorial_decision,
        limit=limit,
    )


@router.get(
    "/poi/{poi_id}/themes/{theme_slug}",
    response_model=AdminThemeMembershipDetailResponse,
)
def admin_theme_membership_detail(
    poi_id: str,
    theme_slug: str,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> AdminThemeMembershipDetailResponse:
    response = backend.get_admin_theme_membership_detail(
        db,
        poi_id=poi_id,
        theme_slug=theme_slug,
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Theme membership not found")
    return response


@router.put(
    "/poi/{poi_id}/themes/{theme_slug}/review",
    response_model=AdminThemeReviewResponse,
)
def review_admin_theme_membership(
    poi_id: str,
    theme_slug: str,
    payload: AdminThemeReviewRequest,
    db: DatabaseSession,
) -> AdminThemeReviewResponse:
    try:
        response = editorial_service.review_theme_membership(
            db,
            poi_id=poi_id,
            theme_slug=theme_slug,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="POI not found")
    return response


@router.get("/poi/{poi_id}/evidence", response_model=AdminPOIEvidenceResponse)
def admin_poi_evidence(
    poi_id: str,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> AdminPOIEvidenceResponse:
    response = backend.get_admin_poi_evidence(db, poi_id)
    if response is None:
        raise HTTPException(status_code=404, detail="POI not found")
    return response


@router.get("/match-diagnostics", response_model=list[AdminMatchDiagnosticItem])
def admin_match_diagnostics(
    db: DatabaseSession,
    backend: ScoringBackendDep,
    region: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    status: str = Query(default="unreviewed"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AdminMatchDiagnosticItem]:
    return backend.get_admin_match_diagnostics(
        db,
        region=region,
        source_id=source_id,
        status=status,
        limit=limit,
    )


@router.post("/match-diagnostics/{diagnostic_id}/resolve", response_model=AdminMatchDiagnosticItem)
def resolve_match_diagnostic(
    diagnostic_id: int,
    payload: AdminResolveDiagnosticRequest,
    db: DatabaseSession,
) -> AdminMatchDiagnosticItem:
    try:
        response = editorial_service.resolve_match_diagnostic(db, diagnostic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Diagnostic row not found")
    return response


@router.post(
    "/match-diagnostics/{diagnostic_id}/alias",
    response_model=AdminMatchDiagnosticItem,
)
def create_alias_from_diagnostic(
    diagnostic_id: int,
    payload: AdminAliasFromDiagnosticRequest,
    db: DatabaseSession,
) -> AdminMatchDiagnosticItem:
    try:
        response = editorial_service.create_alias_from_diagnostic(db, diagnostic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Diagnostic row not found")
    return response


@router.post(
    "/match-diagnostics/{diagnostic_id}/suppress",
    response_model=AdminMatchDiagnosticItem,
)
def suppress_match_diagnostic(
    diagnostic_id: int,
    payload: AdminSuppressDiagnosticRequest,
    db: DatabaseSession,
) -> AdminMatchDiagnosticItem:
    try:
        response = editorial_service.suppress_match_diagnostic(db, diagnostic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Diagnostic row not found")
    return response


@router.post("/poi/{poi_id}/aliases", response_model=AdminAliasMutationResponse)
def add_poi_alias(
    poi_id: str,
    payload: AdminCreateAliasRequest,
    db: DatabaseSession,
) -> AdminAliasMutationResponse:
    try:
        response = editorial_service.add_poi_alias(db, poi_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="POI not found")
    return response


@router.get("/query-logs", response_model=QueryLogListResponse)
def admin_query_logs(
    db: DatabaseSession,
    endpoint: str | None = Query(default=None),
    start: datetime | None = OPTIONAL_DATETIME_QUERY,
    end: datetime | None = OPTIONAL_DATETIME_QUERY,
    min_result_count: int | None = Query(default=None, ge=0),
    max_result_count: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> QueryLogListResponse:
    return list_query_logs(
        db,
        endpoint=endpoint,
        start=start,
        end=end,
        min_result_count=min_result_count,
        max_result_count=max_result_count,
        limit=limit,
        offset=offset,
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
