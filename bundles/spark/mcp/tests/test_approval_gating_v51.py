"""v0.2.51 — approval gating closes the un-gated high-impact tool holes:
  #74 XSIAM write/EDR/response tools (isolate, RCE, quarantine, blocklist, …)
  #76 export_to_webhook (was listed but, as an unwrapped built-in, never gated)
  #81 skills_create / skills_update (was un-gated → arbitrary skill authoring)

These pin (a) the manifest data the gate keys on and (b) the wiring that makes
the gate actually fire (async self-gating wrappers + registration target).
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import yaml

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MANIFEST = Path(__file__).resolve().parents[2] / "manifest.yaml"

# A representative slice of the high-impact XSIAM tools that MUST gate.
XSIAM_GATED = [
    "xsiam.endpoints_isolate",
    "xsiam.endpoints_unisolate",
    "xsiam.endpoints_scan_all",
    "xsiam.endpoints_quarantine_file",
    "xsiam.scripts_run_script",
    "xsiam.scripts_run_snippet",
    "xsiam.hash_blocklist",
    "xsiam.ioc_insert_json",
    "xsiam.alert_exclusions_delete",
    "xsiam.distribution_create",
]


def _human_required() -> set[str]:
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return set(m["approvals"]["humanRequired"])


def test_xsiam_edr_tools_are_gated():
    hr = _human_required()
    missing = [t for t in XSIAM_GATED if t not in hr]
    assert not missing, f"XSIAM high-impact tools missing from humanRequired (#74): {missing}"


def test_skills_create_update_are_gated():
    hr = _human_required()
    assert "skills_create" in hr and "skills_update" in hr  # #81


def test_export_to_webhook_is_gated():
    assert "export_to_webhook" in _human_required()  # #76


def test_skills_wrappers_are_async_self_gating():
    from usecase.builtin_components import self_mod_tools as smt
    assert inspect.iscoroutinefunction(smt.skills_create)
    assert inspect.iscoroutinefunction(smt.skills_update)
    # body must route through gate_and_execute
    for fn in (smt.skills_create, smt.skills_update):
        assert "gate_and_execute" in inspect.getsource(fn)


def test_export_to_webhook_is_async_self_gating():
    from usecase.builtin_components import investigation_tools as it
    assert inspect.iscoroutinefunction(it.export_to_webhook)
    assert "gate_and_execute" in inspect.getsource(it.export_to_webhook)


def test_registration_points_at_gated_skill_wrappers():
    from usecase import connector_loader as cl
    from usecase.builtin_components import self_mod_tools as smt
    reg = dict(cl._BUILTIN_LEGACY_TOOLS)
    assert reg["skills_create"] is smt.skills_create  # not skills_crud (ungated)
    assert reg["skills_update"] is smt.skills_update
