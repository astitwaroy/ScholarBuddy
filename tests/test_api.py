from fastapi.testclient import TestClient

from app.main import app


def client():
    return TestClient(app)


def test_match_endpoint():
    with client() as c:
        r = c.post("/api/match", json={"gender": "female", "income": 500000, "level": "ug", "course_type": "technical"})
        assert r.status_code == 200
        body = r.json()
        first = body["results"][0]
        assert first["scheme"]["id"] == "aicte-pragati" and first["verdict"] in ("eligible", "maybe")
        assert first["scheme"]["rules"][0]["source"]["url"].startswith("https://")


def test_match_rejects_bad_input():
    with client() as c:
        assert c.post("/api/match", json={"income": -5}).status_code == 422
        assert c.post("/api/match", json={"category": "martian"}).status_code == 422


def test_catalog_and_status(indexed):
    with client() as c:
        cat = c.get("/api/catalog").json()
        assert len(cat["schemes"]) >= 20
        csss = next(d for d in cat["documents"] if d["id"] == "csss-2024")
        assert csss["status"] == "ok" and csss["chunks"] > 0
        st = c.get("/api/status").json()
        assert st["documents"]["ok"] >= 3 and st["llm"] is False


def test_ask_validation_and_rate_limit(indexed):
    with client() as c:
        assert c.post("/api/ask", json={"question": "hi"}).status_code == 422
        assert c.post("/api/ask", json={"question": "income limit?", "schemeId": "nope"}).status_code == 404
        codes = [c.post("/api/ask", json={"question": "What is the NMMSS amount?"}, headers={"x-forwarded-for": "9.9.9.9"}).status_code
                 for _ in range(14)]
        assert codes[0] == 200 and 429 in codes


def test_admin_routes_need_token():
    with client() as c:
        assert c.post("/api/admin/ingest").status_code == 403


def test_spoofed_forwarded_for_does_not_bypass_limit(indexed):
    from app import main

    main._hits.clear()
    with client() as c:
        codes = [c.post("/api/ask", json={"question": "What is the NMMSS amount?"},
                        headers={"x-forwarded-for": f"{i}.{i}.{i}.{i}, 7.7.7.7"}).status_code for i in range(14)]
    assert 429 in codes  # the real (last) hop is the same every time
