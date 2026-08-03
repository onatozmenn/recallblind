# RecallBlind

**Do AI shopping assistants know which products have been recalled?**

RecallBlind is an open benchmark that measures whether large language models and
AI shopping agents recommend, or fail to warn about, consumer products that have
been officially recalled for safety reasons.

> **Status:** early development. Data pipeline works; benchmark tasks not yet built.
> See [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Why this exists

AI assistants are becoming a default entry point for shopping. Existing
evaluations ask whether their recommendations are *relevant*, *stylish*, or
*commercially biased*. None ask whether they are *safe*.

That gap matters because product recalls are frequent and rising. From the US
CPSC alone we measured **1,081 recalls between January 2024 and August 2026**,
growing from 92 in 2024-Q1 to 160 in 2026-Q2. 46% involve children's or baby
products; 84% were sold through online channels.

The closest prior work, [RECALL-MM](https://arxiv.org/abs/2503.23213) (2025),
builds a recall dataset for *engineering designers* and deliberately strips brand
names from its records. It therefore cannot answer the consumer-facing question:
*is this specific product, right now, subject to a recall?*

## What it measures

| Task | Question |
|---|---|
| **T1 — Status** | Is this product currently recalled? |
| **T2 — Variant discrimination** | Can the model separate a recalled model from a safe sibling in the same brand family? |
| **T3 — Correct action** | Does it tell the user to stop using the product, and state the correct remedy? |
| **T4 — Notice quality** | Does its warning meet the legally required elements of a recall notice? |

Full definitions, metrics and formulas: [docs/BENCHMARK-DESIGN.md](docs/BENCHMARK-DESIGN.md).

**T2 is the hard part.** Over-flagging is as harmful as under-flagging: a recall
notice covers the notified product only, not everything a brand sells.

## Quickstart

Python 3.11+, no third-party dependencies.

```bash
python -m recallblind.cli cpsc --start-year 2024 --end-year 2026
python -m recallblind.cli oecd --limit 500
python -m recallblind.cli extract
python -m recallblind.cli stats
```

Raw responses are cached under `data/raw/`, normalized records land in
`data/normalized/*.jsonl`, derived identifiers in `data/derived/`.
None of it is committed: the pipeline re-fetches from public APIs.

## Findings so far

Measured 2026-08-04 on CPSC recalls from 2023-01-01 to 2026-08-04 (1,405 records):

| Field | Populated |
|---|---|
| Images | 100% |
| Remedies | 100% |
| Hazards | 99.9% |
| Retailers | 99.9% |
| Product UPCs | 3.8% |
| **`Products[].Model`** | **0%** |
| **`Hazards[].HazardType`** | **0%** |

The structured model-number field is entirely empty, so identifiers must be
recovered from prose. Our regex baseline reaches **52.4% coverage** (566 of 1,081
recalls yield at least one identifier). Beating this is the first modelling task.

Details and caveats: [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md).

## Layout

```
recallblind/     ingestion, schema, identifier extraction, CLI
docs/            architecture, benchmark design, data sources, roadmap, decisions
data/            generated locally, git-ignored
```

## Licence and attribution

Code is MIT ([LICENSE](LICENSE)). Documentation is CC BY 4.0.

Recall content belongs to the issuing authorities. This repository distributes
**record identifiers and our own annotations only** — never bulk copies of source
data. OECD content is subject to the
[OECD terms and conditions](https://www.oecd.org/termsandconditions/).

## Disclaimer

RecallBlind is a research instrument, not a consumer safety service and not legal
advice. Recall status can change at any time. Always verify against the issuing
authority before acting.
