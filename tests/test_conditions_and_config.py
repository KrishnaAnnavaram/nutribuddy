import tomllib
from pathlib import Path

import pytest

from nutribuddy.conditions import Condition, condition_from_user, parse_condition_label
from nutribuddy.config import ConfigError, Settings


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Heart disease", Condition.HEART),
        ("heart.", Condition.HEART),
        ("**Diabetes**", Condition.DIABETES),
        ("THYROID", Condition.THYROID),
        ("The answer is: type 2 diabetes", Condition.DIABETES),
        ("Hypothyroidism", Condition.THYROID),
        ("'Heart'", Condition.HEART),
    ],
)
def test_label_parser_accepts_case_punctuation_and_extra_words(text, expected):
    parsed = parse_condition_label(text)
    assert parsed.valid and parsed.condition is expected


def test_label_parser_none_and_ambiguous():
    assert parse_condition_label("None").is_none
    assert parse_condition_label("no condition.").is_none
    ambiguous = parse_condition_label("diabetes or heart disease")
    assert not ambiguous.valid and ambiguous.condition is None
    assert not parse_condition_label("").valid
    assert not parse_condition_label("banana").valid


def test_condition_from_user_rejects_unknown():
    assert condition_from_user("Heart") is Condition.HEART
    with pytest.raises(ValueError):
        condition_from_user("asthma")


def test_settings_from_env_reads_and_validates():
    s = Settings.from_env({"NUTRIBUDDY_TOP_K": "6", "NUTRIBUDDY_LLM_PROVIDER": "openai"})
    assert s.top_k == 6 and s.llm_provider == "openai"
    assert Settings.from_env({}).llm_provider == "offline"
    with pytest.raises(ConfigError):
        Settings.from_env({"NUTRIBUDDY_CHUNK_WORDS": "50", "NUTRIBUDDY_CHUNK_OVERLAP": "50"})
    with pytest.raises(ConfigError):
        Settings.from_env({"NUTRIBUDDY_TOP_K": "abc"})
    with pytest.raises(ConfigError):
        Settings.from_env({"NUTRIBUDDY_EMBEDDER": "magic"})


def test_core_dependencies_are_light():
    meta = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    core = " ".join(meta["project"]["dependencies"]).lower()
    for heavy in ("torch", "transformers", "langchain", "chromadb", "flask"):
        assert heavy not in core
