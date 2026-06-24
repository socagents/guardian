"""v0.2.80 misc batch — the non-doc fixes (optimistic-success, bypass-gate,
dead-config, code changes). Doc-drift / version-drift findings need no test.

Covered here (pure-Python, no pytest-asyncio — the repo has none):

  * #XSIAM-F6 / #XSIAM-F7 — _papi_reply_succeeded honestly reads a PAPI
    mutation response. HTTP 4xx/5xx already raise in the PAPI client; this
    guards the HTTP-200-with-error-body case so a tool can no longer echo an
    input-derived count/`deleted:True` as success when PAPI actually refused.
    A boolean-false reply, an {err_code}/{error} envelope, or a top-level
    err_code → not succeeded; a missing / opaque / true reply → succeeded
    (no evidence of failure) with the raw reply surfaced either way.

  * #JOBS-F10 — _row_to_yaml_doc now emits the execution-policy fields
    (bypass_approvals, model_id, thinking_enabled, permission_policy) so they
    round-trip through the YAML mirror instead of being silently dropped on
    boot reload. Only non-default values are written (plain jobs stay clean).

Findings validated by the py_compile + tsc gate + live smoke instead of a
unit test, because their modules pull CI-only deps:
  * #CDW-F12 — connector_loader._gate_request honors get_current_approval_bypass
    (mirrors _approval_gate): emits an `auto_approved` row + returns None so a
    bypass job/session executes immediately instead of blocking to timeout.
    connector_loader imports pydantic (CI-only).
  * The #JOBS-F10 load_yaml_jobs READ side (croniter-gated add_job) — the YAML
    document shape is asserted here; the boot reconcile is a live-smoke path.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

MCP_SRC = Path(__file__).resolve().parents[1] / "src"
if str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


# ─────────────────────────────────────────────────────────────────
# XSIAM connector — import with light stubs for fastmcp / pydantic so
# the pure helper (_papi_reply_succeeded) is reachable dep-free.
# ─────────────────────────────────────────────────────────────────
def _load_xsiam_connector():
    if "fastmcp" not in sys.modules:
        fastmcp = types.ModuleType("fastmcp")
        fastmcp.Context = object
        sys.modules["fastmcp"] = fastmcp
    if "pydantic" not in sys.modules:
        pyd = types.ModuleType("pydantic")

        class _BaseModel:  # minimal stand-in
            pass

        def _Field(*a, **k):
            return None

        pyd.BaseModel = _BaseModel
        pyd.Field = _Field
        sys.modules["pydantic"] = pyd

    xsiam_src = (
        Path(__file__).resolve().parents[2]
        / "connectors" / "xsiam" / "src"
    )
    # The connector's only module-level relative import is `._papi_client`.
    # Load connector.py under a synthetic package so `src` doesn't collide
    # with the MCP's own `src` package, pre-registering a stub _papi_client.
    import importlib.util

    pkg_name = "xsiam_conn_pkg"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(xsiam_src)]
    sys.modules[pkg_name] = pkg

    papi = types.ModuleType(f"{pkg_name}._papi_client")
    papi.Fetcher = object
    sys.modules[f"{pkg_name}._papi_client"] = papi

    spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.connector", xsiam_src / "connector.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg_name}.connector"] = mod
    spec.loader.exec_module(mod)
    return mod


_XSIAM = _load_xsiam_connector()


def test_papi_reply_succeeded_true_reply():
    ok, reply = _XSIAM._papi_reply_succeeded({"reply": True})
    assert ok is True
    assert reply is True


def test_papi_reply_succeeded_false_reply_is_failure():
    # The exact #XSIAM-F7 case: HTTP 200, reply=false (PAPI refused).
    ok, reply = _XSIAM._papi_reply_succeeded({"reply": False})
    assert ok is False
    assert reply is False


def test_papi_reply_succeeded_error_envelope_is_failure():
    ok, reply = _XSIAM._papi_reply_succeeded(
        {"reply": {"err_code": 500, "err_msg": "boom"}}
    )
    assert ok is False
    assert reply == {"err_code": 500, "err_msg": "boom"}


def test_papi_reply_succeeded_top_level_errcode_is_failure():
    ok, _reply = _XSIAM._papi_reply_succeeded({"err_code": 42, "reply": None})
    assert ok is False


def test_papi_reply_succeeded_missing_reply_is_success():
    # No evidence of failure → succeed, but surface the (None) reply.
    ok, reply = _XSIAM._papi_reply_succeeded({})
    assert ok is True
    assert reply is None


def test_papi_reply_succeeded_non_dict_passthrough():
    ok, reply = _XSIAM._papi_reply_succeeded("opaque")
    assert ok is True
    assert reply == "opaque"


def test_ioc_disable_envelope_is_honest_on_false_reply():
    # Belt-and-suspenders: the helper drives the tool's verdict. Construct
    # the same envelope the tool builds for a refusal and a success.
    ok, reply = _XSIAM._papi_reply_succeeded({"reply": False})
    assert ok is False
    err = _XSIAM._xsiam_err("PAPI did not confirm IoC disable", reply=reply,
                            indicators=["1.2.3.4"])
    assert err["ok"] is False and err["success"] is False
    assert err["reply"] is False

    ok2, reply2 = _XSIAM._papi_reply_succeeded({"reply": True})
    assert ok2 is True
    good = _XSIAM._xsiam_ok({"disabled_count": 1, "reply": reply2})
    assert good["ok"] is True and good["success"] is True
    assert good["reply"] is True


# ─────────────────────────────────────────────────────────────────
# JOBS-F10 — _row_to_yaml_doc emits execution-policy fields.
# ─────────────────────────────────────────────────────────────────
def _make_jobrow(**overrides):
    from usecase.job_scheduler import JobRow

    base = dict(
        name="nightly-hunt",
        cron="0 2 * * *",
        timezone="UTC",
        action={"kind": "chat", "prompt": "hunt"},
        enabled=True,
        removed=False,
        last_fired_at=None,
        last_status=None,
        last_error=None,
        next_due_at=None,
        registered_at="2026-06-24T00:00:00Z",
        source="runtime",
    )
    base.update(overrides)
    return JobRow(**base)


def _row_to_yaml_doc(row):
    # Call the instance method without constructing a scheduler (it touches
    # only `row`, never `self`). Bind via the unbound function.
    from usecase.job_scheduler import CroniterJobScheduler

    return CroniterJobScheduler._row_to_yaml_doc.__wrapped__(None, row) \
        if hasattr(CroniterJobScheduler._row_to_yaml_doc, "__wrapped__") \
        else CroniterJobScheduler._row_to_yaml_doc(None, row)


def test_yaml_doc_omits_policy_for_plain_job():
    doc = _row_to_yaml_doc(_make_jobrow())
    for k in ("bypass_approvals", "model_id", "thinking_enabled",
              "permission_policy"):
        assert k not in doc, f"plain job should not write {k}"
    # Core definition fields always present.
    assert doc["name"] == "nightly-hunt"
    assert doc["cron"] == "0 2 * * *"
    assert doc["action"] == {"kind": "chat", "prompt": "hunt"}


def test_yaml_doc_persists_bypass_and_policy():
    row = _make_jobrow(
        bypass_approvals=True,
        model_id="gemini-3.5-flash",
        thinking_enabled=True,
        permission_policy={"deny": ["xsoar_close_incident"]},
    )
    doc = _row_to_yaml_doc(row)
    assert doc["bypass_approvals"] is True
    assert doc["model_id"] == "gemini-3.5-flash"
    assert doc["thinking_enabled"] is True
    assert doc["permission_policy"] == {"deny": ["xsoar_close_incident"]}
    # action stays last so the YAML reads policy-then-action.
    assert list(doc)[-1] == "action"


def test_yaml_doc_round_trips_via_yaml():
    import yaml

    row = _make_jobrow(bypass_approvals=True, model_id="gemini-2.5-pro")
    doc = _row_to_yaml_doc(row)
    reparsed = yaml.safe_load(yaml.safe_dump(doc, sort_keys=False))
    assert reparsed["bypass_approvals"] is True
    assert reparsed["model_id"] == "gemini-2.5-pro"


if __name__ == "__main__":  # pragma: no cover — manual run convenience
    import traceback

    failures = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"PASS {_name}")
            except Exception:  # noqa: BLE001
                failures += 1
                print(f"FAIL {_name}")
                traceback.print_exc()
    raise SystemExit(1 if failures else 0)
