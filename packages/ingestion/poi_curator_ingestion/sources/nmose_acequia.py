from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from math import cos, radians
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import orjson
from geoalchemy2.shape import from_shape, to_shape
from poi_curator_domain.db import (
    POI,
    POIEvidence,
    POIMatchLog,
    POISignals,
    POISourceRaw,
    SourceRegistry,
)
from poi_curator_domain.descriptions import description_quality_score
from poi_curator_domain.provenance import record_canonical_provenance, record_sourced_field_values
from poi_curator_domain.text import slugify
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from sqlalchemy import select
from sqlalchemy.orm import Session

from poi_curator_ingestion.matching import IncomingSourceRecord, match_incoming_record
from poi_curator_ingestion.pipeline import ensure_editorial_stub

NMOSE_POD_SOURCE_ID = "nmose_pod"
NMOSE_ACEQUIA_SOURCE_ID = "nmose_acequia"
POD_LAYER_URL = (
    "https://services2.arcgis.com/qXZbWTdPDbTjl7Dy/arcgis/rest/services/"
    "OSE_Points_of_Diversion/FeatureServer/0"
)
CONVEYANCE_LAYER_URL = (
    "https://services2.arcgis.com/qXZbWTdPDbTjl7Dy/arcgis/rest/services/"
    "OSE_Conveyances/FeatureServer/0"
)
NMOSE_LICENSE_NOTES = (
    "Public NM OSE ArcGIS REST data; OSE publishes the data as-is without warranty. "
    "Use only public records and do not augment acequia details from private steward records "
    "without explicit permission."
)
SANTA_FE_COUNTY_CODE = "SF"
SANTA_FE_COUNTY_ENVELOPE = (-106.25, 35.35, -105.70, 36.10)
ACEQUIA_MEMBERSHIP_BUFFER_M = 50.0
ACEQUIA_TYPES = {"ACQ", "ACQT", "CMD", "CAN", "DIT"}


@dataclass(frozen=True)
class NMOSEPODRecord:
    external_id: str
    name: str
    lon: float
    lat: float
    county: str
    pod_status: str | None
    conveyance_name: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class NMOSEConveyanceFeature:
    external_id: str
    name: str | None
    conveyance_type: str | None
    status: str | None
    geometry: BaseGeometry
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class NMOSEAcequiaIngestSummary:
    region: str
    pod_candidate_count: int
    pod_canonical_created: int
    pod_evidence_attached: int
    pod_ambiguous_count: int
    pod_skipped_count: int
    conveyance_feature_count: int
    membership_evidence_created: int
    membership_evidence_updated: int
    association_evidence_created: int
    association_evidence_updated: int
    impacted_poi_count: int


