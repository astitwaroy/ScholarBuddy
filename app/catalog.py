"""The curated list of schemes, their eligibility rules and their official source documents."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .config import settings


@lru_cache
def catalog() -> dict[str, Any]:
    return json.loads((settings().data_dir / "catalog.json").read_text(encoding="utf-8"))


def schemes() -> list[dict[str, Any]]:
    return catalog()["schemes"]


def documents() -> list[dict[str, Any]]:
    return catalog()["documents"]


@lru_cache
def scheme_by_id() -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in schemes()}


@lru_cache
def document_by_id() -> dict[str, dict[str, Any]]:
    return {d["id"]: d for d in documents()}


# Names people actually type, mapped to scheme ids. Used to focus retrieval on the scheme asked about.
ALIASES: dict[str, list[str]] = {
    "pm-usp-csss": ["csss", "central sector scheme", "central sector scholarship", "pm-usp", "pm usp"],
    "pms-sc": ["post matric sc", "post-matric sc", "sc post matric", "sc post-matric", "sc student", "sc students",
               "for sc", "scheduled caste", "pms-sc", "pms sc"],
    "pm-yasasvi-pms-obc-ebc-dnt": ["yasasvi post", "obc post matric", "post-matric obc", "post matric obc", "obc post-matric", "ebc", "dnt"],
    "pm-yasasvi-top-class-school": ["top class school", "yasasvi school"],
    "pm-yasasvi-top-class-college": ["top class college", "yasasvi college"],
    "top-class-education-sc": ["top class education for sc", "top class sc", "tces"],
    "nmmss": ["nmmss", "nmms", "means-cum-merit", "means cum merit"],
    "aicte-pragati": ["pragati"],
    "aicte-saksham": ["saksham"],
    "aicte-swanath": ["swanath", "covid", "orphan"],
    "pmss-mha-capf-ar-state-police": ["capf", "assam rifles", "pmss mha", "central armed police", "state police"],
    "pmss-ksb-ex-servicemen": ["ksb", "kendriya sainik", "ex-servicemen", "ex servicemen", "ex-serviceman"],
    "ugc-ishan-uday": ["ishan uday", "ishan", "north east", "north-east", "northeast"],
    "ugc-nspg": ["nspg", "single girl child", "indira gandhi", "post graduate studies", "postgraduate scholarship"],
    "nos-sc": ["overseas", "national overseas", "study abroad", "abroad"],
    "depwd-pre-matric": ["disability", "disabilities", "disabled", "divyang", "pwd", "benchmark disability"],
    "depwd-post-matric": ["disability", "disabilities", "disabled", "divyang", "pwd", "benchmark disability"],
    "depwd-top-class": ["disability", "disabilities", "disabled", "divyang", "pwd"],
    "pms-st": ["scheduled tribe", "post matric st", "post-matric st", "st post matric", "st post-matric", "tribal",
               "st student", "st students", "for st"],
    "inspire-she": ["inspire", "she scholarship"],
    "tn-pudhumai-penn": ["pudhumai", "tamil nadu"],
    "moma-minority-scholarships": ["minority", "merit-cum-means", "merit cum means", "maulana azad"],
    "begum-hazrat-mahal": ["begum hazrat mahal", "hazrat mahal"],
}


def mentioned_schemes(text: str) -> list[str]:
    """Scheme ids whose names or aliases appear in the text (whole-word match, case-insensitive).

    A generic alias loses to a longer, more specific one covering the same words:
    "top class education for SC students" means TCES, not every scheme "for SC".
    """
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    spans: dict[str, list[tuple[int, int]]] = {}
    for sid, names in ALIASES.items():
        sch = scheme_by_id().get(sid)
        candidates = list(names) + ([sch["short"].lower()] if sch else [])
        for n in candidates:
            for m in re.finditer(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", t):
                spans.setdefault(sid, []).append(m.span())

    def beaten(sid: str, a: int, b: int) -> bool:
        return any(c < b and a < d and (d - c) > (b - a)
                   for other, ss in spans.items() if other != sid for c, d in ss)

    return [sid for sid, ss in spans.items() if not all(beaten(sid, a, b) for a, b in ss)]


def public_scheme(s: dict[str, Any]) -> dict[str, Any]:
    """Scheme as sent to the browser, with each rule's source document resolved."""
    docs = document_by_id()

    def src(ref: dict[str, Any]) -> dict[str, Any]:
        d = docs[ref["source"]]
        return {"docId": d["id"], "title": d["title"], "url": d["url"], "version": d["version"],
                "location": ref.get("location"), "quote": ref.get("quote")}

    return {
        "id": s["id"], "name": s["name"], "short": s["short"], "ministry": s["ministry"], "kind": s["kind"],
        "status": s["status"], "statusNote": s.get("status_note"), "forWhom": s["for_whom"], "levels": s["levels"],
        "benefit": s["benefit"], "benefitPerYear": s.get("benefit_inr_per_year", 0),
        "applyUrl": s["apply_url"], "window": s["window"],
        "rules": [{"id": r["id"], "label": r["label"], "source": src(r)} for r in s["rules"]],
        "checks": [{"text": c["text"], "source": src(c)} for c in s["checks"]],
        "notes": s.get("notes", []),
        "documents": [{"id": d["id"], "title": d["title"], "url": d["url"], "version": d["version"]}
                      for d in documents() if s["id"] in d["scheme_ids"]],
    }
