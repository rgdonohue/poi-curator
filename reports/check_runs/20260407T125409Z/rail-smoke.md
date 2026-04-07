# POI Curator Check Report

- Generated: 2026-04-07T12:54:10.271412+00:00
- Runs: 4
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 4
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

## PASS route-railyard-civic · Rail Yard Corridor
- Mode: route
- Category: civic
- Travel mode: driving
- Query: travel_mode=driving, category=civic, max_detour_meters=1500, limit=5
- Result count: 5
- Results:
  - Atchison, Topeka & Santa Fe Railway Depot (history) match=secondary score=73.9
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=12.7, detour_fit=11.3, budget_fit=4.0, significance=20.4, quality=5.8, mode_affinity=7.2
  - Denver & Rio Grande Western Railroad Depot (history) match=secondary score=72.1
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=12.6, detour_fit=11.1, budget_fit=3.6, significance=20.4, quality=5.8, mode_affinity=7.2
  - Rail Trail St. Francis Tunnel Grid Vent (civic) match=primary score=66.3
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=13.5, detour_fit=12.6, budget_fit=4.2, significance=19.2, quality=6.0, mode_affinity=7.2
  - De Fouri Street Bridge (civic) match=primary score=46.3
    summary: Replaced the original, narrower bridge
    breakdown: route_proximity=7.0, detour_fit=2.1, budget_fit=1.1, significance=19.2, quality=6.2, mode_affinity=7.2
  - Guadalupe Street Bridge (civic) match=primary score=46.1
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=6.8, detour_fit=1.9, budget_fit=1.0, significance=19.2, quality=6.5, mode_affinity=7.2

## PASS route-railyard-rail · Rail Corridor Theme Route
- Mode: route
- Category: mixed
- Travel mode: walking
- Theme: rail
- Query: travel_mode=walking, category=mixed, theme=rail, max_detour_meters=900, limit=5
- Result count: 4
- Results:
  - Atchison, Topeka & Santa Fe Railway Depot (history) match=mixed score=57.2
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=11.2, detour_fit=8.8, budget_fit=2.7, significance=20.4, quality=5.8, mode_affinity=4.4
  - Denver & Rio Grande Western Railroad Depot (history) match=mixed score=56.6
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=10.9, detour_fit=8.5, budget_fit=2.7, significance=20.4, quality=5.8, mode_affinity=4.4
  - Rail Trail St. Francis Tunnel Grid Vent (civic) match=mixed score=52.2
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=12.5, detour_fit=11.0, budget_fit=3.6, significance=19.2, quality=6.0, mode_affinity=4.4
  - Santa Fe Railyard Park (scenic) match=mixed score=49.3
    summary: Landscape access point with ecological or scenic value.
    breakdown: route_proximity=11.1, detour_fit=8.7, budget_fit=2.7, significance=15.6, quality=6.8, mode_affinity=6.0
