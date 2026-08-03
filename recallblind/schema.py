"""Unified record schema across recall sources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Iterator

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    if not value:
        return ""
    text = _TAG_RE.sub(" ", str(value))
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
    return _WS_RE.sub(" ", text).strip()


@dataclass
class Recall:
    source: str
    source_id: str
    recall_date: str
    title: str
    description: str
    product_names: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    remedies: list[str] = field(default_factory=list)
    manufacturers: list[str] = field(default_factory=list)
    retailers: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    upcs: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    sold_at: str = ""
    units: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def searchable_text(self) -> str:
        return " ".join([self.title, self.description, *self.product_names]).strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_jsonl(records: Iterable[Recall], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> Iterator[Recall]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield Recall(**json.loads(line))
