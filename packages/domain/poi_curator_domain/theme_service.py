from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from poi_curator_domain.db import POIThemeMembership, POIThemeMembershipEvidence
from poi_curator_domain.themes import ThemeAssignmentBasis, ThemeSlug, ThemeStatus

if TYPE_CHECKING:
    from poi_curator_domain.db import POI


WATER_SYNC_THEMES: tuple[ThemeSlug, ...] = ("water",)
_WATER_EVIDENCE_TOKENS = ("acequia", "canal", "irrigation", "river", "water")


@dataclass(frozen=True)
class EvaluatedThemeMembership:
    theme_slug: ThemeSlug
    status: ThemeStatus
    assignment_basis: ThemeAssignmentBasis
    confidence: float
    rationale_summary: str
    evidence_ids: tuple[int, ...]


def evaluate_water_theme(poi: POI) -> EvaluatedThemeMembership | None:
    raw_tags = {str(key): str(value) for key, value in (poi.raw_tag_summary_json or {}).items()}
    normalized_category = str(getattr(poi, "normalized_category", "") or "")
    normalized_subcategory = str(getattr(poi, "normalized_subcategory", "") or "")
    canonical_name = str(getattr(poi, "canonical_name", "") or "")
    lowered_name = canonical_name.casefold()
    alias_names = [
        str(getattr(alias, "alias_name", "") or "").casefold()
        for alias in getattr(poi, "aliases", []) or []
    ]

    reasons: list[str] = []
    confidence = 0.0
    has_direct_rule = False

    if raw_tags.get("man_made") == "canal":
        has_direct_rule = True
        confidence += 0.7
        reasons.append("OSM marks this place as a canal trace")

    waterway_value = raw_tags.get("waterway")
    if waterway_value is not None:
        has_direct_rule = True
        confidence += 0.65
        reasons.append(f"OSM waterway signal is present ({waterway_value})")

    has_acequia_name = "acequia" in lowered_name or any("acequia" in alias for alias in alias_names)
    if has_acequia_name and _supports_name_only_water_read(normalized_category, normalized_subcategory):
        has_direct_rule = True
        confidence += 0.65
        reasons.append("Canonical or alias naming explicitly references an acequia")

    if normalized_subcategory == "trail_river_access" and waterway_value is not None:
        confidence += 0.1
        reasons.append("Subtype reinforces a water-access reading")
    elif normalized_subcategory == "infrastructure_landmark" and has_direct_rule:
        confidence += 0.05
        reasons.append("Infrastructure subtype fits a water-systems interpretation")

    evidence_ids = _matching_water_evidence_ids(poi)
    if evidence_ids:
        confidence += min(0.2, 0.1 * len(evidence_ids))
        reasons.append("Linked evidence references water corridor terms")

    if not has_direct_rule:
        return None

    confidence = round(min(confidence, 0.95), 2)
    return EvaluatedThemeMembership(
        theme_slug="water",
        status="accepted" if confidence >= 0.6 else "candidate",
        assignment_basis="mixed" if evidence_ids else "rule",
        confidence=confidence,
        rationale_summary="; ".join(dict.fromkeys(reasons)),
        evidence_ids=tuple(evidence_ids),
    )


def evaluate_theme_memberships(poi: POI) -> dict[ThemeSlug, EvaluatedThemeMembership]:
    editorial_by_theme = {
        str(item.theme_slug): item for item in getattr(poi, "theme_editorials", []) or []
    }
    results: dict[ThemeSlug, EvaluatedThemeMembership] = {}

    water_editorial = editorial_by_theme.get("water")
    if water_editorial is not None and water_editorial.editorial_decision == "force_exclude":
        return results

    water_membership = evaluate_water_theme(poi)
    if water_editorial is not None and water_editorial.editorial_decision == "force_include":
        note = water_editorial.notes or "Included by editorial review."
        evidence_ids = water_membership.evidence_ids if water_membership is not None else ()
        results["water"] = EvaluatedThemeMembership(
            theme_slug="water",
            status="accepted",
            assignment_basis="editorial" if water_membership is None else "mixed",
            confidence=1.0 if water_membership is None else max(water_membership.confidence, 0.9),
            rationale_summary=note,
            evidence_ids=evidence_ids,
        )
        return results

    if water_membership is not None:
        results["water"] = water_membership
    return results


