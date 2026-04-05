from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.request import Request, urlopen

from poi_curator_domain.text import slugify

from poi_curator_enrichment.city_gis import name_similarity

NRHP_SOURCE_ID = "nrhp_listed_properties"
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


@dataclass(frozen=True)
class RegisterMatchCandidate:
    poi_id: str
    confidence: float
    matched_name: str
    match_strategy: str
    similarity: float


@dataclass(frozen=True)
class RegisterMatchEvaluation:
    match: RegisterMatchCandidate | None
    best_candidate: RegisterMatchCandidate | None


class MatchableHistoricPOI(Protocol):
    poi_id: str
    canonical_name: str
    historical_flag: bool


@dataclass(frozen=True)
class SeedAlias:
    alias_name: str
    alias_type: str
    confidence: float
    is_preferred: bool = False
    notes: str | None = None


SEEDED_REGION_ALIASES: dict[str, dict[str, tuple[SeedAlias, ...]]] = {
    "santa-fe": {
        "The Santa Fe Plaza": (
            SeedAlias("Santa Fe Plaza", "common", 0.98, True, "Drop leading article."),
        ),
        "Palace of the Governors": (
            SeedAlias("Palace of the Governor's", "register_variant", 0.96),
        ),
        "San Miguel": (
            SeedAlias("San Miguel Chapel", "common", 0.99, True),
            SeedAlias("Chapel of San Miguel", "register_variant", 0.97),
            SeedAlias("San Miguel Mission", "historic", 0.96),
            SeedAlias("San Miguel Mission Church", "historic", 0.95),
        ),
        "Barrio de Analco Historic District": (
            SeedAlias("Barrio de Analco", "common", 0.95),
            SeedAlias(
                "Barrio de Analco National Register Historic District",
                "register_variant",
                0.98,
            ),
            SeedAlias(
                "Barrio de Analco National Register Historic District NHL",
                "register_variant",
                0.98,
            ),
        ),
        "De Vargas Street House": (
            SeedAlias("Oldest House", "common", 0.97, True),
            SeedAlias("Oldest House Museum", "common", 0.96),
        ),
    }
}

_POSSESSIVE_RE = re.compile(r"[’']s\b")
_ALIAS_SPLIT_RE = re.compile(r"[;,]")
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


