"""Benchmark task construction.

T1 recall status, T2 variant discrimination, T3 correct action, T4 notice quality.
T1 and T2 test whether a system knows. T3 and T4 hand it the answer and test what
it tells the household to do, which isolates advice quality from lookup ability.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .index import RecallIndex, brand_of, category_of
from .remedies import hazard_terms, substantive

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

ACTION_PROMPT = (
    "A household owns the following item, which is subject to an official safety recall.\n"
    "Brand: {brand}\n"
    "Product: {category}\n"
    "Model or identifier: {identifier}\n"
    "Hazard: {hazard}\n\n"
    "What should the household do? Be specific about the remedy they are entitled to."
)

NOTICE_PROMPT = (
    "Write a product recall notice addressed to consumers.\n"
    "Brand: {brand}\n"
    "Product: {category}\n"
    "Model or identifier: {identifier}\n"
    "Hazard identified by the authority: {hazard}\n"
    "Remedy offered: {remedy}\n\n"
    "Write the notice exactly as consumers should see it."
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
    gold_remedies: list[str] = field(default_factory=list)
    gold_hazards: list[str] = field(default_factory=list)


def _strata_for(text: str) -> list[str]:
    lowered = text.lower()
    return [name for name, pattern in STRATA.items() if re.search(pattern, lowered)]


def _split_for(recall_date: str, cutoff: str, fresh_after: str | None = None) -> str:
    if fresh_after and recall_date and recall_date > fresh_after:
        return "fresh"
    return "post_cutoff" if recall_date and recall_date > cutoff else "pre_cutoff"


def _truncate(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def _remedy_excerpt(text: str, limit: int = 200) -> str:
    """The sentence that names the remedy, not merely the first 200 characters.

    Blind truncation hid the remedy in a quarter of notices, and T4 would then
    have marked a response non-compliant for omitting text it was never shown.
    """
    for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
        if substantive(sentence):
            shortened = _truncate(sentence, limit)
            # Truncation must not remove the very word the element is scored on.
            return shortened if substantive(shortened) else sentence
    return _truncate(text, limit)



def _action_and_notice_items(
    index: RecallIndex, cutoff: str, fresh_after: str | None
) -> tuple[list[Item], list[Item]]:
    """T3 and T4 draw on recalls whose notice states a substantive remedy."""
    actions: list[Item] = []
    notices: list[Item] = []

    for key, values in index.identifiers.items():
        record = index.by_key[key]
        brand = brand_of(record)
        if not brand:
            continue

        remedy_text = " ".join(record.remedies)
        gold_remedies = sorted(substantive(remedy_text))
        if not gold_remedies:
            continue
        remedy_shown = _remedy_excerpt(remedy_text)

        hazard_text = " ".join(record.hazards) or record.title
        # Ground the hazard on the words actually shown, so scoring never demands
        # knowledge the prompt withheld.
        hazard_shown = _truncate(hazard_text)
        gold_hazards = sorted(hazard_terms(hazard_shown))
        if not gold_hazards:
            continue

        category = category_of(record) or "household product"
        identifier = values[0] if values else "not printed on the item"
        split = _split_for(record.recall_date, cutoff, fresh_after)
        strata = _strata_for(f"{record.title} {hazard_text}")
        common = {
            "brand": brand,
            "category": category,
            "identifier": identifier,
            "split": split,
            "strata": strata,
            "family": "authority_recall",
            "source_key": key,
            "recall_date": record.recall_date,
            "authority_url": record.url,
            "gold_remedies": gold_remedies,
            "gold_hazards": gold_hazards,
        }

        actions.append(
            Item(
                item_id=f"act-{key.replace(':', '-')}",
                task="T3",
                label="action",
                prompt=ACTION_PROMPT.format(
                    brand=brand,
                    category=category,
                    identifier=identifier,
                    hazard=hazard_shown,
                ),
                **common,
            )
        )
        # T3 withholds the remedy on purpose; T4 supplies it, so it may only be
        # scored on a notice whose remedy is actually visible in the prompt.
        if not substantive(remedy_shown):
            continue

        notices.append(
            Item(
                item_id=f"not-{key.replace(':', '-')}",
                task="T4",
                label="notice",
                prompt=NOTICE_PROMPT.format(
                    brand=brand,
                    category=category,
                    identifier=identifier,
                    hazard=hazard_shown,
                    remedy=remedy_shown,
                ),
                **common,
            )
        )

    return actions, notices


def build(
    index: RecallIndex,
    negatives_path: Path,
    out_path: Path,
    cutoff: str = "2025-06-01",
    limit_per_label: int = 400,
    limit_action: int = 300,
    limit_notice: int = 300,
    fresh_after: str | None = None,
    seed: int = 20260804,
) -> dict[str, object]:
    rng = random.Random(seed)

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
                split=_split_for(record.recall_date, cutoff, fresh_after),
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
                    split=_split_for(record.recall_date, cutoff, fresh_after),
                    strata=_strata_for(record.title),
                    family=row["family"],
                    source_key=row["source_key"],
                    recall_date=record.recall_date,
                    authority_url=record.url,
                )
            )

    actions, notices = _action_and_notice_items(index, cutoff, fresh_after)

    rng.shuffle(positives)
    rng.shuffle(negatives)
    rng.shuffle(actions)
    rng.shuffle(notices)

    # T1 and T2 stay balanced; an unbalanced pair would make accuracy unreadable.
    paired = min(limit_per_label, len(positives), len(negatives))
    items = (
        positives[:paired]
        + negatives[:paired]
        + actions[:limit_action]
        + notices[:limit_notice]
    )
    rng.shuffle(items)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    by_task: dict[str, int] = {}
    by_split: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for item in items:
        by_task[item.task] = by_task.get(item.task, 0) + 1
        by_split[item.split] = by_split.get(item.split, 0) + 1
        if item.task == "T2":
            by_family[item.family] = by_family.get(item.family, 0) + 1

    return {
        "items": len(items),
        "by_task": by_task,
        "recalled": sum(1 for item in items if item.label == "recalled"),
        "not_recalled": sum(1 for item in items if item.label == "not_recalled"),
        "by_split": by_split,
        "negative_families": by_family,
        "cutoff": cutoff,
        "fresh_after": fresh_after,
    }
