"""Diet plan: retrieve condition passages, get a validated JSON plan, then add foods from the food store."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from . import DISCLAIMER
from .conditions import Condition
from .fooddb import FoodExample, resolve_nutrient, top_foods
from .index import Hit, Reranker, SearchIndex
from .llm import ChatModel
from .prompts import plan_messages
from .schemas import DietPlanReply, ModelRefusal, StructuredOutputError, complete_structured

_MARKER = re.compile(r"\[(\d+)\]")


class PlanUnavailable(RuntimeError):
    """No plan: the sources have no diet passages for the condition, or the model reply was not usable."""


@dataclass
class DietPlan:
    condition: Condition
    summary: str
    nutrients: list[str]
    unresolved_nutrients: list[str]
    foods: list[FoodExample]
    foods_to_avoid: list[str]
    sources: list[Hit]
    cited: list[int]
    attempts: int
    disclaimer: str = DISCLAIMER
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "condition": self.condition.value,
            "summary": self.summary,
            "nutrients": self.nutrients,
            "unresolved_nutrients": self.unresolved_nutrients,
            "foods": [f.__dict__ for f in self.foods],
            "foods_to_avoid": self.foods_to_avoid,
            "sources": [{"n": n, "citation": self.sources[n - 1].chunk.citation()} for n in self.cited],
            "attempts": self.attempts,
            "warnings": self.warnings,
            "disclaimer": self.disclaimer,
        }


def valid_markers(text: str, n_passages: int) -> tuple[str, list[int]]:
    """Remove markers that point to no passage. Return the text and the valid marker numbers."""
    found: list[int] = []

    def keep(m: re.Match) -> str:
        n = int(m.group(1))
        if 1 <= n <= n_passages:
            if n not in found:
                found.append(n)
            return m.group(0)
        return ""

    return re.sub(r"\s+", " ", _MARKER.sub(keep, text)).strip(), found


class Planner:
    def __init__(self, index: SearchIndex, model: ChatModel, foods: sqlite3.Connection, *, top_k: int,
                 min_score: float, max_attempts: int, foods_per_nutrient: int, reranker: Reranker | None = None):
        self.index, self.model, self.foods = index, model, foods
        self.top_k, self.min_score, self.max_attempts = top_k, min_score, max_attempts
        self.foods_per_nutrient = foods_per_nutrient
        self.reranker = reranker

    def query_for(self, condition: Condition) -> str:
        return f"diet for {condition.display}: foods and nutrients to include, foods to limit or avoid"

    def plan(self, condition: Condition) -> DietPlan:
        hits = self.index.search(self.query_for(condition), self.top_k, kind="diet_plan", condition=condition.value,
                                 min_score=self.min_score, reranker=self.reranker)
        if not hits:
            raise PlanUnavailable(f"the sources have no diet passages for {condition.display.lower()}")
        try:
            res = complete_structured(self.model, plan_messages(condition.display, hits), DietPlanReply, self.max_attempts)
        except ModelRefusal as exc:
            raise PlanUnavailable(f"the model found no diet advice in the passages: {exc}") from exc
        except StructuredOutputError as exc:
            raise PlanUnavailable(f"the model reply was not valid JSON after {self.max_attempts} attempts") from exc
        reply: DietPlanReply = res.value  # type: ignore[assignment]
        warnings: list[str] = []
        summary, markers = valid_markers(reply.diet_plan_summary, len(hits))
        cited = sorted(set(markers) | {n for n in reply.citations if 1 <= n <= len(hits)})
        if not markers:
            warnings.append("The summary has no valid passage marker. Check it against the sources.")
        if not cited:
            cited = list(range(1, len(hits) + 1))
        resolved, unresolved, examples = [], [], []
        for name in reply.nutrients_recommended:
            nutrient = resolve_nutrient(self.foods, name)
            if nutrient is None:
                unresolved.append(name)
                continue
            if nutrient.name in resolved:
                continue
            resolved.append(nutrient.name)
            examples.extend(top_foods(self.foods, nutrient, self.foods_per_nutrient, exclude=reply.foods_to_avoid))
        if unresolved:
            warnings.append("Some nutrient names are not in the food store: " + ", ".join(unresolved))
        return DietPlan(condition, summary, resolved, unresolved, examples, reply.foods_to_avoid, hits, cited,
                        res.attempts, warnings=warnings)
