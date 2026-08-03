"""Minimal HTTP helper: stdlib only, retries, on-disk cache."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "RecallBlind/0.1 (academic research; contact via repository)"


def get_json(
    url: str,
    cache_path: Path | None = None,
    timeout: int = 120,
    retries: int = 4,
    pause: float = 1.0,
) -> Any:
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(raw, encoding="utf-8")
            time.sleep(pause)
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(pause * (2**attempt))

    raise RuntimeError(f"Failed to fetch {url}: {last_error}")
