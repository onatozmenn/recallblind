<p align="left">
	<img src="brand/reclume-logo.svg" width="300" alt="Reclume">
</p>

[![tests](https://github.com/onatozmenn/reclume/actions/workflows/tests.yml/badge.svg)](https://github.com/onatozmenn/reclume/actions/workflows/tests.yml)
[![pages](https://github.com/onatozmenn/reclume/actions/workflows/pages.yml/badge.svg)](https://onatozmenn.github.io/reclume/)

**Do AI shopping assistants know which products have been recalled?**

Reclume is an open benchmark that measures whether large language models and
AI shopping agents recommend, or fail to warn about, consumer products that have
been officially recalled for safety reasons.

> **Status:** two preliminary model runs are published on the
> [benchmark site](https://onatozmenn.github.io/reclume/). The harness is
> validated; human validation of identifiers, negatives and rule scoring is
> still outstanding. See [docs/ROADMAP.md](docs/ROADMAP.md).

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

## Preliminary results

| Model | T1 unsafe silence ↓ | T2 overreach ↓ | T3 wrong repair ↓ | T4 notice quality ↑ |
|---|---:|---:|---:|---:|
| GPT-4o mini (2024-07-18) | 100.0% | 0.0% | 35.7% | 96.3% |
| GPT-5.6 Luna | 80.3% | 13.8% | 39.7% | 95.1% |

GPT-4o mini answered `UNKNOWN` on all 800 status prompts, so its zero overreach
does not demonstrate discrimination. Luna identified 79 of 400 recalled products
but falsely flagged 55 of 400 negatives; its overreach reached **26.7%** on
corrected-successor identifiers. Read the interactive comparison and caveats on
the [Reclume benchmark site](https://onatozmenn.github.io/reclume/).

## Quickstart

Python 3.11+, no third-party dependencies.

```bash
python -m reclume.cli cpsc --start-year 2024 --end-year 2026   # ingest authority data
python -m reclume.cli extract                                  # recover model/SKU codes
python -m reclume.cli negatives                                # build verified hard negatives
python -m reclume.cli tasks                                    # assemble T1-T4
python -m reclume.cli eval lookup_baseline                     # score an adapter
python -m unittest discover -s tests                           # 94 tests, no network
```

Raw responses are cached under `data/raw/`, normalized records land in
`data/normalized/*.jsonl`, derived artefacts in `data/derived/`, the benchmark in
`data/benchmark/`, scores in `results/`. None of it is committed: the pipeline
re-fetches from public APIs. The one exception is `data/gold/`, which holds human
annotations that cannot be regenerated.

### Evaluating your own model

Write a module exposing `answer(prompt: str) -> str`, then:

```bash
python -m reclume.cli eval path/to/my_adapter.py --limit 40   # pilot first
python -m reclume.cli eval path/to/my_adapter.py              # full run
```

`examples/chat_adapter.py` is a working OpenAI-compatible adapter. Put the key in
`secrets/openai.key` with an editor rather than typing it into a shell; that path
is gitignored. `examples/list_models.py` prints the models the key can reach.

A full run is 1,400 prompts, roughly 300,000 tokens including completions, so on a
small model it costs cents. `--limit` spreads a pilot evenly across the four tasks
so the label balance survives.

## Harness validation

Each task has one safety-critical headline metric, and deterministic adapters pin
every one of them at a known value. If these numbers move, scoring is broken
rather than the model.

| Adapter | Accuracy | USR (T1) | BOR (T2) | Unsafe action (T3) | NCS (T4) |
|---|---:|---:|---:|---:|---:|
| `always_recalled` | 0.50 | 0.00 | **1.00** | 0.00 | 0.75 |
| `always_safe` | 0.50 | **1.00** | 0.00 | **1.00** | 0.25 |
| `always_unknown` | 0.00 | 1.00 | 0.00 | 1.00 | 0.25 |
| `minimising_notice` | 0.50 | 1.00 | 0.00 | 1.00 | **0.00** |
| `compliant_notice` | 0.50 | 0.00 | 1.00 | 0.00 | **1.00** |
| `lookup_baseline` | **1.00** | 0.00 | 0.00 | 0.00 | 1.00 |

The blind adapters hit both extremes at once: whatever catches every recall also
flags every safe product. Only `lookup_baseline` reads the identifier, which is
why it alone scores 0.00 on both USR and BOR. Its perfect accuracy is a
dataset-validity check, not a result: every positive is findable by exact
identifier match and every negative is genuinely absent from the recall data. The
open question is whether AI assistants perform this lookup at all.

## Benchmark composition

1,400 items from 1,081 CPSC recalls, with 2,008 verified negatives available:

| Task | Items | Measures |
|---|---:|---|
| T1 recall status | 400 | Does it know? |
| T2 variant discrimination | 400 | Does it over-generalise? |
| T3 correct action | 300 | Told it is recalled, is the advice right? |
| T4 notice quality | 300 | Does the warning meet GPSR Article 36? |

Negative families, each verified absent from the recall index before emission:

| Family | Available | Construction |
|---|---:|---|
| `brand_other_category` | 894 | Brand recalled elsewhere, no recall in this category |
| `corrected_successor` | 557 | Revision suffix, as reissued after a fix |
| `adjacent_code` | 557 | One digit off a recalled code |

Temporal splits run against a 2025-06-01 cutoff, with a `fresh` split for recalls
issued after benchmark release.

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
recovered from prose. Our regex baseline reaches **53.3% coverage** (576 of 1,081
recalls yield at least one identifier). Beating this is the first modelling task.

Details and caveats: [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md).

## Layout

```
reclume/   ingestion, schema, task construction and scoring
site/      static benchmark website deployed with GitHub Pages
brand/     SVG wordmark, marks and multi-size ICO favicon
docs/      architecture, benchmark design, data sources and decisions
data/      generated locally, git-ignored except human annotations
```

## Licence and attribution

Code is MIT ([LICENSE](LICENSE)). Documentation is CC BY 4.0.

Recall content belongs to the issuing authorities. This repository distributes
**record identifiers and our own annotations only** — never bulk copies of source
data. OECD content is subject to the
[OECD terms and conditions](https://www.oecd.org/termsandconditions/).

## Disclaimer

Reclume is a research instrument, not a consumer safety service and not legal
advice. Recall status can change at any time. Always verify against the issuing
authority before acting.
