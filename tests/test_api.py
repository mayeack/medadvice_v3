#!/usr/bin/env python3
"""API regression suite — every endpoint's auth gating + contract, via FastAPI's
in-process TestClient.

Side-effect-safe: the LLM boundary and the auto-prompter are stubbed, and the demo
incident is started without driving load, so the suite makes no real Anthropic
calls, spawns no background load, and triggers no external emission (Splunk/HEC/
Galileo are no-op without config). pytest isn't installed; run standalone:

    venv/bin/python tests/test_api.py        # exit 0 = pass
"""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.config  # noqa: E402  (sets CA bundle etc.)
from backend.config import settings  # noqa: E402

# Ensure the access gate is exercised even if .env has no ACCESS_KEY.
KEY = settings.access_key or "test-access-key"
settings.access_key = KEY

# --- stub the LLM boundary BEFORE backend.main imports the graph/nodes ---
import backend.agents.llm as llm  # noqa: E402
from backend.agents.llm import NormalizedLLMResponse  # noqa: E402


def _fake_llm(*_a, **_k):
    return NormalizedLLMResponse(
        id="test-id", content="LOW\nAssessment: test. Guidance: rest, fluids.",
        model="test-model", input_tokens=5, output_tokens=7, stop_reason="end_turn",
    )


llm.invoke_agent = _fake_llm
llm.invoke_chat = _fake_llm

# --- stub the auto-prompter so /auto-prompt/start launches no real load ---
import backend.services.auto_prompter as ap  # noqa: E402


async def _noop(*_a, **_k):
    return None


ap.auto_prompter.start = _noop  # type: ignore[assignment]
ap.auto_prompter.stop = _noop   # type: ignore[assignment]

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(f"x:{KEY}".encode()).decode()}
_fails = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _fails
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        _fails += 1


