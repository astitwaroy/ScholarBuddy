"""
Ingestion: download each official document, extract text, chunk, embed, store.

    python -m app.cli ingest           # new or failed documents
    python -m app.cli ingest --force   # everything again

Documents can also be supplied by hand: put the file at data/raw/<doc_id>.pdf and it is used
instead of downloading (useful for sites that block servers, or scanned PDFs you OCR yourself).
"""

from __future__ import annotations

import hashlib
import logging
import time
import ssl
from dataclasses import dataclass, field

import httpx
from pgvector import Vector

from ..catalog import documents
from ..config import settings
from ..db import pool
from ..llm import Embedder, get_embedder
from .chunk import chunk_pages
from .parse import parse, text_page_count

log = logging.getLogger(__name__)
UA = "Mozilla/5.0 (compatible; ScholarSathi/1.0; +https://github.com) document fetcher"


@dataclass
class IngestReport:
    ok: list[str] = field(default_factory=list)
    no_text: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    chunks: int = 0
    embedded: int = 0

    def summary(self) -> str:
        return (f"ok={len(self.ok)} scanned/no-text={len(self.no_text)} failed={len(self.failed)} "
                f"skipped={len(self.skipped)} chunks={self.chunks} embedded={self.embedded}")


def fetch(doc: dict) -> bytes:
    local = settings().data_dir / "raw" / f"{doc['id']}.pdf"
    if local.exists():
        return local.read_bytes()
    headers = {"User-Agent": UA, "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.5"}
    try:
        r = httpx.get(doc["url"], headers=headers, follow_redirects=True, timeout=60)
    except httpx.ConnectError as e:
        # Several government sites serve incomplete certificate chains. These are public
        # documents we only read, so retry without verification and say so in the logs.
        if isinstance(e.__cause__, ssl.SSLError) or "CERTIFICATE" in str(e).upper():
            log.warning("TLS verification failed for %s; retrying without verification", doc["url"])
            r = httpx.get(doc["url"], headers=headers, follow_redirects=True, timeout=60, verify=False)
        else:
            raise
    r.raise_for_status()
    return r.content


def _upsert_document(conn, doc: dict) -> None:
    conn.execute(
        """INSERT INTO documents (id, title, url, version, scheme_ids, kind)
           VALUES (%(id)s, %(title)s, %(url)s, %(version)s, %(scheme_ids)s, %(kind)s)
           ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, url = EXCLUDED.url,
             version = EXCLUDED.version, scheme_ids = EXCLUDED.scheme_ids, kind = EXCLUDED.kind""",
        doc,
    )


def sync_documents() -> None:
    """Make the documents table match the catalog (new docs become 'pending'; changed URLs re-ingest)."""
    with pool().connection() as conn:
        existing = {r["id"]: r for r in conn.execute("SELECT id, url FROM documents").fetchall()}
        for d in documents():
            _upsert_document(conn, d)
            if d["id"] in existing and existing[d["id"]]["url"] != d["url"]:
                conn.execute("UPDATE documents SET status = 'pending' WHERE id = %s", (d["id"],))
        ids = [d["id"] for d in documents()]
        conn.execute("DELETE FROM documents WHERE NOT (id = ANY(%s))", (ids,))


def ingest_document(doc: dict, embedder: Embedder | None, report: IngestReport, data: bytes | None = None) -> None:
    try:
        data = data if data is not None else fetch(doc)
        if doc["url"].lower().split("?")[0].endswith(".pdf") and data[:5] != b"%PDF-":
            raise ValueError("expected a PDF but the site returned something else (blocked or moved?)")
        pages = parse(data)
    except Exception as e:  # network, HTTP or parse errors are recorded, not fatal
        report.failed[doc["id"]] = str(e)[:300]
        with pool().connection() as conn:
            conn.execute("UPDATE documents SET status = 'failed', error = %s WHERE id = %s", (str(e)[:500], doc["id"]))
        log.warning("failed %s: %s", doc["id"], e)
        return

    text_pages = text_page_count(pages)
    sha = hashlib.sha256(data).hexdigest()
    if text_pages == 0 or text_pages < 0.4 * len(pages):
        report.no_text.append(doc["id"])
        with pool().connection() as conn:
            conn.execute(
                """UPDATE documents SET status = 'no_text', pages = %s, text_pages = %s, sha256 = %s,
                   error = 'Scanned image without a text layer: OCR it and place it in data/raw/', ingested_at = now()
                   WHERE id = %s""",
                (len(pages), text_pages, sha, doc["id"]),
            )
        return

    chunks = chunk_pages(pages)
    vectors: list[list[float]] | list[None] = [None] * len(chunks)
    if embedder and chunks:
        try:
            vectors = embedder.embed([f"{c.section}\n{c.text}" for c in chunks])
            report.embedded += len(chunks)
        except Exception as e:
            log.warning("embedding failed for %s (%s); storing without vectors", doc["id"], e)

    with pool().connection() as conn, conn.transaction():
        conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc["id"],))
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunks (doc_id, scheme_ids, ord, page_start, page_end, section, text, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [(doc["id"], doc["scheme_ids"], c.ord, c.page_start, c.page_end, c.section, c.text,
                  Vector(v) if v is not None else None)
                 for c, v in zip(chunks, vectors)],
            )
        conn.execute(
            """UPDATE documents SET status = 'ok', error = NULL, pages = %s, text_pages = %s, sha256 = %s,
               ingested_at = now() WHERE id = %s""",
            (len(pages), text_pages, sha, doc["id"]),
        )
    report.ok.append(doc["id"])
    report.chunks += len(chunks)
    log.info("ingested %s: %d pages, %d chunks", doc["id"], len(pages), len(chunks))


def ingest_all(force: bool = False, embedder: Embedder | None = None, only: list[str] | None = None) -> IngestReport:
    sync_documents()
    embedder = embedder if embedder is not None else get_embedder()
    report = IngestReport()
    with pool().connection() as conn:
        status = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM documents").fetchall()}
    for doc in documents():
        if only and doc["id"] not in only:
            continue
        if not force and status.get(doc["id"]) in ("ok", "no_text"):
            report.skipped.append(doc["id"])
            continue
        ingest_document(doc, embedder, report)
    if embedder:
        report.embedded += embed_missing(embedder)
    log.info("ingest finished: %s", report.summary())
    return report


def embed_missing(embedder: Embedder, batch: int = 50, max_failures: int = 15, pause: float = 65) -> int:
    """Add vectors to passages stored without one (no API key yet, or the free-tier
    per-minute quota ran out mid-ingest). Waits out quota errors instead of giving up."""
    total, failures = 0, 0
    while True:
        with pool().connection() as conn:
            rows = conn.execute(
                "SELECT id, section, text FROM chunks WHERE embedding IS NULL ORDER BY id LIMIT %s", (batch,)
            ).fetchall()
        if not rows:
            return total
        try:
            vecs = embedder.embed([f"{r['section']}\n{r['text']}" for r in rows])
            failures = 0
        except Exception as e:
            failures += 1
            if failures >= max_failures:
                log.warning("could not embed stored passages, giving up for now: %s", e)
                return total
            log.warning("embedding paused (%s); retrying in %.0fs (%d left to embed)", e, pause, len(rows))
            time.sleep(pause)
            continue
        with pool().connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.executemany("UPDATE chunks SET embedding = %s WHERE id = %s",
                                [(Vector(v), r["id"]) for v, r in zip(vecs, rows)])
        total += len(rows)
