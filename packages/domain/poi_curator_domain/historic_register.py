from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from poi_curator_domain.db import POIEvidence
from poi_curator_domain.text import slugify

NRHP_SOURCE_ID = "nrhp"
NM_STATE_REGISTER_SOURCE_ID = "nm_hpd_register_workbook"


@dataclass(frozen=True)
class HistoricRegisterRow:
    reference_number: str
    property_name: str
    state: str
    county: str
    city: str
    street_address: str
    category_of_property: str
    listed_date: str
    external_link: str | None
    other_names: str | None
    state_register_year: str | None = None


_POSSESSIVE_RE = re.compile(r"[’']s\b")
_DROP_TOKENS = {
    "the",
    "of",
    "de",
    "la",
    "del",
    "los",
    "las",
    "and",
    "y",
}
_RELAXED_DROP_TOKENS = {
    "historic",
    "historical",
    "national",
    "register",
    "listed",
    "district",
    "nhl",
    "landmark",
    "property",
    "properties",
    "resource",
    "resources",
    "additional",
    "documentation",
    "collection",
    "collections",
}
_TOKEN_NORMALIZATIONS = {
    "st": "saint",
    "ft": "fort",
    "governors": "governor",
    "governor": "governor",
    "residence": "house",
    "home": "house",
    "casa": "house",
    "chapels": "chapel",
    "churches": "chapel",
    "capilla": "chapel",
}


def normalize_historic_name(value: str, *, relaxed: bool = False) -> str:
    prepared = _POSSESSIVE_RE.sub("s", value.lower()).replace("&", " and ")
    raw_tokens = slugify(prepared).replace("-", " ").split()
    normalized_tokens: list[str] = []
    for token in raw_tokens:
        token = _TOKEN_NORMALIZATIONS.get(token, token)
        if token in _DROP_TOKENS:
            continue
        if relaxed and token in _RELAXED_DROP_TOKENS:
            continue
        normalized_tokens.append(token)
    return " ".join(normalized_tokens)


def build_nrhp_evidence_key(poi_id: str, reference_number: str) -> str:
    return slugify(f"{poi_id}:{NRHP_SOURCE_ID}:{reference_number}")[:255]


def build_state_register_evidence_key(
    poi_id: str,
    reference_number: str,
    property_name: str,
) -> str:
    key = reference_number or property_name
    return slugify(f"{poi_id}:{NM_STATE_REGISTER_SOURCE_ID}:{key}")[:255]


def build_nrhp_evidence(
    row: HistoricRegisterRow,
    poi_id: str,
    confidence: float,
    *,
    match_strategy: str | None = None,
) -> POIEvidence:
    return POIEvidence(
        evidence_key=build_nrhp_evidence_key(poi_id, row.reference_number),
        poi_id=poi_id,
        source_id=NRHP_SOURCE_ID,
        evidence_type="historic_designation",
        evidence_label=row.property_name,
        evidence_text=f"Listed in the National Register of Historic Places on {row.listed_date}.",
        evidence_url=row.external_link,
        external_record_id=row.reference_number,
        confidence=round(confidence, 3),
        raw_evidence_json={
            "city": row.city,
            "county": row.county,
            "street_address": row.street_address,
            "category_of_property": row.category_of_property,
            "other_names": row.other_names,
            "state_register_year": row.state_register_year,
            "match_strategy": match_strategy,
        },
        observed_at=datetime.now(UTC),
    )


def build_state_register_evidence(
    row: HistoricRegisterRow,
    poi_id: str,
    confidence: float,
    *,
    match_strategy: str | None = None,
) -> POIEvidence:
    return POIEvidence(
        evidence_key=build_state_register_evidence_key(
            poi_id,
            row.reference_number,
            row.property_name,
        ),
        poi_id=poi_id,
        source_id=NM_STATE_REGISTER_SOURCE_ID,
        evidence_type="state_historic_designation",
        evidence_label=row.property_name,
        evidence_text="Listed in the New Mexico state register workbook.",
        evidence_url=row.external_link,
        external_record_id=row.reference_number or row.property_name,
        confidence=round(confidence, 3),
        raw_evidence_json={
            "city": row.city,
            "county": row.county,
            "street_address": row.street_address,
            "category_of_property": row.category_of_property,
            "other_names": row.other_names,
            "match_strategy": match_strategy,
        },
        observed_at=datetime.now(UTC),
    )
