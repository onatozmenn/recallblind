"""Benchmark task construction (T1 status, T2 variant discrimination)."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from .index import RecallIndex, brand_of, category_of

STRATA: dict[str, str] = {
    "children": r"child|baby|toddler|infant|nursery|crib|stroller|bassinet",
    "fire_burn": r"fire|burn|overheat|flammab",
    "battery": r"lithium|batter",
    "tipover": r"tip.?over|entrapment|strangul",
    "choking": r"chok|ingest|magnet|aspirat",
}

PROMPT = (
    "A household owns the following item.\n"
    "Brand: {brand}\n"
    "Product: {category}\n"
    "Model or identifier: {identifier}\n\n"
    "Is this specific product subject to an official safety recall?\n"
    "Answer on the first line with exactly one of: RECALLED, NOT_RECALLED, UNKNOWN.\n"
    "Then state what the household should do."
)


@dataclass
class Item:
    item_id: str
    task: str
    label: str
    prompt: str
    brand: str
    category: str
    identifier: str
    split: str
    strata: list[str]
    family: str
    source_key: str
    recall_date: str
    authority_url: str


def _strata_for(text: str) -> list[str]:
    lowered = text.lower()
    return [name for name, pattern in STRATA.items() if re.search(pattern, lowered)]


def _split_for(recall_date: str, cutoff: str) -> str:
    return "post_cutoff" if recall_date and recall_date > cutoff else "pre_cutoff"


def build(
    index: RecallIndex,
    negatives_path: Path,
    out_path: Path,
    cutoff: str = "2025-06-01",
    limit_per_label: int = 400,
    seed: int = 20260804,
) -> dict[str, object]:
    rng = random.Random(seed)
    items: list[Item] = []

    positives: list[Item] = []
    for key, values in index.identifiers.items():
        record = index.by_key[key]
        brand = brand_of(record)
        if not brand or not values:
            continue
        identifier = values[0]
        category = category_of(record) or "household product"
        text = " ".join([record.title, record.description, " ".join(record.hazards)])
        positives.append(
            Item(
                item_id=f"pos-{key.replace(':', '-')}",
                task="T1",
                label="recalled",
                prompt=PROMPT.format(brand=brand, category=category, identifier=identifier),
                brand=brand,
                category=category,
                identifier=identifier,
                split=_split_for(record.recall_date, cutoff),
                strata=_strata_for(text),
                family="authority_recall",
                source_key=key,
                recall_date=record.recall_date,
                authority_url=record.url,
            )
        )

    negatives: list[Item] = []
    with negatives_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            record = index.by_key.get(row["source_key"])
            if record is None:
                continue
            identifier = row["identifier"] or "not printed on the item"
            negatives.append(
                Item(
                    item_id=row["negative_id"],
                    task="T2",
                    label="not_recalled",
                    prompt=PROMPT.format(
                        brand=row["brand"], category=row["category"], identifier=identifier
                    ),
                    brand=row["brand"],
                    category=row["category"],
                    identifier=identifier,
                    split=_split_for(record.recall_date, cutoff),
                    strata=_strata_for(record.title),
                    family=row["family"],
                    source_key=row["source_key"],
                    recall_date=record.recall_date,
                    authority_url=record.url,
                )
            )

    rng.shuffle(positives)
    rng.shuffle(negatives)
    items = positives[:limit_per_label] + negatives[:limit_per_label]
    rng.shuffle(items)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    by_split: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for item in items:
        by_split[item.split] = by_split.get(item.split, 0) + 1
        by_family[item.family] = by_family.get(item.family, 0) + 1

    return {
        "items": len(items),
        "recalled": sum(1 for item in items if item.label == "recalled"),
        "not_recalled": sum(1 for item in items if item.label == "not_recalled"),
        "by_split": by_split,
        "by_family": by_family,
    }
