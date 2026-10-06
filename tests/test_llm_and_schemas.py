import json

import httpx
import pytest

from nutribuddy.llm import LLMError, OfflineChatModel, OpenAICompatibleChatModel, ScriptedChatModel
from nutribuddy.schemas import (
    DietPlanReply,
    ModelRefusal,
    ScreenReply,
    StructuredOutputError,
    complete_structured,
    extract_json_object,
)

GOOD_PLAN = json.dumps({"nutrients_recommended": ["Fiber", "fiber", "protein"],
                        "diet_plan_summary": "Eat more beans and oats for fiber [1].", "foods_to_avoid": "soda, sweets",
                        "citations": [1]})


def test_extract_json_from_fences_and_text():
    assert extract_json_object('Sure! ```json\n{"a": 1}\n``` done') == {"a": 1}
    assert extract_json_object('prefix {"a": {"b": 2}} suffix') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        extract_json_object("no json here")


def test_plan_reply_normalizes_lists():
    reply = DietPlanReply.model_validate(json.loads(GOOD_PLAN))
    assert reply.nutrients_recommended == ["Fiber", "protein"]
    assert reply.foods_to_avoid == ["soda", "sweets"]


def test_retry_sends_error_feedback_then_succeeds():
    model = ScriptedChatModel(["not json at all", '{"diet_plan_summary": "short"}', GOOD_PLAN])
    res = complete_structured(model, [{"role": "user", "content": "x"}], DietPlanReply, max_attempts=3)
    assert res.attempts == 3 and len(res.errors) == 2
    assert "not valid" in model.calls[1][-1]["content"]
    assert model.calls[1][-2] == {"role": "assistant", "content": "not json at all"}


def test_retry_gives_up_with_errors():
    model = ScriptedChatModel(["{}", "{}"])
    with pytest.raises(StructuredOutputError) as exc:
        complete_structured(model, [{"role": "user", "content": "x"}], ScreenReply, max_attempts=2)
    assert len(exc.value.errors) == 2


def test_refusal_is_not_retried():
    model = ScriptedChatModel(['{"error": "no diet advice"}', GOOD_PLAN])
    with pytest.raises(ModelRefusal):
        complete_structured(model, [{"role": "user", "content": "x"}], DietPlanReply, max_attempts=3)
    assert len(model.calls) == 1


def test_openai_adapter_sends_json_mode_and_reads_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"condition": "heart"}'}}]})

    m = OpenAICompatibleChatModel("http://llm.test/v1", "m1", api_key="k", transport=httpx.MockTransport(handler))
    assert m.complete([{"role": "user", "content": "hi"}], json_mode=True) == '{"condition": "heart"}'
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["temperature"] == 0 and seen["auth"] == "Bearer k"


def test_openai_adapter_errors():
    m = OpenAICompatibleChatModel("http://llm.test/v1", "m1",
                                  transport=httpx.MockTransport(lambda r: httpx.Response(401, text="no")))
    with pytest.raises(LLMError, match="401"):
        m.complete([{"role": "user", "content": "hi"}])
    m = OpenAICompatibleChatModel("http://llm.test/v1", "m1",
                                  transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(LLMError, match="not reachable"):
        m.complete([{"role": "user", "content": "hi"}])


def test_offline_model_plan_extracts_nutrients_and_avoid_list():
    user = ("Condition: Heart disease\n\nPassages:\n"
            "[1] condition=heart source=s1 page=1\nInclude potassium from fruits. Limit salt, processed meats "
            "and canned soups because they raise blood pressure.\n")
    reply = json.loads(OfflineChatModel().complete([{"role": "system", "content": "TASK: plan"},
                                                    {"role": "user", "content": user}]))
    assert reply["nutrients_recommended"] == ["potassium"]
    assert reply["foods_to_avoid"] == ["salt", "processed meats", "canned soups"]
    assert reply["citations"] == [1] and "[1]" in reply["diet_plan_summary"]
