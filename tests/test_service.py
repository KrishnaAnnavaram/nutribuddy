import json
import os

import pytest

from nutribuddy.conditions import Condition
from nutribuddy.evaluation import classification_metrics, run_all, wilson
from nutribuddy.llm import ScriptedChatModel
from nutribuddy.planner import PlanUnavailable, valid_markers
from nutribuddy.render import plan_to_text
from nutribuddy.screening import KeywordBaseline
from nutribuddy.service import NutriBuddy


def test_screening_is_framed_as_not_a_diagnosis(bot):
    res = bot.screen("I am always thirsty, I urinate a lot at night and my toes tingle")
    assert res.status == "possible_condition" and res.condition is Condition.DIABETES
    assert "not a diagnosis" in res.message and res.hits


def test_red_flag_symptoms_route_to_urgent_care(bot):
    res = bot.screen("I have chest pain and I feel sick")
    assert res.status == "urgent" and res.condition is None and "emergency" in res.message


def test_unrelated_symptoms_give_no_match(bot):
    assert bot.screen("I have a toothache").status == "no_match"


def test_label_with_extra_words_is_accepted(workspace):
    model = ScriptedChatModel(['{"condition": "Heart disease.", "citations": [1, 9]}'])
    bot = NutriBuddy.from_settings(workspace, model=model)
    res = bot.screen("my ankles are swollen and I notice palpitations")
    assert res.condition is Condition.HEART and res.cited == [1]


def test_unreadable_label_is_reported_not_guessed(workspace):
    model = ScriptedChatModel(['{"condition": "diabetes or thyroid"}'])
    bot = NutriBuddy.from_settings(workspace, model=model)
    assert bot.screen("I always feel cold and thirsty").status == "unparsed"


@pytest.mark.parametrize("cond", ["diabetes", "heart", "thyroid"])
def test_plan_is_cited_and_foods_come_from_the_store(bot, cond):
    plan = bot.plan(cond)
    names = {r[0] for r in bot.foods.execute("SELECT description FROM food")}
    assert plan.cited and all(1 <= n <= len(plan.sources) for n in plan.cited)
    assert plan.foods and all(f.description in names for f in plan.foods)
    assert all(s.chunk.condition == cond for s in plan.sources)
    text = plan_to_text(plan)
    assert "Sources:" in text and "not a diagnosis" in text


def test_plan_drops_invalid_markers_and_unknown_nutrients(workspace):
    reply = json.dumps({"nutrients_recommended": ["fiber", "unobtainium"],
                        "diet_plan_summary": "Eat oats daily [1] and moon rocks [42].",
                        "foods_to_avoid": ["sweets"], "citations": [1, 99]})
    bot = NutriBuddy.from_settings(workspace, model=ScriptedChatModel([reply]))
    plan = bot.plan("diabetes")
    assert "[42]" not in plan.summary and plan.cited == [1]
    assert plan.nutrients == ["Fiber, total dietary"] and plan.unresolved_nutrients == ["unobtainium"]


def test_plan_html_in_model_output_is_plain_text(workspace):
    reply = json.dumps({"nutrients_recommended": [], "diet_plan_summary": "<script>alert(1)</script> eat fish [1]",
                        "foods_to_avoid": []})
    bot = NutriBuddy.from_settings(workspace, model=ScriptedChatModel([reply]))
    from nutribuddy.render import to_html

    assert "<script" not in to_html(plan_to_text(bot.plan("heart")))


def test_plan_fails_cleanly_after_bad_replies(workspace):
    bot = NutriBuddy.from_settings(workspace, model=ScriptedChatModel(["oops", "oops", "oops"]))
    with pytest.raises(PlanUnavailable, match="not valid JSON"):
        bot.plan("thyroid")


def test_follow_up_uses_server_side_history(bot):
    sid = bot.new_session("heart")
    first = bot.ask(sid, "Which fish give omega-3 fatty acids?")
    assert first.status == "answered" and first.sources and "[1]" in first.text
    assert bot.ask(sid, "Who won the football match?").status == "out_of_scope"
    assert bot.ask(sid, "Can I eat 2 eggs a day?").status in {"answered", "no_evidence"}
    history = bot.sessions.history(sid, 10)
    assert [r for r, _ in history] == ["user", "assistant", "user", "assistant"]


def test_requests_write_no_shared_files(bot, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot.plan("diabetes")
    bot.ask(bot.new_session("diabetes"), "Which drinks raise blood glucose?")
    assert os.listdir(tmp_path) == []


def test_valid_markers():
    assert valid_markers("a [1] b [3] c [1]", 2) == ("a [1] b c [1]", [1])


def test_metrics_and_wilson():
    lo, hi = wilson(8, 10)
    assert 0.4 < lo < 0.8 < hi < 1.0
    m = classification_metrics(["heart", "none", "thyroid"], ["heart", "heart", "thyroid"])
    assert m["accuracy"] == pytest.approx(0.667, abs=1e-3)
    assert KeywordBaseline().predict("I always feel cold and my hair is thinning") == "thyroid"
    assert KeywordBaseline().predict("my wrist hurts") == "none"


def test_full_evaluation_report(bot, data_dir):
    report = run_all(bot, data_dir / "eval")
    assert report["retrieval"]["n"] == 18 and report["retrieval"]["recall@4"] >= 0.9
    assert report["screening"]["nutribuddy"]["n"] == 60
    assert all(p["ok"] and p["foods_from_store"] and not p["avoided_food_suggested"] for p in report["plans"].values())
    assert report["safety"]["red_flag_recall"] == "6/6" and report["safety"]["food_store_unchanged"]
