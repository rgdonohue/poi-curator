# POI Curator Check Report

- Generated: 2026-04-23T14:56:37.578912+00:00
- Runs: 6
- Fixtures: data/fixtures/eval_santa_fe.json
- Backend mode: hybrid
- Fixture fallback allowed: True
- Database target: localhost:5432/poi_curator
- Passed: 0
- Failed: 6

## FAIL nearby-plaza-history · Plaza-Core History Nearby
- Mode: nearby
- Category: history
- Travel mode: walking
- Result source: fixture_fallback_db_error
- Query: travel_mode=walking, category=history, radius_meters=800, limit=5
- Result count: 2
- Warning: None of the preferred top names appeared in the top 3 results.
- Note: None of the expected candidate names appeared in the result set.
- Note: Expected at least 3 results but got 2.
- Note: Not enough preferred top names appeared in the returned top results (0/2).
- Results:
  - Santa Fe Plaza (culture) match=secondary score=119.5
    summary: Historic civic core where colonial planning, commerce, and public life still intersect.
  - Cross of the Martyrs Overlook (scenic) match=secondary score=77.7
    summary: Overlook with a strong topographic read on the city and visible historical framing.

## FAIL nearby-canyon-art · Canyon Road Art Nearby
- Mode: nearby
- Category: art
- Travel mode: walking
- Result source: fixture_fallback_db_error
- Query: travel_mode=walking, category=art, radius_meters=700, limit=5
- Result count: 1
- Warning: None of the preferred top names appeared in the top 3 results.
- Note: None of the expected candidate names appeared in the result set.
- Results:
  - Canyon Road Arts Corridor (art) match=primary score=117.2
    summary: Dense art corridor where street sequence and galleries read as a cultural landscape.

## FAIL nearby-railyard-rail · Railyard Rail Nearby
- Mode: nearby
- Category: mixed
- Travel mode: walking
- Theme: rail
- Result source: fixture_fallback_db_error
- Query: travel_mode=walking, category=mixed, theme=rail, radius_meters=900, limit=5
- Result count: 1
- Warning: None of the preferred top names appeared in the top 3 results.
- Note: None of the expected candidate names appeared in the result set.
- Results:
  - Santa Fe Rail Yard District (civic) match=mixed score=103.6
    summary: Former rail infrastructure turned civic corridor with strong labor and settlement traces.

## FAIL route-historic-center-driving · Historic Center Driving
- Mode: route
- Category: history
- Travel mode: driving
- Result source: fixture_fallback_db_error
- Query: travel_mode=driving, category=history, max_detour_meters=1800, limit=5
- Result count: 4
- Warning: None of the preferred top names appeared in the top 3 results.
- Note: None of the expected candidate names appeared in the result set.
- Note: Not enough preferred top names appeared in the returned top results (0/2).
- Results:
  - Acequia Madre (history) match=primary score=108.4
    summary: Historic irrigation corridor that still reads the city's water geography.
  - Santa Fe Plaza (culture) match=primary score=104.1
    summary: Historic civic core where colonial planning, commerce, and public life still intersect.
  - Santa Fe Rail Yard District (civic) match=primary score=97.2
    summary: Former rail infrastructure turned civic corridor with strong labor and settlement traces.
  - Cross of the Martyrs Overlook (scenic) match=primary score=87.1
    summary: Overlook with a strong topographic read on the city and visible historical framing.

## FAIL route-railyard-rail · Rail Corridor Theme Route
- Mode: route
- Category: mixed
- Travel mode: walking
- Theme: rail
- Result source: fixture_fallback_db_error
- Query: travel_mode=walking, category=mixed, theme=rail, max_detour_meters=900, limit=5
- Result count: 1
- Warning: None of the preferred top names appeared in the top 3 results.
- Note: None of the expected candidate names appeared in the result set.
- Results:
  - Santa Fe Rail Yard District (civic) match=primary score=94.8
    summary: Former rail infrastructure turned civic corridor with strong labor and settlement traces.

## FAIL route-arts-corridor-walk · Arts Corridor Walk
- Mode: route
- Category: art
- Travel mode: walking
- Result source: fixture_fallback_db_error
- Query: travel_mode=walking, category=art, max_detour_meters=500, limit=5
- Result count: 0
- Note: Expected non-empty result set but got none.
- Note: None of the expected candidate names appeared in the result set.
- Note: Expected at least 1 results but got 0.
- Results: none
