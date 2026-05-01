from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from poi_curator_domain.db import POI, POIEvidence, POISignals
from poi_curator_domain.theme_service import sync_theme_memberships


@dataclass(frozen=True)
class EvidenceSignalSummary:
    has_official_heritage_match: bool
    official_corroboration_score: float
    district_membership_score: float
    institutional_identity_score: float


def recompute_evidence_signals(session: Session, pois: list[POI]) -> None:
    if not pois:
        return
    poi_ids = [poi.poi_id for poi in pois]
    evidence_rows = session.execute(
        select(POIEvidence).where(POIEvidence.poi_id.in_(poi_ids))
    ).scalars().all()
    evidence_by_poi: dict[str, list[POIEvidence]] = {poi_id: [] for poi_id in poi_ids}
    for evidence in evidence_rows:
        evidence_by_poi[evidence.poi_id].append(evidence)

    for poi in pois:
        signals = poi.signals
        if signals is None:
            signals = POISignals(
                poi_id=poi.poi_id,
                computed_at=datetime.now(UTC),
            )
            session.add(signals)
            poi.signals = signals

        evidence_summary = summarize_evidence_signals(evidence_by_poi.get(poi.poi_id, []))
        signals.has_official_heritage_match = evidence_summary.has_official_heritage_match
        signals.official_corroboration_score = evidence_summary.official_corroboration_score
        signals.district_membership_score = evidence_summary.district_membership_score
        signals.institutional_identity_score = evidence_summary.institutional_identity_score
        signals.local_identity_score = max(
            signals.local_identity_score,
            (
                0.4
                + signals.district_membership_score * 0.3
                + signals.institutional_identity_score * 0.3
            ),
        )
        signals.editorial_priority_seed = max(
            signals.editorial_priority_seed,
            0.4 + signals.official_corroboration_score * 0.4,
        )
        signals.computed_at = datetime.now(UTC)
    sync_theme_memberships(session, pois)


def summarize_evidence_signals(evidence_rows: list[POIEvidence]) -> EvidenceSignalSummary:
    official = 0.0
    district = 0.0
    institutional = 0.0
    has_official_heritage_match = False
    for evidence in evidence_rows:
        if evidence.evidence_type == "historic_building_status":
            official += 0.9
            district += 0.45
            has_official_heritage_match = True
        elif evidence.evidence_type == "district_membership":
            official += 0.6
            district += 0.8
            has_official_heritage_match = True
        elif evidence.evidence_type == "boundary_membership":
            official += 0.35
            district += 0.7
        elif evidence.evidence_type == "institution_membership":
            official += 0.3
            institutional += 0.75
        elif evidence.evidence_type == "historic_designation":
            official += 1.0
            has_official_heritage_match = True
            category_of_property = str(
                (evidence.raw_evidence_json or {}).get("category_of_property", "")
            ).upper()
            if "DISTRICT" in category_of_property:
                district += 0.9
        elif evidence.evidence_type == "state_historic_designation":
            official += 0.8
            has_official_heritage_match = True
            category_of_property = str(
                (evidence.raw_evidence_json or {}).get("category_of_property", "")
            ).upper()
            if "DISTRICT" in category_of_property:
                district += 0.75
    return EvidenceSignalSummary(
        has_official_heritage_match=has_official_heritage_match,
        official_corroboration_score=min(1.0, official),
        district_membership_score=min(1.0, district),
        institutional_identity_score=min(1.0, institutional),
    )
