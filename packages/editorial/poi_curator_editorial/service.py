import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from poi_curator_domain.db import POI, OfficialMatchDiagnostic, POIAlias, POIEvidence
from poi_curator_domain.logging_utils import log_event
from poi_curator_domain.schemas import (
    AdminAliasFromDiagnosticRequest,
    AdminAliasMutationResponse,
    AdminCreateAliasRequest,
    AdminPOIAliasItem,
    AdminResolveDiagnosticRequest,
    AdminSuppressDiagnosticRequest,
)
from poi_curator_enrichment.pipeline import (
    build_nrhp_evidence,
    build_state_register_evidence,
    recompute_evidence_signals,
)
from poi_curator_scoring.query_service import build_admin_match_diagnostic_item
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

if TYPE_CHECKING:
    from poi_curator_domain.schemas import AdminMatchDiagnosticItem
    from poi_curator_enrichment.historic_register import HistoricRegisterRow


logger = logging.getLogger(__name__)


def resolve_match_diagnostic(
    db: Session,
    diagnostic_id: int,
    payload: AdminResolveDiagnosticRequest,
) -> "AdminMatchDiagnosticItem | None":
    diagnostic = load_diagnostic(db, diagnostic_id)
    if diagnostic is None:
        return None
    poi = db.get(POI, payload.poi_id)
    if poi is None:
        raise ValueError("POI not found.")
    ensure_editable_diagnostic(diagnostic, target_status="resolved", target_poi_id=poi.poi_id)
    upsert_official_evidence_from_diagnostic(
        db,
        diagnostic=diagnostic,
        poi=poi,
        resolution_method="manual_link",
    )
    apply_diagnostic_review(
        diagnostic,
        status="resolved",
        resolution_method="manual_link",
        resolved_poi_id=poi.poi_id,
        reviewed_by=payload.reviewed_by,
    )
    db.commit()
    log_event(
        logger,
        "diagnostic_resolved",
        diagnostic_id=diagnostic_id,
        poi_id=poi.poi_id,
        resolution_method="manual_link",
        reviewed_by=payload.reviewed_by,
    )
    refreshed = load_diagnostic(db, diagnostic_id)
    return build_admin_match_diagnostic_item(refreshed) if refreshed is not None else None


def create_alias_from_diagnostic(
    db: Session,
    diagnostic_id: int,
    payload: AdminAliasFromDiagnosticRequest,
) -> "AdminMatchDiagnosticItem | None":
    diagnostic = load_diagnostic(db, diagnostic_id)
    if diagnostic is None:
        return None
    poi = db.get(POI, payload.poi_id)
    if poi is None:
        raise ValueError("POI not found.")
    ensure_editable_diagnostic(diagnostic, target_status="resolved", target_poi_id=poi.poi_id)
    alias_name = payload.alias_name or diagnostic.external_name
    ensure_alias(
        db,
        poi=poi,
        alias_name=alias_name,
        alias_type=payload.alias_type,
        source="manual_diagnostic_resolution",
        confidence=1.0,
        is_preferred=payload.is_preferred,
        notes=payload.notes,
    )
    upsert_official_evidence_from_diagnostic(
        db,
        diagnostic=diagnostic,
        poi=poi,
        resolution_method="manual_alias",
    )
    apply_diagnostic_review(
        diagnostic,
        status="resolved",
        resolution_method="manual_alias",
        resolved_poi_id=poi.poi_id,
        reviewed_by=payload.reviewed_by,
    )
    db.commit()
    log_event(
        logger,
        "diagnostic_alias_created",
        diagnostic_id=diagnostic_id,
        poi_id=poi.poi_id,
        alias_name=alias_name,
        reviewed_by=payload.reviewed_by,
    )
    refreshed = load_diagnostic(db, diagnostic_id)
    return build_admin_match_diagnostic_item(refreshed) if refreshed is not None else None


def suppress_match_diagnostic(
    db: Session,
    diagnostic_id: int,
    payload: AdminSuppressDiagnosticRequest,
) -> "AdminMatchDiagnosticItem | None":
    diagnostic = load_diagnostic(db, diagnostic_id)
    if diagnostic is None:
        return None
    ensure_editable_diagnostic(diagnostic, target_status="suppressed", target_poi_id=None)
    apply_diagnostic_review(
        diagnostic,
        status="suppressed",
        resolution_method="suppressed",
        resolved_poi_id=None,
        reviewed_by=payload.reviewed_by,
    )
    db.commit()
    log_event(
        logger,
        "diagnostic_suppressed",
        diagnostic_id=diagnostic_id,
        reviewed_by=payload.reviewed_by,
    )
    refreshed = load_diagnostic(db, diagnostic_id)
    return build_admin_match_diagnostic_item(refreshed) if refreshed is not None else None


def add_poi_alias(
    db: Session,
    poi_id: str,
    payload: AdminCreateAliasRequest,
) -> AdminAliasMutationResponse | None:
    poi = db.scalar(select(POI).where(POI.poi_id == poi_id).options(joinedload(POI.aliases)))
    if poi is None:
        return None
    alias, created = ensure_alias(
        db,
        poi=poi,
        alias_name=payload.alias_name,
        alias_type=payload.alias_type,
        source="manual_editorial",
        confidence=1.0,
        is_preferred=payload.is_preferred,
        notes=payload.notes,
    )
    db.commit()
    log_event(
        logger,
        "poi_alias_added",
        poi_id=poi.poi_id,
        alias_name=alias.alias_name,
        created=created,
    )
    return AdminAliasMutationResponse(
        poi_id=poi.poi_id,
        alias=AdminPOIAliasItem(
            alias_name=alias.alias_name,
            normalized_alias=alias.normalized_alias,
            alias_type=alias.alias_type,
            source=alias.source,
            confidence=alias.confidence,
            is_preferred=alias.is_preferred,
            notes=alias.notes,
            created_at=alias.created_at,
        ),
        created=created,
    )


