"""#SUB-F1/F2/F11 — subagent definition store + validator robustness.

- SUB-F1: get_by_name is case-insensitive (a spawn for "Case-Triage" must
  resolve a stored "case-triage" instead of silently 404ing).
- SUB-F2: a create/rename to an already-used name raises a clean ValueError
  (→ HTTP 4xx) instead of an uncaught sqlite3.IntegrityError (→ 500).
- SUB-F11: the REST validator rejects a missing/empty tools_allowed (which
  would expose the full parent tool catalog); ["*"] is the explicit opt-in.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.agent_definition_store import SqliteAgentDefinitionStore  # noqa: E402
from api.agent_definitions import _validate_definition  # noqa: E402


def _store(tmp_path) -> SqliteAgentDefinitionStore:
    return SqliteAgentDefinitionStore(data_root=tmp_path)


def _def(name: str, **over) -> dict:
    base = {
        "id": name,
        "name": name,
        "system_prompt": "you are a triage agent",
        "tools_allowed": ["xsoar.*"],
        "tools_denied": [],
    }
    base.update(over)
    return base


# ─── SUB-F1 ──────────────────────────────────────────────────────────


def test_get_by_name_is_case_insensitive(tmp_path):
    s = _store(tmp_path)
    s.upsert(_def("case-triage"), origin="operator")
    assert s.get_by_name("case-triage") is not None
    assert s.get_by_name("Case-Triage") is not None
    assert s.get_by_name("CASE-TRIAGE") is not None
    assert s.get_by_name("no-such-agent") is None


# ─── SUB-F2 ──────────────────────────────────────────────────────────


def test_rename_to_existing_name_raises_valueerror(tmp_path):
    s = _store(tmp_path)
    s.upsert(_def("alpha", id="id-alpha"), origin="operator")
    s.upsert(_def("beta", id="id-beta"), origin="operator")
    # Rename beta → alpha (a different row already holds 'alpha').
    with pytest.raises(ValueError) as exc:
        s.upsert(_def("alpha", id="id-beta"), origin="operator")
    assert "already exists" in str(exc.value)


# ─── SUB-F11 ─────────────────────────────────────────────────────────


def test_validator_rejects_missing_tools_allowed():
    err = _validate_definition(
        {"name": "x", "system_prompt": "sp"}  # no tools_allowed
    )
    assert err is not None
    assert "tools_allowed" in err


def test_validator_rejects_empty_tools_allowed():
    err = _validate_definition(
        {"name": "x", "system_prompt": "sp", "tools_allowed": []}
    )
    assert err is not None
    assert "tools_allowed" in err


def test_validator_accepts_explicit_wildcard():
    err = _validate_definition(
        {"name": "x", "system_prompt": "sp", "tools_allowed": ["*"]}
    )
    assert err is None


def test_validator_accepts_scoped_allowlist():
    err = _validate_definition(
        {"name": "x", "system_prompt": "sp", "tools_allowed": ["xsoar.*", "memory_*"]}
    )
    assert err is None
