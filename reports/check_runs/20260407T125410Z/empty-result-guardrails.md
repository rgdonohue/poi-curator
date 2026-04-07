# POI Curator Check Report

- Generated: 2026-04-07T12:54:11.108788+00:00
- Runs: 4
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 4
- Failed: 0

## PASS nearby-plaza-water-empty · Plaza Water Nearby Empty
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: water
- Query: travel_mode=walking, category=mixed, theme=water, radius_meters=250, limit=5
- Result count: 0
- Results: none

## PASS nearby-plaza-rail-empty · Plaza Rail Nearby Empty
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: rail
- Query: travel_mode=walking, category=mixed, theme=rail, radius_meters=350, limit=5
- Result count: 0
- Results: none

## PASS nearby-downtown-scenic-empty · Downtown Scenic Nearby Empty
- Mode: nearby
- Category: scenic
- Travel mode: walking
- Query: travel_mode=walking, category=scenic, radius_meters=350, limit=5
- Result count: 0
- Results: none

## PASS route-downtown-scenic-empty · Downtown Scenic Empty
- Mode: route
- Category: scenic
- Travel mode: driving
- Query: travel_mode=driving, category=scenic, max_detour_meters=400, limit=5
- Result count: 0
- Results: none
