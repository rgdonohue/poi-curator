from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from poi_curator_domain.themes import ThemeEditorialDecision, ThemeSlug, is_query_theme_active


class GeoLineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(min_length=2)


class NamedPoint(BaseModel):
    name: str
    coordinates: list[float] = Field(min_length=2, max_length=2)


class LatLonPoint(BaseModel):
    lat: float
    lon: float


TravelMode = Literal["driving", "walking"]
PublicCategory = Literal["history", "culture", "art", "scenic", "food", "civic", "mixed"]
CategoryMatchType = Literal["primary", "secondary", "mixed"]


class RouteSuggestRequest(BaseModel):
    route_geometry: GeoLineString
    origin: NamedPoint
    destination: NamedPoint
    travel_mode: TravelMode
    category: PublicCategory
    theme: ThemeSlug | None = None
    max_detour_meters: int = Field(gt=0)
    max_extra_minutes: int = Field(gt=0)
    region_hint: str | None = None
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("theme")
    @classmethod
    def validate_active_theme(cls, value: ThemeSlug | None) -> ThemeSlug | None:
        if value is not None and not is_query_theme_active(value):
            raise ValueError(f"Theme '{value}' is defined but not yet active for query use.")
        return value


class PointSuggestRequest(BaseModel):
    location: NamedPoint
    travel_mode: TravelMode
    category: PublicCategory
    theme: ThemeSlug | None = None
    radius_meters: int = Field(gt=0)
    region_hint: str | None = None
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("theme")
    @classmethod
    def validate_active_theme(cls, value: ThemeSlug | None) -> ThemeSlug | None:
        if value is not None and not is_query_theme_active(value):
            raise ValueError(f"Theme '{value}' is defined but not yet active for query use.")
        return value


class NearbySuggestRequest(BaseModel):
    center: LatLonPoint
    travel_mode: TravelMode
    category: PublicCategory
    theme: ThemeSlug | None = None
    radius_meters: int = Field(gt=0)
    region_hint: str | None = None
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("theme")
    @classmethod
    def validate_active_theme(cls, value: ThemeSlug | None) -> ThemeSlug | None:
        if value is not None and not is_query_theme_active(value):
            raise ValueError(f"Theme '{value}' is defined but not yet active for query use.")
        return value

    @classmethod
    def from_point_request(cls, payload: "PointSuggestRequest") -> "NearbySuggestRequest":
        return cls(
            center=LatLonPoint(
                lat=payload.location.coordinates[1],
                lon=payload.location.coordinates[0],
            ),
            travel_mode=payload.travel_mode,
            category=payload.category,
            theme=payload.theme,
            radius_meters=payload.radius_meters,
            region_hint=payload.region_hint,
            limit=payload.limit,
        )


class QuerySummary(BaseModel):
    travel_mode: TravelMode
    category: PublicCategory
    theme: ThemeSlug | None = None
    max_detour_meters: int
    limit: int


class NearbyQuerySummary(BaseModel):
    travel_mode: TravelMode
    category: PublicCategory
    theme: ThemeSlug | None = None
    radius_meters: int
    limit: int


class ThemeEvidenceReference(BaseModel):
    evidence_id: int
    source_id: str
    evidence_type: str
    label: str | None = None
    confidence: float


class POIThemeItem(BaseModel):
    theme_slug: ThemeSlug
    label: str
    status: str
    assignment_basis: str
    confidence: float
    rationale_summary: str | None = None
    is_query_active: bool
    editorial_decision: str | None = None
    evidence: list[ThemeEvidenceReference] = Field(default_factory=list)


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


class NearbyResult(BaseModel):
    poi_id: str
    name: str
    primary_category: str
    secondary_categories: list[str]
    category_match_type: CategoryMatchType | None = None
    coordinates: list[float]
    short_description: str
    distance_from_center_meters: int
    estimated_access_m: int
    estimated_access_minutes: int
    score: float
    score_breakdown: dict[str, float] | None = None
    why_it_matters: list[str]
    badges: list[str]


class NearbySuggestResponse(BaseModel):
    query_summary: NearbyQuerySummary
    results: list[NearbyResult]


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
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    themes: list[POIThemeItem] = Field(default_factory=list)


class AdminPOIItem(BaseModel):
    poi_id: str
    name: str
    city: str
    status: str
    primary_category: str
    notes: str


