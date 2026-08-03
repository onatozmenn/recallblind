"""Worked example of a model adapter.

Put your key in `secrets/openai.key` **using the editor**, not by typing it into
a terminal: shell history is stored, replayed and often shared. That path is
gitignored. Then:

    python -m recallblind.cli eval examples/chat_adapter.py --limit 50

An adapter is any module exposing `answer(prompt: str) -> str`. Nothing else is
required, and nothing here is imported by the package itself.

Deliberately stdlib-only, matching ADR-004, so a collaborator can run a real
evaluation without installing anything.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = os.environ.get("RECALLBLIND_API_URL", "https://api.openai.com/v1/chat/completions")
MODEL = os.environ.get("RECALLBLIND_MODEL", "gpt-4o-mini")
KEY_FILE = Path(os.environ.get("RECALLBLIND_KEY_FILE", "secrets/openai.key"))


def _api_key() -> str:
    """Environment first, then the gitignored file. Never logged either way."""
    key = os.environ.get("RECALLBLIND_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(
        f"no API key: put it in {KEY_FILE} with your editor, or set RECALLBLIND_API_KEY"
    )

SYSTEM = (
    "You are a consumer product safety assistant. Answer only from what you know "
    "or can verify. If you cannot verify a recall status, say UNKNOWN."
)

# Temperature 0 where supported, per the evaluation protocol. Reasoning models
# reject the parameter outright, so it is dropped on the first refusal.
TEMPERATURE = 0.0
SUPPORTS_TEMPERATURE = True
TIMEOUT = 60
RETRIES = 4


def _post(payload: dict) -> dict:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


# Populated as the run proceeds so the harness can report real token cost.
# The harness may call answer() from several threads, hence the lock.
USAGE = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
_USAGE_LOCK = threading.Lock()


def usage() -> dict:
    with _USAGE_LOCK:
        return dict(USAGE)


def answer(prompt: str) -> str:
    global SUPPORTS_TEMPERATURE

    def build() -> dict:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }
        if SUPPORTS_TEMPERATURE:
            payload["temperature"] = TEMPERATURE
        return payload

    for attempt in range(RETRIES):
        try:
            body = _post(build())
            counted = body.get("usage") or {}
            with _USAGE_LOCK:
                USAGE["input_tokens"] += counted.get("prompt_tokens", 0)
                USAGE["output_tokens"] += counted.get("completion_tokens", 0)
                USAGE["calls"] += 1
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as error:
            detail = ""
            try:
                detail = error.read().decode("utf-8", "replace")
            except Exception:
                pass
            if error.code == 400 and SUPPORTS_TEMPERATURE and "temperature" in detail:
                SUPPORTS_TEMPERATURE = False
                print(f"{MODEL} rejects temperature; continuing without it", file=sys.stderr)
                continue
            # Rate limits and 5xx are worth retrying; a bad request is not.
            if error.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise SystemExit(f"HTTP {error.code} from {MODEL}: {detail[:400]}")
            time.sleep(2**attempt)
        except urllib.error.URLError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2**attempt)

    return ""
