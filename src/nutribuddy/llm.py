"""Chat models behind one interface.

- ``OpenAICompatibleChatModel``: any ``/chat/completions`` endpoint (Ollama, vLLM, OpenAI, Groq).
- ``OfflineChatModel``: a deterministic, extractive stand-in. It needs no key and no network.
- ``ScriptedChatModel``: returns fixed replies, for tests.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Protocol

import httpx

from .text import sentences, tokenize

Message = dict[str, str]


class LLMError(RuntimeError):
    """The chat model did not return a usable reply."""


class ChatModel(Protocol):
    name: str

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str: ...


class OpenAICompatibleChatModel:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: float = 60.0,
        seed: int = 7,
        transport: httpx.BaseTransport | None = None,
    ):
        self.name = f"openai:{model}"
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._seed = seed
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(timeout=timeout_s, headers=headers, transport=transport)

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str:
        body: dict = {"model": self._model, "messages": messages, "temperature": 0, "seed": self._seed}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        last: Exception | None = None
        for _ in range(2):
            try:
                resp = self._client.post(self._url, json=body)
            except httpx.HTTPError as exc:
                last = exc
                continue
            if resp.status_code >= 500:
                last = LLMError(f"server error {resp.status_code}")
                continue
            if resp.status_code >= 400:
                raise LLMError(f"request refused with status {resp.status_code}: {resp.text[:200]}")
            try:
                return resp.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise LLMError("reply has no choices[0].message.content") from exc
        raise LLMError(f"chat model not reachable: {last}")


class ScriptedChatModel:
    def __init__(self, replies: list[str]):
        self.name = "scripted"
        self.replies = list(replies)
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str:
        self.calls.append([dict(m) for m in messages])
        if not self.replies:
            raise LLMError("no scripted reply left")
        return self.replies.pop(0)


# ---------------------------------------------------------------- offline model

_PASSAGE = re.compile(r"^\[(\d+)\] condition=(\w+) source=(\S+)[^\n]*\n(.*?)(?=^\[\d+\] condition=|\Z)", re.M | re.S)
_TASK = re.compile(r"^TASK: (\w+)", re.M)
NUTRIENT_WORDS = (
    "soluble fiber", "fiber", "protein", "potassium", "magnesium", "calcium", "iron", "zinc", "selenium",
    "iodine", "vitamin d", "vitamin b12", "vitamin c", "folate", "omega-3 fatty acids", "unsaturated fat",
    "complex carbohydrates",
)
_INCLUDE = re.compile(r"\b(include|choose|eat more|rich in|good sources? of|add|prefer|aim for)\b", re.I)
_LIMIT = re.compile(r"\b(?:limit|avoid|reduce|cut back on)\s+([^.;:]+)", re.I)


def parse_passages(text: str) -> list[tuple[int, str, str, str]]:
    """Read '[n] condition=... source=...' blocks: (number, condition, source id, body)."""
    return [(int(n), c, s, body.strip()) for n, c, s, body in _PASSAGE.findall(text)]


_CUT = re.compile(r"\b(?:if|because|when|unless|to|with|for|so)\b", re.I)
_LEAD = re.compile(r"^(?:the|a|an|foods? (?:high|rich) in|too much|excess|large portions of|small amounts of)\s+", re.I)


def _split_list(text: str) -> list[str]:
    text = _CUT.split(text)[0]
    out = []
    for p in re.split(r",|\band\b|\bor\b", text):
        p = _LEAD.sub("", p.strip()).strip()
        if 2 < len(p) <= 40 and len(p.split()) <= 4 and not re.search(r"\d", p):
            out.append(p.lower())
    return out


class OfflineChatModel:
    """Deterministic stand-in for a chat model. It reads the numbered passages in the prompt.

    - ``screen``: rank-weighted vote of the passage conditions.
    - ``plan``: extracts nutrients next to 'include' words and foods after 'limit' or 'avoid'.
    - ``answer``: returns the two passage sentences with the most question tokens, with markers.
    """

    name = "offline-extractive"

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        user = messages[-1]["content"]
        m = _TASK.search(system)
        task = m.group(1) if m else "answer"
        passages = parse_passages(user)
        if task == "screen":
            return self._screen(passages)
        if task == "plan":
            return self._plan(passages)
        return self._answer(user, passages)

    @staticmethod
    def _screen(passages) -> str:
        votes: dict[str, float] = defaultdict(float)
        for rank, (n, cond, _, _) in enumerate(passages, start=1):
            votes[cond] += 1.0 / rank
        if not votes:
            return json.dumps({"condition": "none", "citations": []})
        best = max(votes, key=lambda c: (votes[c], -min(n for n, cc, _, _ in passages if cc == c)))
        cited = [n for n, c, _, _ in passages if c == best]
        return json.dumps({"condition": best, "citations": cited})

    @staticmethod
    def _plan(passages) -> str:
        nutrients: list[str] = []
        avoid: list[str] = []
        summary: list[str] = []
        cited: list[int] = []
        for n, _, _, body in passages:
            used = False
            for s in sentences(body):
                low = s.lower()
                if _INCLUDE.search(s):
                    for word in NUTRIENT_WORDS:
                        if re.search(rf"\b{re.escape(word)}\b", low) and not any(word in x for x in nutrients):
                            nutrients.append(word)
                            used = True
                for m in _LIMIT.finditer(s):
                    for item in _split_list(m.group(1)):
                        if item not in avoid:
                            avoid.append(item)
                            used = True
                if (_INCLUDE.search(s) or _LIMIT.search(s)) and len(summary) < 4:
                    summary.append(f"{s} [{n}]")
                    used = True
            if used:
                cited.append(n)
        if not summary:
            return json.dumps({"error": "the passages do not give diet advice"})
        return json.dumps(
            {
                "nutrients_recommended": nutrients[:8],
                "diet_plan_summary": " ".join(summary),
                "foods_to_avoid": avoid[:8],
                "citations": cited,
            }
        )

    @staticmethod
    def _answer(user: str, passages) -> str:
        q = user.split("Passages:")[0]
        q_line = re.search(r"Question:\s*(.*)", q)
        q_tokens = set(tokenize(q_line.group(1) if q_line else q))
        scored = []
        for n, _, _, body in passages:
            for s in sentences(body):
                overlap = len(q_tokens & set(tokenize(s)))
                if overlap:
                    scored.append((overlap, -n, s, n))
        if not scored:
            return "The sources do not answer this question."
        scored.sort(reverse=True)
        return " ".join(f"{s} [{n}]" for _, _, s, n in scored[:2])


def build_chat_model(provider: str, base_url: str, model: str, api_key: str, timeout_s: float) -> ChatModel:
    if provider == "offline":
        return OfflineChatModel()
    if provider == "openai":
        return OpenAICompatibleChatModel(base_url, model, api_key, timeout_s)
    raise ValueError(f"unknown chat model provider {provider!r}")


__all__ = [
    "ChatModel", "LLMError", "OfflineChatModel", "OpenAICompatibleChatModel", "ScriptedChatModel",
    "build_chat_model", "parse_passages",
]
