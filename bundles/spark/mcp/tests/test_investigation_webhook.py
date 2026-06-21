"""Stage D — webhook handoff (opt-in, config-driven, approval-gated send).

The send tool reads the target URL from OPERATOR config (env) ONLY — never a
tool arg — so observed content / the agent cannot redirect the outbound. These
tests mock the transport (no real network).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.investigation_store import InvestigationStore  # noqa: E402
from usecase.builtin_components import investigation_tools as it  # noqa: E402


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = InvestigationStore(data_root=tmp_path)
    monkeypatch.setattr(it, "investigation_store", lambda: s)
    return s


def _resolved(store):
    iss = store.create_issue(title="Phish", kind="phishing", severity="high", source_ref="INC-5")
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE", confidence=0.9)
    it.issue_add_technique(iss.id, "T1566.001")
    store.upsert_indicator("evil.com", "domain", issue_id=iss.id, dbot_score=3)
    return iss


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, json.loads(body.decode())))
        return 200, "ok"


def test_webhook_off_by_default(store, monkeypatch):
    monkeypatch.delenv("GUARDIAN_WEBHOOK_URL", raising=False)
    rec = _Recorder()
    monkeypatch.setattr(it, "_webhook_post", rec)
    iss = _resolved(store)
    out = it.export_to_webhook(issue_id=iss.id)
    assert "error" in out
    assert rec.calls == []  # nothing sent when unconfigured (opt-in off)


def test_webhook_sends_when_configured(store, monkeypatch):
    monkeypatch.setenv("GUARDIAN_WEBHOOK_URL", "https://soc.example/hook")
    monkeypatch.delenv("GUARDIAN_WEBHOOK_TOKEN", raising=False)
    rec = _Recorder()
    monkeypatch.setattr(it, "_webhook_post", rec)
    iss = _resolved(store)
    out = it.export_to_webhook(issue_id=iss.id)
    assert out.get("ok") is True and out["status"] == 200
    assert len(rec.calls) == 1
    url, headers, payload = rec.calls[0]
    assert url == "https://soc.example/hook"  # target from env, not arg
    assert payload["verdict"] == "TRUE_POSITIVE"
    assert payload["report"] and payload["stix"]
    assert any(i["value"] == "evil.com" for i in payload["iocs"])
    assert "Authorization" not in headers  # no token set


def test_webhook_token_header(store, monkeypatch):
    monkeypatch.setenv("GUARDIAN_WEBHOOK_URL", "https://soc.example/hook")
    monkeypatch.setenv("GUARDIAN_WEBHOOK_TOKEN", "s3cret")
    rec = _Recorder()
    monkeypatch.setattr(it, "_webhook_post", rec)
    iss = _resolved(store)
    it.export_to_webhook(issue_id=iss.id)
    _, headers, _ = rec.calls[0]
    assert headers.get("Authorization") == "Bearer s3cret"


def test_webhook_preview_is_readonly(store, monkeypatch):
    monkeypatch.setenv("GUARDIAN_WEBHOOK_URL", "https://soc.example/hook")
    rec = _Recorder()
    monkeypatch.setattr(it, "_webhook_post", rec)
    iss = _resolved(store)
    out = it.webhook_preview(issue_id=iss.id)
    assert out["would_send"]["verdict"] == "TRUE_POSITIVE"
    assert out["target"] == "https://soc.example/hook"
    assert rec.calls == []  # preview NEVER sends


def test_webhook_preview_shows_unconfigured(store, monkeypatch):
    monkeypatch.delenv("GUARDIAN_WEBHOOK_URL", raising=False)
    iss = _resolved(store)
    out = it.webhook_preview(issue_id=iss.id)
    assert out["target"] is None  # operator hasn't configured one
    assert out["would_send"]["verdict"] == "TRUE_POSITIVE"


def test_webhook_requires_exactly_one(store, monkeypatch):
    monkeypatch.setenv("GUARDIAN_WEBHOOK_URL", "https://soc.example/hook")
    monkeypatch.setattr(it, "_webhook_post", _Recorder())
    iss = _resolved(store)
    case = store.create_case(title="c")
    assert "error" in it.export_to_webhook(issue_id=iss.id, case_id=case.id)
    assert "error" in it.export_to_webhook()
