from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Literal

from poi_curator_domain.db import POI, OfficialMatchDiagnostic, POIEvidence, POIMatchLog
from poi_curator_domain.text import normalize_name_tokens
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

MatchDecision = Literal["match", "ambiguous", "new"]

DEFAULT_MATCH_CONFIG: dict[str, float] = {
    "spatial_distance_threshold_m": 100.0,
    "name_similarity_threshold": 0.85,
}

@dataclass(frozen=True)
class IncomingSourceRecord:
    source_id: str
    external_id: str
    name: str
    lon: float | None
    lat: float | None
    region: str
    wikidata_id: str | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class MatchResult:
    decision: MatchDecision
    poi: POI | None
    strategy: str
    score: float | None
    candidate_count: int = 0
    notes: str | None = None


def match_incoming_record(
    session: Session,
    record: IncomingSourceRecord,
    *,
    config: dict[str, float] | None = None,
    decided_by: str = "ingest",
) -> MatchResult:
    match_config = {**DEFAULT_MATCH_CONFIG, **(config or {})}
    identifier_match = match_by_wikidata_id(session, record)
    if identifier_match is not None:
        result = MatchResult("match", identifier_match, "identifier:wikidata", 1.0)
        write_match_log(session, record, result, decided_by=decided_by)
        return result

    result = match_by_spatial_name(session, record, config=match_config)
    write_match_log(session, record, result, decided_by=decided_by)
    if result.decision == "ambiguous":
        write_ambiguity_diagnostic(session, record, result)
    return result


def match_by_wikidata_id(session: Session, record: IncomingSourceRecord) -> POI | None:
    if not record.wikidata_id:
        return None
    return session.scalar(
        select(POI)
        .outerjoin(POIEvidence, POIEvidence.poi_id == POI.poi_id)
        .where(
            or_(
                POI.wikidata_id == record.wikidata_id,
                (
                    (POIEvidence.source_id == "wikidata")
                    & (POIEvidence.external_record_id == record.wikidata_id)
                ),
            )
        )
        .limit(1)
    )


def match_by_spatial_name(
    session: Session,
    record: IncomingSourceRecord,
    *,
    config: dict[str, float],
) -> MatchResult:
    if record.lon is None or record.lat is None:
        return MatchResult("new", None, "no_coordinates", None, notes="No source coordinate.")

    pois = (
        session.execute(
            select(POI)
            .where(POI.city == record.region, POI.is_active.is_(True))
            .options(joinedload(POI.aliases))
        )
        .unique()
        .scalars()
        .all()
    )
    threshold_m = config["spatial_distance_threshold_m"]
    similarity_threshold = config["name_similarity_threshold"]
    candidates: list[tuple[POI, float, float]] = []
    for poi in pois:
        distance_m = approx_distance_m(record.lon, record.lat, poi)
        if distance_m > threshold_m:
            continue
        similarity = best_name_similarity(record.name, poi)
        if similarity >= similarity_threshold:
            candidates.append((poi, similarity, distance_m))

    candidates.sort(key=lambda item: (-item[1], item[2], item[0].poi_id))
    if len(candidates) == 1:
        poi, similarity, distance_m = candidates[0]
        return MatchResult(
            "match",
            poi,
            "spatial_name",
            round(similarity, 4),
            candidate_count=1,
            notes=f"distance_m={distance_m:.1f}",
        )
    if len(candidates) > 1:
        _, similarity, distance_m = candidates[0]
        return MatchResult(
            "ambiguous",
            None,
            "spatial_name",
            round(similarity, 4),
            candidate_count=len(candidates),
            notes=f"top_distance_m={distance_m:.1f}; candidates={len(candidates)}",
        )
    return MatchResult("new", None, "spatial_name", None, candidate_count=0)


def best_name_similarity(source_name: str, poi: POI) -> float:
    names = [poi.canonical_name]
    names.extend(alias.alias_name for alias in getattr(poi, "aliases", []) or [])
    return max(normalized_name_similarity(source_name, candidate_name) for candidate_name in names)


def normalized_name_similarity(left: str, right: str) -> float:
    left_tokens = normalize_name_tokens(left)
    right_tokens = normalize_name_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    ratio = SequenceMatcher(
        None,
        " ".join(sorted(left_tokens)),
        " ".join(sorted(right_tokens)),
    ).ratio()
    return max(overlap, ratio)


def approx_distance_m(lon: float, lat: float, poi: POI) -> float:
    from geoalchemy2.shape import to_shape

    point = to_shape(poi.centroid)
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(lat)) * lat_scale
    dx = (float(point.x) - lon) * lon_scale
    dy = (float(point.y) - lat) * lat_scale
    return math.hypot(dx, dy)


def write_match_log(
    session: Session,
    record: IncomingSourceRecord,
    result: MatchResult,
    *,
    decided_by: str,
) -> POIMatchLog:
    log = POIMatchLog(
        canonical_poi_id=result.poi.poi_id if result.poi is not None else None,
        candidate_source=record.source_id,
        candidate_external_id=record.external_id,
        match_strategy=result.strategy,
        match_score=result.score,
        decision=result.decision,
        decided_at=datetime.now(UTC),
        decided_by=decided_by,
        notes=result.notes,
    )
    session.add(log)
    return log


def write_ambiguity_diagnostic(
    session: Session,
    record: IncomingSourceRecord,
    result: MatchResult,
) -> OfficialMatchDiagnostic:
    now = datetime.now(UTC)
    diagnostic = OfficialMatchDiagnostic(
        source_id=record.source_id,
        region=record.region,
        external_record_id=record.external_id,
        external_name=record.name,
        matched_poi_id=None,
        resolved_poi_id=None,
        best_candidate_name=None,
        best_similarity=result.score,
        match_strategy=result.strategy,
        status="ambiguous",
        resolution_method=None,
        raw_payload_json={
            "candidate_count": result.candidate_count,
            "notes": result.notes,
            "record": record.raw_payload or {},
        },
        reviewed_at=None,
        reviewed_by=None,
        created_at=now,
        updated_at=now,
    )
    session.add(diagnostic)
    return diagnostic
