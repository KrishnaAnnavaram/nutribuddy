"""Hybrid search index: BM25 plus dense vectors, reciprocal-rank fusion, then a reranker.

The index lives in one folder: ``chunks.json``, ``vectors.npy`` and ``manifest.json``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from .chunker import Chunk
from .embeddings import Embedder
from .text import tokenize

INDEX_FORMAT = 1
RRF_K = 60


class IndexNotReady(RuntimeError):
    """The index is missing, stale or built with another embedder."""


@dataclass
class Hit:
    chunk: Chunk
    dense: float
    lexical: float
    fused: float
    score: float = 0.0


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


class NoReranker:
    name = "none"

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        for h in hits:
            h.score = h.fused
        return hits


class CoverageReranker:
    """Second stage: share of the query tokens that the chunk contains, then the fused score."""

    name = "coverage"

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        q = set(tokenize(query))
        for h in hits:
            c = set(tokenize(h.chunk.text))
            coverage = len(q & c) / len(q) if q else 0.0
            h.score = 0.5 * coverage + 0.5 * h.fused
        return sorted(hits, key=lambda h: h.score, reverse=True)


class CrossEncoderReranker:  # pragma: no cover - needs the optional "embeddings" extra
    name = "cross-encoder"

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        if not hits:
            return hits
        scores = self._model.predict([(query, h.chunk.text) for h in hits])
        for h, s in zip(hits, scores):
            h.score = float(s)
        return sorted(hits, key=lambda h: h.score, reverse=True)


def build_reranker(kind: str) -> Reranker:
    if kind == "coverage":
        return CoverageReranker()
    if kind == "none":
        return NoReranker()
    if kind == "cross-encoder":
        return CrossEncoderReranker()
    raise ValueError(f"unknown reranker {kind!r}")


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=np.float64)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df: Counter[str] = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tf))
        for i, tf in enumerate(self.tf):
            s = 0.0
            for t in set(query):
                f = tf.get(t, 0)
                if f:
                    denom = f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1.0))
                    s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            out[i] = s
        return out


def fingerprint(chunks: list[Chunk], embedder_name: str) -> str:
    h = hashlib.sha256(f"format={INDEX_FORMAT};embedder={embedder_name}".encode())
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(c.text.encode())
    return h.hexdigest()


class SearchIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray, embedder: Embedder):
        if len(chunks) != len(vectors):
            raise IndexNotReady("chunk count and vector count differ")
        self.chunks = chunks
        self.vectors = vectors
        self.embedder = embedder
        self.bm25 = BM25([tokenize(c.text) for c in chunks])

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder) -> "SearchIndex":
        if not chunks:
            raise IndexNotReady("no chunks to index")
        return cls(chunks, embedder.embed([c.text for c in chunks]), embedder)

    def save(self, folder: Path) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "chunks.json").write_text(json.dumps([c.to_dict() for c in self.chunks]), encoding="utf-8")
        np.save(folder / "vectors.npy", self.vectors)
        manifest = {
            "format": INDEX_FORMAT,
            "embedder": self.embedder.name,
            "chunks": len(self.chunks),
            "fingerprint": fingerprint(self.chunks, self.embedder.name),
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return folder

    @classmethod
    def load(cls, folder: Path, embedder: Embedder) -> "SearchIndex":
        folder = Path(folder)
        mpath = folder / "manifest.json"
        if not mpath.exists():
            raise IndexNotReady(f"no index in {folder}. Run 'nutribuddy index' first.")
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        if manifest.get("format") != INDEX_FORMAT:
            raise IndexNotReady("index format changed. Run 'nutribuddy index' again.")
        if manifest.get("embedder") != embedder.name:
            raise IndexNotReady(
                f"index was built with {manifest.get('embedder')!r}, not {embedder.name!r}. Run 'nutribuddy index' again."
            )
        chunks = [Chunk(**d) for d in json.loads((folder / "chunks.json").read_text(encoding="utf-8"))]
        vectors = np.load(folder / "vectors.npy")
        if fingerprint(chunks, embedder.name) != manifest.get("fingerprint"):
            raise IndexNotReady("index files do not match the manifest. Run 'nutribuddy index' again.")
        return cls(chunks, vectors, embedder)

    def search(
        self,
        query: str,
        k: int,
        *,
        kind: str | None = None,
        condition: str | None = None,
        min_score: float = 0.0,
        reranker: Reranker | None = None,
    ) -> list[Hit]:
        """Return up to ``k`` hits. A chunk is a candidate only if it shares a token with the query
        and its cosine similarity is at least ``min_score`` (the evidence check)."""
        mask = np.ones(len(self.chunks), dtype=bool)
        if kind:
            mask &= np.array([c.kind == kind for c in self.chunks])
        if condition:
            mask &= np.array([c.condition == condition for c in self.chunks])
        q_tokens = tokenize(query)
        if not q_tokens or not mask.any():
            return []
        dense = self.vectors @ self.embedder.embed([query])[0]
        lexical = self.bm25.scores(q_tokens)
        candidates = np.where(mask & (lexical > 0) & (dense >= min_score))[0]
        if candidates.size == 0:
            return []
        dense_rank = {int(i): r for r, i in enumerate(candidates[np.argsort(-dense[candidates])])}
        lex_rank = {int(i): r for r, i in enumerate(candidates[np.argsort(-lexical[candidates])])}
        hits = []
        for i in candidates:
            i = int(i)
            fused = 1 / (RRF_K + 1 + dense_rank[i]) + 1 / (RRF_K + 1 + lex_rank[i])
            hits.append(Hit(self.chunks[i], float(dense[i]), float(lexical[i]), fused * (RRF_K + 1) / 2))
        hits.sort(key=lambda h: h.fused, reverse=True)
        pool = hits[: max(k * 3, k)]
        pool = (reranker or NoReranker()).rerank(query, pool)
        return pool[:k]
