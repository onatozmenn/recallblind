# Roadmap

Two-person team over eight weeks.

- **CS** — data pipeline, extraction models, evaluation harness, dashboard.
- **CONS** — consumer-science lead: hazard taxonomy, scoring rubric, annotation
  protocol, consumer scenarios, interpretation of harm.

Both roles co-own the benchmark design. CONS is not a labelling assistant; it
owns what counts as consumer harm and how it is measured.

## Milestone 1 — Ingestion `DONE`

CPSC and OECD ingestion, unified schema, on-disk cache, CLI, field-coverage
measurement.

**Done when:** `stats` reports non-zero records for both sources. ✅

## Milestone 2 — Identifier extraction `IN PROGRESS`

Baseline regex extractor exists at 52.4% coverage on 1,081 CPSC recalls.

- [ ] Gold set: 300 recalls labelled by two annotators, adjudicated
- [ ] Report baseline precision / recall / $F_1$ against the gold set
- [ ] LLM-assisted extractor, measured on the same gold set
- [ ] Keep whichever wins; publish both numbers

**Done when:** extractor $F_1 \geq 0.85$ on held-out gold data. — *CS + CONS*

## Milestone 3 — Hazard taxonomy

`Hazards[].HazardType` is empty in the source, so the label set is ours.

- [ ] Draft categories from CPSC hazard prose
- [ ] Double-annotate 100 items per category, report Cohen's $\kappa$
- [ ] Rewrite any definition scoring below 0.70 rather than forcing agreement
- [ ] Publish taxonomy with definitions and boundary examples

**Done when:** $\kappa \geq 0.70$ on every category. — *CONS lead*

## Milestone 4 — Hard negatives

The benchmark stands or falls here.

- [ ] Sibling models, adjacent series, corrected successors
- [ ] Verify each negative appears in no recall, at generation time
- [ ] Difficulty tiers by string and semantic distance from the positive
- [ ] Manual review of a sample; a wrong negative is worse than a missing one

**Done when:** ≥ 500 verified negatives across three families. — *CS + CONS*

## Milestone 5 — Task construction

- [ ] T1 status, T2 variant discrimination, T3 correct action, T4 notice quality
- [ ] Fixed prompt templates, published verbatim
- [ ] Temporal splits: pre-cutoff, post-cutoff, fresh
- [ ] Stratified sampling across the strata in the design doc

**Done when:** task files validate and a mock adapter scores end to end. — *CS*

## Milestone 6 — Scoring rubric

- [ ] Operationalise EU GPSR Articles 36–37 elements into scoreable checks
- [ ] Risk-minimising language detector with an explicit term list
- [ ] Human validation of the rubric on 100 responses
- [ ] Inter-rater agreement reported

**Done when:** rubric applied by two humans agrees at $\kappa \geq 0.70$. — *CONS lead*

## Milestone 7 — Model runs

- [ ] Adapters for at least four models
- [ ] Deterministic retrieval baseline for comparison
- [ ] Parametric versus tool-assisted runs reported separately
- [ ] Cost and latency logged per run

**Done when:** four models scored on all four tasks. — *CS*

## Milestone 8 — Release

- [ ] Leaderboard and error-analysis views
- [ ] Dataset card: provenance, limitations, intended use, misuse
- [ ] Technical report with USR / BOR / NCS and confidence intervals
- [ ] Archived release with DOI

**Done when:** an outsider can reproduce the headline numbers from a clean clone.

## Explicit non-goals

- Not a consumer-facing recall lookup product.
- No claim of global coverage; scope is CPSC plus OECD-listed economies.
- No bulk redistribution of authority content.
- No legal advice.

## Open risks

| Risk | Response |
|---|---|
| Extraction errors propagate into ground truth | Gold set before any modelling claim |
| Over-flagging harms sellers | BOR is co-primary with USR |
| Recall status drifts between build and publication | Re-verify positives at release |
| Judge-model bias in T4 | Human-validated sample; publish judge prompt |
| Scope creep back into multi-country legal analysis | Decisions log requires an ADR to reopen |
