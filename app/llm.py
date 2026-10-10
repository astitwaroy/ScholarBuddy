"""
Thin clients for embeddings and text generation.

* Gemini (Google AI Studio free tier) for both embeddings and answers.
* Any OpenAI-compatible chat API (e.g. Groq) for answers, if preferred.
* A deterministic fake for tests.
All calls retry on rate limits with backoff.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from typing import Protocol

import httpx

from .config import EMBED_DIM, settings

log = logging.getLogger(__name__)
GEMINI = "https://generativelanguage.googleapis.com/v1beta"


class LLMError(RuntimeError):
    pass


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _post(url: str, *, headers: dict, body: dict, timeout: float = 60, retries: int = 4,
          max_wait: float = 60) -> dict:
    """POST with retries. User-facing calls pass small retries/max_wait so a quota error fails fast."""
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        except httpx.HTTPError as e:
            if attempt == retries:
                raise LLMError(f"network error: {e}") from e
            time.sleep(min(delay, max_wait))
            delay *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            try:
                wait = float(r.headers.get("retry-after") or delay)
            except ValueError:
                wait = delay
            log.warning("model API %s, retrying in %.0fs", r.status_code, min(wait, max_wait))
            time.sleep(min(wait, max_wait))
            delay *= 2
            continue
        if r.status_code >= 400:
            raise LLMError(f"{r.status_code}: {r.text[:300]}")
        return r.json()
    raise LLMError("exhausted retries")


# ------------------------------------------------------------------ embeddings

class Embedder(Protocol):
    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str):
        self.key, self.model = api_key, model

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        out: list[list[float]] = []
        task = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
        # A search query is on the user's clock: one quick retry at most. Ingestion can wait.
        fast = {"retries": 1, "max_wait": 2, "timeout": 15} if query else {}
        for i in range(0, len(texts), 50):
            batch = texts[i:i + 50]
            data = _post(
                f"{GEMINI}/models/{self.model}:batchEmbedContents",
                headers={"x-goog-api-key": self.key},
                body={"requests": [{
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t[:8000]}]},
                    "taskType": task,
                    "outputDimensionality": EMBED_DIM,
                } for t in batch]},
                **fast,
            )
            embs = data.get("embeddings") or []
            if len(embs) != len(batch):
                raise LLMError("embedding response size mismatch")
            # Reduced-dimension Gemini embeddings must be normalised by the caller.
            out.extend(_normalize(e["values"]) for e in embs)
        return out


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder. Used in tests; no network, no key."""

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        vecs = []
        for t in texts:
            v = [0.0] * EMBED_DIM
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                v[h % EMBED_DIM] += 1.0 if (h >> 9) & 1 else -1.0
            vecs.append(_normalize(v))
        return vecs


def get_embedder() -> Embedder | None:
    s = settings()
    if s.gemini_api_key:
        return GeminiEmbedder(s.gemini_api_key, s.embed_model)
    return None


# ------------------------------------------------------------------ generation

class Generator(Protocol):
    name: str

    def generate_json(self, system: str, user: str) -> dict: ...


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LLMError("model did not return JSON")
    return json.loads(m.group(0))


class GeminiGenerator:
    def __init__(self, api_key: str, model: str, fallback: str | None):
        self.key, self.model, self.fallback = api_key, model, fallback
        self.name = model

    def _call(self, model: str, system: str, user: str) -> dict:
        data = _post(
            f"{GEMINI}/models/{model}:generateContent",
            headers={"x-goog-api-key": self.key},
            body={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192},
            },
            retries=1, max_wait=2, timeout=45,
        )
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError(f"no candidates (blocked?): {str(data.get('promptFeedback'))[:200]}")
        parts = cands[0].get("content", {}).get("parts", [])
        return _parse_json("".join(p.get("text", "") for p in parts))

    def generate_json(self, system: str, user: str) -> dict:
        try:
            out = self._call(self.model, system, user)
            self.name = self.model
            return out
        except LLMError as e:
            if not self.fallback:
                raise
            log.warning("primary model failed (%s); trying %s", e, self.fallback)
            out = self._call(self.fallback, system, user)
            self.name = self.fallback
            return out


class OpenAICompatGenerator:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base, self.key, self.model = base_url.rstrip("/"), api_key, model
        self.name = model

    def generate_json(self, system: str, user: str) -> dict:
        data = _post(
            f"{self.base}/chat/completions",
            headers={"Authorization": f"Bearer {self.key}"},
            body={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            retries=1, max_wait=2, timeout=45,
        )
        return _parse_json(data["choices"][0]["message"]["content"])


def get_generator() -> Generator | None:
    s = settings()
    if s.llm_provider == "gemini" and s.gemini_api_key:
        return GeminiGenerator(s.gemini_api_key, s.gemini_model, s.gemini_fallback_model)
    if s.llm_provider == "openai" and s.openai_api_key:
        return OpenAICompatGenerator(s.openai_base_url, s.openai_api_key, s.openai_model)
    return None
