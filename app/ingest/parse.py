"""Turn a downloaded file (PDF or HTML) into clean text, page by page."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

import pymupdf


@dataclass
class Page:
    number: int  # 1-based
    text: str


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")  # soft hyphen
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # words hyphenated across lines
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(data: bytes) -> list[Page]:
    pages: list[Page] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            pages.append(Page(i + 1, clean(page.get_text("text", sort=True))))
    return pages


def parse_html(data: bytes) -> list[Page]:
    raw = data.decode("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return [Page(1, clean(text))]


def parse(data: bytes) -> list[Page]:
    if data[:5] == b"%PDF-":
        return parse_pdf(data)
    head = data[:2000].lower()
    if b"<html" in head or b"<!doctype html" in head:
        return parse_html(data)
    raise ValueError("not a PDF or HTML document")


def text_page_count(pages: list[Page], min_chars: int = 40) -> int:
    """Pages with a real text layer. Scanned pages come out (nearly) empty."""
    return sum(1 for p in pages if len(p.text) >= min_chars)
