from __future__ import annotations

from typing import cast

from poi_curator_domain.db import POI, OfficialMatchDiagnostic, POIEvidence, POIThemeMembership
from poi_curator_domain.historic_register import normalize_historic_name
from poi_curator_domain.schemas import (
    AdminMatchDiagnosticItem,
    AdminThemeAutomatedMembership,
    AdminThemeEditorialRecord,
    AdminThemeEffectiveOutcome,
    AdminThemeMembershipDetailResponse,
    ThemeEvidenceReference,
)
from poi_curator_domain.theme_service import (
    get_theme_editorial_by_slug,
    get_theme_membership_by_slug,
    resolve_effective_theme_membership,
)
from poi_curator_domain.themes import (
    THEME_LABELS,
    ThemeEditorialDecision,
    ThemeSlug,
    is_query_theme_active,
)


def build_admin_match_diagnostic_item(
    item: OfficialMatchDiagnostic,
) -> AdminMatchDiagnosticItem:
    return AdminMatchDiagnosticItem(
        id=item.id,
        source_id=item.source_id,
        source_name=item.source.source_name if item.source is not None else None,
        source_type=item.source.source_type if item.source is not None else None,
        region=item.region,
        external_record_id=item.external_record_id,
        external_name=item.external_name,
        normalized_name=normalize_historic_name(item.external_name, relaxed=True),
        best_candidate_poi_id=item.matched_poi_id,
        best_candidate_name=(
            item.poi.canonical_name if item.poi is not None else item.best_candidate_name
        ),
        resolved_poi_id=item.resolved_poi_id,
        resolved_poi_name=(
            item.resolved_poi.canonical_name if item.resolved_poi is not None else None
        ),
        best_similarity=item.best_similarity,
        match_strategy=item.match_strategy,
        resolution_method=item.resolution_method,
        why_not_auto_linked=why_not_auto_linked(item),
        status=item.status,
        reviewed_at=item.reviewed_at,
        reviewed_by=item.reviewed_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def match_method_for_evidence(item: object) -> str | None:
    raw = getattr(item, "raw_evidence_json", None) or {}
    match_strategy = raw.get("match_strategy")
    if isinstance(match_strategy, str):
        return match_strategy
    return None


def why_not_auto_linked(item: OfficialMatchDiagnostic) -> str:
    if item.status == "resolved":
        target_name = (
            item.resolved_poi.canonical_name
            if item.resolved_poi is not None
            else item.best_candidate_name
        )
        resolution_method = item.resolution_method or "manual review"
        return f"Resolved manually to '{target_name}' via {resolution_method}."
    if item.status == "suppressed":
        return "Suppressed during editorial review."
    if item.best_candidate_name is None:
        return "No plausible canonical POI candidate was found."
    similarity = item.best_similarity or 0.0
    strategy = item.match_strategy or "fuzzy_fallback"
    return (
        f"Best candidate '{item.best_candidate_name}' via {strategy} scored "
        f"{similarity:.3f}, below the auto-link threshold."
    )


def build_admin_theme_membership_detail(
    poi: POI,
    theme_slug: str,
) -> AdminThemeMembershipDetailResponse:
    evidence_by_id = {item.id: item for item in getattr(poi, "evidence_items", []) or []}
    membership = get_theme_membership_by_slug(poi, theme_slug)
    editorial = get_theme_editorial_by_slug(poi, theme_slug)
    effective = resolve_effective_theme_membership(theme_slug, membership, editorial)

    automated_membership = None
    if membership is not None:
        automated_membership = AdminThemeAutomatedMembership(
            status=membership.status,
            assignment_basis=membership.assignment_basis,
            confidence=round(float(membership.confidence), 2),
            rationale_summary=membership.rationale_summary,
            computed_at=membership.computed_at,
            evidence=build_theme_evidence_references(membership, evidence_by_id),
        )

    editorial_record = None
    if editorial is not None:
        editorial_record = AdminThemeEditorialRecord(
            editorial_decision=cast(
                ThemeEditorialDecision | None,
                editorial.editorial_decision,
            ),
            notes=editorial.notes,
            reviewed_by=editorial.reviewed_by,
            reviewed_at=editorial.reviewed_at,
            reviewed_membership_computed_at=editorial.reviewed_membership_computed_at,
        )

    effective_outcome = None
    if effective is not None:
        effective_outcome = AdminThemeEffectiveOutcome(
            status=effective.status,
            assignment_basis=effective.assignment_basis,
            confidence=effective.confidence,
            rationale_summary=effective.rationale_summary,
        )

    return AdminThemeMembershipDetailResponse(
        poi_id=poi.poi_id,
        poi_name=poi.canonical_name,
        city=poi.city,
        primary_category=poi.normalized_category,
        theme_slug=cast(ThemeSlug, theme_slug),
        theme_label=THEME_LABELS.get(theme_slug, theme_slug),
        is_query_active=is_query_theme_active(theme_slug),
        automated_membership=automated_membership,
        editorial_record=editorial_record,
        effective_outcome=effective_outcome,
    )


def build_theme_evidence_references(
    membership: POIThemeMembership | None,
    evidence_by_id: dict[int, POIEvidence],
) -> list[ThemeEvidenceReference]:
    if membership is None:
        return []
    return [
        ThemeEvidenceReference(
            evidence_id=link.poi_evidence_id,
            source_id=evidence_by_id[link.poi_evidence_id].source_id,
            evidence_type=evidence_by_id[link.poi_evidence_id].evidence_type,
            label=evidence_by_id[link.poi_evidence_id].evidence_label,
            confidence=evidence_by_id[link.poi_evidence_id].confidence,
        )
        for link in sorted(
            getattr(membership, "evidence_links", []) or [],
            key=lambda item: item.poi_evidence_id,
        )
        if link.poi_evidence_id in evidence_by_id
    ]
