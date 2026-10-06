"""The source registry and the document loader.

Every document must have an entry in ``sources.json`` with its URL, its licence, its condition
and its kind. The loader refuses a document that has no entry, so each answer can name its source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .conditions import Condition
from .text import clean_text

Kind = Literal["disease", "diet_plan"]
SUPPORTED_SUFFIXES = (".md", ".txt", ".pdf")


class SourceError(ValueError):
    """The source registry or a document is not valid."""


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    title: str = Field(min_length=3, max_length=300)
    url: str = Field(min_length=4)
    licence: str = Field(min_length=2, max_length=120)
    condition: Condition
    kind: Kind
    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        p = Path(value)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("path must be relative to the data folder and must not contain '..'")
        if p.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"path must end with one of {SUPPORTED_SUFFIXES}")
        return value


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[Source] = Field(min_length=1)


@dataclass(frozen=True)
class Page:
    source: Source
    page: int
    text: str


def load_registry(data_dir: Path) -> list[Source]:
    path = Path(data_dir) / "sources.json"
    if not path.exists():
        raise SourceError(f"{path} not found. Run 'nutribuddy synth' or write the registry (see data/README.md).")
    try:
        registry = Registry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise SourceError(f"{path} is not a valid source registry: {exc}") from exc
    ids = [s.id for s in registry.sources]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise SourceError(f"duplicate source ids in {path}: {duplicates}")
    return registry.sources


def _read_pdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader  # optional extra: pip install "nutribuddy[pdf]"
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        raise SourceError(f"{path} is a PDF. Install the extra: pip install 'nutribuddy[pdf]'") from exc
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def read_pages(source: Source, data_dir: Path) -> list[Page]:
    """Return the pages of one document. A form feed character separates pages in text files."""
    path = Path(data_dir) / source.path
    if not path.exists():
        raise SourceError(f"source {source.id!r}: file {path} not found")
    if path.suffix.lower() == ".pdf":
        raw_pages = _read_pdf(path)
    else:
        raw_pages = path.read_text(encoding="utf-8").split("\f")
    pages = [Page(source, n, clean_text(t)) for n, t in enumerate(raw_pages, start=1)]
    return [p for p in pages if p.text]


def load_documents(data_dir: Path) -> list[Page]:
    """Load every registered document. Warn about files on disk that have no registry entry."""
    data_dir = Path(data_dir)
    sources = load_registry(data_dir)
    pages: list[Page] = []
    for source in sources:
        pages.extend(read_pages(source, data_dir))
    return pages


def unregistered_files(data_dir: Path) -> list[Path]:
    data_dir = Path(data_dir)
    known = {(data_dir / s.path).resolve() for s in load_registry(data_dir)}
    found = []
    for kind in ("disease", "diet_plan"):
        root = data_dir / kind
        if root.exists():
            for p in root.rglob("*"):
                if p.suffix.lower() in SUPPORTED_SUFFIXES and p.resolve() not in known:
                    found.append(p)
    return sorted(found)


_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split page text at Markdown headings. Return (section title, body) pairs."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            sections.append((m.group(1).strip(), []))
        else:
            sections[-1][1].append(line)
    out = []
    for title, lines in sections:
        body = " ".join(line.strip() for line in lines if line.strip())
        if body:
            out.append((title, body))
    return out
