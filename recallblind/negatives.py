"""Hard negative generation.

A recall covers the notified product only. Negatives probe whether a model
over-generalises that notice to a brand's other products or to lookalike codes.

Every candidate is verified against the full recall index before it is emitted.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path

from .index import CATEGORIES, RecallIndex, brand_of, category_of, normalize_code


@dataclass
class Negative:
    negative_id: str
    family: str
    brand: str
    category: str
    identifier: str
    source_key: str
    difficulty: str
    rationale: str


def _perturb(code: str, rng: random.Random) -> str | None:
    digits = [i for i, char in enumerate(code) if char.isdigit()]
    if not digits:
        return None
    position = rng.choice(digits)
    original = code[position]
    replacement = str((int(original) + rng.choice([1, 2, 3, 7])) % 10)
    if replacement == original:
        replacement = str((int(original) + 1) % 10)
    return code[:position] + replacement + code[position + 1 :]


def adjacent_codes(index: RecallIndex, per_recall: int = 1) -> list[Negative]:
    """Same brand, one character off a recalled code, absent from all recalls."""
    out: list[Negative] = []
    for key, values in index.identifiers.items():
        record = index.by_key[key]
        brand = brand_of(record)
        category = category_of(record)
        if not brand or not values:
            continue

        rng = random.Random(key)
        made = 0
        for value in values:
            if made >= per_recall or len(value) < 4:
                continue
            candidate = _perturb(value, rng)
            if not candidate or index.is_recalled_code(candidate):
                continue
            out.append(
                Negative(
                    negative_id=f"adj-{key.replace(':', '-')}-{made}",
                    family="adjacent_code",
                    brand=brand,
                    category=category or "product",
                    identifier=candidate,
                    source_key=key,
                    difficulty="hard",
                    rationale=(
                        f"One digit away from recalled code {value}; "
                        f"absent from the recall index."
                    ),
                )
            )
            made += 1
    return out


def brand_other_category(index: RecallIndex, per_brand: int = 2) -> list[Negative]:
    """Same brand, a category in which that brand has no recall on record."""
    out: list[Negative] = []
    for brand, keys in index.brands.items():
        if not keys:
            continue
        rng = random.Random(brand)
        record = index.by_key[keys[0]]
        own = {category_of(index.by_key[key]) for key in keys}
        pool = [c for c in CATEGORIES if c not in own and not index.brand_has_category(brand, c)]
        if not pool:
            continue
        for offset, category in enumerate(rng.sample(pool, min(per_brand, len(pool)))):
            out.append(
                Negative(
                    negative_id=f"brand-{normalize_code(brand)[:16]}-{offset}",
                    family="brand_other_category",
                    brand=brand_of(record),
                    category=category,
                    identifier="",
                    source_key=keys[0],
                    difficulty="medium",
                    rationale=(
                        f"Brand appears in recalls for other categories, "
                        f"but has no recall on record for {category}."
                    ),
                )
            )
    return out


def build(index: RecallIndex, out_path: Path, per_brand: int = 1) -> dict[str, object]:
    negatives = adjacent_codes(index) + brand_other_category(index, per_brand=per_brand)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for negative in negatives:
            handle.write(json.dumps(asdict(negative), ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for negative in negatives:
        counts[negative.family] = counts.get(negative.family, 0) + 1
    return {"total": len(negatives), "by_family": counts}
