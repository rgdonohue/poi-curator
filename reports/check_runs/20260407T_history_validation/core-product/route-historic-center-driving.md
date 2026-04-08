# POI Curator Check Report

- Generated: 2026-04-08T03:27:50.387685+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 0
- Failed: 1

## FAIL route-historic-center-driving · Historic Center Driving
- Mode: route
- Category: history
- Travel mode: driving
- Query: travel_mode=driving, category=history, max_detour_meters=1800, limit=5
- Result count: 5
- Note: Not enough preferred top names appeared in the returned top results (1/2).
- Results:
  - Digneo-Valdes House (history) match=primary score=81.0
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=14.3, detour_fit=13.9, budget_fit=4.5, significance=22.5, quality=8.5, mode_affinity=7.2
  - De Vargas Street House (history) match=primary score=80.1
    summary: Museum or interpretive site with clear historical context.
    breakdown: route_proximity=14.7, detour_fit=14.5, budget_fit=4.6, significance=21.3, quality=9.0, mode_affinity=6.0
  - Gregorio Crespín House (history) match=primary score=78.4
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=13.4, detour_fit=12.5, budget_fit=4.3, significance=22.5, quality=8.5, mode_affinity=7.2
  - Kruger Building (history) match=primary score=78.4
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=14.6, detour_fit=14.4, budget_fit=4.6, significance=20.4, quality=7.2, mode_affinity=7.2
  - Tudesque House (history) match=primary score=77.3
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=13.6, detour_fit=12.7, budget_fit=4.3, significance=21.6, quality=8.0, mode_affinity=7.2
