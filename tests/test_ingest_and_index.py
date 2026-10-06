import json

import pytest

from nutribuddy.chunker import chunk_pages, window
from nutribuddy.documents import Page, Source, SourceError, load_registry, split_sections
from nutribuddy.embeddings import HashingEmbedder
from nutribuddy.index import CoverageReranker, IndexNotReady, SearchIndex


def _source(**kw):
    base = dict(id="s1", title="Test source", url="https://example.org/x", licence="CC0", condition="heart",
                kind="diet_plan", path="diet_plan/heart/x.md")
    base.update(kw)
    return Source(**base)


def test_window_overlap_and_full_coverage():
    words = [f"w{i}" for i in range(25)]
    wins = window(words, 10, 3)
    assert wins[0][-3:] == wins[1][:3]
    assert {w for win in wins for w in win} == set(words)
    with pytest.raises(ValueError):
        window(words, 5, 5)


def test_long_page_is_fully_searchable_not_truncated():
    body = " ".join(f"word{i}" for i in range(1000)) + " magnesiumrare"
    chunks = chunk_pages([Page(_source(), 3, body)], 100, 20)
    assert len(chunks) > 10
    assert any("magnesiumrare" in c.text for c in chunks)
    assert all(c.page == 3 and c.source_id == "s1" for c in chunks)


def test_sections_keep_their_heading_for_citations():
    secs = split_sections("intro text\n# Salt\nless salt\n## Fish\neat fish")
    assert secs == [("", "intro text"), ("Salt", "less salt"), ("Fish", "eat fish")]
    chunks = chunk_pages([Page(_source(), 1, "# Salt\nless salt please")], 50, 5)
    assert "section 'Salt'" in chunks[0].citation()


def test_registry_validation(tmp_path):
    bad = dict(_source().model_dump(), path="../x.md")
    (tmp_path / "sources.json").write_text(json.dumps({"sources": [bad]}))
    with pytest.raises(SourceError):
        load_registry(tmp_path)
    good = _source().model_dump()
    (tmp_path / "sources.json").write_text(json.dumps({"sources": [good, good]}))
    with pytest.raises(SourceError, match="duplicate"):
        load_registry(tmp_path)
    with pytest.raises(SourceError):
        load_registry(tmp_path / "missing")


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder()
    a, b = e.embed(["oily fish twice a week"]), e.embed(["oily fish twice a week"])
    assert (a == b).all()
    assert abs(float((a * a).sum()) - 1.0) < 1e-5


def test_search_filters_and_evidence_check(workspace):
    index = SearchIndex.load(workspace.index_dir, HashingEmbedder())
    hits = index.search("which fish give omega-3 fatty acids", 3, kind="diet_plan", condition="heart",
                        reranker=CoverageReranker())
    assert hits and all(h.chunk.condition == "heart" and h.chunk.kind == "diet_plan" for h in hits)
    assert hits[0].chunk.source_id == "syn-heart-diet"
    assert index.search("quantum chromodynamics lattice", 3) == []


def test_index_load_refuses_other_embedder_and_changed_files(workspace, tmp_path):
    with pytest.raises(IndexNotReady):
        SearchIndex.load(workspace.index_dir, HashingEmbedder(dim=64))
    index = SearchIndex.load(workspace.index_dir, HashingEmbedder())
    folder = index.save(tmp_path / "idx")
    data = json.loads((folder / "chunks.json").read_text())
    data[0]["text"] = "changed"
    (folder / "chunks.json").write_text(json.dumps(data))
    with pytest.raises(IndexNotReady):
        SearchIndex.load(folder, HashingEmbedder())
    with pytest.raises(IndexNotReady):
        SearchIndex.load(tmp_path / "nothing", HashingEmbedder())
