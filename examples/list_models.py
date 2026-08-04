"""List the models your key can actually reach, so the choice is not guesswork.

    python examples/list_models.py
    python examples/list_models.py mini      # filter by substring

Reads the key exactly like the adapter does: `secrets/openai.key`, or the
RECLUME_API_KEY environment variable. The key is never printed.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = os.environ.get("RECLUME_API_BASE", "https://api.openai.com/v1")
KEY_FILE = Path(os.environ.get("RECLUME_KEY_FILE", "secrets/openai.key"))


def api_key() -> str:
    key = os.environ.get("RECLUME_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(f"no API key: put it in {KEY_FILE} with your editor")


def main() -> None:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    request = urllib.request.Request(
        f"{BASE}/models", headers={"Authorization": f"Bearer {api_key()}"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))

    names = sorted(entry["id"] for entry in body.get("data", []))
    shown = [name for name in names if needle in name.lower()]
    for name in shown:
        print(name)
    print(f"\n{len(shown)} of {len(names)} models", file=sys.stderr)


if __name__ == "__main__":
    main()
