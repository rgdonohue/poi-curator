# Needed Admin Endpoints

The static admin viewer is read-only and does not add API routes in this pass. These endpoints are
needed to complete the requested views without CSV exports or hand-written SQL.

## Paginated POI List

- **View**: POI List, Map Browser
- **Method**: `GET`
- **Path**: `/v1/admin/pois`
- **Query params**:
  - `search: string | null` - match canonical name and aliases
  - `category: string | null`
  - `review_state: string | null`
  - `source: string | null`
  - `theme: string | null`
  - `has_diagnostics: bool | null`
  - `has_editorial_overrides: bool | null`
  - `active_only: bool` - default `true`
  - `limit: int` - default `50`, max `500`
  - `offset: int` - default `0`
- **Response shape**:

```json
{
  "items": [
    {
      "poi_id": "string",
      "name": "string",
      "primary_category": "string",
      "secondary_categories": ["string"],
      "review_state": "needs_review",
      "source": "OSM",
      "themes": ["water", "rail"],
      "last_updated": "2026-04-30T12:00:00Z",
      "coordinates": [-105.9378, 35.687],
      "has_diagnostics": true,
      "has_editorial_overrides": false
    }
  ],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

## Read-Only POI Curation Detail

- **View**: POI Detail, Map Browser side panel
- **Method**: `GET`
- **Path**: `/v1/admin/pois/{poi_id}`
- **Query params**: none
- **Response shape**:

```json
{
  "poi_id": "string",
  "canonical": {
    "name": "string",
    "primary_category": "string",
    "secondary_categories": ["string"],
    "review_state": "needs_review",
    "source": "OSM",
    "coordinates": [-105.9378, 35.687],
    "short_description": "string",
    "why_it_matters": ["string"],
    "badges": ["string"],
    "provenance": {}
  },
  "editorial_overrides": {
    "name": {
      "value": "string",
      "source_value": "string",
      "updated_at": "2026-04-30T12:00:00Z",
      "updated_by": "string"
    }
  },
  "aliases": [
    {
      "alias_name": "string",
      "normalized_alias": "string",
      "alias_type": "manual",
      "source": "editorial",
      "confidence": 1.0,
      "is_preferred": false,
      "notes": "string",
      "created_at": "2026-04-30T12:00:00Z"
    }
  ],
  "evidence": [
    {
      "evidence_id": 1,
      "source_id": "wikidata",
      "source_name": "Wikidata",
      "source_type": "linked_open_data",
      "trust_class": "reference",
      "evidence_type": "identity",
      "label": "string",
      "text": "string",
      "url": "https://example.test",
      "external_record_id": "Q123",
      "confidence": 0.9,
      "match_method": "string",
      "observed_at": "2026-04-30T12:00:00Z",
      "raw_payload": {}
    }
  ],
  "themes": [
    {
      "theme_slug": "water",
      "label": "Water",
      "status": "accepted",
      "assignment_basis": "automated",
      "confidence": 0.85,
      "score": 0.85,
      "rationale_summary": "string",
      "evidence": [
        {
          "evidence_id": 1,
          "source_id": "wikidata",
          "evidence_type": "identity",
          "label": "string",
          "confidence": 0.9
        }
      ],
      "editorial_decision": null
    }
  ],
  "match_diagnostics": [
    {
      "id": 1,
      "source_id": "nrhp",
      "external_record_id": "string",
      "external_name": "string",
      "best_candidate_poi_id": "string",
      "best_candidate_name": "string",
      "best_similarity": 0.72,
      "match_strategy": "string",
      "why_not_auto_linked": "string",
      "state": "unreviewed",
      "reviewer_notes": "string",
      "reviewed_at": null,
      "reviewed_by": null
    }
  ],
  "external_links": {
    "osm": "https://www.openstreetmap.org/node/1",
    "wikidata": "https://www.wikidata.org/wiki/Q123"
  },
  "last_updated": "2026-04-30T12:00:00Z"
}
```

## Map POI Collection

- **View**: Map Browser
- **Method**: `GET`
- **Path**: `/v1/admin/pois/map`
- **Query params**:
  - Same filters as `GET /v1/admin/pois`
  - `bbox: string | null` - optional `min_lon,min_lat,max_lon,max_lat`
- **Response shape**:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-105.9378, 35.687]
      },
      "properties": {
        "poi_id": "string",
        "name": "string",
        "primary_category": "string",
        "review_state": "needs_review",
        "source": "OSM",
        "themes": ["water"],
        "has_diagnostics": true,
        "has_editorial_overrides": false
      }
    }
  ]
}
```
