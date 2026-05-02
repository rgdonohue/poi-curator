# Provenance Model

Canonical POIs are source-agnostic. A canonical row may originate from OSM, NRHP, or a later source,
but source origin does not grant authority to overwrite reviewed fields.

## Tables

`poi_field_provenance` records sourced values for canonical fields:

- `poi_id`: canonical POI
- `field_name`: public field name, such as `name`, `primary_category`, `coordinates`, or
  `short_description`
- `source_id`: contributor, for example `osm`, `nrhp`, or `wikidata`
- `value`: JSONB value as observed or derived from that source
- `confidence`: source/adapter confidence
- `observed_at`: ingest/enrichment observation time
- `is_canonical`: true for the value currently shown on the canonical POI row

`poi_match_log` records source-to-canonical matching decisions:

- `candidate_source` and `candidate_external_id`
- `match_strategy`, such as `identifier:wikidata`, `spatial_name`, or `source_identifier`
- `match_score`
- `decision`: `match`, `ambiguous`, or `new`
- `decided_at`, `decided_by`, and `notes`

`poi_field_conflicts` is a database view over `poi_field_provenance` that surfaces fields with more
than one distinct sourced value.

## Conflict Policy

Conflicts are visible, not automatically resolved. If NRHP says one name and OSM says another, both
values remain in `poi_field_provenance`; the canonical row keeps its current reviewed value until an
editor changes it.

New source records that match an existing canonical POI attach evidence and provenance. They do not
overwrite canonical fields. New canonical POIs are created only when matching returns `new`.

## Examples

An OSM-origin POI may have:

- canonical `name`: `Palace of the Governors`
- provenance rows from `osm` and `wikidata` for `name`
- an `nrhp` alternate `name` row if the register label differs

An NRHP-only property may have:

- `primary_source = nrhp`
- canonical provenance rows from `nrhp`
- historic designation evidence from `nrhp`
- no OSM raw source rows
