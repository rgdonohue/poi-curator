# Admin Viewer

This is a minimal read-only admin viewer served by the FastAPI app at:

```text
http://localhost:8000/admin
```

Start the API with:

```bash
make api
```

The viewer has no build step and no separate deployment. It uses `index.html`, `admin.js`,
`admin.css`, and MapLibre GL JS from the same CDN pattern used by `/map-test`.

## Admin Key

Open **Settings**, paste the `X-POI-Curator-Admin-Key`, and choose **Save key**. The key is stored
in `localStorage` and sent as the `X-POI-Curator-Admin-Key` header on admin requests. After saving,
the UI clears the input and does not display the key. Use **Clear key** to remove it from
`localStorage`.

## Views

- **POI List**: Uses `GET /v1/admin/pois` for a paginated POI inventory with category,
  review-state, source, theme, diagnostics, editorial-override, active-only, and free-text filters.
- **POI Detail**: Loads a known POI id through `GET /v1/admin/pois/{poi_id}`. It shows canonical
  fields, editorial override badges, aliases, evidence grouped by source with raw payloads, theme
  memberships, match diagnostics, external OSM/Wikidata links, and a small MapLibre location map.
- **Map Browser**: Uses `GET /v1/admin/pois/map` for clustered active POI markers with the same
  filters as the POI List. If the endpoint returns `truncated=true`, the sidebar shows the returned
  and total counts so curators know to apply tighter filters.
- **Query Logs**: Uses `GET /v1/admin/query-logs` with the saved admin key. Supports endpoint, date
  range, and result-count filters. Expanding a row shows `request_payload` and the result array, with
  result POI ids linked to the POI Detail view.
- **Health & Source**: Shows a top-bar `scoring_source` badge from `/v1/health` and raw formatted
  output for `/v1/health` and `/v1/config`.

## Limitations

- No mutation UI: no editorial overrides, alias creation, diagnostic resolution, theme review, or
  ingest actions.
- No bulk actions.
- No authentication beyond the existing admin key header.
- The map browser requests up to 2000 features. Use filters to reduce the result set when the UI
  reports truncation.
- Frontend tests are intentionally out of scope for this pass; use a manual smoke test through the
  running FastAPI app.
