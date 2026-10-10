"""
Rule engine for scheme eligibility.

Rules are data (see data/catalog.json). Each rule has a condition tree:
    {"field": "income", "op": "lte", "value": 450000}
    {"all": [cond, cond]}   {"any": [cond, cond]}

Evaluation is three-valued: True (meets it), False (does not), None (we don't know yet because
the student left that question blank). That lets us say "you might qualify, if ..." instead of
wrongly ruling a scheme in or out.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .catalog import public_scheme, schemes

Level = Literal["class_9_10", "class_11_12", "diploma", "ug", "pg", "phd"]
Category = Literal["general", "ews", "obc", "ebc", "dnt", "sc", "st"]


class Profile(BaseModel):
    """Everything is optional: unknown answers make rules 'unknown', never 'failed'."""

    state: str | None = Field(default=None, description="Two-letter state/UT code, e.g. AS, TN")
    category: Category | None = None
    gender: Literal["female", "male", "transgender"] | None = None
    disability_pct: float | None = Field(default=None, ge=0, le=100)
    income: float | None = Field(default=None, ge=0, description="Annual family income in rupees")
    level: Level | None = None
    course_type: Literal["technical", "medical", "general", "professional_other", "mba_mca"] | None = None
    study_mode: Literal["regular", "distance"] | None = None
    class12_percentile: float | None = Field(default=None, ge=0, le=100)
    qualifying_marks_pct: float | None = Field(default=None, ge=0, le=100)
    school_type: Literal["government", "govt_aided", "local_body", "private", "kv_jnv"] | None = None
    top_institution: bool | None = None
    studying_abroad: bool | None = None
    other_scholarship: bool | None = None
    age: int | None = Field(default=None, ge=5, le=80)
    flags: list[str] = Field(default_factory=list)
    # Flags the student explicitly answered "no" to are just absent; the form sends this so that
    # an empty flags list means "none apply" rather than "didn't answer".
    flags_answered: bool = False


Tri = bool | None


def _cmp(op: str, actual: Any, expected: Any) -> Tri:
    if op == "has_any":
        return None if actual is None else bool(set(actual) & set(expected))
    if actual is None:
        return None
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    raise ValueError(f"unknown op {op}")


def evaluate(cond: dict[str, Any], p: Profile) -> Tri:
    if "all" in cond:
        vals = [evaluate(c, p) for c in cond["all"]]
        if any(v is False for v in vals):
            return False
        return None if any(v is None for v in vals) else True
    if "any" in cond:
        vals = [evaluate(c, p) for c in cond["any"]]
        if any(v is True for v in vals):
            return True
        return None if any(v is None for v in vals) else False
    field = cond["field"]
    if field == "flags":
        actual = p.flags if (p.flags or p.flags_answered) else None
    else:
        actual = getattr(p, field)
    return _cmp(cond["op"], actual, cond["value"])


Verdict = Literal["eligible", "maybe", "not_eligible"]


def match_scheme(s: dict[str, Any], p: Profile) -> dict[str, Any]:
    passed, failed, unknown = [], [], []
    for r in s["rules"]:
        v = evaluate(r["when"], p)
        (passed if v is True else failed if v is False else unknown).append(r["id"])
    verdict: Verdict = "not_eligible" if failed else ("maybe" if unknown else "eligible")
    return {"scheme": public_scheme(s), "verdict": verdict, "passed": passed, "failed": failed, "unknown": unknown}


_ORDER = {"eligible": 0, "maybe": 1, "not_eligible": 2}


def match_all(p: Profile) -> dict[str, Any]:
    """Open schemes ranked: eligible first, then 'maybe' with the fewest open questions; closed ones listed apart."""
    open_results, closed = [], []
    for s in schemes():
        if s["status"] != "active":
            closed.append({"scheme": public_scheme(s)})
            continue
        open_results.append(match_scheme(s, p))
    open_results.sort(
        key=lambda m: (_ORDER[m["verdict"]], len(m["unknown"]), -m["scheme"]["benefitPerYear"])
    )
    counts = {v: sum(1 for m in open_results if m["verdict"] == v) for v in _ORDER}
    return {"results": open_results, "closed": closed, "counts": counts}
