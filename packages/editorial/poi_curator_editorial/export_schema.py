"""Versioned schema validation for the Detour export CSV rows and manifest.

This module is the executable form of the column and manifest contracts in
docs/INTEGRATION_CONTRACT.md. Changes here and changes to that document must
land together. Existing CSV columns are never renamed, dropped, or reordered
under ROW_SCHEMA_VERSION 1; additive columns require a version bump.
"""

from __future__ import annotations

from math import isfinite
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

ROW_SCHEMA_VERSION = 1

# Santa Fe bounding box (gate contract).
BBOX = {"lon_min": -106.10, "lon_max": -105.80, "lat_min": 35.55, "lat_max": 35.78}

DETOUR_REQUIRED_COLUMNS = [
    "poi_id",
    "dedupe_key",
    "name",
    "lon",
    "lat",
    "primary_category",
    "display_priority",
    "quality_score",
    "walk_affinity_hint",
    "drive_affinity_hint",
    "wikipedia_title",
    "short_description",
    "description_map_v1",
    "description_card_v1",
    "description_subcategory_v1",
    "description_confidence_v1",
    "description_basis_v1",
    "address",
]

DETOUR_OPTIONAL_COLUMNS = [
    "evidence_sources",
    "preferred_aliases",
    "active_themes",
]

GOVERNANCE_COLUMNS = [
    "record_origin",
    "source_basis",
    "evidence_strength",
    "description_status",
    "description_method",
    "description_review_status",
    "claim_basis",
    "risk_flags",
]

AUDIT_COLUMNS = ["merged_from", "merge_reason"]

EXPORT_COLUMNS = (
    DETOUR_REQUIRED_COLUMNS + DETOUR_OPTIONAL_COLUMNS + GOVERNANCE_COLUMNS + AUDIT_COLUMNS
)

# Public categories present in Detour exports (food/mixed are query-time only).
EXPORT_CATEGORIES = {"history", "art", "scenic", "culture", "civic"}

CONFIDENCE_VALUES = {"high", "medium", "low"}

# Governance vocabularies (docs/DATA_QUALITY_GOVERNANCE.md, export governance).
RECORD_ORIGINS = {"database", "fixture_overlay", "manual_export", "test_fixture"}
EVIDENCE_STRENGTHS = {"high", "medium", "low", "unknown"}
DESCRIPTION_STATUSES = {"none", "source", "generated_draft", "editorial_approved"}
DESCRIPTION_METHODS = {
    "source_import",
    "deterministic_draft",
    "model_draft",
    "model_draft_batch",
    "editorial",
}
DESCRIPTION_REVIEW_STATUSES = {"unreviewed", "needs_revision", "approved", "rejected"}

# Producer vocabulary from build_description_risk_flags plus synthetic labeling.
RISK_FLAG_TOKENS = {
    "synthetic_fixture",
    "missing_name",
    "low_confidence",
    "low_evidence",
    "category_fallback",
    "culture_sensitivity",
    "history_sensitivity",
    "civic_sensitivity",
}

MERGE_REASONS = {"osm_relation_members", "name+proximity"}

MAX_REPORTED_ERRORS = 20


class ExportSchemaError(ValueError):
    """The export rows or manifest violate the versioned Detour contract."""


def _split_pipe(value: str) -> list[str]:
    return [part for part in (item.strip() for item in value.split("|")) if part]


