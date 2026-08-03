"""Ingest US CPSC recalls (public REST API, no key required)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .http import get_json
from .schema import Recall, clean_text

BASE_URL = "https://www.saferproducts.gov/RestWebServices/Recall"


def _values(items: Any, *keys: str) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict):
            for key in keys:
                value = clean_text(item.get(key))
                if value:
                    out.append(value)
                    break
            else:
                # Unknown key layout: fall back to the first non-empty string value.
                for value in item.values():
                    text = clean_text(value)
                    if text:
                        out.append(text)
                        break
        else:
            text = clean_text(item)
            if text:
                out.append(text)
    return out


def normalize(raw: dict[str, Any]) -> Recall:
    products = raw.get("Products") or []
    units = ""
    if isinstance(products, list) and products and isinstance(products[0], dict):
        units = clean_text(products[0].get("NumberOfUnits"))

    return Recall(
        source="cpsc",
        source_id=str(raw.get("RecallNumber") or raw.get("RecallID") or "").strip(),
        recall_date=str(raw.get("RecallDate") or "")[:10],
        title=clean_text(raw.get("Title")),
        description=clean_text(raw.get("Description")),
        product_names=_values(products, "Name"),
        hazards=_values(raw.get("Hazards"), "Name"),
        remedies=_values(raw.get("Remedies"), "Name"),
        manufacturers=_values(raw.get("Manufacturers"), "Name"),
        retailers=_values(raw.get("Retailers"), "Name"),
        countries=_values(raw.get("ManufacturerCountries"), "Country"),
        upcs=_values(raw.get("ProductUPCs"), "UPC"),
        images=_values(raw.get("Images"), "URL"),
        sold_at=clean_text(raw.get("SoldAtLabel")),
        units=units,
        url=clean_text(raw.get("URL")),
    )


def fetch_year(year: int, cache_dir: Path) -> list[Recall]:
    url = f"{BASE_URL}?RecallDateStart={year}-01-01&RecallDateEnd={year}-12-31&format=json"
    payload = get_json(url, cache_path=cache_dir / f"cpsc_{year}.json")
    if not isinstance(payload, list):
        return []
    return [normalize(item) for item in payload if isinstance(item, dict)]


def fetch_range(start_year: int, end_year: int, cache_dir: Path) -> list[Recall]:
    records: list[Recall] = []
    seen: set[str] = set()
    for year in range(start_year, end_year + 1):
        for record in fetch_year(year, cache_dir):
            if record.source_id and record.source_id not in seen:
                seen.add(record.source_id)
                records.append(record)
        print(f"  cpsc {year}: {len(records)} cumulative")
    return records
