# Description Enrichment Batch

- Records: 519
- Pilot selection size: 20
- Origins: {"database": 515, "fixture_overlay": 4}
- Evidence strength counts: {"high": 43, "low": 421, "medium": 55}

Governance note: this batch contains generated draft artifacts. They are not source data, evidence,
or canonical POI descriptions. Fixture-overlay rows must remain visibly labeled, and no generated
description should be treated as approved copy until a human review decision records that status.

Artifacts:
- `evidence_packets.jsonl`: grounded evidence packet for each seed row
- `pilot_evidence_packets.jsonl`: pilot-only evidence packets
- `extractor_tasks.jsonl`: batch-ready fact extraction prompts
- `pilot_extractor_tasks.jsonl`: pilot-only extractor prompts
- `writer_tasks.jsonl`: batch-ready writer prompts
- `pilot_writer_tasks.jsonl`: pilot-only writer prompts
- `critic_tasks.jsonl`: batch-ready critic prompts with a writer output placeholder
- `pilot_critic_tasks.jsonl`: pilot-only critic prompts
- `pilot_selection.csv`: high-priority rows to review first
- `schemas/*.json`: output templates for each pass
- `starter_*_results.jsonl`: empty starter files keyed to the pilot rows

Recommended pass order:
1. Run extractor on the pilot selection first.
2. Run writer using the extractor outputs.
3. Run critic on the writer outputs.
4. Review flagged rows manually before scaling to the full set.
5. Only after the pilot looks good, run the full batch.

Before any frontend handoff, preserve or add fields for `record_origin`, `description_status`,
`description_method`, `description_review_status`, and `claim_basis`.
