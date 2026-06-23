"""#API-F18/OBS-F8/CHAT-F2 — TriggerContextMiddleware reads X-Guardian-Actor
(set by the Next.js middleware post-auth) into the actor contextvar, so audit
attributes a mutation to the specific principal (apikey:<id> | user:operator)
instead of a hardcoded user:operator. Reset on request exit (no leakage).
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from starlette.applications import Starlette  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from api.trigger_context import TriggerContextMiddleware  # noqa: E402
from usecase.audit_log import get_current_actor  # noqa: E402


async def _who(request):
    return JSONResponse({"actor": get_current_actor()})


def _client() -> TestClient:
    app = Starlette(routes=[Route("/who", _who)])
    app.add_middleware(TriggerContextMiddleware)
    return TestClient(app)


def test_actor_header_sets_contextvar():
    r = _client().get("/who", headers={"X-Guardian-Actor": "apikey:abc123"})
    assert r.status_code == 200
    assert r.json()["actor"] == "apikey:abc123"


def test_session_actor_header():
    r = _client().get("/who", headers={"X-Guardian-Actor": "user:operator"})
    assert r.json()["actor"] == "user:operator"


def test_no_actor_header_does_not_inherit():
    # Without the header the middleware must NOT set an apikey actor.
    r = _client().get("/who")
    assert r.json()["actor"] != "apikey:abc123"


def test_actor_resets_after_request():
    c = _client()
    c.get("/who", headers={"X-Guardian-Actor": "apikey:zzz"})
    # The contextvar must be reset on request exit — no cross-request leak.
    assert get_current_actor() != "apikey:zzz"
