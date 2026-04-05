from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import orjson
from poi_curator_domain.text import slugify
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

LayerKind = Literal["point", "polygon"]


@dataclass(frozen=True)
class CityGISLayerSpec:
    source_id: str
    layer_id: int
    source_name: str
    evidence_type: str
    kind: LayerKind
    name_field: str | None
    default_label: str
    confidence: float


@dataclass(frozen=True)
class CityGISFeature:
    layer: CityGISLayerSpec
    feature_id: str
    name: str | None
    label: str
    geometry: BaseGeometry
    properties: dict[str, Any]
    source_url: str


@dataclass(frozen=True)
class CandidatePOI:
    poi_id: str
    canonical_name: str
    normalized_category: str
    display_categories: list[str]
    centroid: Point


@dataclass(frozen=True)
class MatchCandidate:
    poi_id: str
    confidence: float
    matched_name: str | None
    distance_m: float | None


CITY_GIS_LAYER_SPECS: tuple[CityGISLayerSpec, ...] = (
    CityGISLayerSpec(
        source_id="city_gis_museums",
        layer_id=9,
        source_name="City of Santa Fe GIS Museums",
        evidence_type="institution_membership",
        kind="point",
        name_field="DEPARTMENT",
        default_label="Museums",
        confidence=0.85,
    ),
    CityGISLayerSpec(
        source_id="city_gis_public_art",
        layer_id=12,
        source_name="City of Santa Fe GIS Public Art",
        evidence_type="institution_membership",
        kind="point",
        name_field="NAME",
        default_label="Public Art",
        confidence=0.75,
    ),
    CityGISLayerSpec(
        source_id="city_gis_place_of_worship",
        layer_id=11,
        source_name="City of Santa Fe GIS Places of Worship",
        evidence_type="institution_membership",
        kind="point",
        name_field="NAME",
        default_label="Places of Worship",
        confidence=0.7,
    ),
    CityGISLayerSpec(
        source_id="city_gis_historic_districts",
        layer_id=118,
        source_name="City of Santa Fe GIS Historic Districts",
        evidence_type="district_membership",
        kind="polygon",
        name_field=None,
        default_label="Historic Districts",
        confidence=0.8,
    ),
    CityGISLayerSpec(
        source_id="city_gis_historic_building_status",
        layer_id=125,
        source_name="City of Santa Fe GIS Historical Buildings Status",
        evidence_type="historic_building_status",
        kind="polygon",
        name_field="HBSTAT",
        default_label="Historical Buildings Status",
        confidence=0.9,
    ),
    CityGISLayerSpec(
        source_id="city_gis_plaza_park",
        layer_id=91,
        source_name="City of Santa Fe GIS Plaza Park Boundary",
        evidence_type="boundary_membership",
        kind="polygon",
        name_field=None,
        default_label="Plaza Park",
        confidence=0.85,
    ),
    CityGISLayerSpec(
        source_id="city_gis_railyard_boundary",
        layer_id=93,
        source_name="City of Santa Fe GIS Railyard Boundary",
        evidence_type="boundary_membership",
        kind="polygon",
        name_field=None,
        default_label="The Railyard",
        confidence=0.85,
    ),
)


def fetch_arcgis_geojson(
    base_url: str,
    layer_id: int,
    *,
    timeout_seconds: int = 45,
) -> dict[str, Any]:
    query = urlencode(
        {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
        }
    )
    request = Request(
        f"{base_url.rstrip('/')}/{layer_id}/query?{query}",
        headers={
            "User-Agent": "poi-curator/0.1.0",
            "Accept": "application/geo+json,application/json",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return orjson.loads(response.read())


def parse_city_gis_features(
    payload: dict[str, Any],
    *,
    layer: CityGISLayerSpec,
    base_url: str,
) -> list[CityGISFeature]:
    features: list[CityGISFeature] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry")
        properties = feature.get("properties", {})
        if geometry is None:
            continue
        feature_id = str(feature.get("id") or properties.get("OBJECTID") or "")
        name = _clean_optional_value(properties.get(layer.name_field)) if layer.name_field else None
        label = name or _clean_optional_value(properties.get("HBDIST")) or layer.default_label
        features.append(
            CityGISFeature(
                layer=layer,
                feature_id=feature_id,
                name=name,
                label=label,
                geometry=shape(geometry),
                properties={str(key): value for key, value in properties.items()},
                source_url=f"{base_url.rstrip('/')}/{layer.layer_id}/{feature_id}",
            )
        )
    return features


def match_point_feature_to_poi(
    feature: CityGISFeature,
    pois: list[CandidatePOI],
    *,
    max_distance_m: float = 250.0,
) -> MatchCandidate | None:
    if feature.name is None or not isinstance(feature.geometry, Point):
        return None

    feature_point = feature.geometry
    best_match: MatchCandidate | None = None
    for poi in pois:
        distance_m = feature_point.distance(poi.centroid) * 111_320.0
        if distance_m > max_distance_m:
            continue

        similarity = name_similarity(feature.name, poi.canonical_name)
        category_bonus = (
            0.08 if poi.normalized_category in {"history", "culture", "art", "civic"} else 0.0
        )
        proximity_score = max(0.0, 1.0 - (distance_m / max_distance_m))
        combined = round(similarity * 0.7 + proximity_score * 0.22 + category_bonus, 4)
        if combined < 0.45:
            continue

        candidate = MatchCandidate(
            poi_id=poi.poi_id,
            confidence=min(combined, 0.99),
            matched_name=poi.canonical_name,
            distance_m=distance_m,
        )
        if best_match is None or candidate.confidence > best_match.confidence:
            best_match = candidate
    return best_match


def poi_ids_within_polygon(feature: CityGISFeature, pois: list[CandidatePOI]) -> list[str]:
    polygon = feature.geometry
    poi_ids: list[str] = []
    for poi in pois:
        if polygon.contains(poi.centroid) or polygon.intersects(poi.centroid):
            poi_ids.append(poi.poi_id)
    return poi_ids


def name_similarity(left: str, right: str) -> float:
    left_tokens = normalized_tokens(left)
    right_tokens = normalized_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    token_overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    ratio = SequenceMatcher(
        None,
        " ".join(sorted(left_tokens)),
        " ".join(sorted(right_tokens)),
    ).ratio()
    return max(token_overlap, ratio)


def normalized_tokens(value: str) -> set[str]:
    raw_tokens = slugify(value).replace("-", " ").split()
    tokens: set[str] = set()
    for token in raw_tokens:
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        if token in {"the", "of", "de", "la", "and", "museum"}:
            continue
        tokens.add(token)
    return tokens


def _clean_optional_value(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized or normalized == " ":
        return None
    return normalized