class DetourExportRow(BaseModel):
    """One delivery CSV row under ROW_SCHEMA_VERSION 1. Values arrive as CSV strings."""

    model_config = ConfigDict(extra="forbid")

    poi_id: str = Field(min_length=1)
    dedupe_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    lon: float
    lat: float
    primary_category: str
    display_priority: int = Field(ge=0)
    quality_score: float
    walk_affinity_hint: float = Field(ge=0.0, le=1.0)
    drive_affinity_hint: float = Field(ge=0.0, le=1.0)
    wikipedia_title: str = ""
    short_description: str = ""
    description_map_v1: str = ""
    description_card_v1: str = ""
    description_subcategory_v1: str = ""
    description_confidence_v1: str
    description_basis_v1: str = ""
    address: str = ""
    evidence_sources: str = ""
    preferred_aliases: str = ""
    active_themes: str = ""
    record_origin: str
    source_basis: str = ""
    evidence_strength: str
    description_status: str
    description_method: str
    description_review_status: str
    claim_basis: str = ""
    risk_flags: str = ""
    merged_from: str = ""
    merge_reason: str = ""

    @field_validator("primary_category")
    @classmethod
    def validate_primary_category(cls, value: str) -> str:
        if value not in EXPORT_CATEGORIES:
            raise ValueError(f"primary_category {value!r} not in {sorted(EXPORT_CATEGORIES)}")
        return value

    @field_validator("description_confidence_v1")
    @classmethod
    def validate_confidence(cls, value: str) -> str:
        if value not in CONFIDENCE_VALUES:
            raise ValueError(
                f"description_confidence_v1 {value!r} not in {sorted(CONFIDENCE_VALUES)}"
            )
        return value

    @field_validator("record_origin")
    @classmethod
    def validate_record_origin(cls, value: str) -> str:
        if value not in RECORD_ORIGINS:
            raise ValueError(f"record_origin {value!r} not in {sorted(RECORD_ORIGINS)}")
        return value

    @field_validator("evidence_strength")
    @classmethod
    def validate_evidence_strength(cls, value: str) -> str:
        if value not in EVIDENCE_STRENGTHS:
            raise ValueError(f"evidence_strength {value!r} not in {sorted(EVIDENCE_STRENGTHS)}")
        return value

    @field_validator("description_status")
    @classmethod
    def validate_description_status(cls, value: str) -> str:
        if value not in DESCRIPTION_STATUSES:
            raise ValueError(
                f"description_status {value!r} not in {sorted(DESCRIPTION_STATUSES)}"
            )
        return value

    @field_validator("description_method")
    @classmethod
    def validate_description_method(cls, value: str) -> str:
        if value not in DESCRIPTION_METHODS:
            raise ValueError(
                f"description_method {value!r} not in {sorted(DESCRIPTION_METHODS)}"
            )
        return value

    @field_validator("description_review_status")
    @classmethod
    def validate_description_review_status(cls, value: str) -> str:
        if value not in DESCRIPTION_REVIEW_STATUSES:
            raise ValueError(
                f"description_review_status {value!r} not in "
                f"{sorted(DESCRIPTION_REVIEW_STATUSES)}"
            )
        return value

    @field_validator("risk_flags")
    @classmethod
    def validate_risk_flags(cls, value: str) -> str:
        unknown = [token for token in _split_pipe(value) if token not in RISK_FLAG_TOKENS]
        if unknown:
            raise ValueError(f"unknown risk_flags tokens {unknown}")
        return value

    @model_validator(mode="after")
    def validate_row_invariants(self) -> DetourExportRow:
        if not isfinite(self.lon) or not isfinite(self.lat):
            raise ValueError("lon/lat must be finite")
        in_bbox = (
            BBOX["lon_min"] <= self.lon <= BBOX["lon_max"]
            and BBOX["lat_min"] <= self.lat <= BBOX["lat_max"]
        )
        if not in_bbox:
            raise ValueError(f"coordinates ({self.lon},{self.lat}) outside Santa Fe bbox")
        merged_from = _split_pipe(self.merged_from)
        merge_reasons = _split_pipe(self.merge_reason)
        if bool(merged_from) != bool(merge_reasons):
            raise ValueError(
                "audit columns inconsistent: merged_from and merge_reason must be "
                "both empty or both set"
            )
        unknown_reasons = [reason for reason in merge_reasons if reason not in MERGE_REASONS]
        if unknown_reasons:
            raise ValueError(f"unknown merge_reason tokens {unknown_reasons}")
        if self.record_origin == "fixture_overlay" and "synthetic_fixture" not in _split_pipe(
            self.risk_flags
        ):
            raise ValueError("fixture_overlay rows must carry the synthetic_fixture risk flag")
        return self


class ManifestSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows_before: int = Field(ge=0)
    rows_after: int = Field(ge=0)
    clusters_collapsed: int = Field(ge=0)
    clusters_left_colocated: int = Field(ge=0)
    review_candidates: int = Field(ge=0)


class DroppedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dedupe_key: str = Field(min_length=1)
    poi_id: str = Field(min_length=1)
    name: str
    lon: float
    lat: float


class CollapsedClusterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal["collapsed"]
    reason: str
    survivor_poi_id: str = Field(min_length=1)
    survivor_dedupe_key: str = Field(min_length=1)
    chosen_display_name: str
    alias_names: list[str]
    dropped: list[DroppedRow] = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if value not in MERGE_REASONS:
            raise ValueError(f"collapse reason {value!r} not in {sorted(MERGE_REASONS)}")
        return value


class LeftColocatedClusterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal["left_colocated"]
    members: list[str] = Field(min_length=2)


class ReviewCandidateClusterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal["review_candidate"]
    members: list[str] = Field(min_length=2)
    distance_m: float = Field(ge=0.0)


