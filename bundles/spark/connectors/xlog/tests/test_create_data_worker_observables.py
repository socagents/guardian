"""Regression test — the `schema_override` path of `phantom_create_data_worker`
MUST forward `observables_dict` as `observablesDict` in the `createDataWorker`
mutation variables.

Pre-v0.17.106 the schema-override branch built the mutation input with
`type/count/interval/destination/vendor/product/schemaOverride` only and
DROPPED `observablesDict`. Consequence: every forced-field override (a
threat-intel IP, a username, or — critically — a classifier value a modeling
rule keys on via `filter <field> in (...)`) never reached the synthesized
event. XDM capped at 0 for enum-classified vendors (Okta, Alibaba, Qualys,
Azure Flow Logs/WAF/AKS, CyberArk, Proofpoint email), and the shared-CEF-header
Okta SSO stream never routed to its own dataset.

These tests don't hit the network — they patch the GraphQL client to capture
the mutation variables, and patch the URL resolver so no real `ctx` is needed.
"""

from __future__ import annotations

import asyncio
import sys
import types as _types
from pathlib import Path

# `_xlog_url_resolver` / `_graphql_client` transitively import `config.config`
# at module load in some build layouts. Stub it so the test stays hermetic.
if "config.config" not in sys.modules:
    config_pkg = _types.ModuleType("config")
    config_mod = _types.ModuleType("config.config")

    class _Cfg:
        technology_stack = None
        xlog_url = "http://localhost:8000"

    config_mod.get_config = lambda: _Cfg()  # type: ignore[attr-defined]
    config_pkg.config = config_mod  # type: ignore[attr-defined]
    sys.modules["config"] = config_pkg
    sys.modules["config.config"] = config_mod

# Connector root on sys.path so `from src.workers import …` resolves and the
# relative `from ._graphql_client import …` inside it works.
_CONN_ROOT = Path(__file__).resolve().parents[1]
if str(_CONN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CONN_ROOT))

from src import workers  # noqa: E402


class _FakeClient:
    """Captures the (query, variables) passed to execute_query."""

    captured: dict = {}

    def __init__(self, url):  # url comes from the patched resolve_xlog_url
        pass

    async def execute_query(self, query, variables):
        _FakeClient.captured = {"query": query, "variables": variables}
        return {
            "createDataWorker": {
                "worker": "worker_test",
                "type": "CEF",
                "status": "Running",
                "count": "1",
                "interval": "2",
                "destination": "udp:10.10.0.8:514",
                "createdAt": "now",
            }
        }


def _run_worker(**kwargs):
    """Invoke the tool with the GraphQL client + URL resolver patched."""
    orig_client = workers.PhantomGraphQLClient
    orig_resolver = workers.resolve_xlog_url
    workers.PhantomGraphQLClient = _FakeClient
    workers.resolve_xlog_url = lambda ctx: "http://localhost:8000"
    try:
        _FakeClient.captured = {}
        asyncio.run(workers.phantom_create_data_worker(**kwargs))
    finally:
        workers.PhantomGraphQLClient = orig_client
        workers.resolve_xlog_url = orig_resolver
    return _FakeClient.captured.get("variables", {})


def test_schema_override_path_forwards_observables_dict():
    variables = _run_worker(
        type="CEF",
        destination="udp:10.10.0.8:514",
        vendor="Okta",
        product="Okta",
        schema_override=[{"name": "eventType", "type": "string"}],
        observables_dict={"eventType": ["user.session.start"]},
    )
    inp = variables.get("input", {})
    # The schema-override branch must carry observablesDict into the mutation.
    assert "observablesDict" in inp and inp["observablesDict"], inp
    # The seeded classifier value survives normalization (key may be remapped,
    # the value must not be dropped).
    assert "user.session.start" in str(inp["observablesDict"]), inp


def test_schema_override_path_omits_observables_when_absent():
    """Defensive — with no observables_dict, observablesDict is None-stripped
    from the input (no empty key leaking into the mutation)."""
    variables = _run_worker(
        type="CEF",
        destination="udp:10.10.0.8:514",
        vendor="Okta",
        product="Okta",
        schema_override=[{"name": "eventType", "type": "string"}],
    )
    inp = variables.get("input", {})
    assert "schemaOverride" in inp  # sanity: we hit the override branch
    assert "observablesDict" not in inp, inp
