# Gold annotations

Files in this directory are the **only** data committed to the repository.
Everything else under `data/` is regenerated from public APIs; these labels are
hours of human judgement and cannot be recovered if lost.

## Workflow

```bash
python -m reclume.cli gold-sample                 # 300 records, fixed seed
python -m reclume.cli annotate onat --limit 50    # label a session at a time
python -m reclume.cli annotate <second-name>      # independently, same items
python -m reclume.cli agreement data/gold/onat.jsonl data/gold/<second>.jsonl
python -m reclume.cli extractor-score data/gold/*.jsonl
```

Both annotators label the same sample: `gold-sample` is seeded, so it is
reproducible without committing the sample itself.

## Labelling rule

A proposal is **correct** when the string identifies *which* product was
recalled, so a consumer could match it against the item in their home.

Correct: `MODEL BX-4400`, `SKU 71829`, `LOT 2024-05`, a serial range.
Incorrect: capacities (`40V`), dimensions (`20-in`), prices, years, phone
numbers, quantities recalled, the recall number itself.

When in doubt, ask: *could someone holding the product check this?*

## Acceptance

Cohen's kappa must reach 0.70 before the labels are usable. Below that, the
rule above is ambiguous and needs revising — do not adjudicate your way past a
low kappa, fix the definition and relabel.

Extractor target: F1 >= 0.85 against the adjudicated set.
