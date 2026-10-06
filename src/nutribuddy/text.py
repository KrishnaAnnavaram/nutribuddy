"""Tokenizer shared by BM25, the hashing embedder and the offline chat model."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an and are as at be been but by can do does for from had has have how i i'm if in into is it its
    me my of on or our she he so some than that the their them then there these they this to too was we
    what when which who why will with you your am feel feeling get got also about after before very lot
    lately recently often sometimes much more most any all not no""".split()
)
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens with stopwords removed and a light plural stem."""
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]


def clean_text(text: str) -> str:
    """Join words split by a line-end hyphen, then collapse white space inside each line."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()
