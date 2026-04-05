from fastapi import APIRouter, HTTPException
from poi_curator_domain.categories import PUBLIC_CATEGORIES, CategoryResponse
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
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "poi-curator",
        "environment": settings.env,
        "scoring_profile_version": settings.scoring_profile_version,
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
    return backend.suggest_places(db, payload)


@router.post("/point/suggest", response_model=NearbySuggestResponse)
def point_suggest(
    payload: PointSuggestRequest,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> NearbySuggestResponse:
    return backend.suggest_nearby_places(db, NearbySuggestRequest.from_point_request(payload))


@router.post("/nearby/suggest", response_model=NearbySuggestResponse)
def nearby_suggest(
    payload: NearbySuggestRequest,
    db: DatabaseSession,
    backend: ScoringBackendDep,
) -> NearbySuggestResponse:
    return backend.suggest_nearby_places(db, payload)


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
