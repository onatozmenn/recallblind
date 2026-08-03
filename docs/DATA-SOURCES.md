# Data sources

All figures below were measured on 2026-08-04 by querying the live APIs.

## US CPSC — primary source

- Endpoint: `https://www.saferproducts.gov/RestWebServices/Recall`
- Formats: XML, or JSON with `&format=json`
- No API key. Filter with `RecallDateStart` / `RecallDateEnd`.
- Docs: <https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information>

### Volume

| Period | Recalls |
|---|---:|
| 2023 | 324 |
| 2024 | 305 |
| 2025 | 420 |
| 2026 (to 4 Aug) | 356 |

Quarterly trend is upward: 2024-Q1 92 → 2026-Q2 160.

### Field coverage (2023–2026, n = 1,405)

| Field | Populated |
|---|---:|
| `Images` | 1,405 |
| `Remedies` | 1,405 |
| `Hazards` | 1,403 |
| `Retailers` | 1,404 |
| `ProductUPCs` | 53 |
| `Products[].Model` | 0 |
| `Products[].Description` | 0 |
| `Hazards[].HazardType` | 0 |

### Consequences

1. **Model numbers live in prose.** 61% of 2025–2026 descriptions mention
   model/SKU/item/lot/style. Example: `"SKU: N-YSXR0055B" and "Item: Steel Cabinet"
   are printed on the product packaging.` An extraction layer is mandatory.
2. **Hazard types must be built.** `HazardType` is empty everywhere, so a hazard
   taxonomy is our own contribution, not a copied field.
3. **Remedies are rich and actionable.** Free text naming refund, disposal proof,
   and contact routes — the basis for task T3.

### Remedy signals (2024–2026, n = 1,081)

| Signal | Records |
|---|---:|
| "stop using" | 973 |
| refund | 668 |
| dispose / destroy / discard | 527 |
| repair | 202 |

## OECD Global Recalls — secondary source

- Endpoint: `https://globalrecalls.oecd.org/ws/search.xqy?q=&start=1&num=20`
- Returns JSON. **No API key needed for reads**; keys are only for publishing.
- Portal: <https://globalrecalls.oecd.org/>
- Total records: 56,608 across 50 economies.

### Pagination semantics (non-obvious)

The `end` field is the **page size, not an absolute offset**, and the response
`start` is the request `start` plus one. Correct paging advances by the number of
rows returned:

```
next_start = current_start + len(results)
```

Reading `end` as an offset silently truncates ingestion after two pages.

### Known limitation: unreliable dates

`orderby=date-desc` does not yield recent records, and many entries carry the
placeholder `1900-01-01` — including a record whose linked CPSC notice is from
2009. **Do not use OECD dates for temporal splits.** CPSC is the temporal
backbone; OECD provides breadth and its product taxonomy.

### Coverage

Top recall economies: EU/EEA 15,002 · US 8,202 · Australia 6,570 · Canada 5,633 ·
Germany 4,507 · Italy 3,403 · UK 3,171 · Korea 2,968.

**Türkiye does not publish to this portal** and is absent from the economy list.

## Sources considered and excluded

| Source | Why excluded |
|---|---|
| Türkiye GÜBİS | No public API; bulk scraping inappropriate; out of project scope |
| EU Safety Gate | Public distribution is weekly XML/XLSX reports, not a query API; OECD already aggregates EU/EEA alerts |
| Commercial recall APIs | Paid, closed, unsuitable for an open benchmark |

## Licensing and redistribution

- **CPSC** — US federal government work, public domain.
- **OECD** — responses carry `© OECD. All rights reserved`. See the
  [terms](https://www.oecd.org/termsandconditions/).

We therefore distribute **record identifiers plus our own annotations**, together
with the fetch scripts. We do not commit bulk copies of source content. This is
standard benchmark practice and keeps the dataset current rather than frozen.

## Reproducing

```bash
python -m recallblind.cli cpsc --start-year 2023 --end-year 2026
python -m recallblind.cli oecd --limit 2000
python -m recallblind.cli extract
python -m recallblind.cli stats
```

Raw responses are cached under `data/raw/`, so re-runs do not re-hit the APIs.
