"""
Grounded answers with citations.

The model only sees the retrieved passages (numbered S1..Sn) plus a short status list of schemes,
and must cite a source for every claim and quote the exact words it relied on. We then check
those quotes against the passages: a citation whose quote isn't actually in its source is dropped,
and an answer left with no supported citation is flagged. Without a model configured we fall back
to an extractive answer built from the most relevant sentences.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from .catalog import mentioned_schemes, scheme_by_id
from .eligibility import Profile
from .llm import Generator, LLMError, get_generator
from .retrieval import Hit, search

SYSTEM = """You help students in India understand government scholarship schemes.
Answer ONLY from the numbered SOURCES (official guideline text) and the SCHEME STATUS list.
Rules:
- Every factual sentence must end with citations like [S1] or [S2][S4] pointing to the sources that support it.
- Use exact figures from the sources (income limits, amounts, percentages, ages). Never invent or round them.
- If the sources do not answer the question, set "found" to false and say briefly what is missing; do not guess.
- If a scheme is listed as discontinued or paused in SCHEME STATUS, say so clearly.
- If the student's profile is given, apply the rules to it and say which conditions they meet, fail or need to check.
- Be concise: at most about 150 words, plain language, short paragraphs or a short list. No headings.
- Remind the student to confirm on the official portal only when deadlines or amounts may have changed.
Return JSON: {"answer": "<markdown with [S#] citations>", "found": true|false,
"quotes": [{"source": "S1", "text": "<exact words copied from that source, 5-30 words>"}]}
Give one quote for each source you cite."""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9₹%.]+", " ", s.lower()).strip()


def quote_supported(quote: str, source_text: str) -> bool:
    """True if the quote really appears in the source (tolerant of spacing, punctuation and case)."""
    q, src = _norm(quote), _norm(source_text)
    if len(q) < 8:
        return False
    if q in src:
        return True
    # Tolerate small extraction differences (spacing, line breaks, a dropped word), but every
    # number in the quote must appear in the source: "8 lakh" must not pass for "4.5 lakh".
    qw = q.split()
    sw = set(src.split())
    nums = [w for w in qw if any(ch.isdigit() for ch in w)]
    if any(n.strip(".") not in {x.strip(".") for x in sw} for n in nums):
        return False
    return len(qw) >= 5 and sum(w in sw for w in qw) / len(qw) >= 0.85


def profile_summary(p: Profile | None) -> str:
    if not p:
        return ""
    labels = {
        "state": "State/UT", "category": "Category", "gender": "Gender", "disability_pct": "Disability %",
        "income": "Annual family income (₹)", "level": "Studying at", "course_type": "Course type",
        "study_mode": "Mode", "class12_percentile": "Class 12 percentile", "qualifying_marks_pct": "Qualifying exam %",
        "school_type": "School type", "top_institution": "At an IIT/IIM/NIT/AIIMS-type notified institute",
        "studying_abroad": "Studying abroad", "other_scholarship": "Already has another scholarship", "age": "Age",
    }
    parts = [f"{lbl}: {getattr(p, k)}" for k, lbl in labels.items() if getattr(p, k) is not None]
    if p.flags:
        parts.append("Special situation: " + ", ".join(p.flags))
    return "; ".join(parts)


def _status_lines(hits: list[Hit], extra_ids: list[str]) -> str:
    ids = list(dict.fromkeys([sid for h in hits for sid in h.scheme_ids] + extra_ids))
    lines = []
    for sid in ids:
        s = scheme_by_id().get(sid)
        if s:
            note = f" ({s['status_note']})" if s.get("status_note") else ""
            lines.append(f"- {s['short']}: {s['status'].upper()}{note}")
    return "\n".join(lines)


def build_prompt(question: str, hits: list[Hit], profile: Profile | None, extra_ids: list[str]) -> str:
    src = "\n\n".join(
        f"[S{i + 1}] {h.doc_title} — {h.section or 'section not detected'}, {h.page_label}\n{h.text}"
        for i, h in enumerate(hits)
    )
    prof = profile_summary(profile)
    return (f"SCHEME STATUS:\n{_status_lines(hits, extra_ids) or '- (none)'}\n\n"
            f"SOURCES:\n{src}\n\n"
            + (f"STUDENT PROFILE: {prof}\n\n" if prof else "")
            + f"QUESTION: {question}")


def _citation(i: int, h: Hit, quote: str | None) -> dict[str, Any]:
    return {
        "n": i + 1, "docId": h.doc_id, "title": h.doc_title, "url": h.url, "version": h.version,
        "page": h.page_start, "pageLabel": h.page_label, "section": h.section,
        "schemeIds": h.scheme_ids, "quote": quote, "excerpt": h.text[:600],
    }


_ABBR = r"(?<!\bRs)(?<!\bNo)(?<!\bDr)(?<!\bSr)(?<!\bviz)(?<!\bi\.e)(?<!\be\.g)"


def _sentences(text: str) -> list[str]:
    """Split guideline text into sentences/clauses without breaking at 'Rs.' or clause numbers."""
    parts = re.split(_ABBR + r"(?<=[.;])\s+(?=[A-Z(])|\s(?=\([ivx]{1,4}\)|\(\d{1,2}\)\s)", text)
    return [s.strip() for s in parts if 25 <= len(s.strip()) <= 400]


_HOW_MUCH = re.compile(r"how much|amount|money|limit|ceiling|income|percent|marks|age|rs|₹|lakh", re.I)


def _sentence_score(sentence: str, qwords: set[str], wants_number: bool) -> float:
    words = set(_norm(sentence).split())
    score = len(qwords & words)
    if wants_number:
        score += 2 if re.search(r"(rs\.?|₹)\s*[\d,]+|\d+\s*(%|lakh|per)", sentence, re.I) else -1
    if is_heading_like(sentence):
        score -= 2
    return score


def is_heading_like(s: str) -> bool:
    return len(s) < 60 and not re.search(r"[.;]$", s)


def extractive_answer(question: str, hits: list[Hit]) -> dict[str, Any]:
    """No model available: show the most relevant sentences, each cited."""
    qwords = {w for w in _norm(question).split() if len(w) > 2} - {"the", "and", "for", "what", "how", "can", "does", "scheme", "scholarship"}
    wants_number = bool(_HOW_MUCH.search(question))
    focus = set(mentioned_schemes(question))
    candidates = [(i, h) for i, h in enumerate(hits[:5]) if not focus or focus & set(h.scheme_ids)] or list(enumerate(hits[:4]))
    picked = []
    for i, h in candidates:
        sents = sorted(_sentences(h.text), key=lambda s: -_sentence_score(s, qwords, wants_number))
        if sents and _sentence_score(sents[0], qwords, wants_number) >= 1.5:
            picked.append((i, sents[0]))
        if len(picked) == 3:
            break
    if not picked:
        return {"answer": "I couldn't find this in the official documents I have.", "found": False,
                "citations": [_citation(i, h, None) for i, h in enumerate(hits[:3])], "mode": "extractive"}
    body = "\n".join(f"- {s} [S{i + 1}]" for i, s in picked)
    return {"answer": "From the official guidelines:\n" + body, "found": True,
            "citations": [_citation(i, hits[i], s) for i, s in picked],
            "mode": "extractive"}


def answer(question: str, profile: Profile | None = None, scheme_id: str | None = None,
           generator: Generator | None = None, k: int = 6, **search_kw) -> dict[str, Any]:
    question = question.strip()
    hits = search(question, k=k, scheme_ids=[scheme_id] if scheme_id else None, **search_kw)
    extra = [scheme_id] if scheme_id else []
    if not hits:
        return {"answer": "The official documents aren't indexed yet, or nothing matched your question. "
                          "Try naming the scheme, or ask again in a minute.",
                "found": False, "citations": [], "mode": "none", "retrieval": []}

    gen = generator if generator is not None else get_generator()
    retrieval = [{"n": i + 1, "docId": h.doc_id, "page": h.page_start, "score": round(h.score, 4), "via": h.via}
                 for i, h in enumerate(hits)]
    if gen is None:
        out = extractive_answer(question, hits)
        out["retrieval"] = retrieval
        return out

    try:
        raw = gen.generate_json(SYSTEM, build_prompt(question, hits, profile, extra))
    except (LLMError, ValueError) as e:
        out = extractive_answer(question, hits)
        out.update(retrieval=retrieval, warning=f"The language model was unavailable ({str(e)[:120]}); showing the source passages instead.")
        return out

    if not isinstance(raw, dict) or not isinstance(raw.get("answer"), str) or not raw["answer"].strip():
        out = extractive_answer(question, hits)
        out.update(retrieval=retrieval, warning="The AI answer was malformed; showing the source passages instead.")
        return out
    text = raw["answer"].strip()
    f = raw.get("found", True)
    found = not (f is False or (isinstance(f, str) and f.strip().lower() in ("false", "no", "0")))
    quotes: dict[int, str] = {}
    rejected = 0
    raw_quotes = raw.get("quotes") if isinstance(raw.get("quotes"), list) else []
    for q in raw_quotes:
        if not isinstance(q, dict):
            rejected += 1
            continue
        m = re.fullmatch(r"S(\d+)", str(q.get("source", "")).strip())
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= len(hits) and quote_supported(str(q.get("text", "")), hits[n - 1].text):
            quotes.setdefault(n, str(q["text"]).strip())
        else:
            rejected += 1

    cited = sorted({int(n) for n in re.findall(r"\[S(\d+)\]", text) if 1 <= int(n) <= len(hits)})
    # drop markers that point at sources that don't exist
    text = re.sub(r"\[S(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(hits) else "", text)
    supported = [n for n in cited if n in quotes]
    out: dict[str, Any] = {
        "answer": text, "found": found, "mode": "llm", "model": getattr(gen, "name", "model"),
        "citations": [_citation(n - 1, hits[n - 1], quotes.get(n)) for n in cited]
                     or [_citation(i, h, None) for i, h in enumerate(hits[:3])],
        "grounding": {"cited": len(cited), "verified": len(supported), "rejectedQuotes": rejected},
        "retrieval": retrieval,
    }
    if found and cited and not supported:
        out["warning"] = "I couldn't match this answer's quotes to the documents. Please check the cited sources."
    elif found and not cited:
        out["warning"] = "This answer has no citations. Treat it with care and check the official guidelines."
    return out


def hit_dict(h: Hit) -> dict[str, Any]:
    return asdict(h)