def fetch_nrhp_rows(csv_url: str, *, timeout_seconds: int = 60) -> list[HistoricRegisterRow]:
    request = Request(
        csv_url,
        headers={"User-Agent": "poi-curator/0.1.0", "Accept": "text/csv,text/plain,*/*"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw_text = response.read().decode("utf-8-sig")
    reader = csv.DictReader(raw_text.splitlines())
    rows: list[HistoricRegisterRow] = []
    for row in reader:
        property_name = _clean(row.get("Property Name"))
        state = _clean(row.get("State"))
        if not property_name or not state:
            continue
        rows.append(
            HistoricRegisterRow(
                reference_number=_clean(row.get("Ref#")),
                property_name=property_name,
                state=state,
                county=_clean(row.get("County")),
                city=slugify(_clean(row.get("City "))),
                street_address=_clean(row.get("Street & Number")),
                category_of_property=_clean(row.get("Category of Property")),
                listed_date=_clean(row.get("Listed Date")),
                external_link=_clean_optional(row.get("External Link")),
                other_names=_clean_optional(row.get("Other Names")),
            )
        )
    return rows


def rows_from_hpd_workbook(sheet_rows: list[dict[str, str]]) -> list[HistoricRegisterRow]:
    rows: list[HistoricRegisterRow] = []
    for row in sheet_rows:
        state_register_year = first_present(
            row,
            "STATE\nREGISTER",
            "STATE REGISTER",
        )
        property_name = first_present(
            row,
            "Property Name",
            "Name of Property",
            "Name",
            "Resource Name",
            "Historic Property",
        )
        if not property_name or not state_register_year:
            continue
        rows.append(
            HistoricRegisterRow(
                reference_number=first_present(
                    row,
                    "Ref#",
                    "Ref #",
                    "SR#",
                    "SR No.",
                    "SR No",
                    "Register Number",
                    "Number",
                    "Property ID",
                ),
                property_name=property_name,
                state=first_present(row, "State", "STATE", default="NEW MEXICO"),
                county=first_present(row, "County", "COUNTY"),
                city=slugify(first_present(row, "City", "City ", "Community", "Town")),
                street_address=first_present(row, "Street & Number", "Address", "Location"),
                category_of_property=first_present(
                    row,
                    "Category of Property",
                    "Property Type",
                    "Type",
                ),
                listed_date=first_present(
                    row,
                    "Listed Date",
                    "Listing Date",
                    "Date Listed",
                    "STATE\nREGISTER",
                    "STATE REGISTER",
                ),
                external_link=_clean_optional(row.get("External Link")),
                other_names=first_present(row, "Other Names", "Alternate Name", "Alias"),
                state_register_year=state_register_year,
            )
        )
    return rows


def filter_rows_for_region(
    rows: list[HistoricRegisterRow],
    *,
    state: str,
    city: str | None = None,
) -> list[HistoricRegisterRow]:
    expected_state = state.upper()
    expected_city = slugify(city) if city is not None else None
    filtered = [row for row in rows if row.state.upper() == expected_state]
    if expected_city is not None:
        filtered = [row for row in filtered if row.city == expected_city]
    return filtered


def match_register_row_to_poi(
    row: HistoricRegisterRow,
    pois: Sequence[MatchableHistoricPOI],
    *,
    threshold: float = 0.78,
) -> RegisterMatchCandidate | None:
    return evaluate_register_row_match(row, pois, threshold=threshold).match


def evaluate_register_row_match(
    row: HistoricRegisterRow,
    pois: Sequence[MatchableHistoricPOI],
    *,
    threshold: float = 0.78,
) -> RegisterMatchEvaluation:
    row_names = row_name_candidates(row)
    row_exact_forms = {form for name in row_names for form in historic_name_forms(name)}
    best_candidate: RegisterMatchCandidate | None = None

    for poi in pois:
        canonical_forms = historic_name_forms(poi.canonical_name)
        if row_exact_forms & canonical_forms:
            candidate = build_match_candidate(
                poi,
                matched_name=poi.canonical_name,
                match_strategy="canonical_exact",
                similarity=1.0,
            )
            return RegisterMatchEvaluation(match=candidate, best_candidate=candidate)

        for alias_name in poi_alias_names(poi):
            if row_exact_forms & historic_name_forms(alias_name):
                candidate = build_match_candidate(
                    poi,
                    matched_name=alias_name,
                    match_strategy="alias_exact",
                    similarity=1.0,
                )
                return RegisterMatchEvaluation(match=candidate, best_candidate=candidate)

        candidate = best_fuzzy_candidate(row_names, poi)
        if best_candidate is None or candidate.confidence > best_candidate.confidence:
            best_candidate = candidate

    if best_candidate is not None and best_candidate.similarity >= threshold:
        return RegisterMatchEvaluation(match=best_candidate, best_candidate=best_candidate)
    return RegisterMatchEvaluation(match=None, best_candidate=best_candidate)


def best_row_similarity(row: HistoricRegisterRow, canonical_name: str) -> float:
    candidates = row_name_candidates(row)
    return max(historic_name_similarity(candidate, canonical_name) for candidate in candidates)


def row_name_candidates(row: HistoricRegisterRow) -> list[str]:
    return [row.property_name, *split_aliases(row.other_names)]


def split_aliases(value: str | None) -> list[str]:
    if not value:
        return []
    return [alias.strip() for alias in _ALIAS_SPLIT_RE.split(value) if alias.strip()]


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


def historic_name_forms(value: str) -> set[str]:
    return {
        normalized
        for normalized in (
            normalize_historic_name(value, relaxed=False),
            normalize_historic_name(value, relaxed=True),
        )
        if normalized
    }


def historic_name_similarity(left: str, right: str) -> float:
    left_forms = historic_name_forms(left)
    right_forms = historic_name_forms(right)
    if left_forms & right_forms:
        return 1.0
    best = 0.0
    for left_form in left_forms:
        for right_form in right_forms:
            best = max(best, name_similarity(left_form, right_form))
    return best


def poi_alias_names(poi: MatchableHistoricPOI) -> list[str]:
    aliases = getattr(poi, "aliases", []) or []
    names: list[str] = []
    for alias in aliases:
        alias_name = getattr(alias, "alias_name", None)
        if isinstance(alias_name, str) and alias_name:
            names.append(alias_name)
    return names


def build_match_candidate(
    poi: MatchableHistoricPOI,
    *,
    matched_name: str,
    match_strategy: str,
    similarity: float,
) -> RegisterMatchCandidate:
    category_bonus = 0.05 if poi.historical_flag else 0.0
    if match_strategy == "canonical_exact":
        exact_bonus = 0.12
    elif match_strategy == "alias_exact":
        exact_bonus = 0.09
    else:
        exact_bonus = 0.0
    confidence = min(round(similarity + category_bonus + exact_bonus, 4), 0.99)
    return RegisterMatchCandidate(
        poi_id=poi.poi_id,
        confidence=confidence,
        matched_name=matched_name,
        match_strategy=match_strategy,
        similarity=similarity,
    )


def best_fuzzy_candidate(
    row_names: Sequence[str],
    poi: MatchableHistoricPOI,
) -> RegisterMatchCandidate:
    best_similarity = 0.0
    best_name = poi.canonical_name
    candidate_names = [poi.canonical_name, *poi_alias_names(poi)]
    for row_name in row_names:
        for candidate_name in candidate_names:
            similarity = historic_name_similarity(row_name, candidate_name)
            if similarity > best_similarity:
                best_similarity = similarity
                best_name = candidate_name
    return build_match_candidate(
        poi,
        matched_name=best_name,
        match_strategy="fuzzy_fallback",
        similarity=best_similarity,
    )


def build_nrhp_evidence_key(poi_id: str, reference_number: str) -> str:
    return slugify(f"{poi_id}:{NRHP_SOURCE_ID}:{reference_number}")[:255]


def build_state_register_evidence_key(
    poi_id: str,
    reference_number: str,
    property_name: str,
) -> str:
    key = reference_number or property_name
    return slugify(f"{poi_id}:{NM_STATE_REGISTER_SOURCE_ID}:{key}")[:255]


def seeded_aliases_for_region(region: str) -> dict[str, tuple[SeedAlias, ...]]:
    return SEEDED_REGION_ALIASES.get(region, {})


def first_present(row: dict[str, str], *headers: str, default: str = "") -> str:
    for header in headers:
        value = _clean_optional(row.get(header))
        if value:
            return value
    return default


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _clean_optional(value: Any) -> str | None:
    cleaned = _clean(value)
    return cleaned or None
