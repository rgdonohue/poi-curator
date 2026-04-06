# Santa Fe Evaluation Report

- Cases: 11
- Passed: 11
- Failed: 0

## PASS nearby-acequia-water · Acequia Water Nearby
- Mode: nearby
- Purpose: Prove that the water theme can narrow nearby suggestions to acequia-linked landscape traces.
- Query: travel_mode=walking, category=mixed, theme=water, radius_meters=500, limit=5
- Result count: 1
- Matched expected: Acequia Madre
- Results:
  - Acequia Madre (civic) match=mixed score=33.2 distance_from_center_m=415 access_min=5
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: point_proximity=3.1, radius_fit=2.0, significance=19.2, quality=6.0, mode_affinity=4.4, penalties=-1.5

## PASS nearby-plaza-history · Plaza-Core History Nearby
- Mode: nearby
- Purpose: Protect historical anchors around the plaza core without turning nearby into generic downtown search.
- Query: travel_mode=walking, category=history, radius_meters=800, limit=5
- Result count: 5
- Matched expected: Palace of the Governors
- Results:
  - Museum of Contemporary Native Arts (history) match=primary score=71.8 distance_from_center_m=84 access_min=1
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=16.1, radius_fit=10.7, significance=20.4, quality=8.5, mode_affinity=6.0, category_bonus=10.0
  - Palace of the Governors (history) match=primary score=71.4 distance_from_center_m=131 access_min=2
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=15.1, radius_fit=10.0, significance=21.3, quality=9.0, mode_affinity=6.0, category_bonus=10.0
  - Soldiers' Monument (history) match=primary score=71.0 distance_from_center_m=100 access_min=1
    summary: Monument or memorial with strong public memory value.
    breakdown: point_proximity=15.8, radius_fit=10.5, significance=21.3, quality=9.0, mode_affinity=4.4, category_bonus=10.0
  - Loretto Chapel (history) match=primary score=69.1 distance_from_center_m=191 access_min=2
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=13.7, radius_fit=9.1, significance=21.3, quality=9.0, mode_affinity=6.0, category_bonus=10.0
  - Don Diego de Vargas Zapata Luján Ponce de León, El Marques de la Nava de Barcinas (history) match=primary score=68.2 distance_from_center_m=156 access_min=2
    summary: Monument or memorial with strong public memory value.
    breakdown: point_proximity=14.5, radius_fit=9.7, significance=20.7, quality=9.0, mode_affinity=4.4, category_bonus=10.0

## PASS nearby-canyon-art · Canyon Road Art Nearby
- Mode: nearby
- Purpose: Protect art-oriented nearby behavior around Canyon Road.
- Query: travel_mode=walking, category=art, radius_meters=700, limit=5
- Result count: 1
- Matched expected: Convergence Gallery
- Results:
  - Convergence Gallery (art) match=primary score=44.7 distance_from_center_m=696 access_min=9
    summary: Art space with strong corridor-level cultural identity.
    breakdown: significance=16.8, quality=8.0, mode_affinity=7.2, penalties=-1.5, art_anchor_bonus=4.0, category_bonus=10.0

## PASS nearby-railyard-civic · Railyard Civic Nearby
- Mode: nearby
- Purpose: Protect infrastructural and civic readings around the railyard.
- Query: travel_mode=walking, category=civic, radius_meters=900, limit=5
- Result count: 3
- Matched expected: Atchison, Topeka & Santa Fe Railway Depot, Denver & Rio Grande Western Railroad Depot
- Results:
  - Atchison, Topeka & Santa Fe Railway Depot (history) match=secondary score=47.5 distance_from_center_m=707 access_min=9
    summary: Historic site with strong local landscape context.
    breakdown: point_proximity=3.9, radius_fit=2.6, significance=20.4, quality=5.8, mode_affinity=4.4, civic_anchor_bonus=10.0
  - Rail Trail St. Francis Tunnel Grid Vent (civic) match=primary score=47.4 distance_from_center_m=472 access_min=6
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: point_proximity=8.6, radius_fit=5.7, significance=19.2, quality=6.0, mode_affinity=4.4, penalties=-1.5
  - Denver & Rio Grande Western Railroad Depot (history) match=secondary score=47.2 distance_from_center_m=715 access_min=9
    summary: Historic site with strong local landscape context.
    breakdown: point_proximity=3.7, radius_fit=2.5, significance=20.4, quality=5.8, mode_affinity=4.4, civic_anchor_bonus=10.0

## PASS nearby-plaza-water-empty · Plaza Water Nearby Empty
- Mode: nearby
- Purpose: Protect honest empty behavior when a tight plaza-core query asks specifically for the water theme.
- Query: travel_mode=walking, category=mixed, theme=water, radius_meters=250, limit=5
- Result count: 0
- Results: none

## PASS nearby-downtown-scenic-empty · Downtown Scenic Nearby Empty
- Mode: nearby
- Purpose: Protect honest empty behavior when a tight scenic query in the downtown core has no meaningful answer.
- Query: travel_mode=walking, category=scenic, radius_meters=350, limit=5
- Result count: 0
- Results: none

## PASS route-acequia-water · Acequia Water Route
- Mode: route
- Purpose: Prove that the water theme can pull route-plausible acequia and water-linked traces without turning into generic civic search.
- Query: travel_mode=walking, category=mixed, theme=water, max_detour_meters=600, limit=5
- Result count: 1
- Matched expected: Acequia Madre
- Results:
  - Acequia Madre (civic) match=mixed score=62.8 distance_from_route_m=1 detour_m=2 extra_min=1
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=15.0, detour_fit=14.9, budget_fit=4.7, significance=19.2, quality=6.0, mode_affinity=4.4

