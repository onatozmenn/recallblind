# Decision log

Short architecture decision records. Reopening a decision requires a new entry,
not an edit to an old one.

---

## ADR-001 — Scope is recall-blindness, not general shopping-AI auditing

**Date:** 2026-08-04 · **Status:** accepted

Broader framings (commercial bias, dark patterns, personalised pricing) are
already occupied. Measured on GitHub the same day: `"dark patterns"` 738 repos,
`ecommerce price tracker` 1,422, `"fake review detection"` 1,752. Product-safety
auditing of AI shopping assistants returned no direct hits.

Prior art we do **not** duplicate:

- [RECALL-MM](https://arxiv.org/abs/2503.23213) — CPSC dataset for engineering
  designers; strips brand names, so it cannot answer "is this product recalled?"
- [ACES](https://arxiv.org/abs/2508.02630) — position, sponsorship and price bias
  in agentic commerce.
- [ShoppingMMLU](https://github.com/KL4805/ShoppingMMLU) — shopping skill.
- [Bias Beware](https://github.com/geofila/Bias-Beware) — cognitive-bias attacks
  on recommenders.

**Consequence:** every task must trace back to physical consumer safety.

---

## ADR-002 — Türkiye is out of scope

**Date:** 2026-08-04 · **Status:** accepted

Türkiye publishes unsafe-product notices only through GÜBİS, which offers no
public API. It is absent from the OECD Global Recalls economy list, verified by
querying the facet endpoint. The only route to structured Turkish data would be a
ministry relationship, which the team has ruled out.

**Consequence:** no Turkish data source, and no Turkish legal axis. The rubric is
based on EU GPSR alone. Non-English evaluation, if revisited, needs its own ADR.

---

## ADR-003 — CPSC is primary, OECD is secondary

**Date:** 2026-08-04 · **Status:** accepted

CPSC gives depth: hazard prose, remedy text, images, retailers, and the free text
that carries model numbers. OECD gives breadth: 56,608 records across 50
economies plus a product taxonomy, but its dates are unreliable — `orderby=date-desc`
does not return recent records and placeholder `1900-01-01` values are common.

**Consequence:** temporal splits come from CPSC only. OECD supports coverage
claims and taxonomy, never recency.

---

## ADR-004 — Core pipeline uses the standard library only

**Date:** 2026-08-04 · **Status:** accepted

Ingestion and extraction must run on a clean Python 3.11 install with no
packaging step, so a collaborator can reproduce numbers immediately.

**Consequence:** model adapters and analysis may add dependencies, but they stay
outside the core modules.

---

## ADR-005 — Distribute identifiers and annotations, not bulk source data

**Date:** 2026-08-04 · **Status:** accepted

CPSC output is US public domain, but OECD responses carry `© OECD. All rights
reserved`. Shipping fetch scripts plus our annotations respects both, and keeps
the benchmark current instead of frozen.

**Consequence:** `data/` is git-ignored; reproduction requires running the CLI.

---

## ADR-006 — Ship a regex extraction baseline before any LLM extractor

**Date:** 2026-08-04 · **Status:** accepted

`Products[].Model` is empty in 100% of records, so identifiers must come from
prose. A transparent baseline reaching 52.4% coverage sets the bar any learned
extractor must clear on the same human-labelled sample.

An early precision bug is instructive: `40V` and `20-in` were captured as model
numbers. A unit filter removed 37 spurious tokens while coverage moved only
52.5% → 52.4%.

**Consequence:** no extractor replaces the baseline without a measured $F_1$ on
the gold set.

---

## ADR-007 — Notice-quality scoring derives from EU GPSR Articles 36–37

**Date:** 2026-08-04 · **Status:** accepted

Rather than invent a "good warning" rubric, we operationalise the elements that
[Regulation (EU) 2023/988](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R0988)
requires of a recall notice, in force since 13 December 2024: clear hazard
description, no risk-minimising language, an explicit instruction to stop using
the product, and available remedies. Recital 87 reports that about one third of
consumers keep using dangerous products after seeing a notice.

**Consequence:** T4 scores are defensible against an external standard rather
than team preference.

---

## ADR-008 — USR and BOR are co-primary metrics

**Date:** 2026-08-04 · **Status:** accepted

Under-warning endangers consumers; over-flagging damages sellers and mirrors a
real failure seen on marketplaces, where safe variants are blocked because a
sibling model was recalled. Authorities are explicit that a notice covers only the
notified product.

**Consequence:** no headline result may report one metric without the other.


---

## ADR-009 — Unsafe action means the absence of a stop-using instruction

**Date:** 2026-08-04 · **Status:** accepted

T3's headline was first defined as "no stop-using instruction OR wording that
invites continued use". The oracle adapter then failed on real items, because
authorities do scope a recall to one function: SharkNinja's notice tells consumers
to stop using the pressure-cooking function while continuing to use the rest.
Quoting the authority was being scored as unsafe advice.

`unsafe_action` is therefore the absence of a stop-using instruction alone.
Continuation wording is still recorded as `unsafe_continuation_rate` and reported
as a diagnostic.

**Consequence:** the headline is high precision and cannot be triggered by a
faithful quotation. Contradictory advice that both stops and permits use is not
detected by rules and is left to the T4 human validation sample.

---

## ADR-010 — T4 is scored only on facts the prompt showed

**Date:** 2026-08-04 · **Status:** accepted

Hazard and remedy text is truncated before it enters a prompt. Scoring against the
full authority record marked responses non-compliant for omitting text they were
never given, which cost the ceiling adapter 26% of the remedy element.

Gold hazards are derived from the truncated string that actually appears in the
prompt, and the remedy excerpt is the sentence naming the remedy rather than the
first N characters. An item whose remedy cannot be shown is dropped from T4.

**Consequence:** NCS = 1.0 is reachable, so the metric has a real ceiling. T3
still withholds the remedy on purpose, since knowing it is the thing being tested.

---

## ADR-011 — Negative identifiers are synthetic, and this bounds the claim

**Date:** 2026-08-04 · **Status:** accepted

`adjacent_code` and `corrected_successor` build identifiers that are absent from
every recall record but are not known to exist as products. A model answering
NOT_RECALLED for a string that names nothing is right for a weaker reason than one
that discriminates two real catalogue entries. No public dataset of non-recalled
consumer products exists to do better.

**Consequence:** BOR measures over-generalisation from brand and code resemblance,
which is the marketplace failure we care about. It does not measure real catalogue
discrimination, and results must not be described as if it did.

---

## ADR-012 — The hazard taxonomy labels mechanism, not outcome

**Date:** 2026-08-04 · **Status:** accepted

CPSC hazard prose puts both in one sentence: "posing a risk of serious injury or
death from fire". Counting phrases across 1,081 recalls, "serious injury or death"
and its variants are among the most frequent strings in the corpus, but they name
no cause. A taxonomy that admits them collapses: almost every recall becomes
"injury".

The label set is therefore eleven mechanisms — how the product hurts someone —
drafted from the measured phrasing rather than from intuition. Severity is
recorded as a separate field with values `death`, `serious_injury` and `injury`.

**Consequence:** categories stay discriminative and stratified reporting is
meaningful. The draft covers 97.7% of records; the residual states only "an injury
hazard" with no mechanism at all, which a human must infer from the product
description. `unauthorised_access` matches 8 records and is reported descriptively
only, like the elderly stratum.