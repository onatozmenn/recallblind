"""Categorical annotation campaigns.

Two open questions need human labels rather than code: which hazard mechanism a
recall describes, and whether a generated negative is plausible. Both are the same
job — show a reviewer some text, collect a label, measure agreement — so they
share one implementation.

Identifier annotation lives in `gold.py` and stays there: it labels proposals
produced by the extractor rather than choosing from a fixed set.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import hazards
from .schema import Recall


@dataclass(frozen=True)
class Campaign:
    name: str
    choices: tuple[str, ...]
    multi: bool
    question: str
    guidance: str


CAMPAIGNS: dict[str, Campaign] = {
    "hazards": Campaign(
        name="hazards",
        choices=tuple(category.name for category in hazards.CATEGORIES),
        multi=True,
        question="Which hazard mechanisms does this describe?",
        guidance=(
            "Label the mechanism, not the outcome. \"Serious injury or death\" is an\n"
            "outcome and is never a label on its own. More than one mechanism is\n"
            "normal: a battery that ignites and burns is fire_burn only, but a heater\n"
            "that tips over and starts a fire is fall_tipover and fire_burn."
        ),
    ),
    "negatives": Campaign(
        name="negatives",
        choices=("valid", "implausible", "wrong"),
        multi=False,
        question="Is this a fair negative?",
        guidance=(
            "valid        a household could plausibly own this and it is not recalled\n"
            "implausible  the brand would never sell this category\n"
            "wrong        it is actually covered by a recall\n\n"
            "Absurd pairings make the benchmark easier than the real task, so mark\n"
            "them implausible even though they are technically not recalled."
        ),
    ),
}


def sample_hazards(records: list[Recall], size: int, seed: int) -> list[dict[str, Any]]:
    pool = sorted(records, key=lambda record: record.key)
    rng = random.Random(seed)
    rows = []
    for record in rng.sample(pool, min(size, len(pool))):
        text = hazards.hazard_text(record)
        rows.append(
            {
                "id": record.key,
                "text": text,
                "context": record.title,
                "suggested": sorted(hazards.classify(text)),
                "severity": hazards.severity(text),
            }
        )
    return rows


def sample_negatives(rows: list[dict[str, Any]], size: int, seed: int) -> list[dict[str, Any]]:
    """Stratified: an equal share of each family, so no family goes unreviewed."""
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(rows, key=lambda row: row["negative_id"]):
        by_family.setdefault(row["family"], []).append(row)

    rng = random.Random(seed)
    per_family = max(1, size // max(len(by_family), 1))
    out = []
    for family in sorted(by_family):
        for row in rng.sample(by_family[family], min(per_family, len(by_family[family]))):
            out.append(
                {
                    "id": row["negative_id"],
                    "text": f"{row['brand']} {row['category']} {row['identifier']}".strip(),
                    "context": row["rationale"],
                    "suggested": [],
                    "family": family,
                }
            )
    rng.shuffle(out)
    return out


def write_sample(rows: list[dict[str, Any]], out_path: Path) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
    )
    return {"sampled": len(rows), "path": str(out_path)}


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def annotate(
    campaign: Campaign,
    sample_path: Path,
    out_path: Path,
    annotator: str,
    limit: int | None = None,
    reader: Callable[[str], str] = input,
) -> int:
    items = load(sample_path)
    done = {row["id"]: row for row in load(out_path)} if out_path.exists() else {}
    pending = [item for item in items if item["id"] not in done]
    if limit:
        pending = pending[:limit]

    print(f"\n{campaign.question}\n")
    print(campaign.guidance)
    print("\nChoices:")
    for number, choice in enumerate(campaign.choices, start=1):
        print(f"  {number}. {choice}")
    print(
        "\nEnter the number"
        + ("s, separated by spaces" if campaign.multi else "")
        + ". Enter alone skips, 'q' saves and stops.\n"
    )
    print(f"{len(done)} already labelled, {len(pending)} in this session.")

    for position, item in enumerate(pending, start=1):
        print("=" * 70)
        print(f"[{position}/{len(pending)}] {item['id']}")
        if item.get("context"):
            print(item["context"][:200])
        print("-" * 70)
        print(item["text"][:700])
        if item.get("suggested"):
            print(f"\n(automatic guess: {', '.join(item['suggested'])})")

        raw = reader("> ").strip()
        if raw.lower() == "q":
            break
        picked = [
            campaign.choices[int(token) - 1]
            for token in raw.split()
            if token.isdigit() and 1 <= int(token) <= len(campaign.choices)
        ]
        if not picked:
            continue
        if not campaign.multi:
            picked = picked[:1]

        done[item["id"]] = {"id": item["id"], "annotator": annotator, "labels": picked}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in done.values()),
            encoding="utf-8",
        )

    print(f"\nSaved {len(done)} annotations to {out_path}")
    return len(done)


def _kappa(po: float, pe: float) -> float:
    return 1.0 if pe >= 1.0 else round((po - pe) / (1 - pe), 4)


def agreement(campaign: Campaign, first: Path, second: Path) -> dict[str, Any]:
    a = {row["id"]: row["labels"] for row in load(first)}
    b = {row["id"]: row["labels"] for row in load(second)}
    shared = sorted(set(a) & set(b))
    if not shared:
        return {"error": "no overlapping items"}

    n = len(shared)
    if campaign.multi:
        # One binary kappa per category; a single multi-class kappa would hide a
        # category that both reviewers simply never use.
        per_category: dict[str, float] = {}
        for choice in campaign.choices:
            in_a = [choice in a[key] for key in shared]
            in_b = [choice in b[key] for key in shared]
            po = sum(1 for x, y in zip(in_a, in_b) if x == y) / n
            pa, pb = sum(in_a) / n, sum(in_b) / n
            per_category[choice] = _kappa(po, pa * pb + (1 - pa) * (1 - pb))
        usable = {name: value for name, value in per_category.items() if value is not None}
        weak = sorted(name for name, value in usable.items() if value < 0.70)
        return {
            "items": n,
            "kappa_by_category": per_category,
            "mean_kappa": round(sum(usable.values()) / len(usable), 4) if usable else None,
            "below_threshold": weak,
            "verdict": "acceptable" if not weak else "rewrite these definitions",
        }

    po = sum(1 for key in shared if a[key] == b[key]) / n
    pe = 0.0
    for choice in campaign.choices:
        pa = sum(1 for key in shared if a[key] and a[key][0] == choice) / n
        pb = sum(1 for key in shared if b[key] and b[key][0] == choice) / n
        pe += pa * pb
    kappa = _kappa(po, pe)
    return {
        "items": n,
        "observed_agreement": round(po, 4),
        "cohens_kappa": kappa,
        "verdict": "acceptable" if kappa >= 0.70 else "rewrite the definitions",
    }


def summarise(campaign: Campaign, paths: list[Path]) -> dict[str, Any]:
    counts: dict[str, int] = {choice: 0 for choice in campaign.choices}
    total = 0
    for path in paths:
        for row in load(path):
            total += 1
            for label in row["labels"]:
                counts[label] = counts.get(label, 0) + 1
    return {"annotations": total, "by_label": counts}