def fetch_arcgis_geojson(
    layer_url: str,
    *,
    where: str,
    geometry: tuple[float, float, float, float] | None = None,
    timeout_seconds: int = 60,
    page_size: int = 2000,
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params: dict[str, Any] = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "f": "geojson",
        }
        if geometry is not None:
            params.update(
                {
                    "geometry": ",".join(str(value) for value in geometry),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                }
            )
        request = Request(
            f"{layer_url.rstrip('/')}/query?{urlencode(params)}",
            headers={
                "User-Agent": "poi-curator/0.1.0",
                "Accept": "application/geo+json,application/json",
            },
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = orjson.loads(response.read())
        page_features = payload.get("features", [])
        features.extend(page_features)
        if not payload.get("properties", {}).get("exceededTransferLimit") or not page_features:
            break
        offset += len(page_features)
    return {"type": "FeatureCollection", "features": features}


def ingest_nmose_acequia(
    session: Session,
    region: str,
    *,
    pod_loader: Callable[[], dict[str, Any]] | None = None,
    conveyance_loader: Callable[[], dict[str, Any]] | None = None,
    membership_buffer_m: float = ACEQUIA_MEMBERSHIP_BUFFER_M,
) -> NMOSEAcequiaIngestSummary:
    ensure_nmose_source_registry(session)
    pods = parse_pod_records(
        pod_loader()
        if pod_loader is not None
        else fetch_arcgis_geojson(
            POD_LAYER_URL,
            where=(
                f"county='{SANTA_FE_COUNTY_CODE}' AND ditch_name <> ' ' "
                "AND pod_status='ACT'"
            ),
        )
    )
    conveyances = parse_conveyance_features(
        conveyance_loader()
        if conveyance_loader is not None
        else fetch_arcgis_geojson(
            CONVEYANCE_LAYER_URL,
            where=(
                "Type IN ('ACQ','ACQT','CMD','CAN','DIT') "
                "AND Status='Active' AND CnvyName <> 'Unknown'"
            ),
            geometry=SANTA_FE_COUNTY_ENVELOPE,
        )
    )

    pod_canonical_created = 0
    pod_evidence_attached = 0
    pod_ambiguous_count = 0
    pod_skipped_count = 0

    for pod in pods:
        persist_raw_record(
            session,
            NMOSE_POD_SOURCE_ID,
            pod.external_id,
            pod.raw_payload,
            Point(pod.lon, pod.lat),
        )
        match_result = match_incoming_record(
            session,
            IncomingSourceRecord(
                source_id=NMOSE_POD_SOURCE_ID,
                external_id=pod.external_id,
                name=pod.name,
                lon=pod.lon,
                lat=pod.lat,
                region=region,
                raw_payload=pod.raw_payload,
            ),
            decided_by="ingest:nmose_acequia",
        )
        if match_result.decision == "ambiguous":
            pod_ambiguous_count += 1
            continue
        if match_result.poi is None:
            poi = create_pod_canonical_poi(session, pod, region)
            pod_canonical_created += 1
            record_canonical_provenance(
                session,
                poi,
                source_id=NMOSE_POD_SOURCE_ID,
                confidence=0.75,
                observed_at=datetime.now(UTC),
            )
            session.add(
                POIMatchLog(
                    canonical_poi_id=poi.poi_id,
                    candidate_source=NMOSE_POD_SOURCE_ID,
                    candidate_external_id=pod.external_id,
                    match_strategy=match_result.strategy,
                    match_score=match_result.score,
                    decision="new",
                    decided_at=datetime.now(UTC),
                    decided_by="ingest:nmose_acequia",
                    notes="Canonical POI created for unmatched public OSE POD record.",
                )
            )
        else:
            poi = match_result.poi

        upsert_pod_evidence(session, poi.poi_id, pod)
        if pod.conveyance_name:
            upsert_association_evidence(
                session,
                poi.poi_id,
                pod.conveyance_name,
                pod.external_id,
                pod.raw_payload,
                evidence_url=f"{POD_LAYER_URL}/{pod.external_id}",
            )
        record_sourced_field_values(
            session,
            poi_id=poi.poi_id,
            source_id=NMOSE_POD_SOURCE_ID,
            values=pod_field_values(pod),
            confidence=0.75,
            observed_at=datetime.now(UTC),
        )
        pod_evidence_attached += 1

    persist_conveyance_raw_records(session, conveyances)
    pois = session.scalars(select(POI).where(POI.city == region, POI.is_active.is_(True))).all()
    membership_created = 0
    membership_updated = 0
    association_created = 0
    association_updated = 0
    impacted_poi_ids: set[str] = set()

    for feature in conveyances:
        for poi in pois:
            centroid = to_shape(poi.centroid)
            if distance_point_to_geometry_m(centroid, feature.geometry) > membership_buffer_m:
                continue
            created = upsert_acequia_membership_evidence(session, poi.poi_id, feature)
            if created:
                membership_created += 1
            else:
                membership_updated += 1
            if feature.name:
                association_was_created = upsert_association_evidence(
                    session,
                    poi.poi_id,
                    feature.name,
                    feature.external_id,
                    feature.raw_payload,
                )
                if association_was_created:
                    association_created += 1
                else:
                    association_updated += 1
            impacted_poi_ids.add(poi.poi_id)

    session.commit()
    return NMOSEAcequiaIngestSummary(
        region=region,
        pod_candidate_count=len(pods),
        pod_canonical_created=pod_canonical_created,
        pod_evidence_attached=pod_evidence_attached,
        pod_ambiguous_count=pod_ambiguous_count,
        pod_skipped_count=pod_skipped_count,
        conveyance_feature_count=len(conveyances),
        membership_evidence_created=membership_created,
        membership_evidence_updated=membership_updated,
        association_evidence_created=association_created,
        association_evidence_updated=association_updated,
        impacted_poi_count=len(impacted_poi_ids),
    )


def parse_pod_records(payload: dict[str, Any]) -> list[NMOSEPODRecord]:
    records: list[NMOSEPODRecord] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry")
        properties = normalized_properties(feature)
        if not geometry or geometry.get("type") != "Point":
            continue
        lon, lat = geometry.get("coordinates", [None, None])[:2]
        if lon is None or lat is None:
            continue
        county = clean_value(properties.get("county"))
        conveyance_name = meaningful_name(properties.get("ditch_name"))
        if county != SANTA_FE_COUNTY_CODE or conveyance_name is None:
            continue
        status = clean_value(properties.get("pod_status"))
        if status != "ACT":
            continue
        external_id = str(properties.get("OBJECTID") or feature.get("id") or "")
        if not external_id:
            continue
        pod_name = meaningful_name(properties.get("pod_name"))
        name = pod_name or f"Point of Diversion - {conveyance_name}"
        records.append(
            NMOSEPODRecord(
                external_id=external_id,
                name=name,
                lon=float(lon),
                lat=float(lat),
                county=county,
                pod_status=status,
                conveyance_name=conveyance_name,
                raw_payload={"properties": properties, "geometry": geometry},
            )
        )
    return records


def parse_conveyance_features(payload: dict[str, Any]) -> list[NMOSEConveyanceFeature]:
    features: list[NMOSEConveyanceFeature] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry")
        properties = normalized_properties(feature)
        if geometry is None:
            continue
        geom = shape(geometry)
        if not isinstance(geom, (LineString, MultiLineString)):
            continue
        conveyance_type = clean_value(properties.get("Type"))
        status = clean_value(properties.get("Status"))
        name = meaningful_name(properties.get("CnvyName") or properties.get("Conveyance Name"))
        if conveyance_type not in ACEQUIA_TYPES or status != "Active" or name is None:
            continue
        external_id = str(
            properties.get("OBJECTID") or feature.get("id") or properties.get("GlobalID") or ""
        )
        if not external_id:
            continue
        features.append(
            NMOSEConveyanceFeature(
                external_id=external_id,
                name=name,
                conveyance_type=conveyance_type,
                status=status,
                geometry=geom,
                raw_payload={"properties": properties, "geometry": geometry},
            )
        )
    return features


def create_pod_canonical_poi(session: Session, pod: NMOSEPODRecord, region: str) -> POI:
    now = datetime.now(UTC)
    point = Point(pod.lon, pod.lat)
    poi = POI(
        canonical_name=pod.name,
        slug=unique_slug(session, f"{pod.name}-{NMOSE_POD_SOURCE_ID}-{pod.external_id}"),
        geom=from_shape(point, srid=4326),
        centroid=from_shape(point, srid=4326),
        city=region,
        region="New Mexico",
        country="US",
        normalized_category="civic",
        normalized_subcategory="infrastructure_landmark",
        display_categories=["civic"],
        short_description="Public OSE point of diversion associated with a named conveyance.",
        primary_source=NMOSE_POD_SOURCE_ID,
        raw_tag_summary_json={
            "source": NMOSE_POD_SOURCE_ID,
            "external_id": pod.external_id,
            "conveyance_name": pod.conveyance_name,
        },
        historical_flag=False,
        cultural_flag=True,
        scenic_flag=False,
        infrastructure_flag=True,
        food_identity_flag=False,
        walk_affinity_hint=0.25,
        drive_affinity_hint=0.35,
        base_significance_score=3.5,
        quality_score=45.0,
        review_status="needs_review",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(poi)
    session.flush()
    session.add(
        POISignals(
            poi_id=poi.poi_id,
            source_count=1,
            has_official_heritage_match=False,
            official_corroboration_score=0.6,
            district_membership_score=0.0,
            institutional_identity_score=0.0,
            description_quality=description_quality_score(
                poi.short_description,
                poi.normalized_subcategory,
            ),
            entity_type_confidence=0.7,
            local_identity_score=0.55,
            interpretive_value_score=0.45,
            genericity_penalty=0.2,
            editorial_priority_seed=0.55,
            computed_at=now,
        )
    )
    ensure_editorial_stub(session, poi)
    return poi


def upsert_pod_evidence(session: Session, poi_id: str, pod: NMOSEPODRecord) -> bool:
    key = evidence_key(poi_id, NMOSE_POD_SOURCE_ID, "point_of_diversion", pod.external_id)
    evidence = pending_evidence_by_key(session, key) or session.scalar(
        select(POIEvidence).where(POIEvidence.evidence_key == key)
    )
    created = evidence is None
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=NMOSE_POD_SOURCE_ID,
            evidence_type="point_of_diversion",
            external_record_id=pod.external_id,
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
    evidence.evidence_label = pod.name
    evidence.evidence_text = evidence_text_for_pod(pod)
    evidence.evidence_url = f"{POD_LAYER_URL}/{pod.external_id}"
    evidence.confidence = 0.75
    evidence.raw_evidence_json = pod.raw_payload
    evidence.observed_at = datetime.now(UTC)
    return created


def upsert_acequia_membership_evidence(
    session: Session,
    poi_id: str,
    feature: NMOSEConveyanceFeature,
) -> bool:
    key = evidence_key(
        poi_id,
        NMOSE_ACEQUIA_SOURCE_ID,
        "acequia_membership",
        feature.external_id,
    )
    evidence = pending_evidence_by_key(session, key) or session.scalar(
        select(POIEvidence).where(POIEvidence.evidence_key == key)
    )
    created = evidence is None
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=NMOSE_ACEQUIA_SOURCE_ID,
            evidence_type="acequia_membership",
            external_record_id=feature.external_id,
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
    evidence.evidence_label = feature.name or "OSE acequia conveyance"
    evidence.evidence_text = (
        f"Within {ACEQUIA_MEMBERSHIP_BUFFER_M:.0f} m of public OSE conveyance data."
    )
    evidence.evidence_url = f"{CONVEYANCE_LAYER_URL}/{feature.external_id}"
    evidence.confidence = 0.7
    evidence.raw_evidence_json = feature.raw_payload
    evidence.observed_at = datetime.now(UTC)
    return created


def upsert_association_evidence(
    session: Session,
    poi_id: str,
    association_name: str,
    external_id: str,
    raw_payload: dict[str, Any],
    evidence_url: str | None = None,
) -> bool:
    key = evidence_key(
        poi_id,
        NMOSE_ACEQUIA_SOURCE_ID,
        "acequia_association",
        association_name,
    )
    evidence = pending_evidence_by_key(session, key) or session.scalar(
        select(POIEvidence).where(POIEvidence.evidence_key == key)
    )
    created = evidence is None
    if evidence is None:
        evidence = POIEvidence(
            evidence_key=key,
            poi_id=poi_id,
            source_id=NMOSE_ACEQUIA_SOURCE_ID,
            evidence_type="acequia_association",
            external_record_id=external_id,
            observed_at=datetime.now(UTC),
        )
        session.add(evidence)
    evidence.evidence_label = association_name
    evidence.evidence_text = f"Associated with {association_name} in public OSE data."
    evidence.evidence_url = evidence_url or f"{CONVEYANCE_LAYER_URL}/{external_id}"
    evidence.confidence = 0.7
    evidence.raw_evidence_json = raw_payload
    evidence.observed_at = datetime.now(UTC)
    return created


def pending_evidence_by_key(session: Session, key: str) -> POIEvidence | None:
    for item in session.new:
        if isinstance(item, POIEvidence) and item.evidence_key == key:
            return item
    return None


def persist_conveyance_raw_records(
    session: Session,
    conveyances: Iterable[NMOSEConveyanceFeature],
) -> None:
    for feature in conveyances:
        persist_raw_record(
            session,
            NMOSE_ACEQUIA_SOURCE_ID,
            feature.external_id,
            feature.raw_payload,
            feature.geometry,
        )


def persist_raw_record(
    session: Session,
    source_id: str,
    external_id: str,
    raw_payload: dict[str, Any],
    geometry: BaseGeometry,
) -> None:
    content_hash = sha256(orjson.dumps(raw_payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
    existing = session.scalar(
        select(POISourceRaw).where(
            POISourceRaw.source_name == source_id,
            POISourceRaw.source_record_id == external_id,
            POISourceRaw.is_current.is_(True),
        )
    )
    now = datetime.now(UTC)
    if existing is not None and existing.content_hash == content_hash:
        existing.fetched_at = now
        return
    if existing is not None:
        existing.is_current = False
    session.add(
        POISourceRaw(
            source_name=source_id,
            source_record_id=external_id,
            source_url=f"{source_base_url(source_id)}/{external_id}",
            raw_payload_json=raw_payload,
            geom=from_shape(geometry, srid=4326),
            fetched_at=now,
            content_hash=content_hash,
            is_current=True,
            license=NMOSE_LICENSE_NOTES[:128],
        )
    )


def ensure_nmose_source_registry(session: Session) -> None:
    upsert_source_registry(
        session,
        source_id=NMOSE_POD_SOURCE_ID,
        source_name="NM OSE Points of Diversion",
        source_type="arcgis_feature_layer",
        trust_class="official_infrastructure",
        base_url=POD_LAYER_URL,
    )
    upsert_source_registry(
        session,
        source_id=NMOSE_ACEQUIA_SOURCE_ID,
        source_name="NM OSE Acequia and Conveyance Structures",
        source_type="arcgis_feature_layer",
        trust_class="official_infrastructure",
        base_url=CONVEYANCE_LAYER_URL,
    )


def upsert_source_registry(
    session: Session,
    *,
    source_id: str,
    source_name: str,
    source_type: str,
    trust_class: str,
    base_url: str,
) -> None:
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, source_id)
    if source is None:
        session.add(
            SourceRegistry(
                source_id=source_id,
                organization_name="New Mexico Office of the State Engineer",
                source_name=source_name,
                source_type=source_type,
                trust_class=trust_class,
                base_url=base_url,
                license_notes=NMOSE_LICENSE_NOTES,
                crawl_allowed=True,
                ingest_method="arcgis_rest",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        return
    source.updated_at = now
    source.is_active = True


def pod_field_values(pod: NMOSEPODRecord) -> dict[str, Any]:
    return {
        "name": pod.name,
        "primary_category": "civic",
        "coordinates": {"lon": round(pod.lon, 7), "lat": round(pod.lat, 7)},
        "short_description": "Public OSE point of diversion associated with a named conveyance.",
        "pod_status": pod.pod_status,
        "acequia_association": pod.conveyance_name,
    }


def evidence_text_for_pod(pod: NMOSEPODRecord) -> str:
    if pod.conveyance_name:
        return f"OSE point of diversion associated with {pod.conveyance_name}."
    return "OSE point of diversion."


def distance_point_to_geometry_m(point: Point, geometry: BaseGeometry) -> float:
    lat_scale = 111_320.0
    lon_scale = cos(radians(float(point.y))) * lat_scale

    def project(lon: float, lat: float, z: float | None = None) -> tuple[float, float]:
        del z
        return (lon * lon_scale, lat * lat_scale)

    projected_point = transform(project, point)
    projected_geometry = transform(project, geometry)
    return float(projected_point.distance(projected_geometry))


def normalized_properties(feature: dict[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in feature.get("properties", {}).items()}


def clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def meaningful_name(value: Any) -> str | None:
    text = clean_value(value)
    if text is None:
        return None
    if text.casefold() in {"unknown", "n/a", "na", "none"}:
        return None
    if len([char for char in text if char.isalnum()]) < 3:
        return None
    return text


def evidence_key(poi_id: str, source_id: str, evidence_type: str, external_id: str) -> str:
    return slugify(f"{poi_id}:{source_id}:{evidence_type}:{external_id}")[:255]


def source_base_url(source_id: str) -> str:
    if source_id == NMOSE_POD_SOURCE_ID:
        return POD_LAYER_URL
    return CONVEYANCE_LAYER_URL


def unique_slug(session: Session, value: str) -> str:
    base = slugify(value)[:220]
    slug = base
    suffix = 2
    while session.scalar(select(POI.poi_id).where(POI.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