class AdminPOIAliasItem(BaseModel):
    alias_name: str
    normalized_alias: str
    alias_type: str
    source: str
    confidence: float
    is_preferred: bool
    notes: str | None = None
    created_at: datetime


class AdminPOIEvidenceItem(BaseModel):
    source_id: str
    source_name: str | None = None
    source_type: str | None = None
    trust_class: str | None = None
    evidence_type: str
    label: str | None = None
    text: str | None = None
    url: str | None = None
    external_record_id: str | None = None
    confidence: float
    match_method: str | None = None
    observed_at: datetime


class AdminPOIEvidenceResponse(BaseModel):
    poi_id: str
    name: str
    primary_category: str
    aliases: list[AdminPOIAliasItem]
    evidence: list[AdminPOIEvidenceItem]
    themes: list[POIThemeItem] = Field(default_factory=list)


class AdminThemeSummaryItem(BaseModel):
    theme_slug: ThemeSlug
    label: str
    is_query_active: bool
    automated_accepted_count: int
    automated_candidate_count: int
    reviewed_count: int
    unreviewed_count: int
    stale_count: int
    force_included_count: int
    force_excluded_count: int


class AdminThemeMembershipQueueItem(BaseModel):
    poi_id: str
    poi_name: str
    city: str
    primary_category: str
    theme_slug: ThemeSlug
    theme_label: str
    automated_status: str | None = None
    automated_assignment_basis: str | None = None
    automated_confidence: float | None = None
    evidence_count: int = 0
    computed_at: datetime | None = None
    editorial_decision: str | None = None
    review_state: str
    reviewed_at: datetime | None = None
    effective_status: str | None = None


class AdminThemeAutomatedMembership(BaseModel):
    status: str
    assignment_basis: str
    confidence: float
    rationale_summary: str | None = None
    computed_at: datetime
    evidence: list[ThemeEvidenceReference] = Field(default_factory=list)


class AdminThemeEditorialRecord(BaseModel):
    editorial_decision: ThemeEditorialDecision | None = None
    notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    reviewed_membership_computed_at: datetime | None = None


class AdminThemeEffectiveOutcome(BaseModel):
    status: str
    assignment_basis: str
    confidence: float
    rationale_summary: str | None = None


class AdminThemeMembershipDetailResponse(BaseModel):
    poi_id: str
    poi_name: str
    city: str
    primary_category: str
    theme_slug: ThemeSlug
    theme_label: str
    is_query_active: bool
    automated_membership: AdminThemeAutomatedMembership | None = None
    editorial_record: AdminThemeEditorialRecord | None = None
    effective_outcome: AdminThemeEffectiveOutcome | None = None


class AdminThemeReviewRequest(BaseModel):
    editorial_decision: ThemeEditorialDecision | None = None
    notes: str | None = None
    reviewed_by: str | None = None


class AdminThemeReviewResponse(BaseModel):
    poi_id: str
    theme_slug: ThemeSlug
    reviewed: bool
    detail: AdminThemeMembershipDetailResponse


class AdminMatchDiagnosticItem(BaseModel):
    id: int
    source_id: str
    source_name: str | None = None
    source_type: str | None = None
    region: str
    external_record_id: str | None = None
    external_name: str
    normalized_name: str
    best_candidate_poi_id: str | None = None
    best_candidate_name: str | None = None
    resolved_poi_id: str | None = None
    resolved_poi_name: str | None = None
    best_similarity: float | None = None
    match_strategy: str | None = None
    resolution_method: str | None = None
    why_not_auto_linked: str
    status: str
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminResolveDiagnosticRequest(BaseModel):
    poi_id: str
    reviewed_by: str | None = None


class AdminAliasFromDiagnosticRequest(BaseModel):
    poi_id: str
    alias_name: str | None = None
    alias_type: str = "register_variant"
    is_preferred: bool = False
    notes: str | None = None
    reviewed_by: str | None = None


class AdminSuppressDiagnosticRequest(BaseModel):
    reviewed_by: str | None = None


class AdminCreateAliasRequest(BaseModel):
    alias_name: str
    alias_type: str = "manual"
    is_preferred: bool = False
    notes: str | None = None


class AdminAliasMutationResponse(BaseModel):
    poi_id: str
    alias: AdminPOIAliasItem
    created: bool


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
