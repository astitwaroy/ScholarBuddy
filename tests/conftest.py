import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql://dev:dev@localhost:5432/schemes_test")
os.environ["AUTO_INGEST"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

import psycopg  # noqa: E402
import pymupdf  # noqa: E402
import pytest  # noqa: E402


def make_pdf(pages: list[str]) -> bytes:
    """A real PDF with a text layer, one string per page (lines separated by \\n)."""
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        y = 60
        for line in text.split("\n"):
            page.insert_text((50, y), line, fontsize=10)
            y += 14
    data = doc.tobytes()
    doc.close()
    return data


def make_scanned_pdf(n: int = 2) -> bytes:
    """A PDF whose pages are images only (like a scanned government order)."""
    doc = pymupdf.open()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pix.set_rect(pix.irect, (240, 240, 240))
    for _ in range(n):
        page = doc.new_page()
        page.insert_image(page.rect, pixmap=pix)
    data = doc.tobytes()
    doc.close()
    return data


# Test fixtures written in the style of the real guidelines (numbered clauses). They are NOT the
# official texts; they exist only so the pipeline can be tested offline.
CSSS_TEXT = [
    "Central Sector Scheme of Scholarship for College and University Students\n"
    "1. Objective\nTo provide financial assistance to meritorious students from low income families\n"
    "to meet a part of their day-to-day expenses while pursuing higher studies.\n"
    "2. Number of scholarships\nThe scholarships will be divided amongst Science, Humanities and Commerce\n"
    "streams in the ratio of 3:3:1. 50% of scholarships are earmarked for girls.",
    "4. Eligibility\n(i) Students who are above 80th percentile of successful candidates in the relevant stream\n"
    "from the respective Board of Examination in Class XII.\n"
    "(ii) Pursuing regular degree courses and not correspondence or distance mode or pursuing Diploma courses.\n"
    "(iv) Students already receiving other scholarships, including state schemes or fee waiver are not eligible.\n"
    "(v) Students with gross parental/family income upto Rs. 4.5 lakh per annum are eligible.\n"
    "5. Rate of scholarship\nThe rate of scholarship is Rs.12,000 per annum at Graduation level for first three years\n"
    "and Rs.20,000 per annum at Post-Graduation level.",
]
PRAGATI_TEXT = [
    "AICTE Pragati Scholarship Scheme for Girl Students (Technical Degree)\n"
    "2.0 Eligibility\n(1) The girl candidate should be admitted to First year of Degree level course\n"
    "in any of the AICTE approved institution.\n(2) Maximum two girl child per family are eligible.\n"
    "(3) Family income from all sources should not be more than Rs. 8 lakh per annum.\n"
    "4.0 Amount of Scholarship\n(1) Rs. 50,000 per annum for every year of study, maximum 4 years.",
]
NMMSS_TEXT = [
    "National Means-cum-Merit Scholarship Scheme\n1.1 Objective\nScholarships are awarded to meritorious\n"
    "students of economically weaker sections whose parental income is not more than Rs 3,50,000 per annum.\n"
    "1.2 Eligibility\nStudents of Kendriya Vidyalayas and Jawahar Navodaya Vidyalayas and residential schools\n"
    "are not eligible. Students must secure minimum of 55 % marks in Class VII examination.\n"
    "1.3 Amount\nRs 12000 per annum at Rs 1000 per month.",
]


@pytest.fixture(scope="session", autouse=True)
def fresh_db():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    from app.db import close_pool, migrate
    from app.ingest.pipeline import sync_documents

    migrate()
    sync_documents()
    yield
    close_pool()


@pytest.fixture(scope="session")
def indexed(fresh_db):
    """Ingest three fixture documents with the offline hashing embedder."""
    from app.catalog import document_by_id
    from app.ingest.pipeline import IngestReport, ingest_document
    from app.llm import HashEmbedder

    report = IngestReport()
    emb = HashEmbedder()
    for doc_id, pages in [("csss-2024", CSSS_TEXT), ("aicte-pragati-g", PRAGATI_TEXT), ("nmmss-2022", NMMSS_TEXT)]:
        ingest_document(document_by_id()[doc_id], emb, report, data=make_pdf(pages))
    assert report.ok == ["csss-2024", "aicte-pragati-g", "nmmss-2022"], report
    return emb
