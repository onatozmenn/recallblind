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
Annotation tooling is built; the labelling itself is the remaining work.

- [x] Deterministic 300-record sample, fixed seed, reproducible without sharing files
- [x] Annotation CLI with resume, plus a written labelling rule in `data/gold/README.md`
- [x] Cohen's $\kappa$ and micro-averaged precision / recall / $F_1$, self-checked
- [ ] Two independent annotation passes over the sample
- [ ] Adjudicate disagreements and report baseline $F_1$
- [ ] LLM-assisted extractor, measured on the same gold set
- [ ] Keep whichever wins; publish both numbers

**Done when:** extractor $F_1 \geq 0.85$ on held-out gold data. — *CS + CONS*

## Milestone 3 — Hazard taxonomy `IN PROGRESS`

`Hazards[].HazardType` is empty in the source, so the label set is ours. Eleven
mechanism categories drafted from the prose of 1,081 recalls, covering 97.7%.

- [x] Draft categories from CPSC hazard prose, with measured frequencies
- [x] Separate mechanism from outcome, so categories do not collapse into "injury"
- [x] Publish taxonomy with definitions and boundary examples
- [x] Annotation tooling with per-category $\kappa$
- [ ] Double-annotate the 200-record sample
- [ ] Rewrite any definition scoring below 0.70 rather than forcing agreement

**Done when:** $\kappa \geq 0.70$ on every category. — *CONS lead*

## Milestone 4 — Hard negatives `DONE`

The benchmark stands or falls here. 1,981 candidates, each verified against the
recall index before emission.

- [x] Adjacent series: one digit changed, verified absent from all recalls (543)
- [x] Corrected successor: revision suffix, as reissued after a fix (544)
- [x] Brand-other-category: brand recalled elsewhere, none in this category (894)
- [x] Difficulty tiers recorded per family
- [ ] Manual review of a sample; a wrong negative is worse than a missing one

**Done when:** ≥ 500 verified negatives across three families. — *CS + CONS*

## Milestone 5 — Task construction `DONE`

All four tasks build and score, with 45 tests pinning the harness.

- [x] Fixed prompt templates, published in `recallblind/tasks.py`
- [x] Temporal splits: pre-cutoff, post-cutoff and fresh
- [x] T1 status and T2 variant discrimination, balanced 400 + 400
- [x] T3 correct action, scored on the authority's own remedy
- [x] T4 notice quality, scored on the weighted GPSR Article 36 elements
- [x] Deterministic adapters pin every headline metric at both extremes

**Done when:** all four tasks validate and a mock adapter scores. — *CS*

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
