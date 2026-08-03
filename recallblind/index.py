"""Brand, category and identifier indexes derived from normalized recalls.

Every hard negative must be checked against these indexes, otherwise we would
label a genuinely recalled product as safe.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import Recall

# Curated category vocabulary: keeps negatives inside plausible product space.
CATEGORIES: tuple[str, ...] = (
    "dresser", "chest", "bookcase", "crib", "bassinet", "playard", "stroller",
    "car seat", "high chair", "booster", "bed rail", "mattress", "swing",
    "bouncer", "carrier", "walker", "helmet", "scooter", "bicycle", "treadmill",
    "space heater", "heater", "furnace", "candle", "lamp", "lantern",
    "power bank", "charger", "battery", "generator", "chainsaw", "drill",
    "saw", "ladder", "grill", "blender", "air fryer", "coffee maker", "kettle",
    "toaster", "humidifier", "dehumidifier", "fan", "vacuum", "toy", "doll",
    "puzzle", "magnet", "water bottle", "cup", "pacifier", "sleeper",
    "swaddle", "nightlight", "smoke alarm", "detector", "pressure cooker",
    "hoverboard", "e-bike", "furniture", "jacket", "sweatshirt", "pajamas",
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
STOPWORDS = {
    "the", "and", "due", "to", "recalls", "recall", "recalled", "by", "of",
    "with", "for", "risk", "hazard", "hazards", "sold", "at", "in", "on", "a",
    "an", "violate", "violates", "mandatory", "federal", "safety", "standard",
    "standards", "inc", "llc", "co", "corp", "company", "ltd", "usa", "us",
}


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def brand_of(recall: Recall) -> str:
    if recall.manufacturers:
        return recall.manufacturers[0].strip()
    for token in _TOKEN_RE.findall(recall.title):
        if token.lower() not in STOPWORDS and len(token) > 2:
            return token
    return ""


def category_of(recall: Recall) -> str:
    haystack = " ".join([recall.title, *recall.product_names]).lower()
    # Longest match wins so "space heater" beats "heater".
    best = ""
    for category in CATEGORIES:
        if category in haystack and len(category) > len(best):
            best = category
    return best


@dataclass
class RecallIndex:
    by_key: dict[str, Recall] = field(default_factory=dict)
    identifiers: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    codes: set[str] = field(default_factory=set)
    brand_categories: set[tuple[str, str]] = field(default_factory=set)
    brands: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def is_recalled_code(self, value: str) -> bool:
        normalized = normalize_code(value)
        return bool(normalized) and normalized in self.codes

    def brand_has_category(self, brand: str, category: str) -> bool:
        return (brand.lower(), category.lower()) in self.brand_categories


def build_index(records: Iterable[Recall], identifiers_path: Path) -> RecallIndex:
    index = RecallIndex()

    extracted: dict[str, list[str]] = defaultdict(list)
    if identifiers_path.exists():
        with identifiers_path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                for item in row.get("identifiers", []):
                    if item.get("kind") != "upc":
                        extracted[row["key"]].append(item["value"])

    for record in records:
        index.by_key[record.key] = record
        brand = brand_of(record)
        category = category_of(record)
        if brand:
            index.brands[brand.lower()].append(record.key)
            if category:
                index.brand_categories.add((brand.lower(), category.lower()))

        values = extracted.get(record.key, [])
        index.identifiers[record.key] = values
        for value in values + record.upcs:
            normalized = normalize_code(value)
            if normalized:
                index.codes.add(normalized)

    return index
