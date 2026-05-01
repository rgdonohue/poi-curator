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

- **POI List**: Shows the intended table and filter controls for a paginated POI inventory. The
  required list endpoint is not exposed yet, so this pass renders an explicit endpoint-needed state.
- **POI Detail**: Loads a known POI id through `GET /v1/poi/{poi_id}`. It shows canonical public
  fields, exposed evidence grouped by source, exposed theme memberships, external OSM/Wikidata
  links when discoverable, and a small MapLibre location map.
- **Map Browser**: Provides the full-screen MapLibre shell and filter sidebar. Clustered active POI
  markers require a collection endpoint that is not exposed yet.
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
- POI list pagination/filtering, all-POI map browsing, aliases, diagnostics, reviewer notes, and
  editorial override indicators need additional read-only admin API support. See
  `apps/admin/NEEDED_ENDPOINTS.md`.
- Frontend tests are intentionally out of scope for this pass; use a manual smoke test through the
  running FastAPI app.
