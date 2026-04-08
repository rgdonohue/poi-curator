# POI Curator Check Report

- Generated: 2026-04-08T03:27:50.567925+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 1
- Failed: 0

## PASS nearby-railyard-rail · Railyard Rail Nearby
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: rail
- Query: travel_mode=walking, category=mixed, theme=rail, radius_meters=900, limit=5
- Result count: 4
- Results:
  - Atchison, Topeka & Santa Fe Railway Depot (history) match=mixed score=49.0
    summary: Historic site with strong local landscape context.
    breakdown: point_proximity=3.9, radius_fit=2.6, significance=20.4, quality=5.8, mode_affinity=4.4, rail_anchor_bonus=4.0
  - Denver & Rio Grande Western Railroad Depot (history) match=mixed score=48.7
    summary: Historic site with strong local landscape context.
    breakdown: point_proximity=3.7, radius_fit=2.5, significance=20.4, quality=5.8, mode_affinity=4.4, rail_anchor_bonus=4.0
  - Santa Fe Railyard Park (scenic) match=mixed score=48.5
    summary: Landscape access point with ecological or scenic value.
    breakdown: point_proximity=13.0, radius_fit=8.6, significance=15.6, quality=6.8, mode_affinity=6.0, penalties=-1.5
  - Rail Trail St. Francis Tunnel Grid Vent (civic) match=mixed score=39.4
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: point_proximity=8.6, radius_fit=5.7, significance=19.2, quality=6.0, mode_affinity=4.4, penalties=-1.5
