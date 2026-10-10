"""
Retrieval and answer evaluation against eval/questions.jsonl.

Retrieval metrics (no model needed):
  scheme hit@1 / hit@3 / hit@k  – a passage from an expected scheme's documents is in the top results
  term recall@k                 – one of the expected key phrases (e.g. "4.5 lakh") appears in the top results
  MRR                           – mean reciprocal rank of the first passage from an expected scheme
Answer metrics (needs a model; --answers):
  found rate, citation rate, verified-quote rate (quotes that really occur in the cited passage)

Questions whose schemes have no ingested text are reported separately instead of counting as misses.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .answer import answer
from .config import ROOT
from .db import pool
from .llm import Embedder
from .retrieval import search

QUESTIONS = ROOT / "eval" / "questions.jsonl"


def load_questions(path: Path = QUESTIONS) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _indexed_schemes() -> set[str]:
    with pool().connection() as conn:
        rows = conn.execute("SELECT DISTINCT unnest(scheme_ids) AS s FROM chunks").fetchall()
    return {r["s"] for r in rows}


def run_retrieval_eval(k: int = 6, embedder: Embedder | None = None, use_vectors: bool = True,
                       questions: list[dict] | None = None) -> dict[str, Any]:
    qs = questions or load_questions()
    indexed = _indexed_schemes()
    rows, skipped = [], []
    for q in qs:
        if not set(q["schemes"]) & indexed:
            skipped.append(q["q"])
            continue
        t0 = time.perf_counter()
        hits = search(q["q"], k=k, embedder=embedder, use_vectors=use_vectors)
        ms = (time.perf_counter() - t0) * 1000
        ranks = [i for i, h in enumerate(hits) if set(h.scheme_ids) & set(q["schemes"])]
        first = ranks[0] + 1 if ranks else None
        text = " ".join(h.text for h in hits).lower()
        term = any(t.lower() in text for t in q.get("terms", [])) if q.get("terms") else None
        rows.append({"q": q["q"], "first_rank": first, "term_hit": term, "ms": round(ms, 1),
                     "top": [h.doc_id for h in hits[:3]]})
    n = len(rows) or 1

    def rate(pred) -> float:
        return round(sum(1 for r in rows if pred(r)) / n, 3)

    term_rows = [r for r in rows if r["term_hit"] is not None]
    return {
        "questions": len(rows), "skipped_not_indexed": len(skipped), "k": k,
        "hit@1": rate(lambda r: r["first_rank"] == 1),
        "hit@3": rate(lambda r: r["first_rank"] is not None and r["first_rank"] <= 3),
        f"hit@{k}": rate(lambda r: r["first_rank"] is not None),
        "mrr": round(sum(1 / r["first_rank"] for r in rows if r["first_rank"]) / n, 3),
        f"term_recall@{k}": round(sum(1 for r in term_rows if r["term_hit"]) / (len(term_rows) or 1), 3),
        "avg_ms": round(sum(r["ms"] for r in rows) / n, 1),
        "misses": [r for r in rows if r["first_rank"] is None or r["term_hit"] is False],
        "skipped": skipped,
    }


def run_answer_eval(limit: int | None = None, pause: float = 4.0) -> dict[str, Any]:
    qs = load_questions()[:limit] if limit else load_questions()
    indexed = _indexed_schemes()
    results = []
    for q in qs:
        if not set(q["schemes"]) & indexed:
            continue
        out = answer(q["q"])
        g = out.get("grounding", {})
        results.append({"q": q["q"], "found": out["found"], "mode": out["mode"],
                        "cited": g.get("cited", 0), "verified": g.get("verified", 0)})
        time.sleep(pause)  # stay under free-tier rate limits
    n = len(results) or 1
    cited = sum(r["cited"] for r in results)
    return {
        "questions": len(results),
        "found_rate": round(sum(r["found"] for r in results) / n, 3),
        "answers_with_citations": round(sum(1 for r in results if r["cited"]) / n, 3),
        "verified_citation_rate": round(sum(r["verified"] for r in results) / (cited or 1), 3),
        "results": results,
    }
