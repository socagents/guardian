"""Bundle-aware tool registry — instance-gated edition (stage 3A).

Reads the bundle at boot:
  - manifest.yaml → toolConnectors[]
  - connectors/<id>/connector.yaml → spec.tools[] + runtimeMapping

For each connector that has ≥1 instance in `data_root/instances.db`,
registers the connector's tools with names `<id>.<tool>` (and legacy
`<functionPrefix><tool>` aliases when MCP_LEGACY_TOOL_NAMES=true).
Every registered callable is wrapped in a closure that sets a
contextvar with the instance's config+secrets BEFORE invoking the
underlying connector function — so `get_config()` inside the function
returns the instance-specific values instead of env-var defaults.

Connectors with **zero** configured instances have **none** of their
tools advertised — this is objective 5 from the bundle architecture.

Built-in legacy tools (skills_*, cognitive + self-mod tools) are NOT
instance-gated; they're agent-runtime built-ins that today live in
the embedded MCP for legacy reasons. Phase 2C/3D will move them.

Auto-migration: at startup, for each toolConnectors[] entry with no
instance, if the matching env vars are set, this module materializes
a default instance from them. This preserves existing dev-loop
behavior — operators with the old env-var-driven setup don't need to
re-onboard. Once stage 3C lands the setup-form pipeline, auto-migration
becomes optional.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import logging
import os
from pathlib import Path
from typing import Any, Callable, Iterator, NamedTuple

import yaml

from config.config import (
    config as env_settings,
    reset_current_instance,
    set_current_instance,
)
from usecase.builtin_components import (
    cognitive_tools,
    indicator_tools,
    investigation_tools,
    playbook_tools,
    self_mod_tools,
    skills_crud,
)
from usecase.event_log import event_log
from usecase.instance_store import Instance, InstanceStore
from usecase.secret_store import SecretStore

logger = logging.getLogger("Guardian MCP")


def _emit_tool_failed_event(
    tool: str, error: str | None, duration_ms: int, approval_id: str | None
) -> None:
    """Best-effort emit of `rt.tool.failed` to the observability event log.

    Called from both async + sync wrappers when a tool call raised. The
    audit log already captures the same data via `record_event()` — this
    is the parallel feed for runtime alerting / dashboards declared in
    `manifest.observability.events[]`.

    Returns None on any failure (event log not yet wired, undeclared
    event name, sqlite hiccup); never raises into caller.
    """
    el = event_log()
    if el is None:
        return
    payload: dict[str, Any] = {
        "tool": tool,
        "error": error,
        "duration_ms": duration_ms,
    }
    if approval_id is not None:
        payload["approval_id"] = approval_id
    try:
        el.record("rt.tool.failed", payload=payload, actor="agent")
    except Exception as exc:  # pragma: no cover — record() already swallows
        logger.debug("rt.tool.failed emit suppressed: %s", exc)


class ToolRegistration(NamedTuple):
    """One tool the MCP should register at startup.

    `namespaced_name` is the v1.2 form (`<connector_id>.<tool_name>`).
    `legacy_name` is the pre-v1.2 flat form
    (`<functionPrefix><tool_name>` for connector tools, or just the
    function name for built-ins); None when no legacy alias should
    be registered.
    `connector_id` is None for tools that aren't part of any v1.2
    connector (i.e. runtime built-ins).
    """

    namespaced_name: str
    legacy_name: str | None
    callable: Callable
    connector_id: str | None


def _legacy_alias(function_prefix: str, tool_name: str) -> str | None:
    """Compute the flat (pre-v1.2) legacy alias for a connector tool.

    Normally `f"{function_prefix}{tool_name}"`. But the xsoar tools are
    authored with the connector prefix ALREADY baked into
    `spec.tools[].name`, so naive concatenation DOUBLES it
    (`xsoar_` + `xsoar_list_incidents` -> `xsoar_xsoar_list_incidents`).
    The natural single-prefix name the model / docs / skills call
    ("xsoar_list_incidents") would then never be advertised and would
    404 at the agent layer with "Unknown tool" (#120).

    When the tool name already starts with the prefix, the name IS the
    legacy alias — don't re-prepend. Returns None when no prefix applies.
    """
    if not function_prefix:
        return None
    if tool_name.startswith(function_prefix):
        return tool_name
    return f"{function_prefix}{tool_name}"


# ─────────────────────────────────────────────────────────────────
# Built-in legacy tools — NOT part of any v1.2 connector and NOT
# instance-gated.
# ─────────────────────────────────────────────────────────────────

_BUILTIN_LEGACY_TOOLS: list[tuple[str, Callable]] = [
    ("skills_list_all", skills_crud.skills_list_all),
    ("skills_read", skills_crud.skills_read),
    ("skills_create", skills_crud.skills_create),
    ("skills_update", skills_crud.skills_update),
    # NB: skills_delete is registered below, NOT here. The Phase-11
    # gated wrapper at self_mod_tools.skills_delete intercepts the call,
    # checks manifest.approvals.humanRequired[], and dispatches through
    # gate_and_execute(). Pointing the registration at skills_crud.skills_delete
    # directly would bypass the gate.
    # Phase 8 — cognitive tools (sessions + memory). The agent calls
    # these to manipulate its own conversation history and semantic
    # recall store. Like the skills_* tools, they're agent-runtime
    # built-ins, not connector-mediated, so they bypass the per-
    # instance contextvar wrapper.
    ("memory_store", cognitive_tools.memory_store),
    ("memory_search", cognitive_tools.memory_search),
    ("sessions_list", cognitive_tools.sessions_list),
    ("sessions_history", cognitive_tools.sessions_history),
    # Phase 10 — knowledge base. READ-ONLY at the agent surface; the
    # bundle's manifest.kbWrites: [] enforces that there's no
    # `knowledge_store` counterpart. The KB is populated at boot from
    # `bundles/spark/kbs/<name>/` directories per the manifest's
    # knowledge.bundled[] declaration.
    ("knowledge_search", cognitive_tools.knowledge_search),
    ("knowledge_list", cognitive_tools.knowledge_list),
    # XQL example search — retrieves from the xql-examples KB and enriches
    # each hit with stage-syntax snippets + dataset field lists. Read-only;
    # the retrieval companion to the cortex_xql_query_authoring skill.
    ("xql_examples_search", cognitive_tools.xql_examples_search),
    # v0.2.24 — playbook-builder validator. Pure structural check (no secrets,
    # no catalog mutation) → safe as an agent tool. Paired with the
    # build_xsoar_playbook skill + the /playbooks/build UI.
    ("playbook_validate", playbook_tools.playbook_validate),
    # Phase 11 — agent self-modification (Tier 1: read tools).
    # Lets the agent introspect the same operator-facing state the UI
    # shows: jobs, settings, instances, providers, approvals, audit,
    # api keys, manifest, metrics. None of these are gated — they're
    # pure reads. The corresponding write tools (Tier 2-4) land in
    # later commits, gated via approvals.humanRequired[].
    # See docs/spec-patch-agent-self-modification.md.
    ("jobs_list", self_mod_tools.jobs_list),
    ("jobs_get", self_mod_tools.jobs_get),
    ("jobs_runs", self_mod_tools.jobs_runs),
    ("settings_get", self_mod_tools.settings_get),
    ("personality_get", self_mod_tools.personality_get),
    ("instances_list", self_mod_tools.instances_list),
    ("instances_get", self_mod_tools.instances_get),
    ("providers_list", self_mod_tools.providers_list),
    ("providers_get", self_mod_tools.providers_get),
    ("approvals_list_pending", self_mod_tools.approvals_list_pending),
    ("approvals_list_history", self_mod_tools.approvals_list_history),
    ("notifications_list", self_mod_tools.notifications_list),
    ("notifications_unread_count", self_mod_tools.notifications_unread_count),
    ("audit_search", self_mod_tools.audit_search),
    ("audit_recent", self_mod_tools.audit_recent),
    ("api_keys_list", self_mod_tools.api_keys_list),
    ("manifest_get", self_mod_tools.manifest_get),
    ("metrics_snapshot", self_mod_tools.metrics_snapshot),
    ("health_status", self_mod_tools.health_status),
    # Phase 11 — Tier 2 soft-write tools. Each gates via
    # manifest.approvals.humanRequired[] so the agent can't mutate
    # runtime state without operator confirmation. The
    # _approval_gate.gate_and_execute helper handles the request +
    # wait + execute dance and emits agent_self_mod_* audit events.
    ("jobs_create", self_mod_tools.jobs_create),
    ("jobs_update", self_mod_tools.jobs_update),
    ("jobs_run_now", self_mod_tools.jobs_run_now),
    ("personality_update", self_mod_tools.personality_update),
    # v0.1.23: atomic merge variant. Agent prefers this when changing
    # only a subset of personality fields (e.g. just personalityMd)
    # so it doesn't have to read-then-write to avoid wiping the rest.
    # Same approval gate as personality_update (shares humanRequired
    # key — see self_mod_tools.personality_patch).
    ("personality_patch", self_mod_tools.personality_patch),
    ("settings_update", self_mod_tools.settings_update),
    ("notifications_dismiss", self_mod_tools.notifications_dismiss),
    ("notifications_dismiss_all", self_mod_tools.notifications_dismiss_all),
    ("approvals_resolve", self_mod_tools.approvals_resolve),
    # Phase 11 — Tier 3 destructive tools. Same gate as Tier 2 but
    # risk_tier='destructive' so the approval card UI surfaces a red
    # banner. Each is a thin wrapper around an existing store method
    # (delete_job / delete / reset_to_default / clear).
    ("jobs_delete", self_mod_tools.jobs_delete),
    ("skills_delete", self_mod_tools.skills_delete),
    ("personality_reset", self_mod_tools.personality_reset),
    ("settings_reset", self_mod_tools.settings_reset),
    # ─────────────────────────────────────────────────────────────
    # v0.4.0 agent credential guardrail — DO NOT add credential tools
    # ─────────────────────────────────────────────────────────────
    # The following tools are NOT registered as MCP entries in v0.4.0.
    # They remain available at the REST surface (/api/v1/providers,
    # /api/v1/instances, /api/v1/api_keys) so the operator UI works,
    # but the chat agent has no handle to them:
    #
    #   - instances_delete   (per-instance secrets)
    #   - providers_delete   (Vertex SA JSON, Gemini API key, etc.)
    #   - api_keys_create    (mints plaintext token)
    #   - api_keys_rotate    (mints replacement plaintext)
    #   - api_keys_revoke    (mutates credential state)
    #
    # The agent retains the READ-ONLY surface (providers_list,
    # providers_get, instances_list, instances_get, api_keys_list)
    # — those return secrets redacted as "***".
    #
    # If you're adding a new MCP tool, ask: does it read or write a
    # SecretStore value? If yes, REST-only. See CLAUDE.md "Agent
    # credential guardrail (MANDATORY)" for the full rule.
    # Pre-v0.4.0 these lines registered the tools with
    # `risk_tier="destructive"` / `risk_tier="credential"` gating;
    # v0.4.0 drops them from the agent surface entirely.
    # ─────────────────────────────────────────────────────────────
    # v0.3.10 — Tier 5 multi-action batch. Approval-gated like every
    # other self-mod tool, but the ONE approval card it shows covers
    # N actions; the operator approves the plan once. Each action
    # inside executes under the v0.1.27 bypass contextvar so the
    # nested gate is a no-op (audit-only). See self_mod_tools.
    ("agent_batch_propose", self_mod_tools.agent_batch_propose),
    # Benchmark runner. Agent invokes from chat with "run the <name>
    # benchmark"; the runner dispatches each case in the named bench
    # manifest, scores, and records to benchmark_runs.db. See
    # usecase/benchmark_runner.py.
    ("bench_run", self_mod_tools.bench_run),
    # ─────────────────────────────────────────────────────────────
    # v0.5.0 marketplace tools — CATALOG operations (not credentials)
    # ─────────────────────────────────────────────────────────────
    # Per CLAUDE.md's "catalog boundary ≠ credential boundary"
    # distinction (extending the v0.4.0 agent credential guardrail).
    # These tools mutate marketplace-level metadata (install state,
    # connector schemas, registry membership) — NOT credentials. The
    # operator phrases "install the web connector", "upload this
    # connector.yaml", "remove cortex-docs from the marketplace"
    # are all in-bounds for the agent. The phrase "create an instance
    # of xsoar with these credentials" is NOT (instance creation
    # carries secrets — still operator-only).
    ("marketplace_list", self_mod_tools.marketplace_list),
    ("marketplace_install", self_mod_tools.marketplace_install),
    ("marketplace_uninstall", self_mod_tools.marketplace_uninstall),
    ("connector_upload", self_mod_tools.connector_upload),
    # v0.1.3 — Investigation tools. The agent records investigations
    # locally: opens an Issue, logs activity, fills findings, groups Issues
    # into Cases. Catalog side of the guardrail (investigation metadata, no
    # SecretStore access) — safe to expose to the agent.
    ("issue_create", investigation_tools.issue_create),
    ("issue_update", investigation_tools.issue_update),
    ("issue_add_event", investigation_tools.issue_add_event),
    ("issue_set_attack_chain", investigation_tools.issue_set_attack_chain),
    ("issue_set_relation_graph", investigation_tools.issue_set_relation_graph),
    ("issue_get", investigation_tools.issue_get),
    ("issues_list", investigation_tools.issues_list),
    # v0.2.45 (stage A) — structured investigation outcome: queryable verdict
    # + ATT&CK technique mappings + closure report. Catalog side (no secrets).
    ("issue_set_verdict", investigation_tools.issue_set_verdict),
    ("issue_add_technique", investigation_tools.issue_add_technique),
    ("incidents_by_technique", investigation_tools.incidents_by_technique),
    ("generate_investigation_report", investigation_tools.generate_investigation_report),
    ("case_create", investigation_tools.case_create),
    ("case_add_issue", investigation_tools.case_add_issue),
    ("cases_list", investigation_tools.cases_list),
    ("case_get", investigation_tools.case_get),
    ("case_set_attack_chain", investigation_tools.case_set_attack_chain),
    ("case_set_relation_graph", investigation_tools.case_set_relation_graph),
    # v0.2.0 — Indicators (IoCs extracted from issues + imported from the SOAR).
    # Catalog side of the guardrail (investigation metadata, no SecretStore).
    ("indicator_upsert", indicator_tools.indicator_upsert),
    ("indicators_list", indicator_tools.indicators_list),
    ("indicator_get", indicator_tools.indicator_get),
    ("indicator_relate", indicator_tools.indicator_relate),
]


# ─────────────────────────────────────────────────────────────────
# Bundle path resolution
# ─────────────────────────────────────────────────────────────────

DEFAULT_BUNDLE_ROOT = "/app/bundle"


def _bundle_root() -> Path:
    raw = os.getenv("BUNDLE_ROOT", DEFAULT_BUNDLE_ROOT)
    root = Path(raw).resolve()
    if not root.is_dir():
        raise RuntimeError(
            f"Bundle root {root} does not exist. Set BUNDLE_ROOT env var "
            f"or mount the bundle at {DEFAULT_BUNDLE_ROOT}."
        )
    return root


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


# ─────────────────────────────────────────────────────────────────
# [v0.5.0] Auto-migration deleted.
#
# Pre-v0.5.0 connector_loader had an _AUTO_MIGRATION block that read
# environment variables (PAPI_AUTH_HEADER, etc.) and auto-materialized
# primary-<connector> instances at every boot if those env vars
# resolved. That predated
# the v1.2 InstanceStore + setup form path and survived as a "dev
# convenience" fallback. It's been the source of:
#
#   * "default state = no instances" requirement violations — the
#     operator wants fresh installs to come up clean, but auto-migrate
#     silently fills the instance store from env vars at every boot.
#   * "which path created this instance?" debugging — when a setup
#     form save and auto-migrate both fire in the same boot, the row
#     that survives depends on call order, not operator intent.
#   * Coupling between connector_loader (a loader concern) and env
#     settings (a config concern) that crossed two responsibility
#     boundaries.
#
# v0.5.0 deletes it entirely per Rule 2 of CLAUDE.md's canonical-
# state discipline ("delete legacy paths in the same release"). The
# replacement is explicit:
#
#   1. Operator clicks Install on the marketplace card (or the agent
#      calls marketplace_install via the new Phase-F MCP tool).
#   2. Operator creates an instance via /connectors → Create Instance
#      (or POST /api/v1/instances) — supplying the config + secrets.
#
# The upgrade migration (for v0.4.x customers carrying instances in
# the persisted guardian_data volume) lives in
# `usecase.marketplace_store.MarketplaceStore.upgrade_install_existing_instances`,
# which runs once at boot and auto-installs every connector that
# already has an instance row. Customer experience: nothing visibly
# changes; the connectors they were using stay installed.
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# Tool resolution per spec §7.4.1
# ─────────────────────────────────────────────────────────────────


# Map connector.yaml `type` → Python annotation. Anything outside this
# table falls back to `Any` so the tool still registers; the connector's
# own FastMCP will validate against the JSON Schema it derives from its
# real signature.
_YAML_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _build_container_proxy(
    *,
    connector_id: str,
    tool_name: str,
    args_spec: list[dict[str, Any]],
    description: str,
    proxy_call_tool: Callable,
    instance_names: list[str] | None = None,
) -> Callable:
    """Synthesize an async function whose signature mirrors a connector's
    `connector.yaml` tool args, then forwards the call to the connector's
    container via MCP-over-HTTP.

    Why this exists: FastMCP introspects the function's signature to build
    the MCP tool's input schema (one Pydantic field per parameter) and
    rejects callables that use **kwargs. The container-style branch
    doesn't have a real Python function to register — the actual function
    lives in the connector container — so we synthesize one whose only job
    is to satisfy FastMCP's introspection and forward to proxy_call_tool().

    The body packs all bound parameters into a dict (skipping None for
    optional args, matching agent-side legacy behavior) and POSTs to the
    container. The container's own FastMCP does the real validation
    against its in-process function signatures, so this layer doesn't need
    strict types — `Any` is good enough.
    """
    from config.config import get_config  # noqa: PLC0415

    # Build parameter declarations for compile(). Required args MUST come
    # first (no default), then optional args (with `= None`) — Python's
    # syntax rejects "parameter without a default follows parameter with
    # a default" otherwise. v0.5.0 hot-fix: pre-v0.5.0 the loop appended
    # in YAML order, which produced invalid Python the moment a connector
    # had required-after-optional in its args (a tool with name,
    # description=None, ability_ids in that order — the
    # synthesized signature wouldn't compile). Now we split + concatenate
    # so YAML order is irrelevant to the generated source's validity;
    # the param_names list (used to pack the args dict at call time)
    # still preserves YAML order for human-readable kwarg expansion in
    # logs / errors.
    #
    # Names are sanitized in the extreme case the YAML uses non-identifier
    # characters; today every bundled connector uses snake_case so this is
    # defensive.
    required_decls: list[str] = []
    optional_decls: list[str] = []
    param_names: list[str] = []
    annotations: dict[str, Any] = {}
    for arg in args_spec:
        name = arg.get("name")
        if not isinstance(name, str) or not name.isidentifier():
            # Skip — can't map to a Python parameter cleanly. Container
            # will see no value for this arg; the operator will get a
            # validation error from the container's MCP if it was
            # required. Logged loudly so the bundle author notices.
            logger.warning(
                "connector %r tool %r: skipping arg %r (not a valid Python "
                "identifier); container will not receive it",
                connector_id, tool_name, name,
            )
            continue
        py_type = _YAML_TYPE_MAP.get(arg.get("type", "").lower(), Any)
        annotations[name] = py_type
        if arg.get("required"):
            required_decls.append(name)
        else:
            # `= None` makes it optional; the body filters Nones before
            # forwarding so the container sees an absent key (not a
            # null) and can apply its own default.
            optional_decls.append(f"{name}=None")
        param_names.append(name)

    # v0.2.29 (#43): when a connector has 2+ enabled instances, expose an
    # optional `instance` selector so the agent routes the call to a specific
    # tenant (e.g. XSOAR 6 vs XSOAR 8). It goes in the SIGNATURE (so FastMCP
    # advertises it) but NOT in param_names — the call-time wrapper consumes
    # it and never forwards it to the connector container. Single-instance
    # connectors omit it entirely; their signature stays byte-identical to
    # pre-v0.2.29.
    if instance_names:
        optional_decls.append("instance=None")
        annotations["instance"] = str
        _names = ", ".join(repr(n) for n in instance_names)
        base_desc = description or f"Proxy to {connector_id} container for {tool_name}."
        description = (
            f"{base_desc}\n\nThis connector has multiple configured instances. "
            f"Set the `instance` argument to choose which tenant to act on — one "
            f"of: {_names}. Required while more than one instance is enabled; "
            f"omitting it returns an error listing the valid values."
        )

    param_decls = required_decls + optional_decls

    annotations["return"] = Any
    param_list_src = ", ".join(param_decls)
    pack_src = ", ".join(f"{n!r}: {n}" for n in param_names) or ""

    # Synthesize the function. Source is built from connector.yaml (bundle-
    # immutable, not operator input). We compile + run via the builtins
    # exec primitive aliased to a local name; the closure captures
    # connector_id + tool_name + proxy_call_tool + get_config via the
    # namespace dict because compiled function definitions can't see
    # surrounding-frame locals.
    src = (
        f"async def _proxy({param_list_src}):\n"
        f"    cfg = get_config()\n"
        f"    container_url = getattr(cfg, 'container_url', None)\n"
        f"    if not container_url:\n"
        f"        raise RuntimeError(\n"
        f"            f\"connector {connector_id!r} instance has no \"\n"
        f"            f\"container_url — guardian-updater hasn't started \"\n"
        f"            f\"the container yet, or the routing entry was \"\n"
        f"            f\"deleted. Try recreating the instance via /connectors UI.\"\n"
        f"        )\n"
        f"    args = {{ {pack_src} }}\n"
        f"    args = {{k: v for k, v in args.items() if v is not None}}\n"
        f"    return await proxy_call_tool(container_url, {tool_name!r}, args)\n"
    )
    ns: dict[str, Any] = {
        "get_config": get_config,
        "proxy_call_tool": proxy_call_tool,
        "Any": Any,
    }
    _run = __builtins__["exec"] if isinstance(__builtins__, dict) else __builtins__.exec
    try:
        _run(compile(src, f"<container_proxy:{connector_id}/{tool_name}>", "exec"), ns)
    except SyntaxError as exc:
        raise RuntimeError(
            f"failed to build container proxy for "
            f"{connector_id}/{tool_name}: {exc}\n--- generated source ---\n{src}"
        ) from exc
    fn = ns["_proxy"]
    fn.__name__ = f"proxy_{connector_id}_{tool_name}"
    fn.__qualname__ = fn.__name__
    fn.__doc__ = description or f"Proxy to {connector_id} container for {tool_name}."
    fn.__annotations__ = annotations
    return fn


def _resolve_callable(
    connector_id: str,
    connector_dir: Path,
    spec_yaml: dict,
    instance_kwargs: dict | None = None,
    instance_names: list[str] | None = None,
) -> tuple[list[tuple[str, Callable]], str]:
    """Resolve tool callables for a connector — v0.5.0 container-only path.

    Pre-v0.5.0 this function supported three runtime styles: 'module'
    (in-process import via importlib), 'class' (in-process import +
    instantiate a class), and 'container' (per-instance container,
    tool calls proxied over MCP-over-HTTP). v0.5.0 deletes the module
    and class branches as part of the universal container-mode
    migration — every connector now runs as a per-instance container
    so the dispatch model is uniform.

    The schema-level enforcement (bundles/spark/connectors/connector
    .schema.json) was tightened to reject style != 'container' in the
    same release; this function raises ValueError as a defense-in-
    depth check in case any user-uploaded connector.yaml slips past
    the schema (Phase E upload path validates first; this is the
    second line of defense).

    See `_build_container_proxy` for the synthesized-signature
    machinery FastMCP requires.
    """
    runtime_mapping = spec_yaml.get("runtimeMapping") or {}
    style = runtime_mapping.get("style", "container")
    function_prefix = runtime_mapping.get("functionPrefix", "")

    if style != "container":
        raise ValueError(
            f"connectors/{connector_id}/connector.yaml: runtimeMapping.style "
            f"must be 'container' (got {style!r}). v0.5.0 deleted the "
            f"in-process module/class dispatch paths as part of the "
            f"universal container-mode migration — every connector runs "
            f"as a per-instance guardian-connector-<id>-<name> container."
        )

    # The connector code DOESN'T live in this Python process — it runs
    # in a separate container that the agent reaches via MCP-over-HTTP.
    # We don't importlib here; we synthesize closures that read the
    # per-instance `container_url` from get_config() at call time and
    # forward to proxy_call_tool(). The contextvar plumbing in
    # _wrap_with_instance handles instance binding identically for
    # every connector now.
    from pkg.connector_proxy import proxy_call_tool  # noqa: PLC0415

    pairs: list[tuple[str, Callable]] = []
    tools = (spec_yaml.get("spec") or {}).get("tools") or []
    for tool in tools:
        tool_name = tool.get("name")
        if not isinstance(tool_name, str):
            raise ValueError(
                f"connectors/{connector_id}/connector.yaml: spec.tools[] "
                f"entry missing 'name' (got {tool!r})"
            )

        # FastMCP rejects callables that use **kwargs — it introspects
        # the function signature to derive the MCP tool's input schema
        # (one Pydantic field per parameter) and refuses anything it
        # can't enumerate. So we synthesize a function whose signature
        # mirrors the connector.yaml `args` declaration, then close
        # over `tool_name` and forward to proxy_call_tool().
        args_spec = tool.get("args") or []
        proxy_fn = _build_container_proxy(
            connector_id=connector_id,
            tool_name=tool_name,
            args_spec=args_spec,
            description=tool.get("description") or "",
            proxy_call_tool=proxy_call_tool,
            instance_names=instance_names,
        )
        pairs.append((tool_name, proxy_fn))

    return pairs, function_prefix


# ─────────────────────────────────────────────────────────────────
# Per-instance contextvar wrapping
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# Manifest-key → Settings-attr translation table.
#
# `manifest.yaml:setup.bindsInstances[].template.config` uses clean
# abstract keys (api_url, api_key, etc.) — those are what bundle
# authors write and what the connector.yaml configSchema documents.
# The surviving connectors (xsoar / cortex-docs / web) read these
# clean abstract keys directly, so no translation is needed and the
# table below is empty. The proxy passes keys through unchanged when a
# connector has no entry here. This table exists only so a future
# connector that reads differently-named Settings attributes can map
# manifest keys → Settings names before stuffing the dict into the
# contextvar.
# ─────────────────────────────────────────────────────────────────

_MANIFEST_TO_SETTINGS_KEYS: dict[str, dict[str, str]] = {
    "xsoar": {
        # The xsoar connector ships greenfield with the uniform
        # api_url / api_id / api_key field names and reads them as
        # clean abstract keys (no legacy aliases, no env-var first-
        # time-setup path). The empty dict keeps the connector visible
        # in the registry without forcing any synthetic key
        # translation — keys pass through unchanged.
    },
}


def _translate_keys(connector_id: str, source: dict[str, Any]) -> dict[str, Any]:
    """Translate manifest-style keys to Settings attribute names.

    Keys not in the translation table pass through unchanged — auto-
    migrated instances already use Settings names, so this is a no-op
    for them.
    """
    table = _MANIFEST_TO_SETTINGS_KEYS.get(connector_id, {})
    if not table:
        return source
    return {table.get(k, k): v for k, v in source.items()}


def _wrap_with_instance(
    fn: Callable,
    instances: list[Instance],
    secret_store: SecretStore | None = None,
    tool_name: str | None = None,
    legacy_name: str | None = None,
    human_required: set[str] | None = None,
) -> Callable:
    """Return a wrapper that sets the instance contextvar around `fn`.

    v0.2.29 (#43): `instances` is the connector's list of ENABLED instances.
    When more than one is enabled the wrapper resolves the target at call
    time from the `instance` argument the agent passes (added to the
    synthesized signature by _build_container_proxy); a missing-but-ambiguous,
    unknown, or per-instance-disabled selection raises a tool error instead
    of silently routing to the wrong tenant. With a single enabled instance
    the `instance` argument is absent and that one is used directly —
    behavior identical to pre-v0.2.29.

    Phase 5: secret VALUES are read from the SecretStore on EVERY call
    (not at registration time) so live secret rotation works — change
    the underlying file, next call sees the new value.

    Phase 6: every call records one ACTION_TOOL_CALL audit event, with
    duration_ms and status (success/failure). The actor is tagged
    "agent" — that's the contract: anything coming through the MCP
    tool dispatch is the agent acting on behalf of (a delegated)
    user.

    Phase 7: tools whose name is in `human_required` (drawn from the
    manifest's `approvals.humanRequired`) gate on a human approval
    before executing. The wrapper:
      1. Records ACTION_APPROVAL_REQUESTED in audit
      2. Calls `bus.request(...)` → gets approval_id
      3. Awaits `bus.wait_async(approval_id)` (or sync variant)
      4. Records ACTION_APPROVAL_RESOLVED with resolver + decision
      5. If approved: proceeds to call fn (records tool_call with
         metadata.approved_by + approval_id)
      6. If denied/timeout: raises ApprovalDeniedError or
         ApprovalTimeoutError → caller (the MCP) sees a tool error
         and the agent can react.

    The wrapper preserves fn's signature (via functools.wraps) so
    fastmcp's introspection sees the right Pydantic types / parameter
    names. Both async and sync callables are supported.
    """
    import time as _time

    from usecase.approvals_bus import (
        ApprovalDeniedError,
        ApprovalTimeoutError,
        STATUS_APPROVED,
        STATUS_DENIED,
        STATUS_TIMEOUT,
        approvals_bus,
        needs_human_approval,
    )
    from usecase.audit_log import (
        ACTION_APPROVAL_REQUESTED,
        ACTION_APPROVAL_RESOLVED,
        ACTION_TOOL_CALL,
        record_event,
        set_current_actor,
        reset_current_actor,
    )

    if not instances:
        raise ValueError("_wrap_with_instance requires at least one instance")
    connector_id = instances[0].connector_id
    namespaced = f"{connector_id}.{tool_name}" if tool_name else connector_id
    bare_tool_name = tool_name or namespaced
    multi = len(instances) > 1
    _by_name = {i.name: i for i in instances}
    _by_name_ci = {i.name.lower(): i for i in instances}
    _valid_names = sorted(_by_name)

    # v0.1.20: per-instance `trusted: true` config flag bypasses the human-
    # approval gate (lab/sandbox connectors). v0.2.29 (#43): the BASE
    # requirement is manifest-driven (instance-independent); the per-instance
    # `trusted` bypass is applied per call against the RESOLVED target.
    base_require_approval = needs_human_approval(
        tool_name=bare_tool_name,
        namespaced=namespaced,
        legacy_name=legacy_name,
        human_required=human_required or set(),
        instance_trusted=False,
    )

    def _resolve_target(kwargs: dict[str, Any]) -> Instance:
        """Pop `instance` from kwargs and return the target Instance.

        Raises ValueError (surfaced to the agent as a tool error) when the
        selection is missing-but-ambiguous, unknown, or the tool is disabled
        for the chosen instance — never silently routes to the wrong tenant.
        """
        inst_arg = kwargs.pop("instance", None)
        if inst_arg is not None and str(inst_arg) != "":
            target = _by_name.get(str(inst_arg)) or _by_name_ci.get(
                str(inst_arg).lower()
            )
            if target is None:
                raise ValueError(
                    f"unknown instance {inst_arg!r} for connector "
                    f"{connector_id!r}; valid: {_valid_names}"
                )
        elif not multi:
            target = instances[0]
        else:
            raise ValueError(
                f"connector {connector_id!r} has multiple configured "
                f"instances; pass instance= one of {_valid_names}"
            )
        if bare_tool_name in set(target.disabled_tools or []):
            raise ValueError(
                f"tool {bare_tool_name!r} is disabled for instance "
                f"{target.name!r}"
            )
        return target

    def _overrides_for(target: Instance) -> dict[str, Any]:
        merged = target.merged_config(secret_store=secret_store)
        return _translate_keys(connector_id, merged)

    def _audit_arg_keys(args: tuple, kwargs: dict[str, Any]) -> list[str]:
        # Record only the SHAPE of the call (key names), never the
        # values — args may include credentials passed by the agent.
        keys = list(kwargs.keys())
        if args:
            keys.append(f"<{len(args)} positional>")
        return keys

    def _gate_request(
        target: Instance, args: tuple, kwargs: dict[str, Any],
        require_approval: bool,
    ) -> str | None:
        """Open an approval request if needed; return id or None."""
        if not require_approval:
            return None
        bus = approvals_bus()
        if bus is None:
            # Bus not wired (boot order bug or test harness). Fail
            # closed — better to refuse than to silently bypass.
            raise ApprovalDeniedError(
                f"tool {namespaced} requires human approval but the "
                "approvals bus is not configured"
            )
        # Snapshot args by KEY (no values, identical to audit metadata
        # rule). The approval row needs enough context for the human to
        # decide; the bus's own _sanitize_args defends against value
        # leaks if the caller ever passes raw credentials.
        approval_id = bus.request(
            tool=bare_tool_name,
            namespaced=namespaced,
            actor="agent",
            args={**kwargs} if kwargs else {"<positional>": len(args)},
        )
        record_event(
            ACTION_APPROVAL_REQUESTED,
            target=f"approval:{approval_id}",
            status="pending",
            actor="agent",
            metadata={
                "approval_id": approval_id,
                "tool": namespaced,
                "connector_id": connector_id,
                "instance_id": target.id,
                "arg_keys": _audit_arg_keys(args, kwargs),
            },
        )
        return approval_id

    def _gate_finish(approval_id: str, status: str, reason: str | None) -> None:
        """Record resolution in audit. Raises on non-approved status."""
        bus = approvals_bus()
        approval = bus.get(approval_id) if bus else None
        record_event(
            ACTION_APPROVAL_RESOLVED,
            target=f"approval:{approval_id}",
            status=status,
            actor=approval.resolver if approval and approval.resolver else "system",
            metadata={
                "approval_id": approval_id,
                "tool": namespaced,
                "decision": status,
                "reason": reason,
            },
        )
        if status == STATUS_APPROVED:
            return
        if status == STATUS_TIMEOUT:
            raise ApprovalTimeoutError(
                f"tool {namespaced} not approved within timeout "
                f"(approval_id={approval_id})"
            )
        raise ApprovalDeniedError(
            f"tool {namespaced} denied by {approval.resolver if approval else 'unknown'} "
            f"(approval_id={approval_id}, reason={reason!r})"
        )

    def _audit_meta(
        target: Instance, args: tuple, kwargs: dict[str, Any],
        approval_id: str | None,
    ) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "tool": namespaced,
            "connector_id": connector_id,
            "instance_id": target.id,
            "instance_name": target.name,
            "arg_keys": _audit_arg_keys(args, kwargs),
        }
        if approval_id is not None:
            meta["approval_id"] = approval_id
            bus = approvals_bus()
            approval = bus.get(approval_id) if bus else None
            if approval and approval.resolver:
                meta["approved_by"] = approval.resolver
        return meta

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            target = _resolve_target(kwargs)
            require_approval = base_require_approval and not bool(
                target.config.get("trusted", False)
            )
            token = set_current_instance(_overrides_for(target))
            actor_token = set_current_actor("agent")
            approval_id: str | None = None
            start = _time.perf_counter()
            status = "success"
            error: str | None = None
            try:
                # Phase 7: gate on human approval BEFORE running.
                approval_id = _gate_request(target, args, kwargs, require_approval)
                if approval_id is not None:
                    bus = approvals_bus()
                    decision, reason = await bus.wait_async(approval_id)
                    _gate_finish(approval_id, decision, reason)
                return await fn(*args, **kwargs)
            except Exception as exc:
                status = "failure"
                error = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                duration_ms = int((_time.perf_counter() - start) * 1000)
                meta = _audit_meta(target, args, kwargs, approval_id)
                if error is not None:
                    meta["error"] = error
                record_event(
                    ACTION_TOOL_CALL,
                    target=f"tool:{namespaced}",
                    status=status,
                    actor="agent",
                    duration_ms=duration_ms,
                    metadata=meta,
                )
                # Mirror failures into the runtime-events feed declared
                # in manifest.observability.events[]. Audit captures the
                # same data, but observability is the high-signal stream
                # that operators wire alerts/dashboards to.
                if status == "failure":
                    _emit_tool_failed_event(
                        namespaced, error, duration_ms, approval_id
                    )
                reset_current_actor(actor_token)
                reset_current_instance(token)

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        target = _resolve_target(kwargs)
        require_approval = base_require_approval and not bool(
            target.config.get("trusted", False)
        )
        token = set_current_instance(_overrides_for(target))
        actor_token = set_current_actor("agent")
        approval_id: str | None = None
        start = _time.perf_counter()
        status = "success"
        error: str | None = None
        try:
            approval_id = _gate_request(target, args, kwargs, require_approval)
            if approval_id is not None:
                bus = approvals_bus()
                decision, reason = bus.wait_sync(approval_id)
                _gate_finish(approval_id, decision, reason)
            return fn(*args, **kwargs)
        except Exception as exc:
            status = "failure"
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            meta = _audit_meta(args, kwargs, approval_id)
            if error is not None:
                meta["error"] = error
            record_event(
                ACTION_TOOL_CALL,
                target=f"tool:{namespaced}",
                status=status,
                actor="agent",
                duration_ms=duration_ms,
                metadata=meta,
            )
            # Mirror failures into the runtime-events feed (see async
            # wrapper above for rationale).
            if status == "failure":
                _emit_tool_failed_event(
                    namespaced, error, duration_ms, approval_id
                )
            reset_current_actor(actor_token)
            reset_current_instance(token)

    return sync_wrapper


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────


def iter_registrations(
    include_legacy_aliases: bool = True,
    store: InstanceStore | None = None,
    secret_store: SecretStore | None = None,
) -> Iterator[ToolRegistration]:
    """Yield every tool the MCP should register at startup.

    Phase 5: secret_store is passed through to `_wrap_with_instance`
    so each tool call resolves secrets fresh from the store at call
    time. None defaults to no resolution (legacy values pass through).

    Phase 7: extracts `approvals.humanRequired` from the manifest and
    passes it through to the wrapper. Tools whose name appears in that
    set will gate on a human approval before executing (see
    InProcessApprovalsBus). The set membership is checked against the
    bare tool name, the namespaced form, AND the legacy alias — so the
    bundle author can use whichever form is most readable.
    """
    root = _bundle_root()
    manifest = _load_yaml(root / "manifest.yaml")
    tool_connectors = manifest.get("toolConnectors") or []

    # Phase 7: humanRequired list from manifest.yaml.
    approvals_block = manifest.get("approvals") or {}
    raw_human_required = approvals_block.get("humanRequired") or []
    human_required: set[str] = {
        s for s in raw_human_required if isinstance(s, str)
    }
    if human_required:
        logger.info(
            "Approvals: %d tool(s) require human approval before execution: %s",
            len(human_required), sorted(human_required),
        )

    if store is None:
        store = InstanceStore(secret_store=secret_store)
    if secret_store is None:
        secret_store = SecretStore()

    # v0.5.0: _auto_migrate removed. Tool registration now gates on
    # the union of (marketplace_installs.db install state) AND
    # (instances.db instance presence). Both must be true for the
    # connector's tools to advertise. See connector_loader module
    # header for the deleted-auto-migrate rationale.
    declared_ids = {entry.get("id") for entry in tool_connectors if isinstance(entry.get("id"), str)}
    configured_ids = store.configured_connector_ids()

    advertised: list[str] = []
    skipped: list[str] = []

    for entry in tool_connectors:
        cid = entry.get("id")
        path = entry.get("path")
        if not isinstance(cid, str) or not isinstance(path, str):
            raise ValueError(
                f"manifest.yaml: toolConnectors[] entry missing id/path: {entry!r}"
            )

        if cid not in configured_ids:
            skipped.append(cid)
            continue

        connector_dir = (root / path).resolve()
        connector_yaml = connector_dir / "connector.yaml"
        if not connector_yaml.is_file():
            raise ValueError(f"{connector_yaml} does not exist")
        spec = _load_yaml(connector_yaml)

        # v0.2.42 — emulated services (kind:service) advertise ZERO agent
        # tools. They run as containers that EXTERNAL systems (e.g. an
        # XSOAR server) reach over a published host port; the agent never
        # calls them. Skipping here preserves the credential/catalog
        # boundary — the agent gets no handle to a service, the same way
        # it gets no handle to a credential.
        if (spec.get("kind") or "connector") == "service":
            logger.info(
                "connector %r is kind=service; advertising no agent tools", cid
            )
            skipped.append(cid)
            continue

        # v0.2.29 (#43): register over the connector's ENABLED instances.
        # Pre-v0.2.29 the loader hard-picked instances[0] and bound every
        # tool to it (single-active assumption). Now: a connector with 2+
        # enabled instances exposes an `instance` selector argument (added
        # to the synthesized signature) and the wrapper routes each call to
        # the chosen instance at call time. A connector with rows but none
        # enabled advertises nothing.
        instances = store.list_for(cid)
        enabled = [i for i in instances if i.enabled]
        if not enabled:
            skipped.append(cid)
            continue
        multi = len(enabled) > 1
        instance_names = [i.name for i in enabled]

        pairs, function_prefix = _resolve_callable(
            cid, connector_dir, spec,
            instance_names=instance_names if multi else None,
        )

        # v0.14.0 R4.0 — per-instance disabled-tools filter. With multiple
        # enabled instances the CATALOG hides a tool only if EVERY enabled
        # instance disabled it (intersection); the wrapper enforces each
        # instance's own disabled set at call time (a tool disabled for the
        # SELECTED instance returns a clear error). Single-instance: the
        # intersection is just that instance's disabled set — identical to
        # pre-v0.2.29 behavior. The filter matches the BARE tool name so
        # operator-facing toggle strings stay readable.
        disabled_sets = [set(i.disabled_tools or []) for i in enabled]
        catalog_disabled = (
            set.intersection(*disabled_sets) if disabled_sets else set()
        )
        original_count = len(pairs)
        if catalog_disabled:
            pairs = [(t, f) for (t, f) in pairs if t not in catalog_disabled]
            logger.info(
                "Connector %r: %d/%d tools advertised (disabled across ALL "
                "enabled instances: %s)",
                cid, len(pairs), original_count, sorted(catalog_disabled),
            )
        _names_str = ", ".join(instance_names)
        advertised.append(
            f"{cid} ({_names_str}, {len(pairs)}/{original_count} tools)"
            if catalog_disabled
            else f"{cid} ({_names_str}, {len(pairs)} tools)"
        )

        for tool_name, raw_fn in pairs:
            namespaced = f"{cid}.{tool_name}"
            # The flat legacy alias. _legacy_alias() guards against the
            # doubled-prefix bug (#120) for connectors whose
            # spec.tools[].name already carries the connector prefix.
            legacy = (
                _legacy_alias(function_prefix, tool_name)
                if include_legacy_aliases
                else None
            )
            if legacy == namespaced:
                legacy = None
            wrapped = _wrap_with_instance(
                raw_fn,
                enabled,
                secret_store=secret_store,
                tool_name=tool_name,
                legacy_name=legacy,
                human_required=human_required,
            )
            yield ToolRegistration(namespaced, legacy, wrapped, cid)

    if skipped:
        logger.info(
            "Tool advertisement gated: skipping %d connector(s) without "
            "configured instances: %s",
            len(skipped),
            ", ".join(skipped),
        )
    if advertised:
        logger.info("Advertising connectors: %s", "; ".join(advertised))

    for legacy_name, fn in _BUILTIN_LEGACY_TOOLS:
        yield ToolRegistration(legacy_name, None, fn, None)


# ─────────────────────────────────────────────────────────────────
# Module-level singletons for the hot-reload pipeline.
#
# `set_reload_state(mcp, store, secret_store, tool_registry,
#                   include_legacy)` is called once from main.py after
# the initial registration completes. The /api/v1/admin/reload_tools
# endpoint and the post-setup auto-reload in api/setup.py both pull
# this state to invoke `register_all_tools()` without needing
# explicit DI from every callsite.
# ─────────────────────────────────────────────────────────────────

_reload_state: dict[str, Any] | None = None


def set_reload_state(
    mcp: Any,
    store: InstanceStore,
    secret_store: SecretStore | None,
    tool_registry: dict[str, Any],
    include_legacy: bool,
) -> None:
    global _reload_state
    _reload_state = {
        "mcp": mcp,
        "store": store,
        "secret_store": secret_store,
        "tool_registry": tool_registry,
        "include_legacy": include_legacy,
    }


def reload_tools_now() -> tuple[int, int] | None:
    """Trigger a tool-registry reload using the wired state.
    Returns (newly_namespaced, newly_legacy), or None if not yet wired.
    """
    if _reload_state is None:
        return None
    return register_all_tools(
        mcp=_reload_state["mcp"],
        store=_reload_state["store"],
        secret_store=_reload_state["secret_store"],
        tool_registry=_reload_state["tool_registry"],
        include_legacy=_reload_state["include_legacy"],
    )


def register_all_tools(
    mcp: Any,
    store: InstanceStore,
    secret_store: SecretStore | None,
    tool_registry: dict[str, Any],
    include_legacy: bool = True,
) -> tuple[int, int]:
    """Register every tool that the current InstanceStore + bundle imply.

    Always re-registers (does NOT skip already-registered names). This
    is intentional: when the operator submits the setup form with
    `replace: true`, existing instances are deleted and recreated.
    The OLD wrappers held closure references to the OLD instance
    objects whose secret_refs now point to deleted SecretStore paths;
    re-registering swaps in fresh wrappers with the NEW instance
    references. FastMCP's mcp.tool(name=X) tolerates duplicate-name
    registration (logs a "Component already exists" warning) and
    overrides cleanly — verified empirically on FastMCP 2.13+.

    Returns (namespaced_count, legacy_count) — total counts on this
    pass, NOT just newly added. The hot-reload caller uses the
    returned counts as a sanity signal; the post-setup auto-reload
    response folds them into the operator-visible JSON.

    Used by:
      * `main.py` async_main() at boot — first call, populates from zero.
      * `api/admin.py` /reload_tools endpoint — operator-driven reload.
      * `api/setup.py` POST after replace:true — auto-reload so the
        response can flip `requires_mcp_restart` to false AND the
        connector wrappers see the freshly-materialized instances.
    """
    # Clear the tool_registry first so the dict reflects current
    # state. The previous-pass entries get replaced by the loop below.
    tool_registry.clear()

    namespaced_count = 0
    legacy_count = 0
    for reg in iter_registrations(
        include_legacy_aliases=include_legacy,
        store=store,
        secret_store=secret_store,
    ):
        # Re-register unconditionally. FastMCP overrides on duplicate
        # name; the warning it logs is benign in this pattern.
        mcp.tool(name=reg.namespaced_name)(reg.callable)
        tool_registry[reg.namespaced_name] = reg.callable
        namespaced_count += 1
        if reg.legacy_name and reg.legacy_name != reg.namespaced_name:
            mcp.tool(name=reg.legacy_name)(reg.callable)
            tool_registry[reg.legacy_name] = reg.callable
            legacy_count += 1
    return namespaced_count, legacy_count


def tool_summary(store: InstanceStore | None = None) -> dict[str, int]:
    """Return per-connector tool counts ONLY for connectors with instances.

    Connectors without instances contribute 0 (gated). Built-in legacy
    tools count regardless.
    """
    summary: dict[str, int] = {}
    if store is None:
        store = InstanceStore()
    configured = store.configured_connector_ids()
    root = _bundle_root()
    manifest = _load_yaml(root / "manifest.yaml")
    for entry in manifest.get("toolConnectors") or []:
        cid = entry.get("id")
        if not isinstance(cid, str):
            continue
        spec = _load_yaml((root / entry["path"]).resolve() / "connector.yaml")
        tools = (spec.get("spec") or {}).get("tools") or []
        summary[cid] = len(tools) if cid in configured else 0
    summary["_builtin_legacy"] = len(_BUILTIN_LEGACY_TOOLS)
    return summary
