"""Baseline extraction of product identifiers from free-text recall notices.

CPSC exposes an empty structured `Model` field, so model/SKU/lot codes must be
recovered from prose. This regex baseline is the reference point that any
LLM-assisted extractor must beat on a human-labelled sample.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

ANCHORS: dict[str, str] = {
    "model": r"model(?:\s*(?:numbers?|nos?\.?|#|names?))?",
    "sku": r"sku(?:\s*(?:codes?|numbers?|nos?\.?|#))?",
    "item": r"item(?:\s*(?:numbers?|nos?\.?|#))",
    "lot": r"lot(?:\s*(?:codes?|numbers?|nos?\.?|#))?",
    "style": r"style(?:\s*(?:numbers?|nos?\.?|#))",
    "serial": r"serial(?:\s*(?:numbers?|nos?\.?|#))?",
}

WINDOW = 160
CODE_RE = re.compile(r"\b(?=[A-Za-z0-9][A-Za-z0-9\-/\.]{2,})(?=[^\s]*\d)[A-Za-z0-9][A-Za-z0-9\-/\.]{2,}\b")
UPC_RE = re.compile(r"(?i)\bupc[s]?\s*(?:codes?|numbers?)?\s*[:\-]?\s*((?:\d[\d\s,\-]{6,})\d)")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
NOISE = {"800", "888", "877", "866", "24/7", "1/2", "3/4", "1/4"}

# "40V", "20-in", "3.5oz" are product specs, not identifiers.
UNIT_RE = re.compile(
    r"(?i)^\d+(?:\.\d+)?[\-\s]?(v|w|a|ah|mah|hz|in|inch|inches|ft|feet|mm|cm|m|oz|lb|lbs|kg|g|ml|l|pc|pcs|pk|qt|gal|amp|volt|watt|x)$"
)


@dataclass
class Identifier:
    kind: str
    value: str
    evidence: str


def _looks_like_code(token: str) -> bool:
    if token in NOISE or YEAR_RE.match(token) or UNIT_RE.match(token):
        return False
    if not any(char.isdigit() for char in token):
        return False
    # Pure short numbers are usually counts, measurements or prices.
    if token.isdigit() and len(token) < 5:
        return False
    return True


def extract(text: str) -> list[Identifier]:
    if not text:
        return []

    found: list[Identifier] = []
    seen: set[tuple[str, str]] = set()

    for kind, anchor in ANCHORS.items():
        for match in re.finditer(rf"(?i)\b{anchor}\b", text):
            window = text[match.end() : match.end() + WINDOW]
            # Stop at the next sentence boundary to avoid bleeding into other claims.
            window = re.split(r"(?<=[.;])\s+(?=[A-Z])", window)[0]
            for token in CODE_RE.findall(window):
                token = token.strip(".,;:/-")
                if not _looks_like_code(token):
                    continue
                signature = (kind, token.upper())
                if signature in seen:
                    continue
                seen.add(signature)
                found.append(
                    Identifier(kind=kind, value=token, evidence=text[match.start() : match.end() + 60].strip())
                )

    for match in UPC_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        for size in (12, 13, 14, 11, 8):
            if len(digits) >= size and len(digits) % size == 0:
                for index in range(0, len(digits), size):
                    chunk = digits[index : index + size]
                    signature = ("upc", chunk)
                    if signature not in seen:
                        seen.add(signature)
                        found.append(Identifier(kind="upc", value=chunk, evidence=match.group(0).strip()))
                break

    return found


def build(records: Iterable, out_path: Path) -> dict[str, object]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    per_kind: Counter[str] = Counter()
    with_any = 0
    total = 0

    with out_path.open("w", encoding="utf-8") as handle:
        for record in records:
            total += 1
            identifiers = extract(record.searchable_text)
            structured_upcs = [{"kind": "upc", "value": upc, "evidence": "structured field"} for upc in record.upcs]
            payload = [asdict(identifier) for identifier in identifiers] + structured_upcs
            if payload:
                with_any += 1
            for entry in payload:
                per_kind[entry["kind"]] += 1
            handle.write(
                json.dumps(
                    {"key": record.key, "recall_date": record.recall_date, "identifiers": payload},
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {
        "records": total,
        "records_with_identifier": with_any,
        "coverage": round(with_any / total, 4) if total else 0.0,
        "by_kind": dict(per_kind.most_common()),
    }
