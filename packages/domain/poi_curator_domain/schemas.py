from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class GeoLineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(min_length=2)


class NamedPoint(BaseModel):
    name: str
    coordinates: list[float] = Field(min_length=2, max_length=2)


TravelMode = Literal["driving", "walking"]
PublicCategory = Literal["history", "culture", "art", "scenic", "food", "civic", "mixed"]
CategoryMatchType = Literal["primary", "secondary", "mixed"]


class RouteSuggestRequest(BaseModel):
    route_geometry: GeoLineString
    origin: NamedPoint
    destination: NamedPoint
    travel_mode: TravelMode
    category: PublicCategory
    max_detour_meters: int = Field(gt=0)
    max_extra_minutes: int = Field(gt=0)
    region_hint: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class QuerySummary(BaseModel):
    travel_mode: TravelMode
    category: PublicCategory
    max_detour_meters: int
    limit: int


class RouteResult(BaseModel):
    poi_id: str
    name: str
    primary_category: str
    secondary_categories: list[str]
    category_match_type: CategoryMatchType | None = None
    coordinates: list[float]
    short_description: str
    distance_from_route_m: int
    estimated_detour_m: int
    estimated_extra_minutes: int
    score: float
    score_breakdown: dict[str, float] | None = None
    why_it_matters: list[str]
    badges: list[str]


class RouteSuggestResponse(BaseModel):
    query_summary: QuerySummary
    results: list[RouteResult]


class AppConfigResponse(BaseModel):
    supported_regions: list[str]
    supported_categories: list[str]
    default_detour_budgets_by_mode: dict[str, dict[str, int]]
    scoring_profile_version: str


class POIDetailResponse(BaseModel):
    poi_id: str
    name: str
    primary_category: str
    secondary_categories: list[str]
    coordinates: list[float]
    short_description: str
    why_it_matters: list[str]
    badges: list[str]
    provenance: dict[str, Any]


class AdminPOIItem(BaseModel):
    poi_id: str
    name: str
    city: str
    status: str
    primary_category: str
    notes: str


class AdminPOIPatchRequest(BaseModel):
    editorial_status: str | None = None
    editorial_title_override: str | None = None
    editorial_description_override: str | None = None
    editorial_category_override: str | None = None
    editorial_boost: int | None = None
    editorial_notes: str | None = None


class AdminPOIPatchResponse(BaseModel):
    poi_id: str
    applied_changes: dict[str, Any]
    persisted: bool
    message: str


class AdminIngestRunRequest(BaseModel):
    source: str
    region: str


class AdminIngestRunResponse(BaseModel):
    run_id: str
    source: str
    region: str
    status: str
    started_at: datetime


class AdminIngestStatusResponse(BaseModel):
    last_run_id: str | None
    status: str
    last_successful_run_at: datetime | None