ClusterEntry = Annotated[
    CollapsedClusterEntry | LeftColocatedClusterEntry | ReviewCandidateClusterEntry,
    Field(discriminator="disposition"),
]


class ExcludedRowEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dedupe_key: str = Field(min_length=1)
    poi_id: str = Field(min_length=1)
    name: str
    lon: float
    lat: float
    reason: str = Field(min_length=1)


class DataQualityFlagEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dedupe_key: str = Field(min_length=1)
    issue: str = Field(min_length=1)


class ManifestClusterAccounting(BaseModel):
    """Shared summary-vs-clusters consistency for both manifest versions."""

    summary: ManifestSummary
    clusters: list[ClusterEntry]

    @model_validator(mode="after")
    def validate_cluster_counts(self) -> ManifestClusterAccounting:
        collapsed = sum(
            1 for entry in self.clusters if isinstance(entry, CollapsedClusterEntry)
        )
        left = sum(
            1 for entry in self.clusters if isinstance(entry, LeftColocatedClusterEntry)
        )
        review = sum(
            1 for entry in self.clusters if isinstance(entry, ReviewCandidateClusterEntry)
        )
        if collapsed != self.summary.clusters_collapsed:
            raise ValueError(
                f"summary.clusters_collapsed={self.summary.clusters_collapsed} but manifest "
                f"lists {collapsed} collapsed clusters"
            )
        if left != self.summary.clusters_left_colocated:
            raise ValueError(
                f"summary.clusters_left_colocated={self.summary.clusters_left_colocated} but "
                f"manifest lists {left} left_colocated clusters"
            )
        if review != self.summary.review_candidates:
            raise ValueError(
                f"summary.review_candidates={self.summary.review_candidates} but manifest "
                f"lists {review} review candidates"
            )
        return self


class DetourManifestV1(ManifestClusterAccounting):
    """Legacy committed delivery manifest (pre-CLI)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    excluded_rows: list[ExcludedRowEntry] = Field(default_factory=list)
    data_quality_flags: list[DataQualityFlagEntry] = Field(default_factory=list)


class ManifestInputArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: int | None = Field(default=None, ge=0)


class ManifestInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v1_csv: ManifestInputArtifact
    dispositions: ManifestInputArtifact


class DetourManifestV2(ManifestClusterAccounting):
    """CLI-stamped manifest with input-artifact provenance."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    contract: Literal["detour-export"]
    inputs: ManifestInputs
    excluded_rows: list[ExcludedRowEntry]
    data_quality_flags: list[DataQualityFlagEntry]


def _cap_errors(errors: list[str]) -> list[str]:
    if len(errors) > MAX_REPORTED_ERRORS:
        overflow = len(errors) - MAX_REPORTED_ERRORS
        return errors[:MAX_REPORTED_ERRORS] + [f"... and {overflow} more schema errors"]
    return errors


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "<row>"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def validate_export_header(header: list[str]) -> list[str]:
    if header == EXPORT_COLUMNS:
        return []
    missing = [column for column in EXPORT_COLUMNS if column not in header]
    unexpected = [column for column in header if column not in EXPORT_COLUMNS]
    detail: list[str] = []
    if missing:
        detail.append(f"missing {missing}")
    if unexpected:
        detail.append(f"unexpected {unexpected}")
    if not detail:
        detail.append("column order differs from the contract")
    return [
        f"header does not match export row schema v{ROW_SCHEMA_VERSION}: " + "; ".join(detail)
    ]


def validate_export_rows(header: list[str], rows: list[dict[str, str]]) -> list[str]:
    """Validate the CSV header and every row against ROW_SCHEMA_VERSION."""
    errors = validate_export_header(header)
    for index, row in enumerate(rows):
        try:
            DetourExportRow.model_validate(row)
        except ValidationError as exc:
            key = row.get("dedupe_key", "?")
            errors.append(f"row {index + 1} ({key}): {_format_validation_error(exc)}")
    return _cap_errors(errors)


def validate_manifest_payload(payload: dict[str, Any]) -> list[str]:
    """Validate a delivery manifest (legacy v1 or CLI-stamped v2)."""
    schema_version = payload.get("schema_version")
    model: type[DetourManifestV1] | type[DetourManifestV2]
    if schema_version == 1:
        model = DetourManifestV1
    elif schema_version == 2:
        model = DetourManifestV2
    else:
        return [f"unknown manifest schema_version: {schema_version!r}"]
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        return _cap_errors(
            [f"manifest (schema_version {schema_version}): {_format_validation_error(exc)}"]
        )
    return []
