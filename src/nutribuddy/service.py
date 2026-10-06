"""The nutribuddy service. It builds the embedder, the index, the chat model and the stores once."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

from . import DISCLAIMER
from .conditions import Condition, condition_from_user
from .config import Settings
from .embeddings import build_embedder
from .fooddb import connect as connect_foods
from .index import Hit, SearchIndex, build_reranker
from .llm import ChatModel, LLMError, build_chat_model
from .planner import DietPlan, Planner, valid_markers
from .prompts import answer_messages
from .safety import OUT_OF_SCOPE_MESSAGE, URGENT_MESSAGE, clean_input, in_scope, red_flags
from .screening import Screener, ScreeningResult
from .sessions import SessionStore

log = logging.getLogger(__name__)
NO_ANSWER = "The sources do not answer this question."


@dataclass
class Answer:
    status: str  # answered | no_evidence | out_of_scope | urgent | model_error
    text: str
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"status": self.status, "text": self.text, "sources": self.sources, "disclaimer": DISCLAIMER}


class NutriBuddy:
    def __init__(self, settings: Settings, index: SearchIndex, model: ChatModel, foods: sqlite3.Connection,
                 sessions: SessionStore):
        self.settings = settings
        self.index = index
        self.model = model
        self.foods = foods
        self.sessions = sessions
        self.reranker = build_reranker(settings.reranker)
        common = dict(top_k=settings.top_k, min_score=settings.min_score, max_attempts=settings.llm_max_attempts,
                      reranker=self.reranker)
        self.screener = Screener(index, model, **common)
        self.planner = Planner(index, model, foods, foods_per_nutrient=settings.foods_per_nutrient, **common)

    @classmethod
    def from_settings(cls, settings: Settings, model: ChatModel | None = None) -> "NutriBuddy":
        embedder = build_embedder(settings.embedder, settings.embed_model)
        index = SearchIndex.load(settings.index_dir, embedder)
        model = model or build_chat_model(settings.llm_provider, settings.llm_base_url, settings.llm_model,
                                          settings.llm_api_key, settings.llm_timeout_s)
        return cls(settings, index, model, connect_foods(settings.food_db), SessionStore(settings.session_db))

    # -------------------------------------------------------------- operations

    def screen(self, symptoms: str) -> ScreeningResult:
        return self.screener.screen(clean_input(symptoms, self.settings.max_input_chars))

    def plan(self, condition: str | Condition, session_id: str | None = None) -> DietPlan:
        cond = condition if isinstance(condition, Condition) else condition_from_user(condition)
        plan = self.planner.plan(cond)
        if session_id:
            self.sessions.set_condition(session_id, cond.value)
            self.sessions.append(session_id, "assistant", f"Diet plan for {cond.display}: {plan.summary}")
        return plan

    def new_session(self, condition: str | None = None) -> str:
        cond = condition_from_user(condition).value if condition else None
        return self.sessions.create(cond)

    def ask(self, session_id: str, question: str) -> Answer:
        question = clean_input(question, self.settings.max_input_chars)
        if red_flags(question):
            return Answer("urgent", URGENT_MESSAGE)
        if not in_scope(question):
            return Answer("out_of_scope", OUT_OF_SCOPE_MESSAGE)
        cond_value = self.sessions.condition(session_id)
        cond = Condition(cond_value) if cond_value else None
        history = self.sessions.history(session_id, self.settings.max_history_turns)
        hits = self._retrieve_for_question(question, cond, history)
        if not hits:
            answer = Answer("no_evidence", NO_ANSWER)
        else:
            name = cond.display if cond else "not given"
            try:
                reply = self.model.complete(answer_messages(name, question, history, hits))
            except LLMError as exc:
                log.warning("answer failed: %s", exc)
                return Answer("model_error", "The chat model did not answer. Try again later.")
            text, markers = valid_markers(reply, len(hits))
            if not markers or NO_ANSWER.lower() in text.lower():
                answer = Answer("no_evidence", NO_ANSWER)
            else:
                answer = Answer("answered", text, [f"[{n}] {hits[n - 1].chunk.citation()}" for n in markers])
        self.sessions.append(session_id, "user", question)
        self.sessions.append(session_id, "assistant", answer.text)
        return answer

    def _retrieve_for_question(self, question: str, cond: Condition | None,
                               history: list[tuple[str, str]]) -> list[Hit]:
        """History-aware retrieval with no extra model call: add the condition and the last user question."""
        last_user = next((c for r, c in reversed(history) if r == "user"), "")
        parts = [question]
        if cond:
            parts.append(cond.display)
        if last_user:
            parts.append(last_user)
        return self.index.search(" ".join(parts), self.settings.top_k, kind="diet_plan",
                                 condition=cond.value if cond else None, min_score=self.settings.min_score,
                                 reranker=self.reranker)
