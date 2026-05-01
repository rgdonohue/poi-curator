# Admin Endpoint Status

The admin viewer originally needed three read-only admin endpoints. They were implemented on
2026-05-01 in commit `7d14d0d` (`Add read-only admin POI endpoints`).

## Implemented Endpoints

### Paginated POI List

- **Status**: Implemented
- **View**: POI List, Map Browser filters
- **Method**: `GET`
- **Path**: `/v1/admin/pois`
- **Implemented adjustments**:
  - `theme` is a comma-separated list.
  - `theme_match` supports `any` (default) and `all`.
  - `active_only=false` includes inactive/stale POIs for stale-deactivation audits.
  - Each item includes `is_active` and nullable `stale_since`.

Key query params:

- `search: string | null` - match canonical name and aliases
- `category: string | null`
- `review_state: string | null`
- `source: string | null`
- `theme: string | null` - comma-separated theme slugs
- `theme_match: "any" | "all"` - default `any`
- `has_diagnostics: bool | null`
- `has_editorial_overrides: bool | null`
- `active_only: bool` - default `true`
- `limit: int` - default `50`, max `500`
- `offset: int` - default `0`

Response envelope:

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
      "last_updated": "2026-05-01T12:00:00Z",
      "coordinates": [-105.9378, 35.687],
      "has_diagnostics": true,
      "has_editorial_overrides": false,
      "is_active": true,
      "stale_since": null
    }
  ],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

### Read-Only POI Curation Detail

- **Status**: Implemented
- **View**: POI Detail, Map Browser side panel
- **Method**: `GET`
- **Path**: `/v1/admin/pois/{poi_id}`
- **Implemented adjustments**:
  - The endpoint wraps the public `GET /v1/poi/{poi_id}` canonical/detail shape.
  - It adds `editorial_overrides`, evidence `raw_payload`, aliases, match diagnostics, external
    links, and `last_updated`.
  - Shared canonical assembly stays in the existing public POI detail query path.

Response envelope:

```json
{
  "poi_id": "string",
  "canonical": {
    "poi_id": "string",
    "name": "string",
    "primary_category": "string",
    "secondary_categories": ["string"],
    "coordinates": [-105.9378, 35.687],
    "short_description": "string",
    "why_it_matters": ["string"],
    "badges": ["string"],
    "provenance": {},
    "evidence": [],
    "themes": []
  },
  "editorial_overrides": {
    "name": {
      "value": "string",
      "source_value": "string",
      "updated_at": "2026-05-01T12:00:00Z",
      "updated_by": "string"
    }
  },
  "aliases": [],
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
      "observed_at": "2026-05-01T12:00:00Z",
      "raw_payload": {}
    }
  ],
  "themes": [],
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
      "resolution_method": null,
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
  "last_updated": "2026-05-01T12:00:00Z"
}
```

### Map POI Collection

- **Status**: Implemented
- **View**: Map Browser
- **Method**: `GET`
- **Path**: `/v1/admin/pois/map`
- **Implemented adjustments**:
  - Default `limit` is `2000`; max is `5000`.
  - The GeoJSON `FeatureCollection` is wrapped in an envelope with `total_matching`, `returned`,
    `truncated`, and `limit`.
  - Truncation order is deterministic: matching POIs are sorted by `poi_id` before slicing.
  - Endpoint docs note that callers should supply filters or `bbox` to stay under the cap.

Key query params:

- Same filters as `GET /v1/admin/pois`
- `bbox: string | null` - optional `min_lon,min_lat,max_lon,max_lat`
- `limit: int` - default `2000`, max `5000`

Response envelope:

```json
{
  "feature_collection": {
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
          "has_editorial_overrides": false,
          "is_active": true,
          "stale_since": null
        }
      }
    ]
  },
  "total_matching": 4321,
  "returned": 2000,
  "truncated": true,
  "limit": 2000
}
```

## Remaining Notes

- `stale_since` is derived from `poi.updated_at` when an inactive POI has effective review state
  `stale`; there is not a separate database column for stale timestamp yet.
- `reviewer_notes` on detail diagnostics is populated from `raw_payload_json.reviewer_notes` when
  present. The diagnostic table does not currently have a dedicated reviewer-notes column.
