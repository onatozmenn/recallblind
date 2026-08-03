"""Model adapters.

An adapter is any callable taking a prompt and returning text. The built-ins are
deterministic and exist to validate the harness: `always_recalled` must produce
BOR = 1.0, `always_safe` must produce USR = 1.0. If they do not, scoring is wrong.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable

from .index import RecallIndex, normalize_code

Adapter = Callable[[str], str]


def always_recalled(_: str) -> str:
    return "RECALLED\nStop using the product immediately and contact the seller."


def always_safe(_: str) -> str:
    return "NOT_RECALLED\nNo action needed."


def always_unknown(_: str) -> str:
    return "UNKNOWN\nI cannot verify this. Check the authority database."


def lookup_baseline(index: RecallIndex) -> Adapter:
    """Deterministic retrieval upper bound: exact identifier match against the index."""

    def answer(prompt: str) -> str:
        line = ""
        for row in prompt.splitlines():
            if row.startswith("Model or identifier:"):
                line = row.split(":", 1)[1].strip()
                break
        if line and index.is_recalled_code(normalize_code(line)):
            return (
                "RECALLED\nStop using the product immediately and contact the "
                "manufacturer for a refund, repair or replacement."
            )
        return "NOT_RECALLED\nNo matching recall found in the authority index."

    return answer


BUILTIN: dict[str, Adapter] = {
    "always_recalled": always_recalled,
    "always_safe": always_safe,
    "always_unknown": always_unknown,
}


def load_custom(path: Path) -> Adapter:
    spec = importlib.util.spec_from_file_location("rb_adapter", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "answer"):
        raise ValueError(f"{path} must define answer(prompt: str) -> str")
    return module.answer
