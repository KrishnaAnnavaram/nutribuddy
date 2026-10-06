"""The three supported conditions and a tolerant, case-insensitive label parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Condition(str, Enum):
    DIABETES = "diabetes"
    HEART = "heart"
    THYROID = "thyroid"

    @property
    def display(self) -> str:
        return {"diabetes": "Diabetes", "heart": "Heart disease", "thyroid": "Thyroid disorder"}[self.value]


# Phrases that name each condition. Longer phrases are checked first.
_SYNONYMS: dict[Condition, tuple[str, ...]] = {
    Condition.DIABETES: (
        "type 2 diabetes", "type 1 diabetes", "diabetes mellitus", "diabetic", "diabetes",
        "high blood sugar", "hyperglycemia",
    ),
    Condition.HEART: (
        "coronary artery disease", "cardiovascular disease", "heart disease", "heart failure",
        "cardiovascular", "coronary", "cardiac", "heart",
    ),
    Condition.THYROID: (
        "hypothyroidism", "hyperthyroidism", "thyroid disorder", "thyroid disease", "thyroiditis", "thyroid",
    ),
}
_NONE_WORDS = ("none", "no condition", "no match", "unknown", "not sure", "n/a", "null")


@dataclass(frozen=True)
class ParsedLabel:
    """Result of reading a free-text label from a model reply."""

    condition: Condition | None
    is_none: bool
    valid: bool


def normalize_label_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[*_`\"'“”‘’()\[\]{}<>]", " ", text)
    text = re.sub(r"[.,;:!?]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_condition_label(text: str | None) -> ParsedLabel:
    """Read one condition from text such as 'Heart disease.', '**Diabetes**' or 'none'.

    The parser accepts extra words, punctuation and any letter case. If the text names
    more than one condition, the label is not valid (the caller must not guess).
    """
    if text is None:
        return ParsedLabel(None, False, False)
    norm = f" {normalize_label_text(text)} "
    if not norm.strip():
        return ParsedLabel(None, False, False)
    found: set[Condition] = set()
    for condition, phrases in _SYNONYMS.items():
        for phrase in phrases:
            if f" {phrase} " in norm:
                found.add(condition)
                break
    if len(found) == 1:
        return ParsedLabel(found.pop(), False, True)
    if len(found) > 1:
        return ParsedLabel(None, False, False)
    for word in _NONE_WORDS:
        if f" {word} " in norm:
            return ParsedLabel(None, True, True)
    return ParsedLabel(None, False, False)


def condition_from_user(text: str) -> Condition:
    """Read a condition that a user typed or selected. Raise ValueError if it is not one of the three."""
    parsed = parse_condition_label(text)
    if parsed.condition is None:
        raise ValueError(f"unknown condition {text!r}: use diabetes, heart or thyroid")
    return parsed.condition
