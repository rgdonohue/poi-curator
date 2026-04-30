# Data Quality Governance

This project is a data-quality project first. The backend should help Detour surface meaningful
places, but the durable value is the transparent, reviewable corpus underneath: where records came
from, how they were processed, which claims are supported, which claims are uncertain, and where
human editorial judgment entered the system.

The working standard is:

> Preserve source truth, label derived interpretation, and never let generated text become
> canonical data without review.

## Goals

- Make every app-facing POI traceable to source records, evidence rows, and processing decisions.
- Distinguish documented facts from derived signals, editorial interpretation, and generated drafts.
- Expose uncertainty and coverage gaps instead of smoothing them away.
- Treat cultural and historical geography as situated, source-dependent, and reviewable.
- Prevent synthetic or generated material from contaminating the canonical corpus.

## Data Classes

Use these distinctions consistently in code, exports, documentation, and review workflows.

### Source Data

Source data is material imported from an external source or official/local dataset with provenance.

Examples:

- OSM/Overpass raw elements and tags
- Santa Fe City GIS features
- NRHP listed-property rows
- New Mexico HPD register workbook rows
- Wikidata entity fields and identifiers

Rules:

- Store source data with source id, source record id, fetch/load time, raw payload, and license or
  access notes when available.
- Do not rewrite source meaning to fit the app taxonomy.
- Keep source rows separate from canonical POIs.
- Absence from a source is not evidence of insignificance.

### Canonical Data

Canonical data is the normalized POI record used by query paths.

Examples:

- canonical name
- geometry and centroid
- primary category and secondary display categories
- source ids and provenance references
- current active/review status

Rules:

- Canonical data can be derived from source data and editorial decisions, but its basis should be
  inspectable.
- Canonical data should not contain model-generated facts.
- Canonical fields may contain reviewed editorial text, but generated drafts must not overwrite
  canonical descriptions until approved.

### Evidence

Evidence is a structured claim-support record attached to a POI.

Examples:

- official historic-register match
- city GIS district membership
- public art layer match
- place-of-worship layer match
- Wikidata identity link

Rules:

- Evidence records should identify source, evidence type, label/text/url, confidence, and observed
  time.
- Evidence supports specific claims or signals; it does not automatically prove broad cultural
  importance.
- Official evidence means "documented by an official source," not "more important."

### Derived Signals

Derived signals are heuristic scores or classifications computed from canonical data and evidence.

Examples:

- `base_significance_score`
- `quality_score`
- `interpretive_value_score`
- `official_corroboration_score`
- theme membership confidence
- category match type

Rules:

- Derived signals are review aids, not objective measures of cultural value.
- Signal names and formulas should be documented when they affect app-facing ranking.
- Scoring changes should be evaluated with fixtures and check-suite reports.
- Avoid language that implies neutral measurement where the project is encoding judgment.

### Editorial Interpretation

Editorial interpretation is human review or correction.

Examples:

- suppressing a POI
- approving or rewriting a description
- adding an alias
- resolving an official match diagnostic
- force-including or force-excluding a theme membership
- changing category or title display

Rules:

- Editorial decisions should be auditable: reviewer, timestamp, decision, and notes where possible.
- Culturally sensitive corrections, force-includes, and force-excludes should include notes.
- Editorial interpretation may change what the app shows, but it should not erase source records.

### Generated Drafts

Generated drafts are text or structured outputs produced by deterministic scripts or models.

Examples:

- frontend seed `description_map`
- frontend seed `description_card`
- extractor/writer/critic JSONL outputs
- mock writer/critic outputs

Rules:

- Generated drafts are not source data.
- Generated drafts are not canonical data.
- Generated drafts must carry review status and basis metadata.
- Generated drafts must not introduce unsupported dates, actors, events, community claims, or
  historical causality.
- A generated draft may become canonical only after explicit human review and approval.

## Synthetic Data Policy

Synthetic data is allowed only in tests, fixtures, mocks, and clearly labeled drafts.

Synthetic or generated material must not be treated as production corpus data, source evidence, or
canonical historical/cultural fact.

