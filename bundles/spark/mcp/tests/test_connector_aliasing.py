"""Regression guard for the connector legacy-alias doubled-prefix bug (#120).

The xsoar tools are authored with the connector prefix already baked into
``spec.tools[].name`` (e.g. ``xsoar_list_incidents``). The flat legacy alias
``f"{functionPrefix}{tool_name}"`` would double it
(``xsoar_`` + ``xsoar_list_incidents`` -> ``xsoar_xsoar_list_incidents``), so
the natural single-prefix name the model / docs / skills call
(``xsoar_list_incidents``) would never be advertised and would 404 at the
agent layer with "Unknown tool". The fix: when the name already carries the
prefix, the name IS the legacy alias — don't re-prepend.
"""

from __future__ import annotations

import glob
import os

import yaml

from usecase.connector_loader import _legacy_alias


def test_bare_name_gets_prefixed():
    # Normal case: spec.tools[].name is bare → alias = prefix + name.
    assert _legacy_alias("foo_", "incidents_list") == "foo_incidents_list"
    assert _legacy_alias("web_", "navigate") == "web_navigate"


def test_already_prefixed_name_is_not_doubled():
    # The #120 bug: the name already carries the prefix → do NOT re-prepend.
    assert _legacy_alias("xsoar_", "xsoar_list_incidents") == "xsoar_list_incidents"
    assert _legacy_alias("xsoar_", "xsoar_get_incident") == "xsoar_get_incident"


def test_no_prefix_returns_none():
    assert _legacy_alias("", "anything") is None


def test_prefixed_tools_resolve_to_natural_single_prefix_names():
    """The xsoar connector authors fully-prefixed spec.tools[].name entries.
    The model-facing alias must be the single-prefix natural name — never a
    doubled prefix — whether the name arrives bare or already prefixed."""
    assert _legacy_alias("xsoar_", "list_incidents") == "xsoar_list_incidents"
    assert _legacy_alias("xsoar_", "xsoar_list_incidents") == "xsoar_list_incidents"


def test_no_bundled_connector_yaml_yields_a_doubled_alias():
    """End-to-end over the real bundle: no connector's (functionPrefix,
    spec.tools[].name) pair may produce a doubled legacy alias. This catches
    a future connector re-introducing the #120 authoring mistake."""
    root = os.path.join(os.path.dirname(__file__), "..", "..", "connectors")
    yamls = glob.glob(os.path.join(root, "*", "connector.yaml"))
    assert yamls, "no connector.yaml files found — wrong path?"
    offenders: list[str] = []
    for cy in yamls:
        spec = yaml.safe_load(open(cy)) or {}
        cid = spec.get("id") or os.path.basename(os.path.dirname(cy))
        fp = (spec.get("runtimeMapping") or {}).get("functionPrefix", "") or ""
        for tool in (spec.get("spec") or {}).get("tools") or []:
            name = tool.get("name")
            if not isinstance(name, str):
                continue
            alias = _legacy_alias(fp, name)
            if alias and fp and alias.startswith(fp + fp):
                offenders.append(f"{cid}: {name!r} (prefix {fp!r}) -> {alias!r}")
    assert not offenders, "doubled legacy aliases found:\n" + "\n".join(offenders)
