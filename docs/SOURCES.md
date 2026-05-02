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

## Wikidata

- Source id: `wikidata`
- URL: configured by `POI_CURATOR_WIKIDATA_API_URL`
- License/access notes: Wikidata entity metadata used as attributed evidence
- Canonical fields contributed: identity fields and alternate labels/descriptions as provenance
- Match strategy: attached as identity evidence when an existing canonical POI has an OSM/Wikidata
  identifier or already-linked entity.