def sync_theme_memberships(
    session: Session,
    pois: list[POI],
) -> bool:
    changed = False
    seen_poi_ids: set[str] = set()
    for poi in pois:
        if poi.poi_id in seen_poi_ids:
            continue
        seen_poi_ids.add(poi.poi_id)
        changed = _sync_single_poi(session, poi) or changed
    if changed:
        session.flush()
    return changed


def _sync_single_poi(session: Session, poi: POI) -> bool:
    changed = False
    evaluated = evaluate_theme_memberships(poi)
    membership_by_slug = {
        str(membership.theme_slug): membership for membership in getattr(poi, "theme_memberships", []) or []
    }

    for theme_slug in WATER_SYNC_THEMES:
        evaluation = evaluated.get(theme_slug)
        membership = membership_by_slug.get(theme_slug)
        if evaluation is None:
            if membership is not None:
                if membership in poi.theme_memberships:
                    poi.theme_memberships.remove(membership)
                session.delete(membership)
                changed = True
            continue

        if membership is None:
            membership = POIThemeMembership(
                poi=poi,
                theme_slug=theme_slug,
                status=evaluation.status,
                assignment_basis=evaluation.assignment_basis,
                confidence=evaluation.confidence,
                rationale_summary=evaluation.rationale_summary,
                computed_at=datetime.now(UTC),
            )
            session.add(membership)
            changed = True
        else:
            if (
                membership.status != evaluation.status
                or membership.assignment_basis != evaluation.assignment_basis
                or round(float(membership.confidence), 2) != evaluation.confidence
                or membership.rationale_summary != evaluation.rationale_summary
            ):
                changed = True
            membership.status = evaluation.status
            membership.assignment_basis = evaluation.assignment_basis
            membership.confidence = evaluation.confidence
            membership.rationale_summary = evaluation.rationale_summary
            membership.computed_at = datetime.now(UTC)

        changed = _sync_membership_evidence(
            membership,
            evaluation.evidence_ids,
        ) or changed

    return changed


def _sync_membership_evidence(
    membership: POIThemeMembership,
    evidence_ids: tuple[int, ...],
) -> bool:
    changed = False
    existing_links = {link.poi_evidence_id: link for link in membership.evidence_links}
    desired_ids = set(evidence_ids)

    for evidence_id, link in list(existing_links.items()):
        if evidence_id not in desired_ids:
            membership.evidence_links.remove(link)
            changed = True

    for evidence_id in evidence_ids:
        if evidence_id in existing_links:
            continue
        membership.evidence_links.append(
            POIThemeMembershipEvidence(
                poi_evidence_id=evidence_id,
                contribution_type="corroborating",
                weight=1.0,
            )
        )
        changed = True
    return changed


def _matching_water_evidence_ids(poi: POI) -> list[int]:
    evidence_ids: list[int] = []
    for evidence in getattr(poi, "evidence_items", []) or []:
        text_parts = [
            str(getattr(evidence, "evidence_label", "") or ""),
            str(getattr(evidence, "evidence_text", "") or ""),
            str(getattr(evidence, "evidence_url", "") or ""),
            str(getattr(evidence, "external_record_id", "") or ""),
            str(getattr(evidence, "raw_evidence_json", "") or ""),
        ]
        haystack = " ".join(part.casefold() for part in text_parts if part)
        if any(token in haystack for token in _WATER_EVIDENCE_TOKENS):
            evidence_ids.append(int(evidence.id))
    return evidence_ids


def _supports_name_only_water_read(normalized_category: str, normalized_subcategory: str) -> bool:
    if normalized_subcategory in {"infrastructure_landmark", "trail_river_access"}:
        return True
    return normalized_category in {"civic", "scenic"}