def load_diagnostic(db: Session, diagnostic_id: int) -> OfficialMatchDiagnostic | None:
    return db.scalar(
        select(OfficialMatchDiagnostic)
        .where(OfficialMatchDiagnostic.id == diagnostic_id)
        .options(
            joinedload(OfficialMatchDiagnostic.source),
            joinedload(OfficialMatchDiagnostic.poi),
            joinedload(OfficialMatchDiagnostic.resolved_poi),
        )
    )


def ensure_editable_diagnostic(
    diagnostic: OfficialMatchDiagnostic,
    *,
    target_status: str,
    target_poi_id: str | None,
) -> None:
    if diagnostic.status in {"resolved", "suppressed"}:
        same_resolution = (
            diagnostic.status == target_status and diagnostic.resolved_poi_id == target_poi_id
        )
        if same_resolution:
            return
        raise ValueError("Diagnostic row has already been reviewed.")


def apply_diagnostic_review(
    diagnostic: OfficialMatchDiagnostic,
    *,
    status: str,
    resolution_method: str,
    resolved_poi_id: str | None,
    reviewed_by: str | None,
) -> None:
    now = datetime.now(UTC)
    diagnostic.status = status
    diagnostic.resolution_method = resolution_method
    diagnostic.resolved_poi_id = resolved_poi_id
    diagnostic.reviewed_at = now
    diagnostic.reviewed_by = reviewed_by
    diagnostic.updated_at = now


def ensure_alias(
    db: Session,
    *,
    poi: POI,
    alias_name: str,
    alias_type: str,
    source: str,
    confidence: float,
    is_preferred: bool,
    notes: str | None,
) -> tuple[POIAlias, bool]:
    from poi_curator_enrichment.historic_register import normalize_historic_name

    normalized_alias = normalize_historic_name(alias_name, relaxed=False)
    for alias in poi.aliases:
        if alias.normalized_alias == normalized_alias:
            return alias, False
    conflicting_alias = db.scalar(
        select(POIAlias)
        .where(POIAlias.normalized_alias == normalized_alias, POIAlias.poi_id != poi.poi_id)
    )
    if conflicting_alias is not None:
        raise ValueError("Alias already exists on a different POI.")
    alias = POIAlias(
        poi=poi,
        alias_name=alias_name,
        normalized_alias=normalized_alias,
        alias_type=alias_type,
        source=source,
        confidence=confidence,
        is_preferred=is_preferred,
        notes=notes,
        created_at=datetime.now(UTC),
    )
    db.add(alias)
    db.flush()
    return alias, True


def upsert_official_evidence_from_diagnostic(
    db: Session,
    *,
    diagnostic: OfficialMatchDiagnostic,
    poi: POI,
    resolution_method: str,
) -> None:
    from poi_curator_enrichment.historic_register import (
        NM_STATE_REGISTER_SOURCE_ID,
        NRHP_SOURCE_ID,
    )

    row = historic_row_from_diagnostic(diagnostic)
    if diagnostic.source_id == NRHP_SOURCE_ID:
        evidence = build_nrhp_evidence(
            row,
            poi.poi_id,
            1.0,
            match_strategy=resolution_method,
        )
    elif diagnostic.source_id == NM_STATE_REGISTER_SOURCE_ID:
        evidence = build_state_register_evidence(
            row,
            poi.poi_id,
            1.0,
            match_strategy=resolution_method,
        )
    else:
        return

    existing = db.scalar(
        select(POIEvidence).where(POIEvidence.evidence_key == evidence.evidence_key)
    )
    if existing is None:
        db.add(evidence)
    else:
        existing.poi_id = evidence.poi_id
        existing.evidence_type = evidence.evidence_type
        existing.evidence_label = evidence.evidence_label
        existing.evidence_text = evidence.evidence_text
        existing.evidence_url = evidence.evidence_url
        existing.external_record_id = evidence.external_record_id
        existing.confidence = evidence.confidence
        existing.raw_evidence_json = evidence.raw_evidence_json
        existing.observed_at = evidence.observed_at
    if diagnostic.source_id == NRHP_SOURCE_ID and row.reference_number:
        poi.heritage_id = row.reference_number
    recompute_evidence_signals(db, [poi])


def historic_row_from_diagnostic(diagnostic: OfficialMatchDiagnostic) -> "HistoricRegisterRow":
    from poi_curator_enrichment.historic_register import HistoricRegisterRow

    raw = diagnostic.raw_payload_json or {}
    return HistoricRegisterRow(
        reference_number=diagnostic.external_record_id or "",
        property_name=diagnostic.external_name,
        state=str(raw.get("state") or ""),
        county=str(raw.get("county") or ""),
        city=str(raw.get("city") or diagnostic.region),
        street_address=str(raw.get("street_address") or ""),
        category_of_property=str(raw.get("category_of_property") or ""),
        listed_date=str(raw.get("listed_date") or ""),
        external_link=None,
        other_names=(
            str(raw["other_names"])
            if raw.get("other_names") is not None and str(raw.get("other_names")).strip()
            else None
        ),
        state_register_year=(
            str(raw["state_register_year"])
            if raw.get("state_register_year") is not None
            and str(raw.get("state_register_year")).strip()
            else None
        ),
    )
