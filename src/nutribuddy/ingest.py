"""Ingestion: registry -> pages -> chunks -> index, and FoodData Central CSV -> food store."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .chunker import chunk_pages
from .config import Settings
from .documents import load_documents, unregistered_files
from .embeddings import Embedder, build_embedder
from .fooddb import LoadReport, connect, load_fdc
from .index import SearchIndex

log = logging.getLogger(__name__)


@dataclass
class IndexReport:
    sources: int
    pages: int
    chunks: int
    embedder: str
    folder: Path
    unregistered: list[Path]


def build_index(settings: Settings, embedder: Embedder | None = None) -> IndexReport:
    embedder = embedder or build_embedder(settings.embedder, settings.embed_model)
    pages = load_documents(settings.data_dir)
    chunks = chunk_pages(pages, settings.chunk_words, settings.chunk_overlap)
    index = SearchIndex.build(chunks, embedder)
    folder = index.save(settings.index_dir)
    extra = unregistered_files(settings.data_dir)
    for p in extra:
        log.warning("file %s has no entry in sources.json and is not indexed", p)
    return IndexReport(len({p.source.id for p in pages}), len(pages), len(chunks), embedder.name, folder, extra)


def load_food_folders(settings: Settings, fdc_dir: Path) -> LoadReport:
    """Load one release folder, or every sub-folder that has a nutrient.csv file."""
    fdc_dir = Path(fdc_dir)
    folders = [fdc_dir] if (fdc_dir / "nutrient.csv").exists() else sorted(p.parent for p in fdc_dir.rglob("nutrient.csv"))
    if not folders:
        raise FileNotFoundError(f"no nutrient.csv under {fdc_dir}")
    conn = connect(settings.food_db)
    total = LoadReport()
    for folder in folders:
        rep = load_fdc(conn, folder)
        total.nutrients += rep.nutrients
        total.foods += rep.foods
        total.amounts += rep.amounts
        total.skipped_rows += rep.skipped_rows
    conn.close()
    return total
