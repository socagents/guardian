"""v0.2.29 (#43) — multi-active-instance dispatch in connector_loader.

Covers: the synthesized proxy gains an `instance` parameter only when a
connector has 2+ enabled instances (and never forwards it to the container),
and the wrapper resolves the target instance at call time from that argument
(erroring on ambiguous/unknown rather than silently routing wrong).
"""

import asyncio
import inspect

import pytest

from usecase.connector_loader import _build_container_proxy, _wrap_with_instance
from usecase.instance_store import Instance


def _inst(name: str, url: str, disabled=None) -> Instance:
    return Instance(
        id=f"id-{name}",
        connector_id="xsoar",
        name=name,
        config={"container_url": url},
        secret_refs={},
        created_at="2026-01-01T00:00:00Z",
        enabled=True,
        container_url=url,
        disabled_tools=disabled or [],
    )


# ── synthesized proxy: instance param presence ──────────────────────────

def test_proxy_adds_instance_param_when_multi():
    fn = _build_container_proxy(
        connector_id="xsoar",
        tool_name="list_incidents",
        args_spec=[{"name": "status", "type": "string", "required": False}],
        description="List incidents.",
        proxy_call_tool=lambda *a, **k: None,
        instance_names=["xsoar-v6", "xsoar-v8"],
    )
    params = inspect.signature(fn).parameters
    assert "instance" in params
    assert "status" in params
    assert "xsoar-v6" in (fn.__doc__ or "")
    assert "xsoar-v8" in (fn.__doc__ or "")


def test_proxy_omits_instance_when_single():
    fn = _build_container_proxy(
        connector_id="xsoar",
        tool_name="list_incidents",
        args_spec=[{"name": "status", "type": "string", "required": False}],
        description="List incidents.",
        proxy_call_tool=lambda *a, **k: None,
        instance_names=None,
    )
    assert "instance" not in inspect.signature(fn).parameters


# ── wrapper: call-time instance resolution + routing ────────────────────

async def _container_url_tool(status=None):
    """Stand-in for a synthesized proxy: returns the container_url the
    wrapper routed it to (read from the per-call ContextVar)."""
    from config.config import get_config
    return get_config().container_url


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    import usecase.audit_log as al
    monkeypatch.setattr(al, "record_event", lambda *a, **k: None)


V6 = lambda: _inst("xsoar-v6", "http://guardian-connector-xsoar-xsoar-v6:9000")
V8 = lambda: _inst("xsoar-v8", "http://guardian-connector-xsoar-xsoar-v8:9000")


def test_multi_routes_by_instance_name():
    wrapped = _wrap_with_instance(
        _container_url_tool, [V6(), V8()],
        tool_name="list_incidents", legacy_name=None, human_required=set(),
    )
    assert asyncio.run(wrapped(instance="xsoar-v6")).endswith("xsoar-v6:9000")
    assert asyncio.run(wrapped(instance="xsoar-v8")).endswith("xsoar-v8:9000")


def test_multi_missing_instance_errors_not_silent():
    wrapped = _wrap_with_instance(
        _container_url_tool, [V6(), V8()],
        tool_name="list_incidents", legacy_name=None, human_required=set(),
    )
    with pytest.raises(ValueError, match="multiple configured"):
        asyncio.run(wrapped())


def test_multi_unknown_instance_errors():
    wrapped = _wrap_with_instance(
        _container_url_tool, [V6(), V8()],
        tool_name="list_incidents", legacy_name=None, human_required=set(),
    )
    with pytest.raises(ValueError, match="unknown instance"):
        asyncio.run(wrapped(instance="nope"))


def test_single_instance_needs_no_selector():
    wrapped = _wrap_with_instance(
        _container_url_tool, [V6()],
        tool_name="list_incidents", legacy_name=None, human_required=set(),
    )
    assert asyncio.run(wrapped()).endswith("xsoar-v6:9000")


def test_per_instance_disabled_tool_errors():
    v6 = _inst("xsoar-v6", "http://v6:9000", disabled=["list_incidents"])
    wrapped = _wrap_with_instance(
        _container_url_tool, [v6, V8()],
        tool_name="list_incidents", legacy_name=None, human_required=set(),
    )
    # v8 still works; v6 disabled this tool.
    assert asyncio.run(wrapped(instance="xsoar-v8")).endswith("xsoar-v8:9000")
    with pytest.raises(ValueError, match="disabled for instance"):
        asyncio.run(wrapped(instance="xsoar-v6"))
