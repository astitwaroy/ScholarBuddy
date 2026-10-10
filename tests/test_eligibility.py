from app.catalog import scheme_by_id
from app.eligibility import Profile, evaluate, match_all, match_scheme


def verdict(sid: str, **kw) -> str:
    return match_scheme(scheme_by_id()[sid], Profile(**kw))["verdict"]


def test_three_valued_logic():
    p = Profile(income=300000)
    assert evaluate({"field": "income", "op": "lte", "value": 450000}, p) is True
    assert evaluate({"field": "income", "op": "lte", "value": 250000}, p) is False
    assert evaluate({"field": "age", "op": "lt", "value": 30}, p) is None
    # all: any False wins, else unknown if any unknown
    assert evaluate({"all": [{"field": "income", "op": "lte", "value": 1}, {"field": "age", "op": "lt", "value": 30}]}, p) is False
    assert evaluate({"all": [{"field": "income", "op": "lte", "value": 9e9}, {"field": "age", "op": "lt", "value": 30}]}, p) is None
    # any: any True wins
    assert evaluate({"any": [{"field": "income", "op": "lte", "value": 9e9}, {"field": "age", "op": "lt", "value": 30}]}, p) is True


def test_csss_boundaries():
    base = dict(level="ug", study_mode="regular", class12_percentile=85, other_scholarship=False)
    assert verdict("pm-usp-csss", income=450000, **base) == "eligible"  # "up to 4.5 lakh" includes 4.5
    assert verdict("pm-usp-csss", income=450001, **base) == "not_eligible"
    assert verdict("pm-usp-csss", income=300000, **{**base, "class12_percentile": 80}) == "not_eligible"  # must be ABOVE 80th
    assert verdict("pm-usp-csss", income=300000, **{**base, "level": "diploma"}) == "not_eligible"
    assert verdict("pm-usp-csss", income=300000, level="ug") == "maybe"  # percentile etc. unknown


def test_strict_less_than_limits():
    # Ishan Uday says "below Rs 4.5 lakh"; Top Class School says "less than 2.5 lakh"
    ne = dict(state="AS", level="ug", study_mode="regular")
    assert verdict("ugc-ishan-uday", income=449999, **ne) == "eligible"
    assert verdict("ugc-ishan-uday", income=450000, **ne) == "not_eligible"
    assert verdict("ugc-ishan-uday", income=200000, **{**ne, "state": "DL"}) == "not_eligible"


def test_nmmss_school_type():
    ok = dict(income=200000, level="class_9_10")
    assert verdict("nmmss", school_type="government", **ok) == "eligible"
    assert verdict("nmmss", school_type="kv_jnv", **ok) == "not_eligible"
    assert verdict("nmmss", school_type="private", **ok) == "not_eligible"


def test_professional_degree_or_mba_for_pmss():
    base = dict(flags=["ward_ex_servicemen"], qualifying_marks_pct=72, studying_abroad=False, study_mode="regular")
    assert verdict("pmss-ksb-ex-servicemen", level="ug", course_type="medical", **base) == "eligible"
    assert verdict("pmss-ksb-ex-servicemen", level="pg", course_type="mba_mca", **base) == "eligible"
    assert verdict("pmss-ksb-ex-servicemen", level="pg", course_type="technical", **base) == "not_eligible"  # e.g. M.Tech
    assert verdict("pmss-ksb-ex-servicemen", level="ug", course_type="general", **base) == "not_eligible"
    assert verdict("pmss-ksb-ex-servicemen", level="ug", course_type="medical", **{**base, "qualifying_marks_pct": 59}) == "not_eligible"


def test_flags_unknown_vs_answered_none():
    p = dict(income=500000, level="ug", course_type="technical", other_scholarship=False)
    assert verdict("aicte-swanath", **p) == "maybe"  # didn't answer the special-situation question
    assert verdict("aicte-swanath", flags_answered=True, **p) == "not_eligible"  # answered: none apply
    assert verdict("aicte-swanath", flags=["orphan"], **p) == "eligible"


def test_match_all_orders_and_excludes_closed_schemes():
    r = match_all(Profile(gender="female", income=500000, level="ug", course_type="technical", study_mode="regular",
                          class12_percentile=90, other_scholarship=False, category="general", state="KA",
                          disability_pct=0, flags_answered=True, age=19, studying_abroad=False, top_institution=False))
    verdicts = [m["verdict"] for m in r["results"]]
    assert verdicts == sorted(verdicts, key=["eligible", "maybe", "not_eligible"].index)
    eligible = {m["scheme"]["id"] for m in r["results"] if m["verdict"] == "eligible"}
    assert eligible == {"aicte-pragati"}  # CSSS fails on income above 4.5 lakh
    closed = {c["scheme"]["id"] for c in r["closed"]}
    assert {"moma-minority-scholarships", "begum-hazrat-mahal", "inspire-she"} <= closed
    assert all(m["scheme"]["status"] == "active" for m in r["results"])


def test_every_rule_cites_a_document():
    for s in scheme_by_id().values():
        for rule in s["rules"]:
            assert rule["source"] and rule["label"]
