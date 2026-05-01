import sys
import time

from fastapi import APIRouter, HTTPException
from poi_curator_domain.categories import PUBLIC_CATEGORIES, CategoryResponse
from poi_curator_domain.query_logging import write_query_log_if_enabled
from poi_curator_domain.schemas import (
    AppConfigResponse,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIDetailResponse,
    PointSuggestRequest,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
from poi_curator_domain.settings import get_settings

from poi_curator_api.dependencies import DatabaseSession, ScoringBackendDep

router = APIRouter(tags=["public"])


@router.get("/health")
def health(backend: ScoringBackendDep) -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "poi-curator",
        "environment": settings.env,
        "scoring_profile_version": settings.scoring_profile_version,
        "scoring_source": backend.current_scoring_source(),
    }


@router.get("/config", response_model=AppConfigResponse)
def config() -> AppConfigResponse:
    settings = get_settings()
    return AppConfigResponse(
        supported_regions=[settings.default_region],
        supported_categories=[category.slug for category in PUBLIC_CATEGORIES],
        default_detour_budgets_by_mode={
            "driving": {"max_detour_meters": 1600, "max_extra_minutes": 8},
            "walking": {"max_detour_meters": 350, "max_extra_minutes": 6},
        },
        scoring_profile_version=settings.scoring_profile_version,
    )


@router.get("/categories", response_model=list[CategoryResponse])
def categories() -> list[CategoryResponse]:
    return PUBLIC_CATEGORIES


@router.post("/route/suggest", response_model=RouteSuggestResponse)
def route_suggest(
    payload: RouteSuggestRequest,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> RouteSuggestResponse:
    started = time.perf_counter()
    response = backend.suggest_places(db, payload)
    log_suggestion_query(
        db,
        endpoint="route_suggest",
        payload=payload,
        response=response,
        duration_ms=elapsed_ms(started),
    )
    return response


@router.post("/point/suggest", response_model=NearbySuggestResponse)
def point_suggest(
    payload: PointSuggestRequest,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> NearbySuggestResponse:
    started = time.perf_counter()
    nearby_payload = NearbySuggestRequest.from_point_request(payload)
    response = backend.suggest_nearby_places(db, nearby_payload)
    log_suggestion_query(
        db,
        endpoint="point_suggest",
        payload=payload,
        response=response,
        duration_ms=elapsed_ms(started),
    )
    return response


@router.post("/nearby/suggest", response_model=NearbySuggestResponse)
def nearby_suggest(
    payload: NearbySuggestRequest,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> NearbySuggestResponse:
    started = time.perf_counter()
    response = backend.suggest_nearby_places(db, payload)
    log_suggestion_query(
        db,
        endpoint="nearby_suggest",
        payload=payload,
        response=response,
        duration_ms=elapsed_ms(started),
    )
    return response


@router.get("/poi/{poi_id}", response_model=POIDetailResponse)
def poi_detail(
    poi_id: str,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> POIDetailResponse:
    poi = backend.get_poi_detail(db, poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail="POI not found")
    return poi


def elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def log_suggestion_query(
    db: DatabaseSession,
    *,
    endpoint: str,
    payload: RouteSuggestRequest | NearbySuggestRequest | PointSuggestRequest,
    response: RouteSuggestResponse | NearbySuggestResponse,
    duration_ms: int,
) -> None:
    try:
        write_query_log_if_enabled(
            db,
            endpoint=endpoint,
            request_payload=payload.model_dump(mode="json"),
            scoring_profile_version=get_settings().scoring_profile_version,
            response=response,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        print(f"query logging failed: {exc}", file=sys.stderr)
