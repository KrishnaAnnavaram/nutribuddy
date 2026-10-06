"""Structured model output: JSON extraction, pydantic validation and bounded retries with feedback."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .llm import ChatModel, LLMError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


class ModelRefusal(RuntimeError):
    """The model replied with {"error": ...}: the passages do not support an answer."""


def _clean_list(values: list[str], max_len: int) -> list[str]:
    out: list[str] = []
    for v in values:
        v = re.sub(r"\s+", " ", str(v)).strip(" .")
        if v and len(v) <= max_len and v.lower() not in {x.lower() for x in out}:
            out.append(v)
    return out


class DietPlanReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nutrients_recommended: list[str] = Field(default_factory=list, max_length=15)
    diet_plan_summary: str = Field(min_length=20, max_length=3000)
    foods_to_avoid: list[str] = Field(default_factory=list, max_length=15)
    citations: list[int] = Field(default_factory=list)

    @field_validator("nutrients_recommended", "foods_to_avoid", mode="before")
    @classmethod
    def _as_list(cls, v):
        if isinstance(v, str):
            v = [x for x in re.split(r"[,;\n]", v)]
        if isinstance(v, list):
            return _clean_list([x.get("nutrient", "") if isinstance(x, dict) else x for x in v], 60)
        return v


class ScreenReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    condition: str = Field(min_length=1, max_length=80)
    citations: list[int] = Field(default_factory=list)


def extract_json_object(text: str) -> dict:
    """Find the first JSON object in a reply. Accept code fences and text around the object."""
    text = re.sub(r"```(?:json)?", "", text)
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("no JSON object in the reply")


@dataclass
class StructuredResult:
    value: BaseModel
    attempts: int
    errors: list[str] = field(default_factory=list)


def complete_structured(model: ChatModel, messages: list[dict], schema: type[T], max_attempts: int) -> StructuredResult:
    """Call the model until its reply validates against ``schema``, at most ``max_attempts`` times.

    After a failure, the next call gets the previous reply and the error. A reply of the form
    {"error": "..."} is a refusal and is not retried.
    """
    msgs = list(messages)
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            reply = model.complete(msgs, json_mode=True)
        except LLMError as exc:
            errors.append(f"attempt {attempt}: {exc}")
            log.warning("chat model call failed: %s", exc)
            continue
        try:
            obj = extract_json_object(reply)
            if set(obj) == {"error"}:
                raise ModelRefusal(str(obj["error"])[:300])
            return StructuredResult(schema.model_validate(obj), attempt, errors)
        except ModelRefusal:
            raise
        except (ValueError, ValidationError) as exc:
            msg = str(exc).splitlines()[0][:300]
            errors.append(f"attempt {attempt}: {msg}")
            log.info("reply did not validate (attempt %d): %s", attempt, msg)
            msgs = msgs + [
                {"role": "assistant", "content": reply[:4000]},
                {"role": "user", "content": f"Your reply was not valid: {msg}. Reply again with the JSON object only."},
            ]
    raise StructuredOutputError(f"no valid reply after {max_attempts} attempts", errors)
