from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from geoalchemy2.shape import to_shape
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from poi_curator_domain.db import POI, POIFieldProvenance

CANONICAL_PROVENANCE_FIELDS = ("name", "primary_category", "coordinates", "short_description")
OSM_PROVENANCE_SOURCE_ID = "osm"


def canonical_field_values(poi: POI) -> dict[str, Any]:
    values: dict[str, Any] = {
        "name": poi.canonical_name,
        "primary_category": poi.normalized_category,
        "short_description": poi.short_description,
    }
    try:
        centroid = to_shape(poi.centroid)
        values["coordinates"] = {
            "lon": round(float(centroid.x), 7),
            "lat": round(float(centroid.y), 7),
        }
    except Exception:
        values["coordinates"] = None
    return values


def add_field_provenance(
    session: Session,
    *,
    poi_id: str,
    field_name: str,
    source_id: str,
    value: Any,
    confidence: float,
    observed_at: datetime | None = None,
    is_canonical: bool = False,
) -> POIFieldProvenance:
    observed = observed_at or datetime.now(UTC)
    if is_canonical and hasattr(session, "execute"):
        session.execute(
            update(POIFieldProvenance)
            .where(
                POIFieldProvenance.poi_id == poi_id,
                POIFieldProvenance.field_name == field_name,
            )
            .values(is_canonical=False)
        )
    row = POIFieldProvenance(
        poi_id=poi_id,
        field_name=field_name,
        source_id=source_id,
        value=value,
        confidence=round(float(confidence), 3),
        observed_at=observed,
        is_canonical=is_canonical,
    )
    session.add(row)
    return row


def record_canonical_provenance(
    session: Session,
    poi: POI,
    *,
    source_id: str,
    confidence: float,
    fields: Iterable[str] = CANONICAL_PROVENANCE_FIELDS,
    observed_at: datetime | None = None,
) -> None:
    values = canonical_field_values(poi)
    for field_name in fields:
        value = values.get(field_name)
        if value is None:
            continue
        add_field_provenance(
            session,
            poi_id=poi.poi_id,
            field_name=field_name,
            source_id=source_id,
            value=value,
            confidence=confidence,
            observed_at=observed_at,
            is_canonical=True,
        )


def record_sourced_field_values(
    session: Session,
    *,
    poi_id: str,
    source_id: str,
    values: dict[str, Any],
    confidence: float,
    observed_at: datetime | None = None,
    canonical_fields: set[str] | None = None,
) -> None:
    canonical_fields = canonical_fields or set()
    for field_name, value in values.items():
        if value is None or value == "":
            continue
        add_field_provenance(
            session,
            poi_id=poi_id,
            field_name=field_name,
            source_id=source_id,
            value=value,
            confidence=confidence,
            observed_at=observed_at,
            is_canonical=field_name in canonical_fields,
        )


def has_field_provenance(session: Session, poi_id: str, field_name: str) -> bool:
    return (
        session.scalar(
            select(POIFieldProvenance.id)
            .where(
                POIFieldProvenance.poi_id == poi_id,
                POIFieldProvenance.field_name == field_name,
            )
            .limit(1)
        )
        is not None
    )


def provenance_conflicts(rows: Iterable[POIFieldProvenance]) -> dict[str, list[POIFieldProvenance]]:
    by_field: dict[str, list[POIFieldProvenance]] = {}
    for row in rows:
        by_field.setdefault(row.field_name, []).append(row)
    return {
        field_name: field_rows
        for field_name, field_rows in by_field.items()
        if len({stable_value_key(row.value) for row in field_rows}) > 1
    }


def stable_value_key(value: Any) -> str:
    if isinstance(value, dict):
        return repr(sorted(value.items()))
    if isinstance(value, list):
        return repr(value)
    return str(value)
