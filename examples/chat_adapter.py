"""Worked example of a model adapter.

Copy this, point it at whichever chat API you use, then:

    setx RECALLBLIND_API_KEY ...        # or export, on a shell that is not logged
    python -m recallblind.cli eval examples/chat_adapter.py

An adapter is any module exposing `answer(prompt: str) -> str`. Nothing else is
required, and nothing here is imported by the package itself.

Deliberately stdlib-only, matching ADR-004, so a collaborator can run a real
evaluation without installing anything.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

API_URL = os.environ.get("RECALLBLIND_API_URL", "https://api.openai.com/v1/chat/completions")
MODEL = os.environ.get("RECALLBLIND_MODEL", "gpt-4o-mini")
# Never hard-code a key. Never print one: benchmark logs are meant to be published.
API_KEY = os.environ.get("RECALLBLIND_API_KEY", "")

SYSTEM = (
    "You are a consumer product safety assistant. Answer only from what you know "
    "or can verify. If you cannot verify a recall status, say UNKNOWN."
)

# Temperature 0 where supported, per the evaluation protocol.
TEMPERATURE = 0.0
TIMEOUT = 60
RETRIES = 4


def _post(payload: dict) -> dict:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def answer(prompt: str) -> str:
    if not API_KEY:
        raise SystemExit("set RECALLBLIND_API_KEY in the environment")

    payload = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }

    for attempt in range(RETRIES):
        try:
            body = _post(payload)
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as error:
            # Rate limits and 5xx are worth retrying; a bad request is not.
            if error.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise
            time.sleep(2**attempt)
        except urllib.error.URLError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2**attempt)

    return ""
