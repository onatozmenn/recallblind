"""Hazard taxonomy drafted from CPSC hazard prose.

`Hazards[].HazardType` is empty in every record, so the label set is ours. These
categories are not invented: they are the mechanisms that actually appear in the
free text of 1,081 recalls, with the measured frequency of each phrasing.

CPSC prose mixes two different things in one sentence, for example "posing a risk
of serious injury or death from fire". "Fire" is the *mechanism*; "serious injury
or death" is the *outcome*. The taxonomy labels mechanism only, and severity is
recorded separately, otherwise every category collapses into "injury".

The draft assigns at least one mechanism to 97.7% of records. The residual is not
noise: those notices state only "posing an injury hazard" without naming a
mechanism, so a human has to infer it from the product description. That is
precisely the work the annotation campaign exists to do.

`unauthorised_access` matches only 8 records and is too thin to carry an
independent agreement figure. It is kept because the mechanism is genuinely
distinct, and reported descriptively.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .schema import Recall


@dataclass(frozen=True)
class Category:
    name: str
    pattern: str
    definition: str
    includes: tuple[str, ...]
    excludes: tuple[str, ...]


# Ordered by measured frequency in the 2024-2026 CPSC corpus.
CATEGORIES: tuple[Category, ...] = (
    Category(
        name="fire_burn",
        pattern=r"fire|burn|overheat|flammab|melt|scald|thermal",
        definition="Uncontrolled heat, ignition or contact with a hot surface or liquid.",
        includes=("flash fire", "battery overheating", "scalding by hot contents"),
        excludes=("chemical burn from a corrosive substance, which is poisoning_chemical",),
    ),
    Category(
        name="fall_tipover",
        pattern=r"\bfall|\bfell\b|tip.?over|topple|collapse|unstable|detach",
        definition="The product drops the user, or the product itself falls onto them.",
        includes=("furniture tip-over", "a stroller frame collapsing", "a wheel detaching"),
        excludes=("falling because of a crash while riding, which is crash_collision",),
    ),
    Category(
        name="ingestion_choking",
        pattern=r"chok|ingest|swallow|aspirat|small parts?\b",
        definition="A part enters the mouth or airway, or is swallowed.",
        includes=("magnets swallowed", "a small part detaching from a toy"),
        excludes=(
            "swallowing a toxic substance, which is poisoning_chemical",
            "airway blocked by soft material or bedding, which is entrapment_asphyxiation",
        ),
    ),
    Category(
        name="entrapment_asphyxiation",
        pattern=r"entrap|asphyxiat|suffocat|strangul|\bwedge|\bpinn(?:ed|ing)\b",
        definition="The body or airway is confined, compressed or obstructed by the product.",
        includes=("head entrapment in a gap", "soft bedding causing suffocation", "cord strangulation"),
        excludes=("an object lodged in the throat, which is ingestion_choking",),
    ),
    Category(
        name="laceration_impact",
        pattern=r"lacerat|amputat|\bcut\b|crush|impact|blunt|pinch|sever(?:ed|ing)\b|projectile",
        definition="Mechanical injury from a blade, moving part, pinch point or flying object.",
        includes=("blade contact", "a pressure lid ejecting", "a projectile from a toy"),
        excludes=("injury caused by falling, which is fall_tipover",),
    ),
    Category(
        name="electrical",
        pattern=r"shock|electrocut|electrical|short.circuit|arc(?:ing)?\b",
        definition="Electric current reaches the user.",
        includes=("exposed live wiring", "failed insulation"),
        excludes=("a battery igniting, which is fire_burn",),
    ),
    Category(
        name="poisoning_chemical",
        pattern=r"poison|toxic|\blead\b|carbon monoxide|\bco\b|chemical|mold|bacteri|respiratory|formaldehyde|benzene",
        definition="A substance enters or affects the body by ingestion, contact or inhalation.",
        includes=("lead paint", "carbon monoxide from a boiler", "microbial contamination"),
        excludes=("a physical part swallowed, which is ingestion_choking",),
    ),
    Category(
        name="crash_collision",
        pattern=r"crash|collision|loss of control|brake failure|steering",
        definition="Loss of control of a ridden or driven product.",
        includes=("bicycle fork failure", "e-bike brake failure"),
        excludes=("a stationary product falling over, which is fall_tipover",),
    ),
    Category(
        name="drowning",
        pattern=r"drown|submers",
        definition="Immersion in water.",
        includes=("a flotation aid failing",),
        excludes=(),
    ),
    Category(
        name="unauthorised_access",
        pattern=r"unauthorized|unauthorised|can be opened by|fail to lock|lock can fail|defeat",
        definition="A lock or restraint fails, giving access to someone who should not have it.",
        includes=("a biometric gun safe opening for the wrong user", "a child-resistant closure failing"),
        excludes=("a door falling off, which is fall_tipover",),
    ),
    Category(
        name="unintended_activation",
        pattern=r"unexpectedly|unintend|discharge|activat|start(?:s|ing)? on its own|without warning|retract",
        definition="The product operates when it should not, or fails to stop when told to.",
        includes=("a crossbow discharging while being cocked", "a heater running after the thermostat is off"),
        excludes=("a battery igniting on its own, which is fire_burn",),
    ),
)

_COMPILED = tuple((c.name, re.compile(f"(?i){c.pattern}")) for c in CATEGORIES)

# Outcome language, deliberately kept out of the mechanism labels.
_DEATH_RE = re.compile(r"(?i)death|fatal|deadly")
_SERIOUS_RE = re.compile(r"(?i)serious")


def classify(text: str) -> set[str]:
    """Mechanisms named in a hazard description. Multi-label by design."""
    return {name for name, pattern in _COMPILED if pattern.search(text)}


def severity(text: str) -> str:
    if _DEATH_RE.search(text):
        return "death"
    if _SERIOUS_RE.search(text):
        return "serious_injury"
    return "injury"


def hazard_text(record: Recall) -> str:
    return " ".join(record.hazards) or record.title


def coverage(records: Iterable[Recall]) -> dict[str, object]:
    """How much of the corpus the draft taxonomy accounts for."""
    total = 0
    labelled = 0
    per_category: dict[str, int] = {c.name: 0 for c in CATEGORIES}
    per_severity: dict[str, int] = {}
    multi = 0
    unlabelled: list[str] = []

    for record in records:
        total += 1
        text = hazard_text(record)
        names = classify(text)
        if names:
            labelled += 1
            if len(names) > 1:
                multi += 1
            for name in names:
                per_category[name] += 1
        elif len(unlabelled) < 20:
            unlabelled.append(f"{record.key}: {text[:120]}")
        level = severity(text)
        per_severity[level] = per_severity.get(level, 0) + 1

    return {
        "records": total,
        "labelled": labelled,
        "coverage": round(labelled / total, 4) if total else 0.0,
        "multi_label": multi,
        "by_category": dict(sorted(per_category.items(), key=lambda kv: -kv[1])),
        "by_severity": per_severity,
        "unlabelled_examples": unlabelled,
    }
