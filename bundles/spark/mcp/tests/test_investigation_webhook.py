"""Stage D — webhook handoff (opt-in, config-driven, approval-gated send).

The send tool reads the target URL from OPERATOR config (env) ONLY — never a
tool arg — so observed content / the agent cannot redirect the outbound. These
tests mock the transport (no real network).

#76: export_to_webhook is now async and self-gates via gate_and_execute (it was
listed in humanRequired but, as an unwrapped built-in, the gate never fired).
Send tests run under an approval BYPASS context (mirrors a bypass session/job);
a dedicated test proves the gate BLOCKS the send when neither approved nor
bypassed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.investigation_store import InvestigationStore  # noqa: E402
from usecase.builtin_components import investigation_tools as it  # noqa: E402
from usecase.audit_log import (  # noqa: E402
    set_current_approval_bypass,
    reset_current_approval_bypass,
)


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


@contextmanager
def _bypass():
    """Run with approval bypass active (as a bypass session/job would)."""
    tok = set_current_approval_bypass(True)
    try:
        yield
    finally:
        reset_current_approval_bypass(tok)


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
    out = asyncio.run(it.export_to_webhook(issue_id=iss.id))
    assert "error" in out
    assert rec.calls == []  # nothing sent when unconfigured (opt-in off)


def test_webhook_sends_when_configured(store, monkeypatch):
    monkeypatch.setenv("GUARDIAN_WEBHOOK_URL", "https://soc.example/hook")
    monkeypatch.delenv("GUARDIAN_WEBHOOK_TOKEN", raising=False)
    rec = _Recorder()
    monkeypatch.setattr(it, "_webhook_post", rec)
    iss = _resolved(store)
    with _bypass():
        out = asyncio.run(it.export_to_webhook(issue_id=iss.id))
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
    with _bypass():
        asyncio.run(it.export_to_webhook(issue_id=iss.id))
    _, headers, _ = rec.calls[0]
    assert headers.get("Authorization") == "Bearer s3cret"


def test_webhook_gated_blocks_send_without_approval(store, monkeypatch, tmp_path):
    """#76 — with the tool gated and neither approval nor bypass, the send
    is blocked and NOTHING leaves the system."""
    from usecase.approvals_bus import set_approvals_bus
    from usecase.builtin_components import _approval_gate

    # Seed a manifest that gates export_to_webhook; no bus wired → the gate
    # fails closed (ApprovalDeniedError) without executing the send.
    manifest_dir = tmp_path / "bundle"
    manifest_dir.mkdir(exist_ok=True)
    (manifest_dir / "manifest.yaml").write_text(
        "approvals:\n  policy: hybrid\n  humanRequired:\n    - 'export_to_webhook'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BUNDLE_ROOT", str(manifest_dir))
    _approval_gate._human_required_set.cache_clear()
    set_approvals_bus(None)
    try:
        monkeypatch.setenv("GUARDIAN_WEBHOOK_URL", "https://soc.example/hook")
        rec = _Recorder()
        monkeypatch.setattr(it, "_webhook_post", rec)
        iss = _resolved(store)
        out = asyncio.run(it.export_to_webhook(issue_id=iss.id))
        assert "error" in out  # gate blocked it
        assert rec.calls == []  # NOTHING sent
    finally:
        _approval_gate._human_required_set.cache_clear()


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
    with _bypass():
        assert "error" in asyncio.run(it.export_to_webhook(issue_id=iss.id, case_id=case.id))
        assert "error" in asyncio.run(it.export_to_webhook())