Allowed:

- unit-test fixtures
- local UI smoke fixtures
- mock extractor/writer/critic outputs
- deterministic draft descriptions labeled as drafts

Not allowed:

- generated POIs in production exports without clear fixture/mock labeling
- generated evidence rows pretending to be source-backed evidence
- generated descriptions overwriting canonical POI descriptions without review
- synthetic facts inserted to fill source gaps

## Source Bias And Coverage Limits

The project should document limitations for each source family.

### OSM / Overpass

- Coverage and tagging are volunteer-produced and uneven.
- Tags are useful discovery hints, not authoritative cultural classification.
- Named objects are overrepresented relative to vernacular or undocumented landscapes.
- Mapper notes and maintenance-oriented text should not become traveler-facing copy.

### Santa Fe City GIS

- GIS layers are strong for boundaries, civic assets, and local administrative records.
- Layer inclusion reflects municipal data priorities and maintenance practices.
- City GIS evidence should support spatial or institutional context, not broad cultural claims by
  itself.

### NRHP And New Mexico HPD

- Register data is useful formal documentation, but it reflects official recognition systems.
- Official recognition can overrepresent certain property types, time periods, ownership histories,
  and preservation priorities.
- Register absence must not imply lack of cultural or historical significance.

### Wikidata / Wikipedia

- Coverage favors already documented, notable, and internet-visible places.
- Descriptions can be generic or externally framed.
- Wikidata/Wikipedia identifiers help identity resolution but should not dominate local
  interpretation.

## Export Governance

App-facing exports should make record basis obvious.

Recommended fields for current or future exports:

- `record_origin`: database, fixture_overlay, manual_export, test_fixture
- `source_basis`: compact list of source/evidence families used
- `evidence_strength`: high, medium, low, unknown
- `description_status`: none, source, generated_draft, editorial_approved
- `description_method`: source_import, deterministic_draft, model_draft, editorial
- `description_review_status`: unreviewed, needs_revision, approved, rejected
- `claim_basis`: source ids or evidence labels used for human-facing claims
- `risk_flags`: cultural, historical, religious, memorial, low_evidence, synthetic_fixture

Do not publish an export that mixes DB-backed and fixture-overlay rows without a visible
`record_origin` or equivalent field.

## Fixture Fallback Governance

The hybrid scoring backend can fall back to fixture data. This is useful for tests and local UI
work, but it is risky for data-quality claims.

Rules:

- Production-like runs should disable or clearly log fixture fallback.
- Evaluation reports should say whether results came from DB-backed records, fixture fallback, or a
  mix.
- Frontend handoff artifacts should label fixture-overlay rows.
- A response that came from fallback should not be cited as proof of database corpus quality.

## Data Quality Checks

Start with a manual checklist and convert high-value checks into tests or scripts.

Minimum checklist:

- App-facing rows have visible provenance or record-origin fields.
- Generated descriptions are labeled as drafts unless reviewed.
- Claims in generated descriptions have a basis field or evidence packet.
- Fixture rows are visibly labeled.
- Theme assignments expose rule/evidence/editorial basis.
- Official-source matches below confidence thresholds become diagnostics, not silent links.
- Suppressed POIs do not surface in public query results.
- Sensitive rows have review notes before being treated as approved copy.

## Governance Roadmap

### Near Term

- Keep this governance document linked from README, methodology, and agent guidance.
- Add warnings to description-generation workflows.
- Label generated description exports as drafts.
- Document current verification gaps honestly.

### Medium Term

- Add automated checks for export provenance and generated-draft labeling.
- Add runtime diagnostics or config to expose/disable fixture fallback.
- Add review-state fields to frontend handoff outputs where missing.
- Capture reviewer outcomes from check-suite or manual review runs.

### Later

- Build source coverage audits by category, geography, and theme.
- Add second-city readiness criteria focused on local source ecology and review capacity.
- Version scoring profiles and publish before/after quality reports.
- Build admin UI surfaces only for governance bottlenecks that API/export review cannot handle.
