# POI Curator Check Report

- Generated: 2026-04-07T12:54:47.560428+00:00
- Runs: 14
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 14
- Failed: 0

## PASS nearby-acequia-water · Acequia Water Nearby
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: water
- Query: travel_mode=walking, category=mixed, theme=water, radius_meters=500, limit=5
- Result count: 1
- Results:
  - Acequia Madre (civic) match=mixed score=33.2
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: point_proximity=3.1, radius_fit=2.0, significance=19.2, quality=6.0, mode_affinity=4.4, penalties=-1.5

## PASS nearby-plaza-history · Plaza-Core History Nearby
- Mode: nearby
- Category: history
- Travel mode: walking
- Query: travel_mode=walking, category=history, radius_meters=800, limit=5
- Result count: 5
- Results:
  - Museum of Contemporary Native Arts (history) match=primary score=71.8
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=16.1, radius_fit=10.7, significance=20.4, quality=8.5, mode_affinity=6.0, category_bonus=10.0
  - Palace of the Governors (history) match=primary score=71.4
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=15.1, radius_fit=10.0, significance=21.3, quality=9.0, mode_affinity=6.0, category_bonus=10.0
  - Soldiers' Monument (history) match=primary score=71.0
    summary: Monument or memorial with strong public memory value.
    breakdown: point_proximity=15.8, radius_fit=10.5, significance=21.3, quality=9.0, mode_affinity=4.4, category_bonus=10.0
  - Loretto Chapel (history) match=primary score=69.1
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=13.7, radius_fit=9.1, significance=21.3, quality=9.0, mode_affinity=6.0, category_bonus=10.0
  - Don Diego de Vargas Zapata Luján Ponce de León, El Marques de la Nava de Barcinas (history) match=primary score=68.2
    summary: Monument or memorial with strong public memory value.
    breakdown: point_proximity=14.5, radius_fit=9.7, significance=20.7, quality=9.0, mode_affinity=4.4, category_bonus=10.0

## PASS nearby-canyon-art · Canyon Road Art Nearby
- Mode: nearby
- Category: art
- Travel mode: walking
- Query: travel_mode=walking, category=art, radius_meters=700, limit=5
- Result count: 1
- Results:
  - Convergence Gallery (art) match=primary score=44.7
    summary: Art space with strong corridor-level cultural identity.
    breakdown: significance=16.8, quality=8.0, mode_affinity=7.2, penalties=-1.5, art_anchor_bonus=4.0, category_bonus=10.0

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

## PASS route-acequia-water · Acequia Water Route
- Mode: route
- Category: mixed
- Travel mode: walking
- Theme: water
- Query: travel_mode=walking, category=mixed, theme=water, max_detour_meters=600, limit=5
- Result count: 1
- Results:
  - Acequia Madre (civic) match=mixed score=62.8
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=15.0, detour_fit=14.9, budget_fit=4.7, significance=19.2, quality=6.0, mode_affinity=4.4

## PASS route-historic-center-driving · Historic Center Driving
- Mode: route
- Category: history
- Travel mode: driving
- Query: travel_mode=driving, category=history, max_detour_meters=1800, limit=5
- Result count: 5
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

## PASS route-arts-corridor-walk · Arts Corridor Walk
- Mode: route
- Category: art
- Travel mode: walking
- Query: travel_mode=walking, category=art, max_detour_meters=500, limit=5
- Result count: 5
- Results:
  - Convergence Gallery (art) match=primary score=79.2
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=15.0, detour_fit=15.0, budget_fit=4.7, significance=16.8, quality=8.0, mode_affinity=7.2
  - Red Dot Gallery (art) match=primary score=78.2
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.7, detour_fit=14.5, budget_fit=4.6, significance=16.8, quality=8.0, mode_affinity=7.2
  - Ronnie Layden Fine Art (art) match=primary score=77.4
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.6, detour_fit=14.3, budget_fit=4.6, significance=16.8, quality=7.5, mode_affinity=7.2
  - Luca Decor Contemporary Art (art) match=primary score=77.3
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.4, detour_fit=14.1, budget_fit=4.5, significance=16.8, quality=7.8, mode_affinity=7.2
  - 3 Studios Gallery (art) match=primary score=76.2
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.1, detour_fit=13.6, budget_fit=4.5, significance=16.8, quality=7.5, mode_affinity=7.2

## PASS route-downtown-scenic-empty · Downtown Scenic Empty
- Mode: route
- Category: scenic
- Travel mode: driving
- Query: travel_mode=driving, category=scenic, max_detour_meters=400, limit=5
- Result count: 0
- Results: none
