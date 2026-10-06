"""Symptom screening: 'which supported condition do the sources connect to these symptoms?'

This is not a diagnosis. The result names a possible condition to discuss with a clinician,
or it tells the user that the symptoms need urgent care.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from .conditions import Condition, parse_condition_label
from .index import Hit, Reranker, SearchIndex
from .llm import ChatModel
from .prompts import screen_messages
from .safety import URGENT_MESSAGE, red_flags
from .schemas import ModelRefusal, ScreenReply, StructuredOutputError, complete_structured
from .text import tokenize

log = logging.getLogger(__name__)

STATUSES = ("possible_condition", "no_match", "urgent", "unparsed")


@dataclass
class ScreeningResult:
    status: str
    condition: Condition | None
    message: str
    red_flags: list[str] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)
    attempts: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "condition": self.condition.value if self.condition else None,
            "message": self.message,
            "red_flags": self.red_flags,
            "sources": [h.chunk.citation() for h in self.hits],
            "cited": self.cited,
        }


class Screener:
    def __init__(self, index: SearchIndex, model: ChatModel, *, top_k: int, min_score: float,
                 max_attempts: int, reranker: Reranker | None = None):
        self.index, self.model = index, model
        self.top_k, self.min_score, self.max_attempts = top_k, min_score, max_attempts
        self.reranker = reranker

    def screen(self, symptoms: str) -> ScreeningResult:
        flags = red_flags(symptoms)
        if flags:
            return ScreeningResult("urgent", None, URGENT_MESSAGE, red_flags=flags)
        hits = self.index.search(symptoms, self.top_k, kind="disease", min_score=self.min_score, reranker=self.reranker)
        if not hits:
            return ScreeningResult("no_match", None, _no_match_message())
        try:
            res = complete_structured(self.model, screen_messages(symptoms, hits), ScreenReply, self.max_attempts)
        except ModelRefusal:
            return ScreeningResult("no_match", None, _no_match_message(), hits=hits)
        except StructuredOutputError as exc:
            log.warning("screening reply not usable: %s", exc.errors)
            return ScreeningResult("unparsed", None, "nutribuddy could not read the model reply. Try again.", hits=hits,
                                   attempts=self.max_attempts)
        reply: ScreenReply = res.value  # type: ignore[assignment]
        label = parse_condition_label(reply.condition)
        cited = [n for n in reply.citations if 1 <= n <= len(hits)]
        if not label.valid:
            return ScreeningResult("unparsed", None, "nutribuddy could not read the model reply. Try again.", hits=hits,
                                   attempts=res.attempts)
        if label.condition is None:
            return ScreeningResult("no_match", None, _no_match_message(), hits=hits, attempts=res.attempts)
        c = label.condition
        msg = (
            f"The sources connect some of these symptoms with {c.display.lower()}. This is not a diagnosis. "
            "Discuss the symptoms with a clinician, who can order the correct tests."
        )
        return ScreeningResult("possible_condition", c, msg, hits=hits, cited=cited, attempts=res.attempts)


def _no_match_message() -> str:
    return (
        "The sources do not connect these symptoms with diabetes, heart disease or a thyroid disorder. "
        "If the symptoms continue, discuss them with a clinician."
    )


# ------------------------------------------------------------------ baselines

SYMPTOM_LEXICON: dict[Condition, tuple[str, ...]] = {
    Condition.DIABETES: ("thirst", "thirsty", "urination", "urinate", "blurred", "slow-healing", "numbness",
                         "tingling", "hunger", "glucose", "sugar"),
    Condition.HEART: ("palpitation", "ankle", "swelling", "swollen", "breathless", "racing", "heartbeat",
                      "jaw", "cholesterol", "blood pressure"),
    Condition.THYROID: ("cold", "hair", "dry skin", "constipation", "weight gain", "goiter", "neck", "puffy",
                        "hoarse", "heat", "tremor"),
}


class KeywordBaseline:
    """Counts lexicon words for each condition. Ties and zero counts give 'none'."""

    name = "keyword-baseline"

    def predict(self, text: str) -> str:
        low = " " + " ".join(tokenize(text)) + " "
        raw = text.lower()
        scores = Counter()
        for cond, words in SYMPTOM_LEXICON.items():
            for w in words:
                if (" " in w and w in raw) or f" {w} " in low:
                    scores[cond.value] += 1
        if not scores:
            return "none"
        top = scores.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            return "none"
        return top[0][0]


class MajorityBaseline:
    name = "majority-baseline"

    def __init__(self, labels: list[str]):
        self.label = Counter(labels).most_common(1)[0][0]

    def predict(self, text: str) -> str:
        return self.label
