# POI Curator Check Report

- Generated: 2026-05-02T14:48:59.181157+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Backend mode: database_only
- Fixture fallback allowed: False
- Database target: localhost:5432/poi_curator
- Passed: 1
- Failed: 0

## PASS nearby-plaza-water-empty · Plaza Water Nearby Empty
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: water
- Result source: database_empty
- Query: travel_mode=walking, category=mixed, theme=water, radius_meters=250, limit=5
- Result count: 0
- Results: none
