# POI Curator Check Report

- Generated: 2026-05-02T14:48:59.181325+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Backend mode: database_only
- Fixture fallback allowed: False
- Database target: localhost:5432/poi_curator
- Passed: 1
- Failed: 0

## PASS nearby-plaza-rail-empty · Plaza Rail Nearby Empty
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: rail
- Result source: database_empty
- Query: travel_mode=walking, category=mixed, theme=rail, radius_meters=350, limit=5
- Result count: 0
- Results: none
