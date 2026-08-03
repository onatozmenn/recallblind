"""Ingest OECD Global Recalls (public search endpoint, no API key for reads).

Only record identifiers and metadata are stored; content stays attributable to
the issuing authority via `url`. See OECD terms before redistributing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from .http import get_json
from .schema import Recall, clean_text

SEARCH_URL = "https://globalrecalls.oecd.org/ws/search.xqy"


def _tag_values(tags: Any) -> list[str]:
    out: list[str] = []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict):
                value = clean_text(tag.get("value"))
                if value:
                    out.append(value)
    return out


def normalize(raw: dict[str, Any]) -> Recall:
    countries = []
    manufacturer_country = raw.get("manufacturer.country")
    if isinstance(manufacturer_country, list):
        for entry in manufacturer_country:
            if isinstance(entry, dict):
                name = clean_text(entry.get("name"))
                if name:
                    countries.append(name)

    country_id = clean_text(raw.get("countryId"))
    source_id = f"{country_id}-{clean_text(raw.get('id'))}".strip("-")
    image = clean_text(raw.get("imageUri"))

    return Recall(
        source="oecd",
        source_id=source_id,
        recall_date=str(raw.get("date") or "")[:10],
        title=clean_text(raw.get("product.name")),
        description="",
        product_names=[clean_text(raw.get("product.name"))] if raw.get("product.name") else [],
        countries=countries,
        images=[image] if image else [],
        url=clean_text(raw.get("extUrl")),
        tags=_tag_values(raw.get("tags")),
    )


def fetch(
    cache_dir: Path,
    query: str = "",
    max_records: int = 2000,
    order: str = "date-desc",
) -> list[Recall]:
    records: list[Recall] = []
    seen: set[str] = set()
    start = 1
    total: int | None = None

    while len(records) < max_records:
        url = f"{SEARCH_URL}?q={quote(query)}&start={start}&num=20&orderby={order}"
        payload = get_json(url, cache_path=cache_dir / f"oecd_{order}_{start}.json")
        if not isinstance(payload, dict):
            break

        if total is None:
            total = int(payload.get("total") or 0)
            print(f"  oecd total available: {total}")

        results = payload.get("results")
        if not isinstance(results, list) or not results:
            break

        for item in results:
            if isinstance(item, dict):
                record = normalize(item)
                if record.source_id and record.source_id not in seen:
                    seen.add(record.source_id)
                    records.append(record)

        # `end` is the page size, not an absolute offset: advance by rows returned.
        start += len(results)
        if total and start > total:
            break
        print(f"  oecd fetched: {len(records)}")

    return records[:max_records]
