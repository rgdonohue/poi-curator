# Description Enrichment Workflow

This document defines a practical temporary workflow for generating historically truthful, culturally-geographic descriptions for the frontend seed inventory at [query_capable_pois_frontend_seed.csv](/Users/richard/Documents/projects/poi-curator/reports/query_capable_pois_frontend_seed.csv).

It is intentionally conservative. The point is not to produce polished tourism copy. The point is to produce grounded copy that is safer, more specific, and easier to review.

This workflow is governed by
[DATA_QUALITY_GOVERNANCE.md](/Users/richard/Documents/projects/poi-curator/docs/DATA_QUALITY_GOVERNANCE.md).
Generated descriptions are drafts. They are not source data, evidence, or canonical POI
descriptions unless a human reviewer explicitly approves them and records that approval.

## Non-Negotiable Data Rules

- Do not create synthetic POIs.
- Do not create synthetic evidence.
- Do not invent dates, named actors, ownership histories, events, community meanings, or causal
  historical claims.
- Do not let generated draft text overwrite canonical POI descriptions.
- Do not publish generated descriptions without visible review status and basis metadata.
- Treat official-source support as documentation evidence, not proof of greater cultural value.

## Goals

- Turn generic machine descriptions into more place-aware copy.
- Keep every generated sentence tied to an explicit evidence packet.
- Separate writing from fact extraction and criticism.
- Make it easy to review the first 20 rows before scaling to all 519.

## Output Shape

Each POI should eventually have two generated description fields:

- `description_map`: 18 to 30 words
- `description_card`: 35 to 65 words

Each generated row should also carry review metadata:

- `factual_basis`
- `claims_avoided`
- `confidence`
- `risk_flags`
- `critic_verdict`
- `critic_issues`

Recommended governance metadata:

- `description_status`: `generated_draft` until approved
- `description_method`: `deterministic_draft` or `model_draft`
- `description_review_status`: `unreviewed`, `needs_revision`, `approved`, or `rejected`
- `claim_basis`: source ids, evidence labels, or packet fields used for the description
- `record_origin`: database, fixture overlay, or other explicit origin

## Process

Use a three-pass loop.

1. Evidence packet build
2. Extractor pass
3. Writer pass
4. Critic pass

An optional fourth pass can rewrite only rows the critic flagged.

### 1. Evidence packet build

Use [build_description_enrichment_batch.py](/Users/richard/Documents/projects/poi-curator/scripts/build_description_enrichment_batch.py) to transform the frontend seed into grounded packets.

Run:

```bash
python3 scripts/build_description_enrichment_batch.py
```

Default output directory:

```text
reports/description_enrichment/frontend_seed_v1/
```

Artifacts:

- `evidence_packets.jsonl`
- `extractor_tasks.jsonl`
- `writer_tasks.jsonl`
- `critic_tasks.jsonl`
- `pilot_selection.csv`

The evidence packet includes:

- identity fields and coordinates
- category and theme context
- the current short description
- signal fields already present in the seed CSV
- inferred archetype
- factual cues
- writing constraints
- risk flags
- output templates for extractor, writer, and critic results

### 2. Extractor pass

The extractor turns the evidence packet into a narrow factual basis.

The extractor should return:

- `supported_facts`
- `geographic_context`
- `historical_context`
- `cultural_context`
- `hard_constraints`
- `missing_information`
- `confidence`
- `risk_flags`

This pass exists to reduce hallucination pressure on the writer.

### 3. Writer pass

The writer should see:

- the evidence packet
- the extractor output
- the writing rules

The writer should:

- produce `description_map`
- produce `description_card`
- list which facts it actually used
- list which claims it intentionally avoided

The writer should not:

- invent dates, events, or actors
- speak for a living community without evidence
- turn weak evidence into strong narrative claims
- use tourism cliches
- treat a register/GIS/Wikidata match as permission to add unsupported historical explanation

### 4. Critic pass

The critic should use a different model family when possible.

The critic should check for:

- unsupported facts
- romanticized or boosterish language
- flattening of Indigenous, Hispano, colonial, religious, or memorial histories
- geographic vagueness when the packet supports stronger specificity

