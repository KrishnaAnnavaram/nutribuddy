"""Input checks, red-flag symptoms and the scope check for follow-up questions."""

from __future__ import annotations

import re
import unicodedata

from .text import tokenize


class InputError(ValueError):
    """The user text is empty, too long or not printable."""


URGENT_MESSAGE = (
    "Some of the symptoms you describe can be a medical emergency. "
    "Contact emergency services or a clinician now. nutribuddy does not give advice for these symptoms."
)
OUT_OF_SCOPE_MESSAGE = (
    "nutribuddy answers questions about diet, food and nutrition for diabetes, heart disease and thyroid "
    "disorders only."
)

# Phrases that must route the user to urgent care instead of a diet answer.
RED_FLAGS: dict[str, str] = {
    "chest pain": r"\bchest (?:pain|pressure|tightness)\b|\bpain in (?:my|the) chest\b",
    "breathing difficulty": r"\b(?:short(?:ness)? of breath|can(?:no|')t breathe|difficulty breathing|trouble breathing)\b",
    "fainting": r"\b(?:faint(?:ed|ing)?|passed out|pass out|lost consciousness|blackout)\b",
    "stroke signs": r"\b(?:slurred speech|face (?:is )?droop\w*|one side (?:of my body )?(?:is )?(?:numb|weak))\b",
    "confusion": r"\b(?:confused|confusion|disoriented)\b",
    "very high blood sugar": r"\bblood (?:sugar|glucose) (?:of |is |at )?(?:[3-9]\d\d|over 300)\b",
    "very low blood sugar": r"\bblood (?:sugar|glucose) (?:of |is |at )?(?:[1-5]\d)\b(?! ?%)",
    "vomiting blood": r"\bvomit\w* blood\b",
    "self-harm": r"\b(?:suicid\w*|kill myself|self[- ]harm)\b",
}
_RED_FLAG_RX = {name: re.compile(rx, re.I) for name, rx in RED_FLAGS.items()}

_SCOPE_WORDS = set(
    tokenize(
        """diet food foods eat eating meal meals breakfast lunch dinner snack snacks drink drinks nutrition nutrient
        nutrients calorie calories protein fiber fibre carbohydrate carbs sugar salt sodium potassium iodine
        selenium vitamin vitamins mineral fat fats oil cholesterol fruit fruits vegetable vegetables grain grains
        bread rice pasta bean beans lentil nut nuts seed seeds fish meat chicken egg eggs dairy milk cheese
        yogurt coffee tea alcohol juice portion portions serving recipe cook cooking weight glucose insulin
        thyroid diabetes heart blood pressure soy cabbage broccoli oats water supplement supplements"""
    )
)


def clean_input(text: str, max_chars: int) -> str:
    """Normalize Unicode, remove control characters and check the length.

    Digits, commas and apostrophes are allowed ('Can I eat 2 eggs a day?').
    """
    if text is None:
        raise InputError("the text is empty")
    text = unicodedata.normalize("NFKC", str(text))
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise InputError("the text is empty")
    if len(text) > max_chars:
        raise InputError(f"the text has {len(text)} characters. The limit is {max_chars}.")
    if not re.search(r"[A-Za-z]", text):
        raise InputError("the text has no words")
    return text


def red_flags(text: str) -> list[str]:
    return [name for name, rx in _RED_FLAG_RX.items() if rx.search(text)]


def in_scope(question: str) -> bool:
    return bool(set(tokenize(question)) & _SCOPE_WORDS)
