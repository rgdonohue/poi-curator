# POI Curator Check Report

- Generated: 2026-04-08T03:36:30.529765+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 1
- Failed: 0

## PASS nearby-railyard-civic · Railyard Civic Nearby
- Mode: nearby
- Category: civic
- Travel mode: walking
- Query: travel_mode=walking, category=civic, radius_meters=900, limit=5
- Result count: 3
- Results:
  - Atchison, Topeka & Santa Fe Railway Depot (history) match=secondary score=47.5
    summary: Historic site with strong local landscape context.
    breakdown: point_proximity=3.9, radius_fit=2.6, significance=20.4, quality=5.8, mode_affinity=4.4, civic_anchor_bonus=10.0
  - Rail Trail St. Francis Tunnel Grid Vent (civic) match=primary score=47.4
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: point_proximity=8.6, radius_fit=5.7, significance=19.2, quality=6.0, mode_affinity=4.4, penalties=-1.5
  - Denver & Rio Grande Western Railroad Depot (history) match=secondary score=47.2
    summary: Historic site with strong local landscape context.
    breakdown: point_proximity=3.7, radius_fit=2.5, significance=20.4, quality=5.8, mode_affinity=4.4, civic_anchor_bonus=10.0
