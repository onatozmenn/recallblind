"""Gold-set tooling for identifier extraction (issue #1).

Two annotators label the same deterministic sample, disagreements are
adjudicated, and the extractor is then scored against the result. Without this,
the reported 52.4% coverage is an unvalidated number.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .extract_identifiers import extract
from .schema import Recall


def build_sample(records: list[Recall], out_path: Path, size: int = 300, seed: int = 20260804) -> dict[str, Any]:
    """Deterministic sample so every annotator labels exactly the same items."""
    pool = sorted(records, key=lambda record: record.key)
    rng = random.Random(seed)
    chosen = rng.sample(pool, min(size, len(pool)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with_proposals = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for record in chosen:
            proposals = [
                {"kind": item.kind, "value": item.value} for item in extract(record.searchable_text)
            ]
            if proposals:
                with_proposals += 1
            handle.write(
                json.dumps(
                    {
                        "key": record.key,
                        "recall_date": record.recall_date,
                        "title": record.title,
                        "text": record.searchable_text,
                        "proposals": proposals,
                        "url": record.url,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {"sampled": len(chosen), "with_proposals": with_proposals, "seed": seed}


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def annotate(sample_path: Path, out_path: Path, annotator: str, limit: int | None = None) -> None:
    items = _load(sample_path)
    done: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        done = {row["key"]: row for row in _load(out_path)}

    pending = [item for item in items if item["key"] not in done]
    if limit:
        pending = pending[:limit]

    print(f"{len(done)} already labelled, {len(pending)} in this session.\n")
    print("For each item: press Enter to accept all proposals, or type the numbers")
    print("to REJECT (e.g. '1 3'). Then add any codes the extractor missed.")
    print("Type 'q' at any prompt to stop and save.\n")

    for position, item in enumerate(pending, start=1):
        print("=" * 70)
        print(f"[{position}/{len(pending)}] {item['key']}  {item['recall_date']}")
        print(item["title"])
        print("-" * 70)
        print(item["text"][:900])
        print("-" * 70)

        proposals = item["proposals"]
        if proposals:
            for number, proposal in enumerate(proposals, start=1):
                print(f"  {number}. [{proposal['kind']}] {proposal['value']}")
        else:
            print("  (extractor proposed nothing)")

        raw = input("Reject numbers / Enter to accept all / q: ").strip()
        if raw.lower() == "q":
            break
        rejected: set[int] = set()
        for token in raw.split():
            if token.isdigit():
                rejected.add(int(token))

        extra = input("Missed codes, comma separated (blank if none): ").strip()
        if extra.lower() == "q":
            break

        done[item["key"]] = {
            "key": item["key"],
            "annotator": annotator,
            "decisions": [
                {
                    "kind": proposal["kind"],
                    "value": proposal["value"],
                    "correct": (number not in rejected),
                }
                for number, proposal in enumerate(proposals, start=1)
            ],
            "added": [value.strip() for value in extra.split(",") if value.strip()],
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            for row in done.values():
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(done)} annotations to {out_path}")


def _decision_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], bool]:
    return {
        (row["key"], decision["value"]): decision["correct"]
        for row in rows
        for decision in row["decisions"]
    }


def cohens_kappa(first: Path, second: Path) -> dict[str, Any]:
    a, b = _decision_map(_load(first)), _decision_map(_load(second))
    shared = sorted(set(a) & set(b))
    if not shared:
        return {"error": "no overlapping decisions"}

    n = len(shared)
    agree = sum(1 for key in shared if a[key] == b[key])
    po = agree / n

    a_true = sum(1 for key in shared if a[key]) / n
    b_true = sum(1 for key in shared if b[key]) / n
    pe = a_true * b_true + (1 - a_true) * (1 - b_true)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0

    return {
        "overlapping_decisions": n,
        "observed_agreement": round(po, 4),
        "expected_agreement": round(pe, 4),
        "cohens_kappa": round(kappa, 4),
        "interpretation": "acceptable" if kappa >= 0.70 else "revise label definitions",
    }


def score_extractor(gold_paths: list[Path]) -> dict[str, Any]:
    """Micro-averaged precision, recall and F1 against adjudicated annotations."""
    gold: dict[str, set[str]] = {}
    predicted: dict[str, set[str]] = {}

    for path in gold_paths:
        for row in _load(path):
            key = row["key"]
            predicted.setdefault(key, set()).update(d["value"].upper() for d in row["decisions"])
            accepted = {d["value"].upper() for d in row["decisions"] if d["correct"]}
            accepted.update(value.upper() for value in row.get("added", []))
            gold.setdefault(key, set()).update(accepted)

    tp = fp = fn = 0
    for key, gold_values in gold.items():
        pred_values = predicted.get(key, set())
        tp += len(pred_values & gold_values)
        fp += len(pred_values - gold_values)
        fn += len(gold_values - pred_values)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "records": len(gold),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "target": 0.85,
        "meets_target": f1 >= 0.85,
    }
