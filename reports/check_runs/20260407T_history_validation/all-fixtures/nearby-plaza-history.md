# POI Curator Check Report

- Generated: 2026-04-08T03:27:50.567185+00:00
- Runs: 1
- Fixtures: data/fixtures/eval_santa_fe.json
- Passed: 0
- Failed: 1

## FAIL nearby-plaza-history · Plaza-Core History Nearby
- Mode: nearby
- Category: history
- Travel mode: walking
- Query: travel_mode=walking, category=history, radius_meters=800, limit=5
- Result count: 5
- Note: Not enough preferred top names appeared in the returned top results (1/2).
- Results:
  - Palace of the Governors (history) match=primary score=77.4
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=15.1, radius_fit=10.0, significance=21.3, quality=9.0, mode_affinity=6.0, history_anchor_bonus=6.0
  - Museum of Contemporary Native Arts (history) match=primary score=71.8
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=16.1, radius_fit=10.7, significance=20.4, quality=8.5, mode_affinity=6.0, category_bonus=10.0
  - The Palace Press (history) match=primary score=71.5
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=14.2, radius_fit=9.4, significance=19.2, quality=6.8, mode_affinity=6.0, history_anchor_bonus=6.0
  - Soldiers' Monument (history) match=primary score=71.0
    summary: Monument or memorial with strong public memory value.
    breakdown: point_proximity=15.8, radius_fit=10.5, significance=21.3, quality=9.0, mode_affinity=4.4, category_bonus=10.0
  - Loretto Chapel (history) match=primary score=69.1
    summary: Museum or interpretive site with clear historical context.
    breakdown: point_proximity=13.7, radius_fit=9.1, significance=21.3, quality=9.0, mode_affinity=6.0, category_bonus=10.0