The critic should return:

- `verdict`
- `issues`
- `suggested_rewrite_notes`
- `confidence`

## Review Assembly

After you have extractor, writer, and critic outputs, merge them into a review CSV.

Use [merge_description_batch_results.py](/Users/richard/Documents/projects/poi-curator/scripts/merge_description_batch_results.py):

```bash
python3 scripts/merge_description_batch_results.py \
  --extractor-results reports/description_enrichment/frontend_seed_v1/extractor_results.jsonl \
  --writer-results reports/description_enrichment/frontend_seed_v1/writer_results.jsonl \
  --critic-results reports/description_enrichment/frontend_seed_v1/critic_results.jsonl \
  --pilot-only
```

That produces a review surface with:

- source identity and classification columns
- extractor factual basis columns
- writer draft columns
- critic verdict columns
- blank editorial columns for human review

The review CSV should preserve draft status until a reviewer explicitly approves or rewrites the
description. Approval means the reviewer accepts both the wording and the claim basis.

## Validation

Validate each pass before merging:

```bash
python3 scripts/validate_description_batch_outputs.py \
  --kind extractor \
  --input reports/description_enrichment/frontend_seed_v1/extractor_results.jsonl \
  --expected-record-ids reports/description_enrichment/frontend_seed_v1/pilot_selection.csv

python3 scripts/validate_description_batch_outputs.py \
  --kind writer \
  --input reports/description_enrichment/frontend_seed_v1/writer_results.jsonl \
  --expected-record-ids reports/description_enrichment/frontend_seed_v1/pilot_selection.csv

python3 scripts/validate_description_batch_outputs.py \
  --kind critic \
  --input reports/description_enrichment/frontend_seed_v1/critic_results.jsonl \
  --expected-record-ids reports/description_enrichment/frontend_seed_v1/pilot_selection.csv
```

The validator checks:

- record coverage and duplicate `record_id`s
- required keys and value types
- allowed confidence levels
- writer word-count bounds
- critic verdict values

## Rollout Strategy

Do not run all 519 rows first.

Start with the pilot file:

- [pilot_selection.csv](/Users/richard/Documents/projects/poi-curator/reports/description_enrichment/frontend_seed_v1/pilot_selection.csv)

Suggested pilot order:

1. `fixture_overlay` rows
2. highest-significance DB rows
3. rows with high cultural or historical sensitivity

Review the pilot outputs manually before scaling to the full set.

## Acceptance Criteria For Scaling

Do not scale beyond the pilot unless these conditions hold:

- extractor outputs are complete for every pilot row
- writer outputs pass validation with no missing fields
- critic outputs pass validation with no missing fields
- manual review finds no obvious hallucinated dates, actors, or community claims
- manual review finds the wording materially better than the generic seed copy
- high-sensitivity rows are readable without romanticizing or flattening local history
- fixture-overlay rows remain visibly labeled
- generated descriptions remain labeled as drafts unless approved

## Prompting Guidance

Wording preferences:

- Prefer `reflects`, `reveals`, `marks`, `is associated with`, `sits within`
- Prefer geographic and material readings over abstract importance claims
- Use time qualifiers only when supported

Avoid:

- `iconic`
- `charming`
- `vibrant`
- `must-see`
- `hidden gem`
- unsourced claims about oldest, first, unique, authentic, traditional, sacred, or community meaning

## Archetype-Specific Notes

Not every POI should sound the same.

Common archetypes:

- `water_corridor`
- `rail_corridor`
- `ritual_religious_site`
- `civic_core`
- `district_or_corridor`
- `overlook_landscape`
- `art_site`
- `historic_site`
- `landscape_site`
- `civic_infrastructure_site`

The first useful improvement is to vary copy by archetype instead of using one universal style.

## Recommendation

For a temporary frontend corpus:

- keep the generated copy outside the canonical POI table at first
- review it as a sidecar CSV or JSONL artifact
- only promote reviewed descriptions into editorial overrides later

That preserves a clean line between:

- machine-generated source descriptions
- temporary frontend copy
- eventual editorial truth
