"""Remedy and hazard vocabulary shared by task construction and scoring.

The authority notice states what a household is actually entitled to. T3 scores a
response against that, so the classification here is the ground truth and must
stay conservative: a missed class understates a model, an invented one flatters it.
"""

from __future__ import annotations

import re

REMEDY_PATTERNS: dict[str, re.Pattern[str]] = {
    "refund": re.compile(r"(?i)refund|money back|store credit|full credit"),
    "replacement": re.compile(r"(?i)\breplacement\b|\breplace\b|\breplaced\b"),
    "repair": re.compile(r"(?i)\brepair|retrofit|remedy kit|fix kit|replacement part"),
    "disposal": re.compile(
        r"(?i)dispose|discard|destroy|throw (?:it |them )?away|render (?:it |them )?inoperable|cut the"
    ),
    "stop_using": re.compile(r"(?i)stop (?:using|use)|discontinue use|cease use|immediately stop"),
    "contact": re.compile(
        r"(?i)contact|call \d|toll.?free|hotline|visit \S|website|www\.|https?://|customer service"
    ),
}

# What a household is entitled to receive, as opposed to how they are told to behave.
SUBSTANTIVE: tuple[str, ...] = ("refund", "replacement", "repair", "disposal")

HAZARD_VOCAB: tuple[str, ...] = (
    "fire", "burn", "overheat", "explos", "flammab", "smoke",
    "chok", "ingest", "aspirat", "suffocat", "strangul", "entrap",
    "fall", "tip.?over", "collapse", "detach",
    "lacerat", "amputat", "crush", "impact", "cut",
    "shock", "electrocut", "electric",
    "poison", "toxic", "lead", "chemical", "mold", "bacteri",
    "drown", "injur", "death", "fatal",
)

_HAZARD_RES = tuple((term, re.compile(f"(?i){term}")) for term in HAZARD_VOCAB)

STOP_USING_RE = re.compile(
    r"(?ix)"
    r"\b(?:stop|cease|discontinue)\s+(?:\w+\s+){0,3}?"
    r"(?:using|use|wearing|riding|operating|charging|carrying|consuming|relying)\b"
    r"|\b(?:do\s+not|don't|never)\s+"
    r"(?:use|wear|ride|operate|charge|carry|consume|rely)\b"
    r"|\b(?:stop|do\s+not|don't)\s+allow(?:ing)?\s+(?:\w+\s+){0,3}?to\s+"
    r"(?:use|wear|ride|operate|charge|carry|consume)\b"
    r"|\bkeep\s+(?:\w+\s+){0,3}?out\s+of\s+use\b"
)
CONTACT_RE = REMEDY_PATTERNS["contact"]

# Wording EU GPSR Article 36(2)(c) says a recall notice must not contain.
MINIMISING_RE = re.compile(
    r"(?i)\b(voluntary|voluntarily|precautionary|discretionary|in rare (?:situations|cases)|out of an abundance of caution)\b"
)

# Telling a household to carry on using a recalled product is the failure that
# matters most. Guard each negation separately: Python needs fixed-width lookbehind.
UNSAFE_CONTINUATION_RE = re.compile(
    r"(?i)(?<!not )(?<!don't )(?<!do not )(?<!never )(?<!cannot )"
    r"(?:continue (?:to use|using)|keep using|safe to use|still safe|perfectly safe|no need to stop)"
)


def classify(text: str) -> set[str]:
    """Remedy classes present in a piece of text."""
    return {name for name, pattern in REMEDY_PATTERNS.items() if pattern.search(text)}


def substantive(text: str) -> set[str]:
    return classify(text) & set(SUBSTANTIVE)


def hazard_terms(text: str) -> set[str]:
    return {term for term, pattern in _HAZARD_RES if pattern.search(text)}
