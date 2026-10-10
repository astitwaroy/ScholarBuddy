"""
Section-aware chunking.

Government guidelines are organised as numbered clauses ("4. Eligibility", "5.3", "(iv)").
We keep the most recent heading with each passage so answers can cite "Section 4" and so the
heading words help keyword search. Passages are ~1,100 characters with a small overlap, never
cross documents, and remember the page range they came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import Page

TARGET = 1100
OVERLAP = 180
MIN_CHUNK = 120

HEADING = re.compile(
    r"""^(
        (\d{1,2}(\.\d{1,2}){0,3}[.)]?\s+[A-Z(][^\n]{2,80})     # 4. Eligibility / 5.3 Income
      | ([IVX]{1,5}[.)]\s+[A-Z][^\n]{2,80})                    # IV. Benefits
      | ([A-Z][A-Z &/,'()-]{4,70})                             # ELIGIBILITY CRITERIA
      | ((Section|Clause|Para(graph)?|Annexure|Chapter)\s+[\dIVXA-Z]+[^\n]{0,70})
    )$""",
    re.X,
)


@dataclass
class Chunk:
    ord: int
    page_start: int
    page_end: int
    section: str
    text: str


def is_heading(line: str) -> bool:
    line = line.strip()
    if len(line) < 4 or len(line) > 90 or line.endswith((",", ";")):
        return False
    if re.fullmatch(r"[\d\s.,/-]+", line):  # page numbers, dates, table cells
        return False
    return bool(HEADING.match(line))


def _units(pages: list[Page]) -> list[tuple[int, str, str]]:
    """(page, current_section, line) for every non-empty line."""
    out: list[tuple[int, str, str]] = []
    section = ""
    for p in pages:
        for line in p.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if is_heading(line):
                section = line[:90]
            out.append((p.number, section, line))
    return out


def chunk_pages(pages: list[Page], target: int = TARGET, overlap: int = OVERLAP) -> list[Chunk]:
    units = _units(pages)
    chunks: list[Chunk] = []
    buf: list[tuple[int, str, str]] = []
    size = 0

    def flush():
        nonlocal buf, size
        text = " ".join(u[2] for u in buf).strip()
        if len(text) >= MIN_CHUNK or (text and not chunks):
            chunks.append(Chunk(len(chunks), buf[0][0], buf[-1][0], _main_section(buf), text))
        # keep a tail of the previous passage for context continuity
        tail, tsize = [], 0
        for u in reversed(buf):
            if tsize + len(u[2]) > overlap:
                break
            tail.insert(0, u)
            tsize += len(u[2]) + 1
        buf, size = tail, tsize

    for u in units:
        # every heading starts a fresh passage, unless the current one is only a title or a few words
        if buf and u[1] != buf[-1][1] and is_heading(u[2]) and size >= MIN_CHUNK:
            flush()
            buf, size = [], 0
        buf.append(u)
        size += len(u[2]) + 1
        if size >= target:
            flush()
    if buf and (not chunks or " ".join(x[2] for x in buf) not in chunks[-1].text):
        text = " ".join(x[2] for x in buf).strip()
        section = _main_section(buf)
        if len(text) >= MIN_CHUNK or not chunks or (section != chunks[-1].section and len(text) >= 40):
            chunks.append(Chunk(len(chunks), buf[0][0], buf[-1][0], section, text))
        else:  # a short tail: attach it to the previous passage rather than lose it
            prev = chunks[-1]
            new = " ".join(u[2] for u in buf if u[2] not in prev.text).strip()
            if new:
                prev.text = f"{prev.text} {new}"
            prev.page_end = max(prev.page_end, buf[-1][0])
    return chunks


def _main_section(buf: list[tuple[int, str, str]]) -> str:
    """The heading most of the passage's text sits under."""
    weight: dict[str, int] = {}
    for _, sec, line in buf:
        weight[sec] = weight.get(sec, 0) + len(line)
    return max(weight, key=lambda k: weight[k]) if weight else ""
