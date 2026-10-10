from app.answer import answer, quote_supported
from app.retrieval import keyword_search, search


class FakeGen:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def generate_json(self, system, user):
        self.prompts.append(user)
        return self.reply(user) if callable(self.reply) else self.reply


def test_keyword_search_finds_exact_terms(indexed):
    hits = keyword_search("80th percentile class XII", None)
    assert hits and hits[0].doc_id == "csss-2024"


def test_hybrid_search_routes_to_the_right_scheme(indexed):
    cases = {
        "What is the income limit for the central sector scholarship?": "csss-2024",
        "how many girls in one family can get pragati": "aicte-pragati-g",
        "Are Navodaya school students eligible for NMMSS?": "nmmss-2022",
        "my father earns 3 lakh, can I get the Rs 12,000 graduation scholarship": "csss-2024",
    }
    for q, doc in cases.items():
        hits = search(q, k=4, embedder=indexed)
        assert hits[0].doc_id == doc, (q, [h.doc_id for h in hits])
        assert hits[0].via  # ranked by keyword and/or vector


def test_keyword_only_mode_still_works(indexed):
    hits = search("Kendriya Vidyalayas not eligible", k=3, use_vectors=False)
    assert hits[0].doc_id == "nmmss-2022"


def test_quote_verification():
    src = "(v) Students with gross parental/family income upto Rs. 4.5 lakh per annum are eligible."
    assert quote_supported("income upto Rs. 4.5 lakh per annum", src)
    assert quote_supported("Students with gross parental / family income  upto Rs. 4.5 lakh", src)
    assert not quote_supported("income upto Rs. 8 lakh per annum", src)
    assert not quote_supported("lakh", src)


def test_answer_keeps_verified_citations_and_rejects_invented_quotes(indexed):
    def reply(prompt):
        import re
        # cite whichever numbered source actually holds the income clause
        n = next(m.group(1) for m in re.finditer(r"\[S(\d+)\][^\[]*", prompt) if "4.5 lakh" in m.group(0))
        return {
            "answer": f"Family income must be up to Rs 4.5 lakh a year [S{n}]. Other rules apply [S9].",
            "found": True,
            "quotes": [
                {"source": f"S{n}", "text": "income upto Rs. 4.5 lakh per annum are eligible"},
                {"source": "S2", "text": "this sentence is not in any document at all anywhere"},
            ],
        }

    gen = FakeGen(reply)
    out = answer("What is the income limit for CSSS?", generator=gen, embedder=indexed)
    assert out["mode"] == "llm" and out["found"]
    assert "[S9]" not in out["answer"]  # marker for a non-existent source removed
    assert out["grounding"] == {"cited": 1, "verified": 1, "rejectedQuotes": 1}
    assert out["citations"][0]["docId"] == "csss-2024" and out["citations"][0]["quote"]
    assert "SCHEME STATUS" in gen.prompts[0] and "[S1]" in gen.prompts[0]


def test_answer_warns_when_quotes_do_not_match(indexed):
    gen = FakeGen({"answer": "It is 9 lakh [S1].", "found": True, "quotes": [{"source": "S1", "text": "income up to nine lakh rupees for everyone"}]})
    out = answer("income limit central sector scholarship", generator=gen, embedder=indexed)
    assert out["grounding"]["verified"] == 0 and "warning" in out


def test_profile_and_scheme_status_reach_the_prompt(indexed):
    from app.eligibility import Profile

    gen = FakeGen({"answer": "x [S1]", "found": True, "quotes": []})
    answer("Am I eligible for Pragati?", profile=Profile(gender="female", income=600000), scheme_id="aicte-pragati",
           generator=gen, embedder=indexed)
    prompt = gen.prompts[0]
    assert "STUDENT PROFILE" in prompt and "600000" in prompt and "AICTE Pragati" in prompt


def test_extractive_fallback_without_a_model(indexed, monkeypatch):
    monkeypatch.setattr("app.answer.get_generator", lambda: None)
    out = answer("How much is the Pragati scholarship amount per annum?", embedder=indexed)
    assert out["mode"] == "extractive" and out["found"]
    assert "50,000" in out["answer"] and out["citations"][0]["docId"] == "aicte-pragati-g"


def test_model_failure_falls_back_to_passages(indexed):
    class Broken:
        name = "broken"

        def generate_json(self, s, u):
            from app.llm import LLMError
            raise LLMError("429 quota")

    out = answer("NMMSS amount per month", generator=Broken(), embedder=indexed)
    assert out["mode"] == "extractive" and "warning" in out


def test_eval_harness_runs(indexed):
    from app.evaluate import run_retrieval_eval

    r = run_retrieval_eval(k=4, embedder=indexed)
    assert r["questions"] > 0 and r["skipped_not_indexed"] > 0
    assert r["hit@4"] >= 0.8


def test_malformed_model_output_does_not_crash(indexed):
    for reply in ({"answer": "x [S1]", "quotes": ["not a dict"], "found": "false"}, {"quotes": []}, ["a list"]):
        out = answer("NMMSS amount per month", generator=FakeGen(reply), embedder=indexed)
        assert out["mode"] in ("llm", "extractive")
    out = answer("NMMSS amount per month", generator=FakeGen({"answer": "No idea.", "found": "false", "quotes": ["x"]}), embedder=indexed)
    assert out["found"] is False and out["grounding"]["rejectedQuotes"] == 1


def test_non_pdf_response_for_pdf_url_is_rejected(fresh_db):
    from app.catalog import document_by_id
    from app.ingest.pipeline import IngestReport, ingest_document

    r = IngestReport()
    ingest_document(document_by_id()["nos-2526"], None, r, data=b"<!doctype html><html><body>Access denied</body></html>")
    assert "nos-2526" in r.failed
