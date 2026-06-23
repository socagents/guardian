"""#XSOAR-F4/XSIAM-F5 — tool argument VALUES are captured into the audit
trail for forensic visibility, with secrets redacted AT CAPTURE TIME.

Pins connector_loader._sanitize_arg_values:
  - always-redact (tool:arg) blobs → '[redacted]' sentinel
  - sensitive key-name substring → '[redacted]' REGARDLESS of value type
    (audit_log._sanitize only scrubs top-level STRING values, so int/dict
    secrets at a sensitive key would otherwise slip through)
  - large values truncated to 512 chars
  - forensic action data (command/query) is CAPTURED, not redacted
  - GUARDIAN_AUDIT_ARG_VALUES=0 disables capture entirely
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.connector_loader import _sanitize_arg_values, _REDACTED  # noqa: E402


def test_always_redact_blob_pairs():
    # snippet_code (RCE) + skills content + memory value + XSOAR list content
    out = _sanitize_arg_values("xsiam.scripts_run_snippet", {"snippet_code": "rm -rf / # secret=abc"})
    assert out["snippet_code"] == _REDACTED
    out = _sanitize_arg_values("builtins:skills_create", {"content": "always use key sk-XYZ"})
    assert out["content"] == _REDACTED
    out = _sanitize_arg_values("builtins:memory_store", {"key": "note", "value": "password is hunter2"})
    assert out["value"] == _REDACTED
    out = _sanitize_arg_values("xsoar.set_list", {"name": "creds", "content": "api_key=ZZZ"})
    assert out["content"] == _REDACTED
    # the non-blob arg alongside it is still captured
    assert out["name"] == "creds"


def test_sensitive_key_redacted_regardless_of_type():
    # GAP 2 — non-string value at a sensitive key must still be redacted.
    out = _sanitize_arg_values("xsoar.run_command", {"token": 12345})
    assert out["token"] == _REDACTED
    out = _sanitize_arg_values("xsoar.run_command", {"api_key": "ABC"})
    assert out["api_key"] == _REDACTED
    out = _sanitize_arg_values("xsoar.run_command", {"password": ["a", "b"]})
    assert out["password"] == _REDACTED
    # hardened substrings
    out = _sanitize_arg_values("x.y", {"client_secret": "s", "refresh_token": "r", "private_key": "k"})
    assert out["client_secret"] == _REDACTED
    assert out["refresh_token"] == _REDACTED
    assert out["private_key"] == _REDACTED


def test_forensic_values_are_captured_not_redacted():
    # The whole point of the finding: command / query must be VISIBLE.
    out = _sanitize_arg_values("xsoar.run_command", {"command": "!whois ip=1.2.3.4"})
    assert out["command"] == "!whois ip=1.2.3.4"
    out = _sanitize_arg_values("xsiam.run_xql_query", {"query": "dataset=xdr_data | filter x=1"})
    assert out["query"] == "dataset=xdr_data | filter x=1"
    out = _sanitize_arg_values("xsoar.enrich_indicator", {"indicator_value": "8.8.8.8"})
    assert out["indicator_value"] == "8.8.8.8"


def test_large_value_truncated():
    big = "A" * 5000
    out = _sanitize_arg_values("xsiam.run_xql_query", {"query": big})
    assert out["query"].startswith("A" * 512)
    assert "truncated 4488 chars" in out["query"]
    assert len(out["query"]) < 600


def test_dict_value_json_coerced_and_bounded():
    out = _sanitize_arg_values("xsoar.update_incident", {"fields": {"severity": 3, "owner": "ana"}})
    # innocuous key → json-dumped string, not a nested dict
    assert isinstance(out["fields"], str)
    assert "severity" in out["fields"]


def test_flag_off_returns_empty(monkeypatch):
    monkeypatch.setenv("GUARDIAN_AUDIT_ARG_VALUES", "0")
    out = _sanitize_arg_values("xsoar.run_command", {"command": "!x"})
    assert out == {}
    monkeypatch.setenv("GUARDIAN_AUDIT_ARG_VALUES", "false")
    assert _sanitize_arg_values("xsoar.run_command", {"command": "!x"}) == {}


def test_instance_selector_and_context_skipped():
    out = _sanitize_arg_values("xsoar.run_command", {"instance": "primary", "command": "!x"})
    assert "instance" not in out
    assert out["command"] == "!x"
