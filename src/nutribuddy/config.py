"""Settings read from environment variables (one object for the CLI, the API and the evaluation)."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping


class ConfigError(ValueError):
    """A configuration value is missing or out of range."""


def _get(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name, "")
    return value.strip() if value and value.strip() else default


def _int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = _get(env, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}, got {value}")
    return value


def _float(env: Mapping[str, str], name: str, default: float, low: float, high: float) -> float:
    raw = _get(env, name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    work_dir: Path = Path(".nutribuddy")
    embedder: str = "hashing"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    reranker: str = "coverage"
    llm_provider: str = "offline"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "llama3.1:8b"
    llm_api_key: str = ""
    llm_timeout_s: float = 60.0
    llm_max_attempts: int = 3
    chunk_words: int = 180
    chunk_overlap: int = 40
    top_k: int = 4
    min_score: float = 0.05
    max_input_chars: int = 600
    max_history_turns: int = 6
    foods_per_nutrient: int = 3

    @property
    def index_dir(self) -> Path:
        return self.work_dir / "index"

    @property
    def food_db(self) -> Path:
        return self.work_dir / "foods.sqlite"

    @property
    def session_db(self) -> Path:
        return self.work_dir / "sessions.sqlite"

    def with_dirs(self, data_dir: Path | None = None, work_dir: Path | None = None) -> "Settings":
        return replace(self, data_dir=data_dir or self.data_dir, work_dir=work_dir or self.work_dir)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        embedder = _get(env, "NUTRIBUDDY_EMBEDDER", cls.embedder).lower()
        if embedder not in {"hashing", "sentence-transformers"}:
            raise ConfigError("NUTRIBUDDY_EMBEDDER must be 'hashing' or 'sentence-transformers'")
        reranker = _get(env, "NUTRIBUDDY_RERANKER", cls.reranker).lower()
        if reranker not in {"coverage", "cross-encoder", "none"}:
            raise ConfigError("NUTRIBUDDY_RERANKER must be 'coverage', 'cross-encoder' or 'none'")
        provider = _get(env, "NUTRIBUDDY_LLM_PROVIDER", cls.llm_provider).lower()
        if provider not in {"offline", "openai"}:
            raise ConfigError("NUTRIBUDDY_LLM_PROVIDER must be 'offline' or 'openai'")
        chunk_words = _int(env, "NUTRIBUDDY_CHUNK_WORDS", cls.chunk_words, 20, 2000)
        overlap = _int(env, "NUTRIBUDDY_CHUNK_OVERLAP", cls.chunk_overlap, 0, 1000)
        if overlap >= chunk_words:
            raise ConfigError("NUTRIBUDDY_CHUNK_OVERLAP must be smaller than NUTRIBUDDY_CHUNK_WORDS")
        return cls(
            data_dir=Path(_get(env, "NUTRIBUDDY_DATA_DIR", str(cls.data_dir))),
            work_dir=Path(_get(env, "NUTRIBUDDY_WORK_DIR", str(cls.work_dir))),
            embedder=embedder,
            embed_model=_get(env, "NUTRIBUDDY_EMBED_MODEL", cls.embed_model),
            reranker=reranker,
            llm_provider=provider,
            llm_base_url=_get(env, "NUTRIBUDDY_LLM_BASE_URL", cls.llm_base_url),
            llm_model=_get(env, "NUTRIBUDDY_LLM_MODEL", cls.llm_model),
            llm_api_key=_get(env, "NUTRIBUDDY_LLM_API_KEY", ""),
            llm_timeout_s=_float(env, "NUTRIBUDDY_LLM_TIMEOUT_S", cls.llm_timeout_s, 1, 600),
            llm_max_attempts=_int(env, "NUTRIBUDDY_LLM_MAX_ATTEMPTS", cls.llm_max_attempts, 1, 5),
            chunk_words=chunk_words,
            chunk_overlap=overlap,
            top_k=_int(env, "NUTRIBUDDY_TOP_K", cls.top_k, 1, 20),
            min_score=_float(env, "NUTRIBUDDY_MIN_SCORE", cls.min_score, 0.0, 1.0),
            max_input_chars=_int(env, "NUTRIBUDDY_MAX_INPUT_CHARS", cls.max_input_chars, 20, 5000),
            max_history_turns=_int(env, "NUTRIBUDDY_MAX_HISTORY_TURNS", cls.max_history_turns, 0, 50),
            foods_per_nutrient=_int(env, "NUTRIBUDDY_FOODS_PER_NUTRIENT", cls.foods_per_nutrient, 1, 10),
        )
