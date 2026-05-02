# Sources

This file documents source inputs used by the Santa Fe multi-source corpus. Source records remain
separate from canonical POIs; canonical fields carry per-field provenance.

## OpenStreetMap / Overpass

- Source id for field provenance: `osm`
- Raw ingest source name: `osm_overpass`
- URL: configured by `POI_CURATOR_OVERPASS_URL`
- License: ODbL 1.0
- Refresh cadence: manual local ingest for now
- Canonical fields contributed: `name`, `primary_category`, `coordinates`, `short_description`
- Match strategy: OSM source identifiers are stable for OSM refresh. OSM is not privileged over
  other sources; it is one contributor to canonical rows.

## National Register of Historic Places

- Source id: `nrhp`
- URL: `https://irma.nps.gov/DataStore/DownloadFile/662624`
- Reference page/API: `https://irma.nps.gov/DataStore/Reference/Profile/2210280` and
  `https://irma.nps.gov/DataStore/Reference/GetHoldings?referenceId=2210280`
- Chosen format: NPS `NRIS_CR_Standards_Public.gdb.zip` public file geodatabase. Canonical
  ingestion joins `NR_Main.PropertyID` to public geometry layers by `NRIS_Refnum`, filters to
  `State = NEW MEXICO`, `County = Santa Fe`, `Status = Listed`, and uses point coordinates or a
  representative point for public polygon geometry.
- Acquisition date: 2026-05-01
- License/access notes: federal NPS listed-property download; confirm downstream redistribution
  requirements before publishing raw rows.
- Refresh cadence: manual local ingest for now
- Current scope: New Mexico rows filtered to Santa Fe County. The county filter is explicit so the
  same adapter can be re-scoped later.
- Canonical fields contributed: `name`, `primary_category`, `coordinates`, `short_description`
- Match strategy: Wikidata identifier first when present, then a 100 m spatial window plus
  normalized name similarity at threshold 0.85. Ambiguous multi-candidate matches are logged for
  editorial review.

### NRHP ingestion history

- Legacy source id: `nrhp_listed_properties`
- Legacy feed URL: configured by `POI_CURATOR_NRHP_LISTED_CSV_URL`; local default is
  `https://www.nps.gov/common/uploads/sortable_dataset/nationalregister/53699964-0893-68AA-5273CB1C614B8BB3/nri-national-register-listed20250624.csv`
- Legacy feed date/format: NPS listed-properties CSV dated 2025-06-24 in the filename.
- Local legacy run date: evidence rows observed in the database at 2026-04-04 13:18 UTC.
- Legacy behavior: the enrichment path attached high-confidence register evidence to existing
  canonicals, but unmatched records were routed to `official_match_diagnostic` for editorial review
  rather than creating canonical POIs. That CSV did not provide coordinates, so matching was
  name/candidate based and deliberately conservative.

## City of Santa Fe Historic Districts

- Source id: `city_gis_historic_districts`
- URL: `https://gis.santafenm.gov/server/rest/services/Public_Viewer/MapServer/118`
- Chosen format: ArcGIS REST GeoJSON query from the historic district polygon layer
- License/access notes: public City of Santa Fe ArcGIS REST layer; verify downstream use before
  redistribution.
- Refresh cadence: manual local ingest for now
- Current scope: active canonical POIs in the requested Santa Fe region
- Canonical fields contributed: none in this phase
- Evidence contributed: `district_membership`
- Match strategy: polygon containment/intersection against canonical POI centroids. District
  polygons do not become canonical POIs in this phase.

## USGS Geographic Names Information System

- Source id: `gnis`
- Download/documentation URL:
  `https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data`
