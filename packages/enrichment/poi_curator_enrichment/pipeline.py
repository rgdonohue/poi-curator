import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from geoalchemy2.shape import to_shape
from poi_curator_domain.db import (
    POI,
    OfficialMatchDiagnostic,
    POIAlias,
    POIEvidence,
    POISignals,
    SourceRegistry,
)
from poi_curator_domain.descriptions import description_quality_score
from poi_curator_domain.logging_utils import log_event
from poi_curator_domain.settings import get_settings
from poi_curator_domain.text import slugify
from poi_curator_ingestion.normalize import build_short_description
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from poi_curator_enrichment.city_gis import (
    CITY_GIS_LAYER_SPECS,
    CandidatePOI,
    CityGISFeature,
    fetch_arcgis_geojson,
    match_point_feature_to_poi,
    parse_city_gis_features,
    poi_ids_within_polygon,
)
from poi_curator_enrichment.historic_register import (
    NM_STATE_REGISTER_SOURCE_ID,
    NRHP_SOURCE_ID,
    HistoricRegisterRow,
    build_nrhp_evidence_key,
    build_state_register_evidence_key,
    evaluate_register_row_match,
    fetch_nrhp_rows,
    filter_rows_for_region,
    normalize_historic_name,
    rows_from_hpd_workbook,
    seeded_aliases_for_region,
)
from poi_curator_enrichment.wikidata import (
    WikidataEntity,
    extract_wikidata_id,
    extract_wikipedia_title,
    fetch_wikidata_entities,
)
from poi_curator_enrichment.xlsx_reader import (
    best_sheet_by_headers,
    fetch_xlsx_bytes,
    read_workbook_rows,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WikidataEnrichmentSummary:
    region: str
    candidate_count: int
    enriched_count: int
    skipped_without_wikidata_id: int
    fetch_error_count: int


@dataclass(frozen=True)
class CityGISEnrichmentSummary:
    region: str
    feature_count: int
    evidence_created: int
    unmatched_feature_count: int
    impacted_poi_count: int


@dataclass(frozen=True)
class EvidenceSignalSummary:
    has_official_heritage_match: bool
    official_corroboration_score: float
    district_membership_score: float
    institutional_identity_score: float


@dataclass(frozen=True)
class NRHPEnrichmentSummary:
    region: str
    candidate_row_count: int
    evidence_created: int
    unmatched_row_count: int
    impacted_poi_count: int


@dataclass(frozen=True)
class StateRegisterEnrichmentSummary:
    region: str
    candidate_row_count: int
    evidence_created: int
    unmatched_row_count: int
    impacted_poi_count: int


def enrich_region_from_wikidata(
    session: Session,
    region: str,
    *,
    entity_loader: Callable[[list[str]], dict[str, WikidataEntity]] = fetch_wikidata_entities,
) -> WikidataEnrichmentSummary:
    log_event(logger, "wikidata_enrichment_started", region=region)
    pois = (
        session.execute(
            select(POI)
            .where(POI.city == region, POI.is_active.is_(True))
            .options(joinedload(POI.raw_sources), joinedload(POI.signals))
        )
        .unique()
        .scalars()
        .all()
    )

    candidate_count = len(pois)
    enriched_count = 0
    skipped_without_wikidata_id = 0
    fetch_error_count = 0
    wikidata_ids = sorted(
        {
            wikidata_id
            for poi in pois
            if (wikidata_id := extract_wikidata_id(latest_raw_tags_for_poi(poi)) or poi.wikidata_id)
        }
    )
    cache: dict[str, WikidataEntity] = {}
    for batch in chunked(wikidata_ids, 40):
        try:
            cache.update(entity_loader(batch))
        except Exception:
            fetch_error_count += len(batch)

    for poi in pois:
        raw_tags = latest_raw_tags_for_poi(poi)
        wikidata_id = extract_wikidata_id(raw_tags) or poi.wikidata_id
        wikipedia_title = extract_wikipedia_title(raw_tags)
        if wikidata_id is None:
            skipped_without_wikidata_id += 1
            if wikipedia_title and poi.wikipedia_title is None:
                poi.wikipedia_title = wikipedia_title
            continue

        if wikidata_id not in cache:
            fetch_error_count += 1
            continue

        apply_wikidata_entity(
            poi,
            cache[wikidata_id],
            wikipedia_title_hint=wikipedia_title,
        )
        enriched_count += 1

    session.commit()
    summary = WikidataEnrichmentSummary(
        region=region,
        candidate_count=candidate_count,
        enriched_count=enriched_count,
        skipped_without_wikidata_id=skipped_without_wikidata_id,
        fetch_error_count=fetch_error_count,
    )
    log_event(
        logger,
        "wikidata_enrichment_completed",
        region=summary.region,
        candidate_count=summary.candidate_count,
        enriched_count=summary.enriched_count,
        skipped_without_wikidata_id=summary.skipped_without_wikidata_id,
        fetch_error_count=summary.fetch_error_count,
    )
    return summary


def latest_raw_tags_for_poi(poi: POI) -> dict[str, str]:
    for raw_source in poi.raw_sources:
        if raw_source.is_current:
            tags = raw_source.raw_payload_json.get("tags", {})
            return {str(key): str(value) for key, value in tags.items() if value is not None}
    return {}


def apply_wikidata_entity(
    poi: POI,
    entity: WikidataEntity,
    *,
    wikipedia_title_hint: str | None = None,
) -> None:
    poi.wikidata_id = entity.entity_id
    poi.wikipedia_title = wikipedia_title_hint or entity.wikipedia_title or poi.wikipedia_title
    if should_replace_short_description(poi, entity.description):
        poi.short_description = entity.description
    poi.updated_at = datetime.now(UTC)

    if poi.signals is not None:
        poi.signals.has_wikidata = True
        poi.signals.has_wikipedia = poi.wikipedia_title is not None
        poi.signals.entity_type_confidence = max(poi.signals.entity_type_confidence, 0.9)
        poi.signals.description_quality = max(
            poi.signals.description_quality,
            description_quality_score(poi.short_description, poi.normalized_subcategory),
        )
        poi.signals.computed_at = datetime.now(UTC)


def should_replace_short_description(
    poi: POI,
    wikidata_description: str | None,
) -> bool:
    if wikidata_description is None:
        return False
    if poi.short_description is None:
        return True
    if poi.normalized_subcategory is None:
        return False
    template_description = build_short_description(poi.normalized_subcategory, {})
    return poi.short_description == template_description


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def enrich_region_from_city_gis(
    session: Session,
    region: str,
    *,
    feature_loader: Callable[[str, int], dict[str, object]] | None = None,
) -> CityGISEnrichmentSummary:
    log_event(logger, "city_gis_enrichment_started", region=region)
    settings = get_settings()
    base_url = settings.city_gis_mapserver_url
    loader = feature_loader or (
        lambda request_base_url, layer_id: fetch_arcgis_geojson(
            request_base_url,
            layer_id,
            timeout_seconds=settings.city_gis_timeout_seconds,
        )
    )
    pois = (
        session.execute(
            select(POI)
            .where(POI.city == region, POI.is_active.is_(True))
            .options(joinedload(POI.signals))
        )
        .unique()
        .scalars()
        .all()
    )
    candidate_pois = [
        CandidatePOI(
            poi_id=poi.poi_id,
            canonical_name=poi.canonical_name,
            normalized_category=poi.normalized_category,
            display_categories=list(poi.display_categories),
            centroid=to_shape(poi.centroid),
        )
        for poi in pois
    ]
    poi_by_id = {poi.poi_id: poi for poi in pois}
    source_ids = [layer.source_id for layer in CITY_GIS_LAYER_SPECS]
    poi_ids = list(poi_by_id)
    if poi_ids:
        session.execute(
            delete(POIEvidence).where(
                POIEvidence.poi_id.in_(poi_ids),
                POIEvidence.source_id.in_(source_ids),
            )
        )
    ensure_source_registry(session, base_url)

    feature_count = 0
    evidence_created = 0
    unmatched_feature_count = 0
    impacted_poi_ids: set[str] = set()

    for layer in CITY_GIS_LAYER_SPECS:
        payload = loader(base_url, layer.layer_id)
        features = parse_city_gis_features(payload, layer=layer, base_url=base_url)
        feature_count += len(features)
        for feature in features:
            if layer.kind == "point":
                match = match_point_feature_to_poi(feature, candidate_pois)
                if match is None:
                    unmatched_feature_count += 1
                    continue
                poi = poi_by_id[match.poi_id]
                evidence = build_poi_evidence(feature, poi.poi_id, match.confidence)
                session.add(evidence)
                evidence_created += 1
                impacted_poi_ids.add(poi.poi_id)
                continue

            matched_ids = poi_ids_within_polygon(feature, candidate_pois)
            if not matched_ids:
                unmatched_feature_count += 1
                continue
            for poi_id in matched_ids:
                session.add(build_poi_evidence(feature, poi_id, layer.confidence))
                evidence_created += 1
                impacted_poi_ids.add(poi_id)

    session.flush()
    recompute_evidence_signals(session, [poi_by_id[poi_id] for poi_id in impacted_poi_ids])
    session.commit()
    summary = CityGISEnrichmentSummary(
        region=region,
        feature_count=feature_count,
        evidence_created=evidence_created,
        unmatched_feature_count=unmatched_feature_count,
        impacted_poi_count=len(impacted_poi_ids),
    )
    log_event(
        logger,
        "city_gis_enrichment_completed",
        region=summary.region,
        feature_count=summary.feature_count,
        evidence_created=summary.evidence_created,
        unmatched_feature_count=summary.unmatched_feature_count,
        impacted_poi_count=summary.impacted_poi_count,
    )
    return summary


def enrich_region_from_nrhp(
    session: Session,
    region: str,
    *,
    state_name: str = "NEW MEXICO",
    row_loader: Callable[[], list[HistoricRegisterRow]] | None = None,
) -> NRHPEnrichmentSummary:
    log_event(logger, "nrhp_enrichment_started", region=region)
    settings = get_settings()
    rows = (
        row_loader()
        if row_loader is not None
        else fetch_nrhp_rows(
            settings.nrhp_listed_csv_url,
            timeout_seconds=settings.nrhp_timeout_seconds,
        )
    )
    pois = (
        session.execute(
            select(POI)
            .where(POI.city == region, POI.is_active.is_(True))
            .options(joinedload(POI.signals), joinedload(POI.raw_sources), joinedload(POI.aliases))
        )
        .unique()
        .scalars()
        .all()
    )
    filtered_rows = filter_rows_for_region(rows, state=state_name, city=region)
    poi_ids = [poi.poi_id for poi in pois]
    ensure_seeded_historic_aliases(session, region, pois)
    if poi_ids:
        session.execute(
            delete(POIEvidence).where(
                POIEvidence.poi_id.in_(poi_ids),
                POIEvidence.source_id == NRHP_SOURCE_ID,
            )
        )
    clear_match_diagnostics(session, NRHP_SOURCE_ID, region)
    ensure_nrhp_source_registry(session)

    evidence_created = 0
    unmatched_row_count = 0
    impacted_poi_ids: set[str] = set()
    for row in filtered_rows:
        evaluation = evaluate_register_row_match(row, pois)
        match = evaluation.match
        if match is None:
            unmatched_row_count += 1
            session.add(
                build_match_diagnostic(
                    row,
                    source_id=NRHP_SOURCE_ID,
                    region=region,
                    best_candidate=evaluation.best_candidate,
                )
            )
            continue
        poi = next(poi for poi in pois if poi.poi_id == match.poi_id)
        poi.heritage_id = row.reference_number
        session.add(
            build_nrhp_evidence(
                row,
                poi.poi_id,
                match.confidence,
                match_strategy=match.match_strategy,
            )
        )
        evidence_created += 1
        impacted_poi_ids.add(poi.poi_id)

    session.flush()
    recompute_evidence_signals(session, [poi for poi in pois if poi.poi_id in impacted_poi_ids])
    session.commit()
    summary = NRHPEnrichmentSummary(
        region=region,
        candidate_row_count=len(filtered_rows),
        evidence_created=evidence_created,
        unmatched_row_count=unmatched_row_count,
        impacted_poi_count=len(impacted_poi_ids),
    )
    log_event(
        logger,
        "nrhp_enrichment_completed",
        region=summary.region,
        candidate_row_count=summary.candidate_row_count,
        evidence_created=summary.evidence_created,
        unmatched_row_count=summary.unmatched_row_count,
        impacted_poi_count=summary.impacted_poi_count,
    )
    return summary


def enrich_region_from_nm_state_register(
    session: Session,
    region: str,
    *,
    workbook_loader: Callable[[], bytes] | None = None,
) -> StateRegisterEnrichmentSummary:
    log_event(logger, "state_register_enrichment_started", region=region)
    settings = get_settings()
    workbook_bytes = (
        workbook_loader()
        if workbook_loader is not None
        else fetch_xlsx_bytes(
            settings.nm_hpd_register_workbook_url,
            timeout_seconds=settings.nm_hpd_timeout_seconds,
        )
    )
    workbook_rows = read_workbook_rows(workbook_bytes)
    best_sheet = best_sheet_by_headers(
        workbook_rows,
        required_header_sets=(
            {"property name", "name", "resource name"},
            {"city", "city ", "community", "town"},
            {"county"},
        ),
    )
    if best_sheet is None:
        raise ValueError("No usable sheet found in HPD register workbook.")
    _, rows = best_sheet
    register_rows = rows_from_hpd_workbook(rows)

    pois = (
        session.execute(
            select(POI)
            .where(POI.city == region, POI.is_active.is_(True))
            .options(joinedload(POI.signals), joinedload(POI.raw_sources), joinedload(POI.aliases))
        )
        .unique()
        .scalars()
        .all()
    )
    filtered_rows = filter_rows_for_region(register_rows, state="NEW MEXICO", city=region)
    poi_ids = [poi.poi_id for poi in pois]
    ensure_seeded_historic_aliases(session, region, pois)
    if poi_ids:
        session.execute(
            delete(POIEvidence).where(
                POIEvidence.poi_id.in_(poi_ids),
                POIEvidence.source_id == NM_STATE_REGISTER_SOURCE_ID,
            )
        )
    clear_match_diagnostics(session, NM_STATE_REGISTER_SOURCE_ID, region)
    ensure_state_register_source_registry(session)

    evidence_created = 0
    unmatched_row_count = 0
    impacted_poi_ids: set[str] = set()
    for row in filtered_rows:
        evaluation = evaluate_register_row_match(row, pois, threshold=0.8)
        match = evaluation.match
        if match is None:
            unmatched_row_count += 1
            session.add(
                build_match_diagnostic(
                    row,
                    source_id=NM_STATE_REGISTER_SOURCE_ID,
                    region=region,
                    best_candidate=evaluation.best_candidate,
                )
            )
            continue
        poi = next(poi for poi in pois if poi.poi_id == match.poi_id)
        session.add(
            build_state_register_evidence(
                row,
                poi.poi_id,
                match.confidence,
                match_strategy=match.match_strategy,
            )
        )
        evidence_created += 1
        impacted_poi_ids.add(poi.poi_id)

    session.flush()
    recompute_evidence_signals(session, [poi for poi in pois if poi.poi_id in impacted_poi_ids])
    session.commit()
    summary = StateRegisterEnrichmentSummary(
        region=region,
        candidate_row_count=len(filtered_rows),
        evidence_created=evidence_created,
        unmatched_row_count=unmatched_row_count,
        impacted_poi_count=len(impacted_poi_ids),
    )
    log_event(
        logger,
        "state_register_enrichment_completed",
        region=summary.region,
        candidate_row_count=summary.candidate_row_count,
        evidence_created=summary.evidence_created,
        unmatched_row_count=summary.unmatched_row_count,
        impacted_poi_count=summary.impacted_poi_count,
    )
    return summary


def ensure_source_registry(session: Session, base_url: str) -> None:
    now = datetime.now(UTC)
    for layer in CITY_GIS_LAYER_SPECS:
        source = session.get(SourceRegistry, layer.source_id)
        if source is None:
            session.add(
                SourceRegistry(
                    source_id=layer.source_id,
                    organization_name="City of Santa Fe",
                    source_name=layer.source_name,
                    source_type="gis_layer",
                    trust_class="official_corroboration",
                    base_url=f"{base_url.rstrip('/')}/{layer.layer_id}",
                    license_notes=(
                        "Public ArcGIS REST layer; verify downstream use before redistribution."
                    ),
                    crawl_allowed=True,
                    ingest_method="arcgis_rest",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            continue
        source.organization_name = "City of Santa Fe"
        source.source_name = layer.source_name
        source.source_type = "gis_layer"
        source.trust_class = "official_corroboration"
        source.base_url = f"{base_url.rstrip('/')}/{layer.layer_id}"
        source.ingest_method = "arcgis_rest"
        source.is_active = True
        source.updated_at = now


def ensure_nrhp_source_registry(session: Session) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, NRHP_SOURCE_ID)
    if source is None:
        session.add(
            SourceRegistry(
                source_id=NRHP_SOURCE_ID,
                organization_name="National Park Service",
                source_name="National Register of Historic Places Listed Properties",
                source_type="historic_register",
                trust_class="official_heritage",
                base_url=settings.nrhp_listed_csv_url,
                license_notes="Federal listed-properties CSV used as corroboration metadata.",
                crawl_allowed=True,
                ingest_method="csv_download",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        return
    source.organization_name = "National Park Service"
    source.source_name = "National Register of Historic Places Listed Properties"
    source.source_type = "historic_register"
    source.trust_class = "official_heritage"
    source.base_url = settings.nrhp_listed_csv_url
    source.ingest_method = "csv_download"
    source.is_active = True
    source.updated_at = now


def ensure_state_register_source_registry(session: Session) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    source = session.get(SourceRegistry, NM_STATE_REGISTER_SOURCE_ID)
    if source is None:
        session.add(
            SourceRegistry(
                source_id=NM_STATE_REGISTER_SOURCE_ID,
                organization_name="New Mexico Historic Preservation Division",
                source_name="State and National Register Spreadsheet",
                source_type="historic_register_workbook",
                trust_class="official_state_register",
                base_url=settings.nm_hpd_register_workbook_url,
                license_notes="HPD workbook used as corroboration metadata.",
                crawl_allowed=True,
                ingest_method="xlsx_download",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        return
    source.organization_name = "New Mexico Historic Preservation Division"
    source.source_name = "State and National Register Spreadsheet"
    source.source_type = "historic_register_workbook"
    source.trust_class = "official_state_register"
    source.base_url = settings.nm_hpd_register_workbook_url
    source.ingest_method = "xlsx_download"
    source.is_active = True
    source.updated_at = now


def ensure_seeded_historic_aliases(session: Session, region: str, pois: Sequence[POI]) -> None:
    alias_specs = seeded_aliases_for_region(region)
    if not alias_specs:
        return
    now = datetime.now(UTC)
    poi_by_name = {poi.canonical_name: poi for poi in pois}
    for canonical_name, aliases in alias_specs.items():
        poi = poi_by_name.get(canonical_name)
        if poi is None:
            continue
        existing = {alias.normalized_alias for alias in poi.aliases}
        for alias_spec in aliases:
            normalized_alias = normalize_historic_name(alias_spec.alias_name, relaxed=False)
            if normalized_alias in existing:
                continue
            session.add(
                POIAlias(
                    poi=poi,
                    alias_name=alias_spec.alias_name,
                    normalized_alias=normalized_alias,
                    alias_type=alias_spec.alias_type,
                    source="seeded_historic_aliases",
                    confidence=alias_spec.confidence,
                    is_preferred=alias_spec.is_preferred,
                    notes=alias_spec.notes,
                    created_at=now,
                )
            )
            existing.add(normalized_alias)
    session.flush()


def clear_match_diagnostics(session: Session, source_id: str, region: str) -> None:
    session.execute(
        delete(OfficialMatchDiagnostic).where(
            OfficialMatchDiagnostic.source_id == source_id,
            OfficialMatchDiagnostic.region == region,
        )
    )


def build_match_diagnostic(
    row: HistoricRegisterRow,
    *,
    source_id: str,
    region: str,
    best_candidate: object | None,
) -> OfficialMatchDiagnostic:
    matched_poi_id = getattr(best_candidate, "poi_id", None)
    matched_name = getattr(best_candidate, "matched_name", None)
    best_similarity = getattr(best_candidate, "similarity", None)
    match_strategy = getattr(best_candidate, "match_strategy", None)
    now = datetime.now(UTC)
    return OfficialMatchDiagnostic(
        source_id=source_id,
        region=region,
        external_record_id=row.reference_number or row.property_name,
        external_name=row.property_name,
        matched_poi_id=matched_poi_id,
        best_candidate_name=matched_name,
        best_similarity=best_similarity,
        match_strategy=match_strategy,
        status="unreviewed",
        resolution_method=None,
        raw_payload_json={
            "property_name": row.property_name,
            "other_names": row.other_names,
            "street_address": row.street_address,
            "category_of_property": row.category_of_property,
            "listed_date": row.listed_date,
            "city": row.city,
            "county": row.county,
            "state": row.state,
            "state_register_year": row.state_register_year,
        },
        reviewed_at=None,
        reviewed_by=None,
        created_at=now,
        updated_at=now,
    )


def build_poi_evidence(feature: CityGISFeature, poi_id: str, confidence: float) -> POIEvidence:
    return POIEvidence(
        evidence_key=build_evidence_key(feature, poi_id),
        poi_id=poi_id,
        source_id=feature.layer.source_id,
        evidence_type=feature.layer.evidence_type,
        evidence_label=feature.label,
        evidence_text=build_evidence_text(feature),
        evidence_url=feature.source_url,
        external_record_id=feature.feature_id,
        confidence=round(confidence, 3),
        raw_evidence_json={"properties": feature.properties, "layer_id": feature.layer.layer_id},
        observed_at=datetime.now(UTC),
    )


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


def build_evidence_key(feature: CityGISFeature, poi_id: str) -> str:
    raw = (
        f"{poi_id}:{feature.layer.source_id}:{feature.layer.evidence_type}:"
        f"{feature.feature_id}:{feature.label}"
    )
    return slugify(raw)[:255]


def build_evidence_text(feature: CityGISFeature) -> str:
    if feature.layer.evidence_type == "historic_building_status":
        status = str(feature.properties.get("HBSTAT", "")).strip()
        district = str(feature.properties.get("HBDIST", "")).strip()
        parts = [part for part in [status, district] if part]
        if parts:
            return "; ".join(parts)
    return f"{feature.label} via City of Santa Fe GIS"


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
