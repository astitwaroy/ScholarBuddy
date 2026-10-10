"""ScholarSathi API + web app."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import catalog as cat
from .answer import answer
from .config import settings
from .db import close_pool, migrate, pool
from .eligibility import Profile, match_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scholarsathi")
ingest_state = {"running": False, "last": None, "error": None}


def _background_ingest(force: bool = False) -> None:
    from .ingest.pipeline import ingest_all

    if ingest_state["running"]:
        return
    ingest_state["running"] = True
    try:
        ingest_state["last"] = ingest_all(force=force).summary()
        ingest_state["error"] = None
    except Exception as e:  # keep serving; status endpoint reports it
        log.exception("ingest failed")
        ingest_state["error"] = str(e)[:300]
    finally:
        ingest_state["running"] = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    migrate()
    from .ingest.pipeline import sync_documents

    sync_documents()
    if settings().auto_ingest:
        threading.Thread(target=_background_ingest, daemon=True).start()
    yield
    close_pool()


app = FastAPI(title="ScholarSathi", version="1.0", lifespan=lifespan)


# ------------------------------------------------------------------ rate limiting (per IP, in memory)

_hits: dict[str, deque] = defaultdict(deque)
GLOBAL_PER_MINUTE = 60  # protects the shared model quota


def client_ip(request: Request) -> str:
    # Render's proxy appends the real client address as the LAST X-Forwarded-For entry;
    # earlier entries are whatever the client sent and can't be trusted.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "?"


def _take(key: str, limit: int, window: float, now: float) -> bool:
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def rate_limit(request: Request, limit: int, window: float = 60.0) -> None:
    now = time.monotonic()
    if len(_hits) > 5000:  # forget idle clients so memory stays bounded
        for k in [k for k, q in _hits.items() if not q or now - q[-1] > window]:
            del _hits[k]
    if not _take(f"{request.url.path}:{client_ip(request)}", limit, window, now):
        raise HTTPException(429, "Too many questions in a minute. Please wait a little and try again.")
    if not _take(f"{request.url.path}:*", GLOBAL_PER_MINUTE, window, now):
        raise HTTPException(429, "The service is busy right now. Please try again in a minute.")


# ------------------------------------------------------------------ API

@app.get("/api/health")
def health():
    with pool().connection() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


@app.get("/api/catalog")
def get_catalog():
    with pool().connection() as conn:
        docs = conn.execute(
            """SELECT d.id, d.status, d.pages, d.text_pages, d.ingested_at, d.error,
                      count(c.id)::int AS chunks, count(c.embedding)::int AS embedded
                 FROM documents d LEFT JOIN chunks c ON c.doc_id = d.id GROUP BY d.id"""
        ).fetchall()
    status = {d["id"]: d for d in docs}
    return {
        "schemes": [cat.public_scheme(s) for s in cat.schemes()],
        "documents": [{**d, **{k: status.get(d["id"], {}).get(k) for k in
                       ("status", "pages", "text_pages", "chunks", "embedded", "ingested_at", "error")}}
                      for d in cat.documents()],
    }


@app.get("/api/status")
def get_status():
    s = settings()
    with pool().connection() as conn:
        r = conn.execute(
            """SELECT count(*) FILTER (WHERE status = 'ok')::int AS ok,
                      count(*) FILTER (WHERE status = 'no_text')::int AS no_text,
                      count(*) FILTER (WHERE status = 'failed')::int AS failed,
                      count(*) FILTER (WHERE status = 'pending')::int AS pending,
                      (SELECT count(*) FROM chunks)::int AS chunks,
                      (SELECT count(embedding) FROM chunks)::int AS embedded
                 FROM documents"""
        ).fetchone()
    return {"documents": r, "ingesting": ingest_state["running"], "lastIngest": ingest_state["last"],
            "llm": s.llm_enabled, "llmProvider": s.llm_provider if s.llm_enabled else None,
            "embeddings": s.embeddings_enabled}


@app.post("/api/match")
def post_match(profile: Profile):
    return match_all(profile)


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    schemeId: str | None = None
    profile: Profile | None = None


@app.post("/api/ask")
def post_ask(body: AskBody, request: Request):
    rate_limit(request, limit=12)
    if body.schemeId and body.schemeId not in cat.scheme_by_id():
        raise HTTPException(404, "Unknown scheme.")
    return answer(body.question, profile=body.profile, scheme_id=body.schemeId)


def _admin(request: Request) -> None:
    token = settings().admin_token
    if not token or request.headers.get("x-admin-token") != token:
        raise HTTPException(403, "Admin token required.")


@app.post("/api/admin/ingest")
def admin_ingest(request: Request, force: bool = False):
    _admin(request)
    threading.Thread(target=_background_ingest, kwargs={"force": force}, daemon=True).start()
    return {"started": True}


@app.get("/api/admin/eval")
def admin_eval(request: Request, k: int = 6):
    _admin(request)
    from .evaluate import run_retrieval_eval

    return run_retrieval_eval(k=k)


@app.exception_handler(HTTPException)
async def http_error(_req: Request, exc: HTTPException):
    return JSONResponse({"error": {"message": exc.detail}}, status_code=exc.status_code)


# ------------------------------------------------------------------ web app

_dist = settings().web_dist
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _dist / path
        if path and f.is_file() and _dist in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
