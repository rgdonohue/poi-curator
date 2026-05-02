# POI Curator Check Report

- Generated: 2026-05-02T14:48:59.182663+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Backend mode: database_only
- Fixture fallback allowed: False
- Database target: localhost:5432/poi_curator
- Passed: 1
- Failed: 0

## PASS route-downtown-scenic-empty · Downtown Scenic Empty
- Mode: route
- Category: scenic
- Travel mode: driving
- Result source: database_empty
- Query: travel_mode=driving, category=scenic, max_detour_meters=400, limit=5
- Result count: 0
- Results: none
