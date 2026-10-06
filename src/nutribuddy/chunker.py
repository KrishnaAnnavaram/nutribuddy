"""Split pages into overlapping chunks that keep their page and section for citations."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .documents import Page, split_sections


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    title: str
    url: str
    condition: str
    kind: str
    page: int
    section: str
    text: str

    def citation(self) -> str:
        where = f"p. {self.page}"
        if self.section:
            where += f", section '{self.section}'"
        return f"{self.title} ({where}) {self.url}"

    def to_dict(self) -> dict:
        return asdict(self)


def window(words: list[str], size: int, overlap: int) -> list[list[str]]:
    """Sliding windows of ``size`` words. Each window starts ``size - overlap`` words after the last."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("need size > 0 and 0 <= overlap < size")
    if len(words) <= size:
        return [words] if words else []
    step = size - overlap
    out = []
    start = 0
    while start < len(words):
        out.append(words[start : start + size])
        if start + size >= len(words):
            break
        start += step
    return out


def chunk_pages(pages: list[Page], size_words: int, overlap_words: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        src = page.source
        for s_index, (section, body) in enumerate(split_sections(page.text)):
            for w_index, words in enumerate(window(body.split(), size_words, overlap_words)):
                chunks.append(
                    Chunk(
                        chunk_id=f"{src.id}:p{page.page}:s{s_index}:w{w_index}",
                        source_id=src.id,
                        title=src.title,
                        url=src.url,
                        condition=src.condition.value,
                        kind=src.kind,
                        page=page.page,
                        section=section,
                        text=" ".join(words),
                    )
                )
    return chunks
