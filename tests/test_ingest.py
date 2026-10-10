from app.ingest.chunk import chunk_pages, is_heading
from app.ingest.parse import Page, parse, text_page_count

from .conftest import CSSS_TEXT, make_pdf, make_scanned_pdf


def test_parse_pdf_pages_and_text():
    pages = parse(make_pdf(CSSS_TEXT))
    assert [p.number for p in pages] == [1, 2]
    assert "80th percentile" in pages[1].text
    assert text_page_count(pages) == 2


def test_scanned_pdf_has_no_text_layer():
    pages = parse(make_scanned_pdf(3))
    assert len(pages) == 3 and text_page_count(pages) == 0


def test_parse_html():
    pages = parse(b"<!doctype html><html><body><script>x()</script><h1>Scheme</h1><p>Income up to Rs 2.5 lakh</p></body></html>")
    assert "Income up to Rs 2.5 lakh" in pages[0].text and "x()" not in pages[0].text


def test_heading_detection():
    assert is_heading("4. Eligibility")
    assert is_heading("5.3 Income ceiling")
    assert is_heading("ELIGIBILITY CRITERIA")
    assert is_heading("IV. Benefits")
    assert not is_heading("12,000")
    assert not is_heading("students who are above 80th percentile of successful candidates in the relevant stream,")


def test_chunks_keep_sections_and_pages():
    pages = parse(make_pdf(CSSS_TEXT))
    chunks = chunk_pages(pages, target=400, overlap=80)
    assert len(chunks) >= 2
    elig = [c for c in chunks if "80th percentile" in c.text]
    assert elig and elig[0].section.startswith("4. Eligibility") and elig[0].page_start == 2
    assert all(c.page_start <= c.page_end for c in chunks)
    assert all(len(c.text) <= 400 + 200 for c in chunks)


def test_long_document_chunking_covers_all_text():
    body = "\n".join(f"{i}. Clause heading {i}\n" + ("Students must satisfy condition number %d. " % i) * 12 for i in range(1, 15))
    pages = [Page(1, body)]
    chunks = chunk_pages(pages)
    joined = " ".join(c.text for c in chunks)
    for i in range(1, 15):
        assert f"condition number {i}." in joined