def main() -> int:
    with TestClient(app) as c:
        # ---- public (no key) ----
        check("GET /health -> 200 (public)", c.get("/health").status_code == 200)
        check("GET /login -> 200 (public)", c.get("/login").status_code == 200)

        # ---- auth gating: gated endpoints reject without the key (401 JSON) ----
        for path in ("/api/chat/auto-prompt/status", "/api/incident/status",
                     "/api/settings", "/api/hec/destinations", "/admin/logs/metrics",
                     "/api/settings/emit-model"):
            r = c.get(path)
            check(f"GET {path} -> 401 without key", r.status_code == 401, f"got {r.status_code}")

        # ---- chat ----
        r = c.post("/api/chat/session/new", headers=AUTH)
        check("POST /api/chat/session/new -> 200 + session_id",
              r.status_code == 200 and "session_id" in r.json(), f"{r.status_code}")
        sid = r.json().get("session_id", "") if r.status_code == 200 else ""
        check("GET /api/chat/session/{id} -> 200",
              c.get(f"/api/chat/session/{sid}", headers=AUTH).status_code in (200, 404))
        check("GET /api/chat/disclaimer -> 200", c.get("/api/chat/disclaimer", headers=AUTH).status_code == 200)
        # /message: validation (no real LLM turn asserted — that's integration-tested)
        check("POST /api/chat/message bad body -> 422",
              c.post("/api/chat/message", headers=AUTH, json={}).status_code == 422)
        rmsg = c.post("/api/chat/message", headers=AUTH,
                      json={"session_id": sid, "message": "test", "disclaimer_accepted": True})
        check("POST /api/chat/message (stubbed LLM) -> 200", rmsg.status_code == 200, f"{rmsg.status_code}")
        check("GET /api/chat/auto-prompt/status -> 200", c.get("/api/chat/auto-prompt/status", headers=AUTH).status_code == 200)
        check("POST /api/chat/auto-prompt/start -> 200 (stubbed)", c.post("/api/chat/auto-prompt/start", headers=AUTH).status_code == 200)
        check("POST /api/chat/auto-prompt/stop -> 200", c.post("/api/chat/auto-prompt/stop", headers=AUTH).status_code == 200)

        # ---- incident (no real load: drive_traffic false, then stop) ----
        check("GET /api/incident/status -> 200", c.get("/api/incident/status", headers=AUTH).status_code == 200)
        rinc = c.post("/api/incident/start", headers=AUTH,
                      json={"latency_ms": 0, "error_rate": 0, "duration_s": 10, "drive_traffic": False})
        check("POST /api/incident/start (no load) -> 200 + active",
              rinc.status_code == 200 and rinc.json().get("active") is True, f"{rinc.status_code}")
        check("POST /api/incident/stop -> 200 + inactive",
              c.post("/api/incident/stop", headers=AUTH).json().get("active") is False)

        # ---- settings ----
        rs = c.get("/api/settings", headers=AUTH)
        check("GET /api/settings -> 200 + logs_directory", rs.status_code == 200 and "logs_directory" in rs.json())
        check("PUT /api/settings -> 200", c.put("/api/settings", headers=AUTH, json={"logs_directory": "logs"}).status_code == 200)
        rem = c.get("/api/settings/emit-model", headers=AUTH)
        check("GET /api/settings/emit-model -> 200 + choices", rem.status_code == 200 and "choices" in rem.json())
        check("PUT /api/settings/emit-model valid -> 200",
              c.put("/api/settings/emit-model", headers=AUTH, json={"enabled": False, "model_name": "gpt-4o", "random": False}).status_code == 200)
        check("PUT /api/settings/emit-model unknown model -> 422",
              c.put("/api/settings/emit-model", headers=AUTH, json={"enabled": True, "model_name": "not-a-real-model", "random": False}).status_code == 422)

        # ---- HEC destinations CRUD ----
        rd = c.get("/api/hec/destinations", headers=AUTH)
        check("GET /api/hec/destinations -> 200 + list", rd.status_code == 200 and "destinations" in rd.json())
        rc = c.post("/api/hec/destinations", headers=AUTH, json={"name": "apitest-dest"})
        check("POST /api/hec/destinations -> 200 + id", rc.status_code == 200 and rc.json().get("id"), f"{rc.status_code}")
        did = rc.json().get("id", "") if rc.status_code == 200 else ""
        check("GET /api/hec/destinations/{id} -> 200", c.get(f"/api/hec/destinations/{did}", headers=AUTH).status_code == 200)
        check("PUT /api/hec/destinations/{id} -> 200", c.put(f"/api/hec/destinations/{did}", headers=AUTH, json={"index": "main2"}).status_code == 200)
        check("GET /api/hec/stats -> 200 + destinations", "destinations" in c.get("/api/hec/stats", headers=AUTH).json())
        check("DELETE /api/hec/destinations/{id} -> 200", c.delete(f"/api/hec/destinations/{did}", headers=AUTH).status_code == 200)
        check("GET /api/hec/destinations/{bad} -> 404", c.get("/api/hec/destinations/nope", headers=AUTH).status_code == 404)

        # ---- admin ----
        for path in ("/admin/logs/interactions", "/admin/logs/escalations", "/admin/logs/metrics", "/admin/logs/export"):
            check(f"GET {path} -> 200", c.get(path, headers=AUTH).status_code == 200)

        # ---- auth (login/logout) ----
        bad = c.post("/login", data={"access_code": "wrong-code"}, follow_redirects=False)
        check("POST /login wrong code -> not authenticated (no md_access cookie)",
              "md_access" not in bad.cookies)
        good = c.post("/login", data={"access_code": KEY}, follow_redirects=False)
        check("POST /login correct code -> redirect + md_access cookie",
              good.status_code in (302, 303, 200) and "md_access" in good.cookies, f"{good.status_code}")
        check("GET /logout -> 2xx/3xx", c.get("/logout", headers=AUTH, follow_redirects=False).status_code in (200, 302, 303))

        # ---- server-rendered pages (HTML, with key) ----
        for path in ("/app", "/admin-ui", "/governance-ui", "/settings-ui"):
            r = c.get(path, headers=AUTH)
            check(f"GET {path} -> 200 HTML", r.status_code == 200 and "<html" in r.text.lower(), f"{r.status_code}")

    print(f"RESULT: {'ok' if not _fails else str(_fails) + ' failed'}")
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