## PASS route-historic-center-driving · Historic Center Driving
- Mode: route
- Purpose: Protect the downtown history route where strong primary-history anchors should dominate.
- Query: travel_mode=driving, category=history, max_detour_meters=1800, limit=5
- Result count: 5
- Matched expected: De Vargas Street House
- Results:
  - Digneo-Valdes House (history) match=primary score=81.0 distance_from_route_m=65 detour_m=130 extra_min=1
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=14.3, detour_fit=13.9, budget_fit=4.5, significance=22.5, quality=8.5, mode_affinity=7.2
  - De Vargas Street House (history) match=primary score=80.1 distance_from_route_m=29 detour_m=58 extra_min=1
    summary: Museum or interpretive site with clear historical context.
    breakdown: route_proximity=14.7, detour_fit=14.5, budget_fit=4.6, significance=21.3, quality=9.0, mode_affinity=6.0
  - Gregorio Crespín House (history) match=primary score=78.4 distance_from_route_m=149 detour_m=298 extra_min=1
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=13.4, detour_fit=12.5, budget_fit=4.3, significance=22.5, quality=8.5, mode_affinity=7.2
  - Kruger Building (history) match=primary score=78.4 distance_from_route_m=38 detour_m=76 extra_min=1
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=14.6, detour_fit=14.4, budget_fit=4.6, significance=20.4, quality=7.2, mode_affinity=7.2
  - Tudesque House (history) match=primary score=77.3 distance_from_route_m=139 detour_m=278 extra_min=1
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=13.6, detour_fit=12.7, budget_fit=4.3, significance=21.6, quality=8.0, mode_affinity=7.2

## PASS route-railyard-civic · Rail Yard Corridor
- Mode: route
- Purpose: Protect civic and infrastructural route behavior through the railyard corridor.
- Query: travel_mode=driving, category=civic, max_detour_meters=1500, limit=5
- Result count: 5
- Matched expected: Atchison, Topeka & Santa Fe Railway Depot, Denver & Rio Grande Western Railroad Depot
- Results:
  - Atchison, Topeka & Santa Fe Railway Depot (history) match=secondary score=73.9 distance_from_route_m=185 detour_m=370 extra_min=1
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=12.7, detour_fit=11.3, budget_fit=4.0, significance=20.4, quality=5.8, mode_affinity=7.2
  - Denver & Rio Grande Western Railroad Depot (history) match=secondary score=72.1 distance_from_route_m=196 detour_m=392 extra_min=2
    summary: Historic site with strong local landscape context.
    breakdown: route_proximity=12.6, detour_fit=11.1, budget_fit=3.6, significance=20.4, quality=5.8, mode_affinity=7.2
  - Rail Trail St. Francis Tunnel Grid Vent (civic) match=primary score=66.3 distance_from_route_m=119 detour_m=238 extra_min=1
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=13.5, detour_fit=12.6, budget_fit=4.2, significance=19.2, quality=6.0, mode_affinity=7.2
  - De Fouri Street Bridge (civic) match=primary score=46.3 distance_from_route_m=643 detour_m=1286 extra_min=5
    summary: Replaced the original, narrower bridge
    breakdown: route_proximity=7.0, detour_fit=2.1, budget_fit=1.1, significance=19.2, quality=6.2, mode_affinity=7.2
  - Guadalupe Street Bridge (civic) match=primary score=46.1 distance_from_route_m=655 detour_m=1310 extra_min=5
    summary: Infrastructure trace that reveals labor, circulation, or water systems.
    breakdown: route_proximity=6.8, detour_fit=1.9, budget_fit=1.0, significance=19.2, quality=6.5, mode_affinity=7.2

## PASS route-arts-corridor-walk · Arts Corridor Walk
- Mode: route
- Purpose: Protect art-oriented route behavior near Canyon Road.
- Query: travel_mode=walking, category=art, max_detour_meters=500, limit=5
- Result count: 5
- Matched expected: Convergence Gallery, 3 Studios Gallery, Ronnie Layden Fine Art
- Results:
  - Convergence Gallery (art) match=primary score=79.2 distance_from_route_m=0 detour_m=0 extra_min=1
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=15.0, detour_fit=15.0, budget_fit=4.7, significance=16.8, quality=8.0, mode_affinity=7.2
  - Red Dot Gallery (art) match=primary score=78.2 distance_from_route_m=9 detour_m=18 extra_min=1
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.7, detour_fit=14.5, budget_fit=4.6, significance=16.8, quality=8.0, mode_affinity=7.2
  - Ronnie Layden Fine Art (art) match=primary score=77.4 distance_from_route_m=12 detour_m=24 extra_min=1
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.6, detour_fit=14.3, budget_fit=4.6, significance=16.8, quality=7.5, mode_affinity=7.2
  - Luca Decor Contemporary Art (art) match=primary score=77.3 distance_from_route_m=15 detour_m=30 extra_min=1
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.4, detour_fit=14.1, budget_fit=4.5, significance=16.8, quality=7.8, mode_affinity=7.2
  - 3 Studios Gallery (art) match=primary score=76.2 distance_from_route_m=23 detour_m=46 extra_min=1
    summary: Art space with strong corridor-level cultural identity.
    breakdown: route_proximity=14.1, detour_fit=13.6, budget_fit=4.5, significance=16.8, quality=7.5, mode_affinity=7.2

## PASS route-downtown-scenic-empty · Downtown Scenic Empty
- Mode: route
- Purpose: Protect honest empty behavior for downtown scenic route requests.
- Query: travel_mode=driving, category=scenic, max_detour_meters=400, limit=5
- Result count: 0
- Results: none
