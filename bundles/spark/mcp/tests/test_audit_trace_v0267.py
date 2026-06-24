"""v0.2.67 audit-trace batch — silent read/auth paths now leave a trace.

Covers the MCP-side emissions added for:
  * KB-F6/KB-F7  — knowledge_list / knowledge_search emit kb_searched(mode)
  * API-F7       — SqliteApiKeyStore.verify() emits api_key_used; require_bearer
                   emits mcp_bearer_auth_failed on both failure shapes

The Next.js-tier emissions (middleware api_key_* denials, the CLI chat_cli_turn,
the cognitive/ui_auth route handlers) are validated by the pre-deploy
tsc/lint/build gate + the live smoke; this file covers the pure-Python sites.
"""

import types

from usecase import audit_log as audit_mod
from usecase.builtin_components import cognitive_tools


class _StubKb:
    def __init__(self, docs):
        self._docs = docs

    def list_docs(self, kb_name, limit=20):
        return self._docs

    def search(self, query, kb_name=None, category=None, tags=None, limit=5):
        return [(d, 0.9) for d in self._docs]


class _StubDoc:
    def to_dict(self, include_content=True, score=None):
        return {"id": "d1", "score": score}


def test_knowledge_list_emits_kb_searched(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))
    monkeypatch.setattr(
        "usecase.kb_store.knowledge_base", lambda: _StubKb([_StubDoc(), _StubDoc()])
    )

    out = cognitive_tools.knowledge_list("cortex-docs", limit=20)
    assert out["count"] == 2

    rows = [kw for action, kw in calls if action == audit_mod.ACTION_KB_SEARCHED]
    assert len(rows) == 1
    assert rows[0]["metadata"]["mode"] == "list"
    assert rows[0]["metadata"]["kb_name"] == "cortex-docs"
    assert rows[0]["target"] == "kb:cortex-docs"


def test_knowledge_search_emits_kb_searched_active(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))
    monkeypatch.setattr(
        "usecase.kb_store.knowledge_base", lambda: _StubKb([_StubDoc()])
    )

    out = cognitive_tools.knowledge_search("phishing iocs", limit=3)
    assert out["count"] == 1

    rows = [kw for action, kw in calls if action == audit_mod.ACTION_KB_SEARCHED]
    assert len(rows) == 1
    assert rows[0]["metadata"]["mode"] == "active"
    # query content is never logged — only its length
    assert rows[0]["metadata"]["query_chars"] == len("phishing iocs")
    assert "phishing" not in str(rows[0])


def test_knowledge_list_uninitialized_emits_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))
    monkeypatch.setattr("usecase.kb_store.knowledge_base", lambda: None)

    out = cognitive_tools.knowledge_list("cortex-docs")
    assert "error" in out
    assert not [c for c in calls if c[0] == audit_mod.ACTION_KB_SEARCHED]


def test_api_key_used_audit(tmp_path):
    from usecase.api_keys import SqliteApiKeyStore

    captured = []

    class _Audit:
        def record(self, action, **kw):
            captured.append((action, kw))

    store = SqliteApiKeyStore(data_root=tmp_path, audit_log=_Audit())
    created = store.create(label="smoke", scopes=["agent:read"], actor="user:operator")

    captured.clear()  # drop the create row; we only care about verify
    result = store.verify(created.plaintext)
    assert result is not None

    used = [kw for action, kw in captured if action == "api_key_used"]
    assert len(used) == 1
    assert used[0]["target"].startswith("api_key:")
    assert used[0]["metadata"]["label"] == "smoke"


def test_api_key_verify_miss_emits_no_used_row(tmp_path):
    from usecase.api_keys import SqliteApiKeyStore

    captured = []

    class _Audit:
        def record(self, action, **kw):
            captured.append((action, kw))

    store = SqliteApiKeyStore(data_root=tmp_path, audit_log=_Audit())
    store.create(label="smoke", scopes=["agent:read"], actor="user:operator")
    captured.clear()

    # Structurally valid but no matching row.
    assert store.verify("guardian_ak_00000000_" + "0" * 32) is None
    assert not [c for c in captured if c[0] == "api_key_used"]


def _fake_request(authorization: str | None, path: str = "/api/v1/jobs"):
    headers = {}
    if authorization is not None:
        headers["authorization"] = authorization
    return types.SimpleNamespace(
        headers=types.SimpleNamespace(get=lambda k, d=None: headers.get(k.lower(), d)),
        url=types.SimpleNamespace(path=path),
        state=types.SimpleNamespace(),
    )


def test_require_bearer_audits_missing_and_invalid(monkeypatch):
    from api import auth as auth_mod
    from config.config import config

    monkeypatch.setattr(config, "mcp_token", "the-real-token", raising=False)
    calls = []
    monkeypatch.setattr(auth_mod, "record_event", lambda action, **kw: calls.append((action, kw)))
    # No api-key store so the guardian_ak_ branch is a clean miss.
    monkeypatch.setattr(auth_mod, "api_key_store", lambda: None)

    # Missing header → 401 + audit.
    resp = auth_mod.require_bearer(_fake_request(None))
    assert resp is not None and resp.status_code == 401
    # Invalid bearer → 403 + audit.
    resp = auth_mod.require_bearer(_fake_request("Bearer not-the-token"))
    assert resp is not None and resp.status_code == 403
    # Correct token → None (no audit).
    resp = auth_mod.require_bearer(_fake_request("Bearer the-real-token"))
    assert resp is None

    failures = [kw for action, kw in calls if action == audit_mod.ACTION_MCP_BEARER_AUTH_FAILED]
    assert len(failures) == 2
    reasons = {kw["metadata"]["reason"] for kw in failures}
    assert reasons == {"missing_or_malformed_header", "invalid_bearer"}