- Current state text URL:
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/DomesticNames/DomesticNames_NM_Text.zip`
- Variant-name URL:
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/Topical/AllNames_National_Text.zip`
- Historical-feature URL:
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/Topical/HistoricalFeatures_National_Text.zip`
- Chosen format: USGS pipe-delimited text files inside `.zip` downloads. The New Mexico domestic
  names file provides official names and coordinates; the national All Names topical file provides
  official and variant names keyed by `feature_id`; the national Historical Features topical file
  marks records whose GNIS historical designation means the name is no longer in use or the feature
  no longer serves its original purpose.
- Acquisition date: 2026-05-02
- License/access notes: USGS GNIS downloads are public domain.
- Refresh cadence: manual local ingest for now; USGS states that GNIS data products are refreshed
  every other month.
- Current scope: New Mexico rows filtered to Santa Fe County for canonical creation. Other New
  Mexico counties are retained only when they attach as evidence to an existing cross-county
  canonical POI.
- Relevance filter: canonical candidates are limited to `Canal`, `Civil`, `Crossing`, `Military`,
  and `Populated Place`. This intentionally excludes broad natural-feature classes, generic
  reservoir/tank records, and non-POI utility records such as bench marks or coordinate locators
  where they appear in legacy products.
- Canonical fields contributed: `name`, `primary_category`, `coordinates`, `short_description`
- Evidence contributed: `geographic_name`, `variant_name`, and `historical_feature`
- Match strategy: existing shared matcher only; Wikidata identifier first when available, then a
  100 m spatial window plus normalized name similarity at threshold 0.85. Historical GNIS records
  can attach as evidence to an existing canonical, but do not create new canonical POIs.

## New Mexico OSE Points of Diversion and Acequia Conveyances

- Source ids: `nmose_pod`, `nmose_acequia`
- Catalog URL:
  `https://catalog.newmexicowaterdata.org/application/new-mexico-points-of-diversion-and-water-rights-regulatory-map`
- POD ArcGIS REST layer:
  `https://services2.arcgis.com/qXZbWTdPDbTjl7Dy/arcgis/rest/services/OSE_Points_of_Diversion/FeatureServer/0`
- Conveyance ArcGIS REST layer:
  `https://services2.arcgis.com/qXZbWTdPDbTjl7Dy/arcgis/rest/services/OSE_Conveyances/FeatureServer/0`
- Chosen format: ArcGIS REST GeoJSON queries.
- License/access notes: public NM OSE ArcGIS REST data. OSE publishes the geographic data and
  metadata as-is without warranty; verify downstream redistribution before publishing raw rows.
- Refresh cadence: manual local ingest for now. The catalog describes PODs as monthly-updated.
- Current scope: Santa Fe County. POD canonical creation is intentionally limited to active Santa
  Fe County POD records tied to meaningful named conveyances, because the full county POD layer is
  mostly water-rights/well infrastructure and would produce noisy canonical POIs. Acequia evidence
  uses active, named, acequia-like conveyance geometries (`ACQ`, `ACQT`, `CMD`, `CAN`, `DIT`) that
  intersect a Santa Fe County envelope.
- Canonical fields contributed: `name`, `primary_category`, `coordinates`, `short_description` for
  POD-created canonical POIs.
- Evidence contributed: `point_of_diversion`, `acequia_membership`, `acequia_association`.
- Match strategy: POD points use the shared multi-source matcher, with Wikidata identifier support
  if present and the current 100 m spatial/name fallback. Acequia conveyance lines do not become
  canonical POIs; they attach membership evidence to existing canonical POIs within a 50 m buffer.
- Data-sovereignty caveat: Source New Mexico reported on 2023-06-08 that acequia stewards raised
  concerns about public mapping and that about 73% of acequia systems in the state map were
  unnamed. This ingestion uses only publicly published OSE data and does not augment with stewards'
  private records, local knowledge, unpublished names, or steward-collected maps without explicit
  permission.

## Wikidata

- Source id: `wikidata`
- URL: configured by `POI_CURATOR_WIKIDATA_API_URL`
- License/access notes: Wikidata entity metadata used as attributed evidence
- Canonical fields contributed: identity fields and alternate labels/descriptions as provenance
- Match strategy: attached as identity evidence when an existing canonical POI has an OSM/Wikidata
  identifier or already-linked entity.
