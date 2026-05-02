from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import orjson
from geoalchemy2.shape import to_shape
from poi_curator_domain.db import POI, POIEvidence, SourceRegistry
from poi_curator_domain.settings import get_settings
from poi_curator_domain.text import slugify
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

CITY_HISTORIC_DISTRICT_SOURCE_ID = "city_gis_historic_districts"
CITY_HISTORIC_DISTRICT_LAYER_ID = 118
CITY_HISTORIC_DISTRICT_LICENSE = (
    "City of Santa Fe public ArcGIS REST layer; verify downstream use before redistribution."
)


@dataclass(frozen=True)
class HistoricDistrictFeature:
    feature_id: str
    label: str
    geometry: BaseGeometry
    properties: dict[str, Any]
    source_url: str


@dataclass(frozen=True)
class CityHistoricDistrictIngestSummary:
    region: str
    district_count: int
    evidence_created: int
    evidence_updated: int
    impacted_poi_count: int


def fetch_historic_district_geojson(
    base_url: str,
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
        f"{base_url.rstrip('/')}/{CITY_HISTORIC_DISTRICT_LAYER_ID}/query?{query}",
        headers={
            "User-Agent": "poi-curator/0.1.0",
            "Accept": "application/geo+json,application/json",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return orjson.loads(response.read())


def ingest_historic_district_memberships(
    session: Session,
    region: str,
    *,
    feature_loader: Callable[[], dict[str, Any]] | None = None,
) -> CityHistoricDistrictIngestSummary:
    settings = get_settings()
    base_url = settings.city_gis_mapserver_url
    payload = (
        feature_loader()
        if feature_loader is not None
        else fetch_historic_district_geojson(
            base_url,
            timeout_seconds=settings.city_gis_timeout_seconds,
        )
    )
    features = parse_historic_district_features(payload, base_url=base_url)
    ensure_historic_district_source_registry(session, base_url)
    pois = session.scalars(select(POI).where(POI.city == region, POI.is_active.is_(True))).all()

    evidence_created = 0
    evidence_updated = 0
    impacted_poi_ids: set[str] = set()
    for feature in features:
        for poi in pois:
            centroid = to_shape(poi.centroid)
            if not (feature.geometry.contains(centroid) or feature.geometry.intersects(centroid)):
                continue
            created = upsert_district_membership_evidence(session, poi.poi_id, feature)
            if created:
                evidence_created += 1
            else:
                evidence_updated += 1
            impacted_poi_ids.add(poi.poi_id)

    session.commit()
    return CityHistoricDistrictIngestSummary(
        region=region,
        district_count=len(features),
        evidence_created=evidence_created,
        evidence_updated=evidence_updated,
        impacted_poi_count=len(impacted_poi_ids),
    )


def parse_historic_district_features(
    payload: dict[str, Any],
    *,
    base_url: str,
) -> list[HistoricDistrictFeature]:
    features: list[HistoricDistrictFeature] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry")
        if geometry is None:
            continue
        properties = {str(key): value for key, value in feature.get("properties", {}).items()}
        feature_id = str(feature.get("id") or properties.get("OBJECTID") or "")
        label = str(properties.get("HBDIST") or properties.get("NAME") or "Historic District")
        features.append(
            HistoricDistrictFeature(
                feature_id=feature_id,
                label=label.strip(),
                geometry=shape(geometry),
                properties=properties,
                source_url=f"{base_url.rstrip('/')}/{CITY_HISTORIC_DISTRICT_LAYER_ID}/{feature_id}",
            )
        )
    return features


def upsert_district_membership_evidence(
    session: Session,
    poi_id: str,
    feature: HistoricDistrictFeature,
) -> bool:
    key = evidence_key(poi_id, feature)
    evidence = session.scalar(select(POIEvidence).where(POIEvidence.evidence_key == key))
    created = evidence is None
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=CITY_HISTORIC_DISTRICT_SOURCE_ID,
            evidence_type="district_membership",
            evidence_label=feature.label,
            evidence_text=f"{feature.label} via City of Santa Fe GIS",
            evidence_url=feature.source_url,
            external_record_id=feature.feature_id,
            confidence=0.8,
            raw_evidence_json={"properties": feature.properties, "layer_id": 118},
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
        return created
    evidence.evidence_label = feature.label
    evidence.evidence_text = f"{feature.label} via City of Santa Fe GIS"
    evidence.evidence_url = feature.source_url
    evidence.confidence = 0.8
    evidence.raw_evidence_json = {"properties": feature.properties, "layer_id": 118}
    evidence.observed_at = datetime.now(UTC)
    return created


def ensure_historic_district_source_registry(session: Session, base_url: str) -> None:
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, CITY_HISTORIC_DISTRICT_SOURCE_ID)
    if source is None:
        source = SourceRegistry(
            source_id=CITY_HISTORIC_DISTRICT_SOURCE_ID,
            organization_name="City of Santa Fe",
            source_name="City of Santa Fe GIS Historic Districts",
            source_type="gis_layer",
            trust_class="official_corroboration",
            base_url=f"{base_url.rstrip('/')}/{CITY_HISTORIC_DISTRICT_LAYER_ID}",
            license_notes=CITY_HISTORIC_DISTRICT_LICENSE,
            crawl_allowed=True,
            ingest_method="arcgis_rest",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(source)
        return
    source.updated_at = now
    source.is_active = True


def evidence_key(poi_id: str, feature: HistoricDistrictFeature) -> str:
    return slugify(
        f"{poi_id}:{CITY_HISTORIC_DISTRICT_SOURCE_ID}:district_membership:"
        f"{feature.feature_id}:{feature.label}"
    )[:255]
