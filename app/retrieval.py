"""
Hybrid retrieval: Postgres full-text search + pgvector similarity, fused with Reciprocal Rank Fusion.

Keyword search catches exact terms people use ("80th percentile", "4.5 lakh", "Pragati");
vector search catches paraphrases ("my dad earns 3 lakh", "I'm a girl doing B.Tech").
RRF combines the two rankings without having to calibrate their scores against each other.
If no embedding key is configured, keyword search alone is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import psycopg
from pgvector import Vector

from .catalog import mentioned_schemes
from .db import pool
from .llm import Embedder, get_embedder

RRF_K = 60
CANDIDATES = 30


@dataclass
class Hit:
    chunk_id: int
    doc_id: str
    doc_title: str
    url: str
    version: str
    scheme_ids: list[str]
    page_start: int
    page_end: int
    section: str
    text: str
    score: float = 0.0
    via: list[str] = field(default_factory=list)

    @property
    def page_label(self) -> str:
        return f"p. {self.page_start}" if self.page_start == self.page_end else f"pp. {self.page_start}–{self.page_end}"


_SELECT = """SELECT c.id, c.doc_id, d.title, d.url, d.version, c.scheme_ids, c.page_start, c.page_end,
                    c.section, c.text
               FROM chunks c JOIN documents d ON d.id = c.doc_id"""


def _row_to_hit(r: dict) -> Hit:
    return Hit(r["id"], r["doc_id"], r["title"], r["url"], r["version"], r["scheme_ids"],
               r["page_start"], r["page_end"], r["section"], r["text"])


def keyword_search(question: str, scheme_ids: list[str] | None, limit: int = CANDIDATES) -> list[Hit]:
    # websearch_to_tsquery ANDs every word; questions read better as OR with ranking.
    sql = f"""{_SELECT}
              CROSS JOIN (SELECT replace(websearch_to_tsquery('english', %(q)s)::text, ' & ', ' | ')::tsquery AS query) q
              WHERE c.tsv @@ q.query {"AND c.scheme_ids && %(s)s" if scheme_ids else ""}
              ORDER BY ts_rank_cd(c.tsv, q.query, 32) DESC LIMIT %(n)s"""
    with pool().connection() as conn:
        try:
            rows = conn.execute(sql, {"q": question, "s": scheme_ids, "n": limit}).fetchall()
        except psycopg.errors.SyntaxError:  # a query made only of stop-words/symbols gives an empty tsquery
            return []
    return [_row_to_hit(r) for r in rows]


def vector_search(qvec: list[float], scheme_ids: list[str] | None, limit: int = CANDIDATES) -> list[Hit]:
    sql = f"""{_SELECT}
              WHERE c.embedding IS NOT NULL {"AND c.scheme_ids && %(s)s" if scheme_ids else ""}
              ORDER BY c.embedding <=> %(v)s LIMIT %(n)s"""
    with pool().connection() as conn:
        rows = conn.execute(sql, {"v": Vector(qvec), "s": scheme_ids, "n": limit}).fetchall()
    return [_row_to_hit(r) for r in rows]


def rrf(*rankings: tuple[str, list[Hit]], k: int = RRF_K) -> list[Hit]:
    fused: dict[int, Hit] = {}
    for name, hits in rankings:
        for rank, h in enumerate(hits):
            cur = fused.setdefault(h.chunk_id, h)
            cur.score += 1.0 / (k + rank + 1)
            if name not in cur.via:
                cur.via.append(name)
    return sorted(fused.values(), key=lambda h: h.score, reverse=True)


def search(question: str, k: int = 6, scheme_ids: list[str] | None = None,
           embedder: Embedder | None = None, use_vectors: bool = True) -> list[Hit]:
    """Top-k passages. If the question names a scheme, search within it first and top up from everything."""
    embedder = embedder if embedder is not None else (get_embedder() if use_vectors else None)
    focus = scheme_ids or mentioned_schemes(question) or None
    qvec = None
    if embedder:
        try:
            qvec = embedder.embed([question], query=True)[0]
        except Exception:
            qvec = None

    def run(filter_ids: list[str] | None) -> list[Hit]:
        rankings = [("keyword", keyword_search(question, filter_ids))]
        if qvec is not None:
            rankings.append(("vector", vector_search(qvec, filter_ids)))
        return rrf(*rankings)

    results = run(focus) if focus else []
    if len(results) < k:
        seen = {h.chunk_id for h in results}
        results += [h for h in run(None) if h.chunk_id not in seen]
    return _diversify(results, k)


def _diversify(hits: list[Hit], k: int, per_doc: int = 3) -> list[Hit]:
    """Avoid filling every slot from one document when others are relevant too."""
    out, counts = [], {}
    for h in hits:
        if counts.get(h.doc_id, 0) >= per_doc:
            continue
        out.append(h)
        counts[h.doc_id] = counts.get(h.doc_id, 0) + 1
        if len(out) == k:
            break
    if len(out) < k:
        out += [h for h in hits if h not in out][: k - len(out)]
    return out
