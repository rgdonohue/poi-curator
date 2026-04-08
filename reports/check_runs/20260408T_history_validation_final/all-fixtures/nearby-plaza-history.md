# POI Curator Check Report

- Generated: 2026-04-08T03:52:43.734071+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 1
- Failed: 0

## PASS nearby-plaza-history · Plaza-Core History Nearby
- Mode: nearby
- Category: history
- Travel mode: walking
- Query: travel_mode=walking, category=history, radius_meters=800, limit=5
- Result count: 5
- Results:
  - Palace of the Governors (history) match=primary score=77.4
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=15.1, radius_fit=10.0, significance=21.3, quality=9.0, mode_affinity=6.0, history_anchor_bonus=6.0
  - Museum of Contemporary Native Arts (history) match=primary score=71.8
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=16.1, radius_fit=10.7, significance=20.4, quality=8.5, mode_affinity=6.0, category_bonus=10.0
  - The Santa Fe Plaza (civic) match=secondary score=71.3
    summary: Civic space that helps explain the structure of public life.
    breakdown: point_proximity=15.8, radius_fit=10.5, significance=21.9, quality=9.0, mode_affinity=7.2, penalties=-1.5
  - Soldiers' Monument (history) match=primary score=71.0
    summary: Monument or memorial with strong public memory value.
    breakdown: point_proximity=15.8, radius_fit=10.5, significance=21.3, quality=9.0, mode_affinity=4.4, category_bonus=10.0
  - Loretto Chapel (history) match=primary score=69.1
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=13.7, radius_fit=9.1, significance=21.3, quality=9.0, mode_affinity=6.0, category_bonus=10.0
