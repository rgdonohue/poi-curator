from datetime import datetime
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from poi_curator_domain.themes import ThemeEditorialDecision, ThemeSlug, is_query_theme_active


class GeoLineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(min_length=2)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) < 2:
            raise ValueError("LineString must contain at least 2 coordinate pairs.")
        for index, coordinate in enumerate(value):
            validate_lon_lat_coordinate(coordinate, label=f"route coordinate {index}")
        return value


class NamedPoint(BaseModel):
    name: str
    coordinates: list[float] = Field(min_length=2, max_length=2)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[float]) -> list[float]:
        validate_lon_lat_coordinate(value, label="point coordinates")
        return value


class LatLonPoint(BaseModel):
    lat: float
    lon: float

    @model_validator(mode="after")
    def validate_lat_lon(self) -> "LatLonPoint":
        validate_lon_lat_values(self.lon, self.lat, label="center point")
        return self


def validate_lon_lat_coordinate(coordinate: list[float], *, label: str) -> None:
    if len(coordinate) != 2:
        raise ValueError(f"{label} must contain exactly [longitude, latitude].")
    validate_lon_lat_values(coordinate[0], coordinate[1], label=label)


def validate_lon_lat_values(lon: float, lat: float, *, label: str) -> None:
    if not isfinite(lon) or not isfinite(lat):
        raise ValueError(f"{label} must contain finite longitude and latitude values.")
    if lon < -180 or lon > 180:
        raise ValueError(f"{label} longitude must be between -180 and 180.")
    if lat < -90 or lat > 90:
        raise ValueError(f"{label} latitude must be between -90 and 90.")


TravelMode = Literal["driving", "walking"]
PublicCategory = Literal["history", "culture", "art", "scenic", "food", "civic", "mixed"]
CategoryMatchType = Literal["primary", "secondary", "mixed"]
DataSource = Literal["database", "fixture_fallback"]


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


PlaceForm = Literal["corridor", "area"]
EncounterMode = Literal["along_corridor", "within_area"]
EncounterAnchorKind = Literal["encounter", "segment", "center"]


class EncounterAnchor(BaseModel):
    label: str
    coordinates: list[float] = Field(min_length=2, max_length=2)
    kind: EncounterAnchorKind
    is_primary: bool = False


class ExtendedPlaceContext(BaseModel):
    place_form: PlaceForm
    encounter_mode: EncounterMode
    display_hint: str | None = None
    encounter_anchors: list[EncounterAnchor] = Field(default_factory=list)


class RouteResult(BaseModel):
    data_source: DataSource
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
    extended_place: ExtendedPlaceContext | None = None


class RouteSuggestResponse(BaseModel):
    data_source: DataSource
    query_summary: QuerySummary
    results: list[RouteResult]


class NearbyResult(BaseModel):
    data_source: DataSource
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
    extended_place: ExtendedPlaceContext | None = None


class NearbySuggestResponse(BaseModel):
    data_source: DataSource
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
    extended_place: ExtendedPlaceContext | None = None


class AdminPOIItem(BaseModel):
    poi_id: str
    name: str
    city: str
    status: str
    primary_category: str
    notes: str


class AdminPOIListItem(BaseModel):
    poi_id: str
    name: str
    primary_category: str
    secondary_categories: list[str]
    review_state: str
    source: str
    themes: list[str]
    last_updated: datetime
    coordinates: list[float] | None = None
    has_diagnostics: bool
    has_editorial_overrides: bool
    is_active: bool
    stale_since: datetime | None = None


class AdminPOIListResponse(BaseModel):
    items: list[AdminPOIListItem]
    total: int
    limit: int
    offset: int


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


class AdminPOIDetailEvidenceItem(BaseModel):
    evidence_id: int
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
    raw_payload: dict[str, Any] | None = None


class AdminPOIEditorialOverrideItem(BaseModel):
    value: Any
    source_value: Any = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class AdminPOIDetailMatchDiagnosticItem(BaseModel):
    id: int
    source_id: str
    source_name: str | None = None
    source_type: str | None = None
    external_record_id: str | None = None
    external_name: str
    best_candidate_poi_id: str | None = None
    best_candidate_name: str | None = None
    resolved_poi_id: str | None = None
    resolved_poi_name: str | None = None
    best_similarity: float | None = None
    match_strategy: str | None = None
    resolution_method: str | None = None
    why_not_auto_linked: str
    state: str
    reviewer_notes: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminPOIDetailResponse(BaseModel):
    poi_id: str
    canonical: POIDetailResponse
    editorial_overrides: dict[str, AdminPOIEditorialOverrideItem]
    aliases: list[AdminPOIAliasItem]
    evidence: list[AdminPOIDetailEvidenceItem]
    themes: list[POIThemeItem] = Field(default_factory=list)
    match_diagnostics: list[AdminPOIDetailMatchDiagnosticItem] = Field(default_factory=list)
    external_links: dict[str, str]
    last_updated: datetime


class AdminFieldProvenanceItem(BaseModel):
    id: int
    field_name: str
    source_id: str
    value: Any
    confidence: float
    observed_at: datetime
    is_canonical: bool


class AdminPOIProvenanceResponse(BaseModel):
    poi_id: str
    name: str
    fields: dict[str, list[AdminFieldProvenanceItem]]
    conflicts: dict[str, list[AdminFieldProvenanceItem]] = Field(default_factory=dict)


class AdminConflictItem(BaseModel):
    poi_id: str
    name: str
    field_name: str
    canonical_value: Any | None = None
    sources: list[str]
    values: list[AdminFieldProvenanceItem]
    last_observed_at: datetime


class AdminConflictListResponse(BaseModel):
    items: list[AdminConflictItem]
    total: int
    limit: int
    offset: int


class AdminCoverageResponse(BaseModel):
    by_source: dict[str, int]
    by_source_pair: dict[str, int]
    single_source_gaps: dict[str, int]
    total_pois: int


class AdminMatchLogItem(BaseModel):
    id: int
    canonical_poi_id: str | None = None
    canonical_name: str | None = None
    candidate_source: str
    candidate_external_id: str | None = None
    match_strategy: str
    match_score: float | None = None
    decision: str
    decided_at: datetime
    decided_by: str | None = None
    notes: str | None = None


class AdminMatchLogListResponse(BaseModel):
    items: list[AdminMatchLogItem]
    total: int
    limit: int
    offset: int


class AdminPOIMapFeatureGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float]


class AdminPOIMapFeatureProperties(BaseModel):
    poi_id: str
    name: str
    primary_category: str
    review_state: str
    source: str
    themes: list[str]
    has_diagnostics: bool
    has_editorial_overrides: bool
    is_active: bool
    stale_since: datetime | None = None


class AdminPOIMapFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: AdminPOIMapFeatureGeometry
    properties: AdminPOIMapFeatureProperties


class AdminPOIMapFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[AdminPOIMapFeature]


class AdminPOIMapResponse(BaseModel):
    feature_collection: AdminPOIMapFeatureCollection
    total_matching: int
    returned: int
    truncated: bool
    limit: int


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


class QueryLogResultItem(BaseModel):
    poi_id: str
    score: float
    score_breakdown: dict[str, float] | None = None
    rank: int


class QueryLogItem(BaseModel):
    id: str
    timestamp: datetime
    endpoint: str
    request_payload: dict[str, Any]
    scoring_profile_version: str
    data_source: DataSource
    result_count: int
    results: list[QueryLogResultItem]
    duration_ms: int


class QueryLogListResponse(BaseModel):
    items: list[QueryLogItem]
    total: int
    limit: int
    offset: int
