"""Embedders behind one small interface. The service builds the embedder once at start."""

from __future__ import annotations

import zlib
from typing import Protocol

import numpy as np

from .text import tokenize


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalized row for each text."""


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class HashingEmbedder:
    """Offline embedder: signed feature hashing of word unigrams and bigrams.

    It needs no model download and gives the same vectors on every machine (crc32, not ``hash``).
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _features(self, text: str) -> list[tuple[str, float]]:
        toks = tokenize(text)
        feats = [(t, 1.0) for t in toks]
        feats += [(f"{a} {b}", 0.5) for a, b in zip(toks, toks[1:])]
        return feats

    def embed(self, texts: list[str]) -> np.ndarray:
        m = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat, weight in self._features(text):
                h = zlib.crc32(feat.encode("utf-8"))
                sign = 1.0 if (h >> 31) & 1 else -1.0
                m[row, h % self.dim] += sign * weight
        return _normalize(m)


class SentenceTransformerEmbedder:  # pragma: no cover - needs the optional "embeddings" extra
    """Dense embedder from sentence-transformers. The import is lazy, so the core package works without it."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError("install the extra: pip install 'nutribuddy[embeddings]'") from exc
        self._model = SentenceTransformer(model_name)
        self.name = f"st:{model_name}"
        self.max_tokens = int(getattr(self._model, "max_seq_length", 512))

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


def build_embedder(kind: str, model_name: str) -> Embedder:
    if kind == "hashing":
        return HashingEmbedder()
    if kind == "sentence-transformers":
        return SentenceTransformerEmbedder(model_name)
    raise ValueError(f"unknown embedder {kind!r}")
