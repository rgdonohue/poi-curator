# POI Curator Check Suite Run

- Fixtures: data/fixtures/eval_santa_fe.json
- Suites: 4
- Case runs: 28
- Passed: 28
- Failed: 0

- Backend mode: database_only
- Fixture fallback allowed: False
- Database target: localhost:5432/poi_curator

## core-product
- Description: Balanced product smoke suite across nearby, route, themes, and strong anchors.
- Cases: 6
- Passed: 6
- Failed: 0
- JSON: core-product.json
- Markdown: core-product.md

## all-fixtures
- Description: Every saved evaluation case in the fixture file.
- Cases: 14
- Passed: 14
- Failed: 0
- JSON: all-fixtures.json
- Markdown: all-fixtures.md

## empty-result-guardrails
- Description: Cases where honest empty results are better than decorative filler.
- Cases: 4
- Passed: 4
- Failed: 0
- JSON: empty-result-guardrails.json
- Markdown: empty-result-guardrails.md

## rail-smoke
- Description: Rail-focused cases that protect depot anchors and keep weaker corridor traces behind.
- Cases: 4
- Passed: 4
- Failed: 0
- JSON: rail-smoke.json
- Markdown: rail-smoke.md
