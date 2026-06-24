"""Agent self-modification built-in tools — Tier 1 (read-only).

These tools let the agent inspect the same runtime state the operator
sees in the admin UI: jobs, settings, instances, providers, approvals,
notifications, audit log, api keys, manifest, and metrics. They're
the read half of the "agent configures itself via chat" feature
(spec patch in docs/spec-patch-agent-self-modification.md).

# Why "self-modification" includes pure reads

A SOC operator typing "what jobs do I have scheduled?" expects the
agent to actually look — not paraphrase from memory of an older turn.
Without these read tools, the agent has to either (a) lie convincingly
or (b) say "I can't see that". Both are bad. The reads close the
introspection gap; the writes (Tier 2-4, future commits) close the
mutation gap.

# Approval gates

NONE of these tools are gated. They're pure reads: no audit-worthy
state change, no destructive risk. Auditing happens at the underlying
store layer where appropriate (e.g. kb.get_doc emits a
`kb_doc_read` event; instances_get does NOT — connector configs are
read-mostly already).

# Singleton lookup pattern

Each tool resolves its dependency through that store's module-level
singleton (memory_store(), kb_store(), instance_store(), etc.) at
call time. If the runtime didn't wire the store (test harness, early
boot), the tool returns a clean error instead of crashing. Same
convention as cognitive_tools.memory_store / .knowledge_search.

# Schema

Each tool takes plain Python args (FastMCP coerces from JSON-RPC
arguments). Return shape is always `dict[str, Any]` with one of:
  - `{"<resource>s": [...], "count": N}` for list endpoints
  - `{"<resource>": {...}}` for get endpoints
  - `{"error": "..."}` when the underlying store is missing or fails

The agent's chat-route system instruction (Commit 7) teaches it which
tool to reach for given operator phrasing — see the per-tool docstring
for the trigger phrase examples.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("Guardian MCP")


# ─────────────────────────────────────────────────────────────────
# Jobs — agent reads its own scheduled work.
# Trigger phrases: "what jobs are scheduled?", "list my cron jobs",
# "did the daily SOC report run today?", "show me job runs"
# ─────────────────────────────────────────────────────────────────


def jobs_list(source: str | None = None) -> dict[str, Any]:
    """List all scheduled jobs (manifest + runtime).

    Args:
        source: optional filter — "manifest" or "runtime". Null = all.
            Manifest jobs are baked into the bundle; runtime jobs were
            added via the API (and mirror to <data_root>/jobs/*.yaml).

    Returns {jobs: [{name, cron, timezone, action, source, enabled,
                     last_status, next_due_at, ...}], count}.
    """
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}
    jobs = [j.to_dict() for j in s.list_jobs()]
    if source in ("manifest", "runtime"):
        jobs = [j for j in jobs if j.get("source") == source]
    return {"jobs": jobs, "count": len(jobs)}


def jobs_get(name: str) -> dict[str, Any]:
    """Fetch a single job by name (the unique identifier).

    Args:
        name: job name as declared in manifest.jobs[] or POSTed via
            /api/v1/jobs.

    Returns {job: {...}} or {error} on miss.
    """
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}
    j = s.get_job(name)
    if j is None:
        return {"error": f"job {name!r} not found"}
    return {"job": j.to_dict()}


def jobs_runs(name: str, limit: int = 20) -> dict[str, Any]:
    """Recent run history for a job (succeeded + failed).

    Args:
        name: job name.
        limit: max rows (1-200). Default 20.

    Returns {runs: [{run_id, started_at, finished_at, status, result,
                     error}], count}.
    """
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}
    j = s.get_job(name)
    if j is None:
        return {"error": f"job {name!r} not found"}
    limit = max(1, min(int(limit or 20), 200))
    runs = s.list_runs(name, limit=limit)
    return {
        "name": name,
        "runs": [r.to_dict() if hasattr(r, "to_dict") else r for r in runs],
        "count": len(runs),
    }


# ─────────────────────────────────────────────────────────────────
# Settings — runtime overrides over manifest.settings.defaults.
# Trigger phrases: "show my settings", "what model am I using?"
# ─────────────────────────────────────────────────────────────────


def settings_get() -> dict[str, Any]:
    """Snapshot of runtime settings: defaults, overridable allowlist,
    current overrides, and the merged effective values.

    Returns {defaults, overridable, effective, overrides}.

    v0.1.25: was calling s.snapshot() but the store method is named
    describe(); the AttributeError surfaced to the operator as
    "'SqliteSettingsStore' object has no attribute 'snapshot'" on
    every settings_get call. The store's describe() returns exactly
    the {defaults, overridable, effective, overrides} shape this
    docstring promises.
    """
    from usecase.settings_store import settings_store
    s = settings_store()
    if s is None:
        return {"error": "settings store not initialized on this MCP runtime"}
    return s.describe()


# ─────────────────────────────────────────────────────────────────
# Personality — agent reads its own persona doc.
# Trigger phrases: "what's your personality?", "show your system prompt
# overlay", "are you set to concise mode?"
# ─────────────────────────────────────────────────────────────────


def personality_get() -> dict[str, Any]:
    """The agent's current persona — sliders + free-form markdown.

    Returns {personality, updated_at, updated_by, version}.

    The persona document is operator-tunable at runtime via the
    /settings/personality UI page or the Tier-2 `personality_update`
    tool. Reads are cheap (single-row SQLite lookup); the agent should
    consult this when the operator asks about its own configured
    behavior, defaults, or preferences.
    """
    from usecase.personality_store import personality_store
    s = personality_store()
    if s is None:
        return {"error": "personality store not initialized on this MCP runtime"}
    return s.get_or_default().to_dict()


# ─────────────────────────────────────────────────────────────────
# Connector instances — XSOAR, cortex-docs, web config blobs.
# Trigger phrases: "what's my XSOAR URL?", "show me the connector
# instances", "is XSOAR configured?"
# ─────────────────────────────────────────────────────────────────


def instances_list(connector_id: str | None = None) -> dict[str, Any]:
    """List materialized connector instances. Secrets are NEVER
    returned — only secret-slot path references.

    Args:
        connector_id: optional filter — "xsoar", "cortex-docs", "web".
            Null = all.

    Returns {instances: [{id, name, connector_id, config, secret_refs:
                          {slot: path}, created_at, enabled,
                          container_url}], count}.

    v0.6.50: container_url + enabled added to the per-instance dict;
    dead updated_at field removed (the Instance dataclass + schema
    have no updated_at column, so the prior getattr always returned
    None — the docstring promised a field that could never be
    populated). Bug-family fix paired with the HTTP /api/v1/instances
    serializer at bundles/spark/mcp/src/api/instances.py.
    """
    from usecase.instance_store import instance_store
    s = instance_store()
    if s is None:
        return {"error": "instance store not initialized on this MCP runtime"}
    rows = s.list_for(connector_id) if connector_id else s.list_all()
    out = []
    for inst in rows:
        d = {
            "id": inst.id,
            "name": inst.name,
            "connector_id": inst.connector_id,
            "config": dict(inst.config),
            # Expose only the slot names + paths, never values.
            "secret_refs": dict(inst.secret_refs),
            "created_at": getattr(inst, "created_at", None),
            "enabled": getattr(inst, "enabled", True),
            "container_url": getattr(inst, "container_url", None),
        }
        out.append(d)
    return {"instances": out, "count": len(out)}


def instances_get(instance_id: str) -> dict[str, Any]:
    """Fetch one connector instance by id (UUID).

    Returns {instance: {id, name, connector_id, config, secret_refs,
                        created_at, enabled, container_url}} or {error}.
    Secrets are NEVER returned (only paths).

    v0.6.50: container_url + enabled added; dead updated_at field
    removed (no updated_at column exists in the schema). Bug-family
    fix matching instances_list + the HTTP /api/v1/instances
    serializer at bundles/spark/mcp/src/api/instances.py.
    """
    from usecase.instance_store import instance_store
    s = instance_store()
    if s is None:
        return {"error": "instance store not initialized on this MCP runtime"}
    inst = s.get(instance_id)
    if inst is None:
        return {"error": f"instance {instance_id!r} not found"}
    return {
        "instance": {
            "id": inst.id,
            "name": inst.name,
            "connector_id": inst.connector_id,
            "config": dict(inst.config),
            "secret_refs": dict(inst.secret_refs),
            "created_at": getattr(inst, "created_at", None),
            "enabled": getattr(inst, "enabled", True),
            "container_url": getattr(inst, "container_url", None),
        },
    }


# ─────────────────────────────────────────────────────────────────
# Providers — model providers (Vertex, future OpenAI etc).
# Trigger phrases: "what models can I use?", "is Vertex configured?",
# "list my LLM providers"
# ─────────────────────────────────────────────────────────────────


def providers_list(provider_id: str | None = None) -> dict[str, Any]:
    """List materialized provider instances. Secrets redacted (paths only).

    Args:
        provider_id: optional filter — "vertex", future "openai". Null = all.

    Returns {providers: [{id, name, provider_id, config, secret_refs}], count}.
    """
    from usecase.provider_store import provider_store
    s = provider_store()
    if s is None:
        return {"error": "provider store not initialized on this MCP runtime"}
    rows = s.list_for(provider_id) if provider_id else s.list_all()
    out = []
    for p in rows:
        out.append({
            "id": p.id,
            "name": p.name,
            "provider_id": p.provider_id,
            "config": dict(p.config),
            "secret_refs": dict(p.secret_refs),
            "created_at": getattr(p, "created_at", None),
            "updated_at": getattr(p, "updated_at", None),
        })
    return {"providers": out, "count": len(out)}


def providers_get(provider_instance_id: str) -> dict[str, Any]:
    """Fetch one provider instance by id."""
    from usecase.provider_store import provider_store
    s = provider_store()
    if s is None:
        return {"error": "provider store not initialized on this MCP runtime"}
    p = s.get(provider_instance_id)
    if p is None:
        return {"error": f"provider instance {provider_instance_id!r} not found"}
    return {
        "provider": {
            "id": p.id,
            "name": p.name,
            "provider_id": p.provider_id,
            "config": dict(p.config),
            "secret_refs": dict(p.secret_refs),
            "created_at": getattr(p, "created_at", None),
            "updated_at": getattr(p, "updated_at", None),
        },
    }


# ─────────────────────────────────────────────────────────────────
# Approvals — pending + history (this matters because the agent's own
# write-tool calls land here too).
# Trigger phrases: "do I have pending approvals?", "what's waiting on
# my OK?"
# ─────────────────────────────────────────────────────────────────


def approvals_list_pending(limit: int = 50) -> dict[str, Any]:
    """List pending approval requests (not yet approved or rejected).

    Returns {approvals: [{id, tool, args, requested_at, requester_actor,
                          risk_tier}], count}.
    """
    from usecase.approvals_bus import approvals_bus
    bus = approvals_bus()
    if bus is None:
        return {"error": "approvals bus not initialized on this MCP runtime"}
    limit = max(1, min(int(limit or 50), 200))
    rows = bus.list_pending(limit=limit) if hasattr(bus, "list_pending") else []
    return {
        "approvals": [r.to_dict() if hasattr(r, "to_dict") else r for r in rows],
        "count": len(rows),
    }


def approvals_list_history(limit: int = 50) -> dict[str, Any]:
    """List recently-resolved approval requests.

    Returns {approvals: [{id, tool, args, resolved_at, decision, approver_actor}],
             count}.
    """
    from usecase.approvals_bus import approvals_bus
    bus = approvals_bus()
    if bus is None:
        return {"error": "approvals bus not initialized on this MCP runtime"}
    limit = max(1, min(int(limit or 50), 200))
    rows = bus.list_history(limit=limit) if hasattr(bus, "list_history") else []
    return {
        "approvals": [r.to_dict() if hasattr(r, "to_dict") else r for r in rows],
        "count": len(rows),
    }


# ─────────────────────────────────────────────────────────────────
# Notifications — operator inbox.
# Trigger phrases: "any notifications?", "show me unread alerts"
# ─────────────────────────────────────────────────────────────────


def notifications_list(
    unread_only: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """List notifications, newest first.

    Args:
        unread_only: when true, hide already-read notifications.
        limit: max rows (1-500). Default 50.

    Returns {notifications: [...], count}.
    """
    from usecase.notifications import notification_store
    s = notification_store()
    if s is None:
        return {"error": "notification store not initialized on this MCP runtime"}
    limit = max(1, min(int(limit or 50), 500))
    if hasattr(s, "list"):
        rows = s.list(unread_only=bool(unread_only), limit=limit)
    elif hasattr(s, "list_notifications"):
        rows = s.list_notifications(unread_only=bool(unread_only), limit=limit)
    else:
        return {"error": "notification store has no list method"}
    return {
        "notifications": [n.to_dict() if hasattr(n, "to_dict") else n for n in rows],
        "count": len(rows),
    }


def notifications_unread_count() -> dict[str, Any]:
    """How many unread notifications are waiting?

    Returns {unread: N}.
    """
    from usecase.notifications import notification_store
    s = notification_store()
    if s is None:
        return {"error": "notification store not initialized on this MCP runtime"}
    if hasattr(s, "unread_count"):
        n = s.unread_count()
    else:
        # Fallback: count via list().
        rows = s.list(unread_only=True, limit=10000) if hasattr(s, "list") else []
        n = len(rows)
    return {"unread": n}


# ─────────────────────────────────────────────────────────────────
# Audit log — forensic queries on the agent's own behavior.
# Trigger phrases: "show me the last 20 tool calls", "what did the
# agent do at 3pm?", "audit search 'xsoar'"
# ─────────────────────────────────────────────────────────────────


def audit_search(
    q: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    target_prefix: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Search the audit log.

    Args:
        q: free-text match against action/target/metadata. Applied
            client-side after the indexed filters because SqliteAuditLog
            doesn't have a full-text index. Slower than the other
            params; use action/actor/target_prefix when you can.
        action: exact action filter (e.g. "tool_call", "job_fired").
        actor: exact actor filter (e.g. "operator", "scheduler").
        target_prefix: target prefix filter (e.g. "memory:", "kb:cortex-docs:").
        limit: max rows (1-500). Default 50.

    Returns {events: [...], count}.
    """
    from usecase.audit_log import audit_log
    log = audit_log()
    if log is None:
        return {"error": "audit log not initialized on this MCP runtime"}
    limit = max(1, min(int(limit or 50), 500))
    # v0.6.41 — was: `log.search(query=q, action=action, actor=actor,
    # target_prefix=target_prefix, limit=limit)`. SqliteAuditLog has no
    # `search()` method (it's `query()`) AND has no `query=...` free-
    # text param. Pre-v0.6.41 every audit_search invocation raised
    # AttributeError. Same bug family as audit_recent (v0.6.37) — the
    # original CLAUDE.md §7 audit grepped for "audit\.search" but the
    # actual call site was `log.search(...)` which didn't match.
    # Lesson recorded: bug-family greps need to match the CALL pattern
    # (`\.search(`), not just the noun pattern.
    #
    # The fix:
    #   1) Use `log.query(...)` with the parameter names it actually
    #      accepts (action, actor, target_prefix, limit).
    #   2) Honor the historical `q` free-text param by post-filtering
    #      client-side — SqliteAuditLog has no FTS. Applied AFTER the
    #      indexed filters narrow the result set, so this stays
    #      tractable in practice.
    #   3) query() returns list[dict] directly via _row_to_dict; drop
    #      the redundant `r.to_dict() if hasattr(r, "to_dict") else r`.
    rows = log.query(
        action=action or None,
        actor=actor or None,
        target_prefix=target_prefix or None,
        # Overfetch when q is set so post-filtering still has enough
        # to satisfy the caller's `limit` after dropping non-matches.
        limit=(limit * 4 if q else limit),
    )
    if q:
        needle = q.lower()
        rows = [
            r for r in rows
            if needle in (r.get("action") or "").lower()
            or needle in (r.get("target") or "").lower()
            or needle in (r.get("metadata_json") or "").lower()
        ]
        rows = rows[:limit]
    return {
        "events": rows,
        "count": len(rows),
    }


def audit_recent(limit: int = 20) -> dict[str, Any]:
    """Most recent N audit events (cheaper shortcut for the dashboard view).

    Returns {events: [...], count}.
    """
    from usecase.audit_log import audit_log
    log = audit_log()
    if log is None:
        return {"error": "audit log not initialized on this MCP runtime"}
    limit = max(1, min(int(limit or 20), 200))
    # v0.6.37 — was: `log.recent(limit=limit) if hasattr(log, "recent")
    # else log.search(limit=limit)`. Neither method exists on
    # SqliteAuditLog — the canonical query is `query()`. Pre-v0.6.37,
    # the tool raised AttributeError 'SqliteAuditLog object has no
    # attribute search' on every invocation (caught live in
    # session-82f3ee07). The hasattr+fallback pattern was speculative
    # defense for a duck-typed audit_log interface that doesn't exist —
    # there's only one implementation, with one query method. query()
    # already returns list[dict] via _row_to_dict, so the downstream
    # `r.to_dict() if hasattr(r, "to_dict") else r` simplifies to just
    # the dict pass-through.
    rows = log.query(limit=limit)
    return {
        "events": rows,
        "count": len(rows),
    }


# ─────────────────────────────────────────────────────────────────
# API keys — IDs + scopes + last_used. NEVER the secret value.
# Trigger phrases: "what api keys are issued?", "show me my tokens"
# ─────────────────────────────────────────────────────────────────


def api_keys_list() -> dict[str, Any]:
    """List minted API keys. Returns metadata only — the secret value
    is unrecoverable post-mint by design.

    Returns {api_keys: [{id, label, scopes, created_at, last_used_at,
                          revoked}], count}.
    """
    from usecase.api_keys import api_key_store
    s = api_key_store()
    if s is None:
        return {"error": "api key store not initialized on this MCP runtime"}
    rows = s.list() if hasattr(s, "list") else s.list_all()
    out = []
    for k in rows:
        d = k.to_dict() if hasattr(k, "to_dict") else dict(k)
        # Defense-in-depth: scrub anything that looks like a value.
        d.pop("token", None)
        d.pop("secret", None)
        d.pop("hash", None)
        out.append(d)
    return {"api_keys": out, "count": len(out)}


# ─────────────────────────────────────────────────────────────────
# Manifest — the bundle's static config blob. Read-only at runtime
# by spec; agent introspects to know its own capabilities.
# Trigger phrases: "what tools are allowed?", "show the manifest"
# ─────────────────────────────────────────────────────────────────


def manifest_get(section: str | None = None) -> dict[str, Any]:
    """Read the bundle's manifest.yaml. Read-only by spec — runtime
    can never mutate the bundle. Useful for the agent to introspect
    its own contract: which tools are allowed, which require approval,
    which secrets are bound, etc.

    Args:
        section: optional top-level key filter ("tools", "approvals",
            "knowledge", etc.). Null = full manifest.

    Returns {manifest: {...}} or {section: ..., value: {...}}.
    """
    bundle_root = Path(os.getenv("BUNDLE_ROOT", "/app/bundle"))
    manifest_path = bundle_root / "manifest.yaml"
    if not manifest_path.is_file():
        return {"error": f"manifest not found at {manifest_path}"}
    try:
        import yaml  # already a dep via fastmcp
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"failed to parse manifest: {exc}"}
    if not isinstance(data, dict):
        return {"error": "manifest is not a YAML mapping"}
    if section:
        if section not in data:
            return {"section": section, "value": None}
        return {"section": section, "value": data[section]}
    return {"manifest": data}


# ─────────────────────────────────────────────────────────────────
# Metrics — agent self-diagnoses health.
# Trigger phrases: "are you healthy?", "what's your error rate?",
# "show me the embedder stats"
# ─────────────────────────────────────────────────────────────────


def metrics_snapshot(name_prefix: str | None = None) -> dict[str, Any]:
    """Snapshot of all named metrics + their current values. Mirrors
    /api/v1/metrics/snapshot but returns parsed values, not just kinds.

    Args:
        name_prefix: optional filter (e.g. "guardian_embedder_" returns
            just embedder stats).

    Returns {metrics: {name: {kind, values}}, count}.
    """
    from usecase.metrics_registry import metrics_registry
    reg = metrics_registry()
    if reg is None:
        return {"error": "metrics registry not initialized on this MCP runtime"}
    out: dict[str, Any] = {}
    for name in reg.names():
        if name_prefix and not name.startswith(name_prefix):
            continue
        m = reg.get(name)
        if m is None:
            continue
        kind = type(m).__name__.lower()
        # Best-effort value extraction across Counter / Gauge / Histogram.
        values: Any = None
        if hasattr(m, "_values"):
            with getattr(m, "_lock", _NoopLock()):
                # Convert tuple keys (sorted (k,v) pairs) to dict for JSON.
                values = {
                    "" if not k else _format_key(k): v
                    for k, v in m._values.items()
                }
        elif hasattr(m, "_data"):
            values = "histogram (use /api/v1/metrics for buckets)"
        out[name] = {"kind": kind, "values": values}
    return {"metrics": out, "count": len(out)}


class _NoopLock:
    """Context-manager no-op for metrics that don't expose their lock."""
    def __enter__(self) -> None:
        return None
    def __exit__(self, *args: Any) -> None:
        return None


def _format_key(key: tuple[tuple[str, str], ...]) -> str:
    if not key:
        return ""
    return ",".join(f"{k}={v}" for k, v in key)


# ─────────────────────────────────────────────────────────────────
# Health status — agent self-diagnoses ops state.
# Trigger phrases: "are you healthy?", "is everything OK?"
# ─────────────────────────────────────────────────────────────────


def health_status() -> dict[str, Any]:
    """Combined health snapshot: embedder mode, metric registry size,
    pending approvals count, recent error count.

    Returns {ok: bool, embedder_mode, pending_approvals, errors_5min, ...}.

    Determines embedder_mode by inspecting the live `get_embedder()`
    singleton FIRST (most reliable — None means TextHash boot path was
    chosen), then falls back to GUARDIAN_EMBEDDER_MODE env var if the
    singleton accessor isn't available. The env var alone is unreliable
    for cross-process readers (docker exec, subprocess test runners).
    """
    out: dict[str, Any] = {"ok": True}

    # Embedder mode — check the singleton first; the env var is a hint,
    # not authoritative.
    try:
        from usecase.vertex_embedder import get_embedder
        live_embedder = get_embedder()
        if live_embedder is not None:
            out["embedder_mode"] = "vertex"
        else:
            out["embedder_mode"] = os.environ.get(
                "GUARDIAN_EMBEDDER_MODE", "stub"
            )
    except Exception:
        out["embedder_mode"] = os.environ.get("GUARDIAN_EMBEDDER_MODE", "unknown")
    if out["embedder_mode"] != "vertex":
        out["ok"] = False
        out["embedder_warning"] = (
            "Embedder is in stub/unknown mode — semantic search returns "
            "hash-similarity, not real embeddings. Submit Vertex creds via /setup."
        )

    # Approvals pending
    try:
        from usecase.approvals_bus import approvals_bus
        bus = approvals_bus()
        if bus is not None and hasattr(bus, "list_pending"):
            out["pending_approvals"] = len(bus.list_pending(limit=1000))
    except Exception:
        pass

    # Recent error count (audit log)
    try:
        from usecase.audit_log import audit_log
        log = audit_log()
        if log is not None:
            # v0.6.41 — was: `log.search(limit=200) if hasattr(log,
            # "search") else []`. SqliteAuditLog has no .search()
            # method, so the hasattr branch always fell through to []
            # and metrics_health silently reported `errors_recent=0`
            # regardless of actual error volume. Same bug-family as
            # audit_search (line 430) and audit_recent (v0.6.37).
            # query() returns list[dict] directly; the redundant
            # r.to_dict() check below is also dropped.
            recent = log.query(limit=200)
            out["errors_recent"] = sum(
                1 for r in recent if r.get("status") == "failure"
            )
    except Exception:
        pass

    # Vertex embedder error count (mirrors /metrics)
    try:
        from usecase.vertex_embedder import get_embedder
        e = get_embedder()
        if e is not None:
            stats = e.stats()
            out["embedder_errors_total"] = stats.get("error_count", 0)
            out["embedder_upstream_calls_total"] = stats.get("upstream_calls", 0)
            out["embedder_cache_hits"] = stats.get("cache_hits", 0)
    except Exception:
        pass

    return out


# ═════════════════════════════════════════════════════════════════
# TIER 2 — soft-write tools
#
# These mutate runtime state (jobs, settings, personality, notifications)
# and gate via manifest.approvals.humanRequired[]. Each one wraps the
# underlying mutation in `gate_and_execute()` from `_approval_gate`,
# which dispatches through the InProcessApprovalsBus and surfaces a
# pending row in /approvals for operator confirmation.
#
# Trigger phrases the agent recognizes (Commit 7 wires guidance):
#   "schedule a daily SOC report at 8am"     → jobs_create
#   "pause the nightly-report job"            → jobs_update(enabled=False)
#   "run the incident summary now"            → jobs_run_now
#   "always reply in three bullet points"     → personality_update
#   "change my default model to flash"        → settings_update
#   "dismiss notification N"                  → notifications_dismiss
#   "approve approval ABC"                    → approvals_resolve
# ═════════════════════════════════════════════════════════════════


# ─── Jobs (3 tools) ─────────────────────────────────────────────


async def jobs_create(
    name: str,
    cron: str,
    action: dict[str, Any],
    timezone: str = "UTC",
    enabled: bool = True,
    run_once: bool = False,
    bypass_approvals: bool = False,
    model_id: str | None = None,
    thinking_enabled: bool = False,
    permission_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Schedule a new runtime job. Approval-gated.

    Args:
        name: unique identifier (filesystem-safe; no slashes, dots).
        cron: 5-field expression (POSIX cron).
        action: discriminated by `type` — one of:

            type="prompt" — fire an agent turn against this agent:
              {"type": "prompt",
               "message": "...",
               "skill"?: "<canonical_skill_name>",
               "session_id"?: "..."}

              (`chat` is an accepted legacy alias — the scheduler
              migrates stored `chat` actions to `prompt` at boot;
              new jobs should use `prompt`.)

              `skill` (optional) pins which skill the prompt turn loads
              into its system prompt. The scheduler injects the
              skill's MD content into the dispatched turn as
              <skill name="..."> ... </skill>, so the agent enters the
              conversation with that skill already in context. Set
              this when the operator's request names a specific
              skill — e.g. "run the incident-triage skill every
              morning". When omitted, the agent picks a skill at
              runtime based on the message content (good for open-
              ended prompts like "summarize last night's alerts").

            type="tool_call" — invoke an MCP tool with args:
              {"type": "tool_call", "name": "<tool_name>",
               "args": { ...tool_request_body... }}

        timezone: IANA TZ name. Default UTC.
        enabled: schedule starts active. Default true.
        run_once: auto-disable after first fire. Default false.
        bypass_approvals: when true, the job runs without firing the
            Phase-11 approval gate for any destructive tool it calls
            (e.g. skills_delete, settings_reset). Default false — the
            safe default; every destructive tool needs operator
            confirmation. Set true ONLY when the operator explicitly
            says they trust the job to run unattended — concrete
            trigger phrases: "don't ask me each time", "auto-approve
            this job", "run unattended", "set it and forget it".
            The audit log records every bypass-fired tool with
            `auto_approved=true` and `bypass_source=job:<name>` so
            post-hoc review still surfaces what ran. Off by default
            because once a job is bypassed it can do destructive work
            at 3am without the operator looking — match the operator's
            stated intent, don't infer it.
        model_id: per-job model override (v0.5.22+ / Issue #22).
            When set, the job's chat dispatches send `body.model =
            <id>` so the chat route's resolveModelName picks it over
            the runtime default (runtimeConfig.GEMINI_MODEL). Use
            cheap models for high-volume / triage workloads
            ("gemini-2.5-flash") and reserve the default for tasks
            where quality matters. Concrete trigger phrases: "run
            this job on flash", "use gemini-pro for the nightly
            summary", "run this on the cheap model". Omit (default
            None) to use whatever the runtime is configured for at
            dispatch time.
        thinking_enabled: extended-thinking toggle (v0.5.22+ / Issue
            #22). When true, the job's dispatch carries `body.thinking
            = true` so the model uses its extended-reasoning path
            (Gemini's thinkingConfig — only honored on Pro variants;
            flash models silently ignore). Set when the operator says
            "use deep thinking", "give it more reasoning room",
            "extended thinking for this job". Default false. NOTE:
            v0.5.22 ships this as the storage + dispatch path; the
            chat-route side of the thinking integration lands in a
            follow-up release. Today, the body.thinking field is
            received but not yet acted on by the route's Gemini call
            builder — visible-fail-no-effect, not crash-fail.
        permission_policy: per-job tool allowlist (v0.5.23+ / Issue
            #23). Declarative policy enforced by the chat-route's
            tool-dispatch loop: before each tool fires, the loop
            evaluates the policy and may short-circuit with a deny
            (the model sees a tool-error result, the chat thread
            surfaces the denial reason). Shape:
                {
                  "allowed_tools": ["pattern", ...],
                  "denied_tools": ["pattern", ...],
                  "require_approval": ["pattern", ...]
                }
            Patterns are globs (same as HookMatcher.toolGlob: `*`, `?`,
            comma-separated lists). Set when the operator scopes the
            job — concrete trigger phrases: "only let this job touch
            xsoar tools", "don't let this job call any web
            tools", "approve any *_delete this job tries". Omit /
            pass None to leave the policy unrestricted (the runtime
            default). Example: `{"allowed_tools": ["xsoar_*"],
            "denied_tools": ["*_delete"]}` restricts the job to xsoar
            tools AND blocks destructive deletes within that family.
            Evaluation order: denied beats allowed beats
            require_approval beats default-allow.

    Returns the persisted job row on success.

    Trigger phrases: "schedule a daily X at Y", "create a cron job
    that does Z every Monday morning", "summarize open incidents once now".

    Idempotency discipline (v0.3.8+): BEFORE creating a job, call
    `jobs_list()` and check whether a job with the same intent already
    exists. The agent has historically duplicated jobs when the
    operator phrases the request slightly differently across turns
    ("schedule a malicious-email skill every 15 minutes" → creates
    `skill-malicious-email-15min`; then "create an email-malware job
    every 15 minutes" → creates `email-malware-15min` instead of
    recognizing it's the same scheduled work). When a likely duplicate
    is detected, prefer `jobs_update()` to modify the existing job
    over creating a near-duplicate. Distinguish "same intent" via the
    triple (cron expression, action.type, action.skill OR
    action.message gist) — exact name match is too narrow, exact
    payload match is too wide.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        row = s.add_job(
            name=name, cron=cron, timezone_name=timezone,
            action=action, enabled=enabled, run_once=run_once,
            bypass_approvals=bypass_approvals,
            model_id=model_id,
            thinking_enabled=thinking_enabled,
            permission_policy=permission_policy,
        )
        return {"job": row.to_dict() if hasattr(row, "to_dict") else None}

    try:
        return await gate_and_execute(
            tool_name="jobs_create",
            args={
                "name": name, "cron": cron, "action": action,
                "timezone": timezone, "enabled": enabled, "run_once": run_once,
                "bypass_approvals": bypass_approvals,
                "model_id": model_id,
                "thinking_enabled": thinking_enabled,
                "permission_policy": permission_policy,
            },
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "jobs_create"}


async def jobs_update(
    name: str,
    cron: str | None = None,
    timezone: str | None = None,
    action: dict[str, Any] | None = None,
    enabled: bool | None = None,
    bypass_approvals: bool | None = None,
    model_id: str | None = None,
    thinking_enabled: bool | None = None,
    permission_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Modify an existing runtime job. Approval-gated.

    Only fields supplied as non-None get patched; everything else
    stays. To pause a job, call with `enabled=False`. To change the
    cadence, pass `cron`. Manifest jobs (source='manifest') ignore
    most updates and revert at next boot — see job_scheduler docs.

    Args:
        name: the job's canonical name (required for the patch lookup).
        cron: 5-field POSIX cron expression. Pass to change the cadence;
            omit to keep the current schedule.
        timezone: IANA TZ name. Omit to keep current.
        action: discriminated-union job action — same shape as
            jobs_create's action arg (type=prompt / tool_call).
            See jobs_create docstring for the full action shape
            including the `skill` field on the prompt action and the
            `format`-vs-`log_type` gotcha on the (legacy) log action.
        enabled: false to pause the cron, true to resume. Omit to
            keep current state.
        bypass_approvals: toggle the per-job auto-approval flag.
            When true, every dispatch for this job carries
            `X-Guardian-Approval-Bypass: 1` so the MCP-side Phase-11
            gate skips the operator-confirmation dance for tools in
            manifest.approvals.humanRequired[]. Audit rows still
            record each fired tool with `auto_approved=true` and
            `bypass_source=job:<name>` so post-hoc review surfaces
            what ran unattended. Set ONLY when the operator
            explicitly asks ("auto-approve from now on", "stop
            asking me each time", "run unattended"). Omit to keep
            current value.
        model_id: per-job model override (v0.5.22+ / Issue #22).
            Sentinel semantics: omit / None to preserve the current
            override; empty string "" to CLEAR the override (revert
            to runtime default); any other string to set to that
            model id. Example payloads: `{"model_id": "gemini-2.5-
            flash"}` to switch to flash; `{"model_id": ""}` to
            clear; omitting the field entirely leaves the existing
            value untouched. See jobs_create for the full discussion
            of when to set it.
        thinking_enabled: toggle extended thinking on/off for this
            job's dispatches (v0.5.22+). Tri-state — omit to keep
            current, true / false to set. See jobs_create's docstring
            for the v0.5.22 visible-fail-no-effect caveat.
        permission_policy: per-job tool allowlist (v0.5.23+).
            Sentinel semantics: omit / None to preserve the existing
            policy; `{}` (empty dict) to clear the policy (revert to
            no restrictions); non-empty dict to set. See jobs_create
            for the full policy shape + glob syntax discussion.

    Returns the updated job row on success.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        row = s.update_job(
            name,
            cron=cron, timezone_name=timezone,
            action=action, enabled=enabled,
            bypass_approvals=bypass_approvals,
            model_id=model_id,
            thinking_enabled=thinking_enabled,
            permission_policy=permission_policy,
        )
        return {"job": row.to_dict() if hasattr(row, "to_dict") else None}

    try:
        return await gate_and_execute(
            tool_name="jobs_update",
            args={
                k: v for k, v in {
                    "name": name, "cron": cron, "timezone": timezone,
                    "action": action, "enabled": enabled,
                    "bypass_approvals": bypass_approvals,
                    "model_id": model_id,
                    "thinking_enabled": thinking_enabled,
                    "permission_policy": permission_policy,
                }.items() if v is not None
            },
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "jobs_update"}


async def jobs_run_now(name: str) -> dict[str, Any]:
    """Trigger a job immediately, outside its cron schedule.
    Approval-gated.

    Useful for "run the incident summary now" or "test that the
    nightly summary still works." The job's regular schedule is
    unaffected — the next regular fire still happens.

    Returns {run: {...}} with the run record on success.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}

    async def _exec() -> dict[str, Any]:
        run = await s.trigger_now(name)
        return {"run": run.to_dict() if hasattr(run, "to_dict") else None}

    try:
        return await gate_and_execute(
            tool_name="jobs_run_now",
            args={"name": name},
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "jobs_run_now"}


# ─── Personality (1 tool) ───────────────────────────────────────


async def personality_update(blob: dict[str, Any]) -> dict[str, Any]:
    """Replace the agent's persona document. Approval-gated.

    The approval row carries the full proposed blob; the operator's
    UI (Commit 6) renders a diff against the current version so they
    see exactly what's changing before approving.

    Args:
        blob: the full new personality. MUST be a dict matching the
            shape returned by `personality_get` — agent should fetch
            current, modify, then update with the full new object
            (read-modify-write). Partial/unknown keys are accepted but
            unused fields are silently dropped on next read.

    Returns {personality, updated_at, updated_by, version}.

    Trigger phrases: "always answer in three bullet points",
    "be more concise", "raise your proactivity", "update the
    personality so you cite incident IDs more aggressively".
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.personality_store import personality_store
    s = personality_store()
    if s is None:
        return {"error": "personality store not initialized on this MCP runtime"}
    if not isinstance(blob, dict):
        return {"error": "blob must be a JSON object"}

    def _exec() -> dict[str, Any]:
        updated = s.put(blob, actor="agent")
        return updated.to_dict()

    try:
        return await gate_and_execute(
            tool_name="personality_update",
            args={"blob_keys": sorted(blob.keys())},  # full blob would
            # bloat the approval row; keys alone tell the operator
            # what's changing; the diff is computed at render time.
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "personality_update"}


async def personality_patch(updates: dict[str, Any]) -> dict[str, Any]:
    """Atomic merge update for the agent's persona. Approval-gated.

    Like `personality_update` but does the read-modify-write inside
    one call: fetches the current blob, shallow-merges `updates` over
    it, and writes the result. The agent doesn't have to remember to
    fetch first — calling

        personality_patch({"personalityMd": "...new markdown..."})

    is safe and won't wipe the other fields (actionPolicy, model,
    notifications, etc.) the way a naive
    `personality_update({"personalityMd": "..."})` would.

    Args:
        updates: keys to set/replace. A shallow merge — top-level keys
            in `updates` overwrite the current blob's same-named keys;
            unspecified keys pass through unchanged.

    Returns {personality, updated_at, updated_by, version}.

    Approval gate: this tool requests approval under the same
    `personality_update` name (manifest's humanRequired list keys on
    bare names, and patch is semantically the same operation as
    update — different ergonomics, identical risk surface). The
    approval row's `args.blob_keys` lists ONLY the keys being
    patched, so operators see "agent wants to change `personalityMd`"
    instead of the noisier full-blob keylist.

    Trigger phrases: "be more concise", "update your personality.md
    to add a guideline about citing incident IDs", "soften your
    tone".
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.personality_store import personality_store
    s = personality_store()
    if s is None:
        return {"error": "personality store not initialized on this MCP runtime"}
    if not isinstance(updates, dict):
        return {"error": "updates must be a JSON object"}
    if not updates:
        return {"error": "updates must be non-empty"}

    def _apply() -> dict[str, Any]:
        current = s.get_or_default().blob
        merged = {**current, **updates}
        updated = s.put(merged, actor="agent")
        return updated.to_dict()

    try:
        return await gate_and_execute(
            # v0.1.27: use the actual tool name for the gate.
            # Pre-v0.1.27 we aliased to "personality_update" to share
            # the manifest entry — but the chat-side `isToolGated()`
            # check keys on the agent-facing tool name (the one Gemini
            # sees + dispatches), not the gate's internal name. With
            # the alias, isToolGated("personality_patch") returned
            # false → no inline approval card → silent 5-min hang.
            # `personality_patch` now has its own humanRequired entry
            # in manifest.yaml, so this rename is safe and the
            # approval row + audit trail correctly distinguish patches
            # from full-replace updates (operators can see "agent
            # wants to patch personalityMd" instead of the noisier
            # "agent wants to update personality").
            tool_name="personality_patch",
            args={"blob_keys": sorted(updates.keys()), "patch": True},
            risk_tier="soft",
            executor=_apply,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "personality_patch"}


# ─── Settings (1 tool) ──────────────────────────────────────────


async def settings_update(
    updates: dict[str, Any] | None = None,
    clear: list[str] | None = None,
) -> dict[str, Any]:
    """Set or clear runtime settings overrides. Approval-gated (soft).

    Only keys in manifest.settings.overridable[] can be modified; others
    are returned in `rejected[]` rather than mutating anything. The
    current allow-list (Spark bundle) is:

        - geminiModel                       (default model name)
        - setupUiUser                       (operator's display name)
        - requireHumanApprovalForOperations (bool — toggles bundle-wide
                                             approval gate)

    Anything else (random env names, secrets, MCP internals) is silently
    rejected — those go through `instances_create` (connector creds) or
    `providers_create` (provider creds), not here.

    Args:
        updates: {key: value} pairs to set. Values must JSON-serialize.
        clear:   keys to revert to manifest defaults (omit/null = no clear).

    Returns {applied, cleared, rejected}. There is no bypass_approvals
    knob on this tool; if the session's approval mode is "manual" the
    operator approves once in the UI. If "bypass", the call still goes
    through but the operator sees it in the audit log.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.settings_store import settings_store
    s = settings_store()
    if s is None:
        return {"error": "settings store not initialized on this MCP runtime"}
    updates = updates or {}
    clear = clear or []

    def _exec() -> dict[str, Any]:
        applied: list[str] = []
        cleared: list[str] = []
        rejected: list[dict[str, Any]] = []
        for k, v in updates.items():
            try:
                s.set(k, v, actor="agent")
                applied.append(k)
            except PermissionError as pe:
                rejected.append({"key": k, "reason": str(pe)})
        for k in clear:
            try:
                if s.clear(k, actor="agent"):
                    cleared.append(k)
            except PermissionError as pe:
                rejected.append({"key": k, "reason": str(pe)})
        return {
            "applied": applied, "cleared": cleared, "rejected": rejected,
        }

    try:
        return await gate_and_execute(
            tool_name="settings_update",
            args={
                "update_keys": sorted(updates.keys()),
                "clear": list(clear),
            },
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "settings_update"}


# ─── Notifications (2 tools) ────────────────────────────────────


async def notifications_dismiss(notification_id: str) -> dict[str, Any]:
    """Mark one notification as read/acknowledged. Approval-gated
    (low risk but worth a one-click confirm so the agent can't silently
    hide alerts the operator cares about).

    Returns {dismissed: bool}.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.notifications import notification_store
    store = notification_store()
    if store is None:
        return {"error": "notification store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        ok = store.ack(notification_id)
        return {"dismissed": bool(ok), "id": notification_id}

    try:
        return await gate_and_execute(
            tool_name="notifications_dismiss",
            args={"notification_id": notification_id},
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "notifications_dismiss"}


async def notifications_dismiss_all(
    target: str | None = None,
) -> dict[str, Any]:
    """Mark every unread notification as read.
    Approval-gated.

    Args:
        target: optional filter ("user:operator", "channel:soc").
            Null = all targets.

    Returns {dismissed: N}.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.notifications import notification_store
    store = notification_store()
    if store is None:
        return {"error": "notification store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        # NotificationStore.list signature varies; use whichever exists.
        if hasattr(store, "list"):
            rows = store.list(unread_only=True, limit=10000)
        elif hasattr(store, "list_notifications"):
            rows = store.list_notifications(unread_only=True, limit=10000)
        else:
            return {"error": "notification store has no list method"}
        if target:
            rows = [
                r for r in rows
                if (r.target if hasattr(r, "target") else r.get("target")) == target
            ]
        n = 0
        for r in rows:
            rid = r.id if hasattr(r, "id") else r.get("id")
            if rid and store.ack(rid):
                n += 1
        return {"dismissed": n}

    try:
        return await gate_and_execute(
            tool_name="notifications_dismiss_all",
            args={"target": target} if target else {},
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "notifications_dismiss_all"}


# ─── Approvals (1 tool) ─────────────────────────────────────────


async def approvals_resolve(
    approval_id: str,
    decision: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Resolve a pending approval. Approval-gated (yes — gating the
    gate-resolver looks recursive, but it's correct: an agent that
    can resolve random approvals would defeat the human-in-the-loop
    contract entirely. The bus's actor != resolver check additionally
    prevents self-resolution at the storage level.

    The operator's preferred way to resolve approvals is the
    /approvals UI. This tool exists for flows where the operator
    explicitly tells the agent to do it — e.g. "approve the latest
    pending approval and tell me what changed."

    Args:
        approval_id: UUID of a pending row.
        decision: "approved" | "denied" (or aliases).
        reason: optional human-readable note.

    Returns the resolved approval row.
    """
    from usecase.approvals_bus import ApprovalSelfResolveError, approvals_bus
    from usecase.builtin_components._approval_gate import gate_and_execute
    bus = approvals_bus()
    if bus is None:
        return {"error": "approvals bus not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        # NOTE: the bus's resolve() RAISES ApprovalSelfResolveError if
        # the resolver matches the original requester (see
        # bus.resolve). We pass actor="agent" — if the agent is asked
        # to resolve an approval IT initiated, this raises and we
        # surface the error to the agent's reply.
        resolved = bus.resolve(
            approval_id, resolver="agent",
            decision=decision, reason=reason,
        )
        if resolved is None:
            return {"error": f"approval {approval_id!r} not found"}
        return {"approval": resolved.to_dict()}

    try:
        return await gate_and_execute(
            tool_name="approvals_resolve",
            args={"approval_id": approval_id, "decision": decision},
            risk_tier="soft",
            executor=_exec,
        )
    except ApprovalSelfResolveError as exc:
        # #HOOK-F10 — the agent attempting to approve its OWN request. The bare
        # except below would have swallowed this into an opaque {error} with no
        # trace; record the blocked attempt so the self-resolve guard is visible
        # in /observability/events.
        from usecase.audit_log import (
            ACTION_APPROVAL_SELF_RESOLVE_BLOCKED,
            record_event,
        )
        record_event(
            ACTION_APPROVAL_SELF_RESOLVE_BLOCKED,
            target=f"approval:{approval_id}",
            status="failure",
            actor="agent",
            metadata={
                "approval_id": approval_id,
                "resolver": "agent",
                "decision": decision,
                "via": "tool",
            },
        )
        return {"error": str(exc), "tool": "approvals_resolve"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "approvals_resolve"}


# ═════════════════════════════════════════════════════════════════
# TIER 3 — destructive tools
#
# Each one IRRECOVERABLY removes data: a scheduled job, a custom
# skill file, a connector instance, a provider, an entire personality
# blob. Same gate machinery as Tier 2 but with `risk_tier="destructive"`
# so the approval card UI (Commit 6) renders a red banner and the
# operator's audit trail is filterable on agent_self_mod_executed
# WHERE risk_tier='destructive'.
#
# Trigger phrases:
#   "delete the nightly-report job"                → jobs_delete
#   "remove the legacy skill X"                    → skills_delete
#   "reset my personality to defaults"             → personality_reset
#   "clear the geminiModel override"               → settings_reset
#   "delete the primary-xsoar instance"            → instances_delete
#   "remove the secondary-vertex provider"         → providers_delete
# ═════════════════════════════════════════════════════════════════


async def jobs_delete(name: str) -> dict[str, Any]:
    """Permanently remove a runtime job. Approval-gated (destructive).

    Manifest jobs (source='manifest') can be removed via this tool;
    they reappear on next boot from the manifest. Runtime jobs are
    gone for good — their YAML mirror at <data_root>/jobs/<name>.yaml
    is also removed (see job_scheduler._remove_job_yaml).

    Returns {deleted: bool, name}.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.job_scheduler import scheduler
    s = scheduler()
    if s is None:
        return {"error": "scheduler not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        ok = s.delete_job(name)
        return {"deleted": bool(ok), "name": name}

    try:
        return await gate_and_execute(
            tool_name="jobs_delete",
            args={"name": name},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "jobs_delete"}


async def skills_delete(file_path: str) -> dict[str, Any]:
    """Permanently remove a skill markdown file. Approval-gated
    (destructive).

    Wraps the un-gated `skills_crud.skills_delete` function with the
    Phase-11 approval gate. The connector_loader registration for
    `skills_delete` points at THIS function (not skills_crud.skills_delete
    directly) so the gate is always enforced.

    Args:
        file_path: Relative path to skill file (e.g.,
                   'workflows/investigate_incident.md'). Parameter name MUST match
                   the underlying skills_crud.skills_delete signature
                   AND the legacy MCP Tool inputSchema in
                   skills_crud.py — both expect `file_path`. Pre-v0.3.4
                   this wrapper renamed the parameter to `name` for
                   readability, which silently broke the entire delete
                   surface: the Next.js /api/skills DELETE route
                   passed `file_path` per the legacy schema, FastMCP's
                   per-tool validator (derived from THIS function's
                   signature) rejected it as "Unexpected keyword
                   argument," and the Pydantic error string got
                   wrapped into the tool's result content. The Next.js
                   side then JSON.parse'd the error string and threw
                   "Unexpected non-whitespace character after JSON at
                   position 2" — because the error text starts with
                   "2 validation errors..." and the literal `2` at
                   index 2 is the third byte after the quote prefix.
                   Confusing diagnostic; one-line fix.

    Returns the underlying skills_crud result on success.
    """
    from usecase.builtin_components import skills_crud
    from usecase.builtin_components._approval_gate import gate_and_execute

    def _exec() -> dict[str, Any]:
        # skills_crud.skills_delete returns a JSON-encoded string;
        # parse it back so the gate's caller (the MCP tool result
        # content path) gets a structured dict it can compose into
        # its own response shape consistently with the other Phase-11
        # gated wrappers in this module (jobs_delete, settings_reset,
        # etc.) which all return dicts.
        import json as _json
        raw = skills_crud.skills_delete(file_path)
        try:
            return _json.loads(raw) if isinstance(raw, str) else raw
        except (_json.JSONDecodeError, TypeError):
            # Fall through with raw string wrapped — extreme defensive
            # path; should never trigger because skills_crud.skills_delete
            # always returns json.dumps(dict).
            return {"success": True, "raw": raw}

    try:
        return await gate_and_execute(
            tool_name="skills_delete",
            args={"file_path": file_path},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "skills_delete"}


async def skills_create(category: str, filename: str, content: str) -> dict[str, Any]:
    """Create a new skill markdown file. Approval-gated (destructive).

    #81: skills_create was registered un-gated and unaudited, so an agent
    or job could write an arbitrary skill body that the next turn would
    advertise to the model — a self-modifying instruction surface with no
    operator confirmation. This wrapper routes creation through the
    Phase-11 approval gate (like skills_update/skills_delete). risk_tier
    is `destructive` because a new skill is new active attack surface.

    Args mirror `skills_crud.skills_create` (category, filename, content)
    so FastMCP's per-tool schema stays correct.

    Returns the underlying skills_crud result on success.
    """
    from usecase.builtin_components import skills_crud
    from usecase.builtin_components._approval_gate import gate_and_execute

    def _exec() -> dict[str, Any]:
        import json as _json
        raw = skills_crud.skills_create(category, filename, content)
        try:
            return _json.loads(raw) if isinstance(raw, str) else raw
        except (_json.JSONDecodeError, TypeError):
            return {"success": True, "raw": raw}

    try:
        return await gate_and_execute(
            tool_name="skills_create",
            args={"category": category, "filename": filename},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "skills_create"}


async def skills_update(file_path: str, content: str) -> dict[str, Any]:
    """Overwrite an existing skill markdown file. Approval-gated.

    #81: skills_update was registered un-gated. Like skills_create it
    mutates the instruction surface the model trusts, so it now routes
    through the approval gate. risk_tier is `soft` because the existing
    file is backed up (.bak + .history) and the change is auditable.

    Args mirror `skills_crud.skills_update` (file_path, content).
    """
    from usecase.builtin_components import skills_crud
    from usecase.builtin_components._approval_gate import gate_and_execute

    def _exec() -> dict[str, Any]:
        import json as _json
        raw = skills_crud.skills_update(file_path, content)
        try:
            return _json.loads(raw) if isinstance(raw, str) else raw
        except (_json.JSONDecodeError, TypeError):
            return {"success": True, "raw": raw}

    try:
        return await gate_and_execute(
            tool_name="skills_update",
            args={"file_path": file_path},
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "skills_update"}


async def personality_reset() -> dict[str, Any]:
    """Revert the agent's persona to the bundle default. Approval-gated
    (destructive).

    Wipes any operator-tuned customization. The previous version is
    preserved in personality_history so the operator can manually
    re-apply if reset was a mistake.

    Returns {personality, updated_at, updated_by, version}.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.personality_store import personality_store
    s = personality_store()
    if s is None:
        return {"error": "personality store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        updated = s.reset_to_default(actor="agent")
        return updated.to_dict()

    try:
        return await gate_and_execute(
            tool_name="personality_reset",
            args={},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "personality_reset"}


async def settings_reset(
    keys: list[str] | None = None,
) -> dict[str, Any]:
    """Clear runtime settings overrides. Approval-gated (destructive).

    Args:
        keys: list of override keys to clear. If None or empty,
            clears EVERY override — equivalent to "revert all my
            customizations". Operator probably wants this on a fresh
            deploy or when troubleshooting "why is the agent doing X?"

    Returns {cleared: [...], not_found: [...]}.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.settings_store import settings_store
    s = settings_store()
    if s is None:
        return {"error": "settings store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        target_keys = list(keys) if keys else [o.key for o in s.overrides()]
        cleared: list[str] = []
        not_found: list[str] = []
        for k in target_keys:
            if s.clear(k, actor="agent"):
                cleared.append(k)
            else:
                not_found.append(k)
        return {"cleared": cleared, "not_found": not_found}

    try:
        return await gate_and_execute(
            tool_name="settings_reset",
            args={"keys": list(keys or [])},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "settings_reset"}


async def instances_delete(instance_id: str) -> dict[str, Any]:
    """Remove a connector instance. Approval-gated (destructive).

    Connector instances bind credentials (XSOAR API keys, etc.). Deleting one disconnects the agent from that
    backend until the operator runs setup again.

    For container-style connectors (web, cortex-docs, etc.), the
    guardian-updater daemon also stops + removes the per-instance docker
    container associated with this instance — call this tool, don't
    `docker stop` manually. Other instances of the same connector are
    unaffected.

    Always confirm the instance_id with `instances_list` first; the
    string is the canonical instance identifier (a UUID-shaped slug),
    not the connector name or the display label.

    Args:
        instance_id: canonical instance id from `instances_list`.

    Returns {deleted: bool, id}. There is no bypass_approvals knob —
    destructive ops require the per-session approval mode (or per-call
    approval in the UI).
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.instance_store import instance_store
    s = instance_store()
    if s is None:
        return {"error": "instance store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        ok = s.delete(instance_id)
        return {"deleted": bool(ok), "id": instance_id}

    try:
        return await gate_and_execute(
            tool_name="instances_delete",
            args={"instance_id": instance_id},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "instances_delete"}


async def providers_delete(provider_instance_id: str) -> dict[str, Any]:
    """Remove a model-provider instance. Approval-gated (destructive).

    Same shape as instances_delete but for the model-provider side
    (Vertex, Gemini direct, future OpenAI). The encrypted service-account
    JSON / API key in the SecretStore is purged at the same time.

    DANGER: removing the *only* provider disconnects the agent from its
    LLM backend; the chat surface goes dark until the operator runs the
    Providers page → "Add provider" flow again. If the user asks "delete
    my old Vertex creds", call `providers_list` first to confirm there's
    a second provider already wired up, OR confirm with the operator
    that they intend to be locked out until re-setup.

    Args:
        provider_instance_id: canonical id from `providers_list`. NOT the
            display name; NOT the model name. The UUID-shaped slug.

    Returns {deleted: bool, id}. There is no bypass_approvals knob.
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.provider_store import provider_store
    s = provider_store()
    if s is None:
        return {"error": "provider store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        ok = s.delete(provider_instance_id)
        return {"deleted": bool(ok), "id": provider_instance_id}

    try:
        return await gate_and_execute(
            tool_name="providers_delete",
            args={"provider_instance_id": provider_instance_id},
            risk_tier="destructive",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "providers_delete"}


# ═════════════════════════════════════════════════════════════════
# TIER 4 — credential operations
#
# Mints + rotates + revokes API keys. Same gate machinery but with
# risk_tier="credential" so the approval card UI (Commit 6) demands
# a literal "type CONFIRM" challenge before the Approve button
# activates — borrowed from the kubectl-delete / terraform-destroy
# precedent. The friction is the feature.
#
# Why API keys live in their own tier:
#   - Key plaintext is returned ONCE on mint; lost forever if not
#     captured. Different from a misconfigured personality (recoverable
#     via personality_history) or a deleted job (operator can
#     recreate). Operators must understand they're getting a one-shot
#     value before approving.
#   - Rotation is the canonical "after a breach" credential op. The
#     agent should be able to drive it during incident response, but
#     never silently — a careless rotation could lock the operator
#     out of CI/CD.
#
# Trigger phrases:
#   "mint a new api key for X"           → api_keys_create
#   "rotate the key labeled gh-actions"  → api_keys_rotate
#   "revoke key abc123"                   → api_keys_revoke
# ═════════════════════════════════════════════════════════════════


async def api_keys_create(
    label: str,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    """Mint a new API key. Approval-gated (credential, type CONFIRM
    ceremony in UI).

    The plaintext is returned ONCE in the tool result — the chat layer
    surfaces it to the operator; nothing else can recover it after.
    The on-disk store retains only the SHA256-hashed token plus the
    key_id + label + scopes + created_at fields (the plaintext is hashed
    immediately on creation, never persisted in clear).

    Idempotency: there is none. Each call mints a new key, even if a key
    with the same label already exists. Call `api_keys_list` first if the
    operator says "give me a key for X" without specifying "new" — the
    existing one might still be usable (and rotating instead of duplicating
    avoids the CI-consumer drift that comes from having multiple live keys
    with the same name).

    Args:
        label: human-readable name for the key (e.g. "gh-actions",
            "incident-response-bot"). Required, non-empty.
        scopes: optional list of scope strings (e.g. ["jobs:write",
            "skills:read"]). Default ["*"] (full access). Pass the
            narrowest scope that does the job — broader scopes mean a
            bigger blast radius if the key leaks.

    Returns {key_id, label, scopes, created_at, plaintext, warning}.
    Always echo the warning to the operator verbatim. There is no
    bypass_approvals knob — credential ops require the UI ceremony.
    """
    from usecase.api_keys import api_key_store
    from usecase.builtin_components._approval_gate import gate_and_execute
    s = api_key_store()
    if s is None:
        return {"error": "api key store not initialized on this MCP runtime"}
    if not label or not isinstance(label, str):
        return {"error": "label is required (non-empty string)"}

    def _exec() -> dict[str, Any]:
        created = s.create(label=label, scopes=scopes or ["*"], actor="agent")
        return {
            "key_id": created.record.id,
            "label": created.record.label,
            "scopes": created.record.scopes,
            "created_at": created.record.created_at,
            "plaintext": created.plaintext,
            "warning": (
                "This is the ONE TIME this plaintext is visible. Capture "
                "it now — there is no retrieval path."
            ),
        }

    try:
        return await gate_and_execute(
            tool_name="api_keys_create",
            args={"label": label, "scopes": list(scopes or ["*"])},
            risk_tier="credential",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "api_keys_create"}


async def api_keys_rotate(key_id: str) -> dict[str, Any]:
    """Rotate an API key: mint a new one with the same label/scopes,
    then revoke the old one. Approval-gated (credential).

    Use case: post-breach rotation, or scheduled credential hygiene.
    The agent CAN drive it ("rotate the gh-actions key"), but the
    operator must explicitly approve — a careless rotation can lock
    the operator out of CI/CD until they update the consumer.

    Difference from api_keys_create + api_keys_revoke run separately:
        - rotate is one approval ceremony, not two
        - the new key carries the SAME label and scopes (no drift)
        - the old key is revoked at the SAME instant the new one is
          handed out — no window where both are live

    When the operator says "rotate" they almost always mean this, not
    "mint a fresh one and forget the old". Use rotate by default; only
    fall back to create+revoke if the new key must have different scopes.

    Args:
        key_id: canonical id from `api_keys_list`. Must reference an
            UNREVOKED key — rotating an already-revoked key returns an
            error pointing the agent at api_keys_create.

    Returns {rotated, old_key_id, new_key_id, label, scopes, plaintext,
    warning}. Echo the warning verbatim — operators MUST update every
    consumer of the old key (CI workflows, automation scripts, cron
    runners). There is no bypass_approvals knob.
    """
    from usecase.api_keys import api_key_store
    from usecase.builtin_components._approval_gate import gate_and_execute
    s = api_key_store()
    if s is None:
        return {"error": "api key store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        # Find the old key (the store doesn't have a get-by-id method;
        # list() and filter is the canonical pattern).
        old = next((k for k in s.list() if k.id == key_id), None)
        if old is None:
            return {"error": f"api key {key_id!r} not found"}
        if old.revoked_at is not None:
            return {
                "error": (
                    f"api key {key_id!r} is already revoked at "
                    f"{old.revoked_at} — nothing to rotate. Use "
                    f"api_keys_create to mint a fresh one."
                ),
            }
        # Mint with the SAME label + scopes.
        created = s.create(
            label=old.label, scopes=old.scopes, actor="agent",
        )
        # Revoke the old.
        s.revoke(key_id, actor="agent")
        return {
            "rotated": True,
            "old_key_id": key_id,
            "new_key_id": created.record.id,
            "label": created.record.label,
            "scopes": created.record.scopes,
            "plaintext": created.plaintext,
            "warning": (
                "The new plaintext is shown ONCE. Capture it now and "
                "update every consumer of the old key (CI workflows, "
                "automation scripts, etc.) — the old key is now revoked."
            ),
        }

    try:
        return await gate_and_execute(
            tool_name="api_keys_rotate",
            args={"key_id": key_id},
            risk_tier="credential",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "api_keys_rotate"}


async def api_keys_revoke(key_id: str) -> dict[str, Any]:
    """Revoke an API key without minting a replacement. Approval-gated
    (credential).

    Use case: decommissioning a key permanently (e.g. retiring a CI
    consumer, killing a leaked key). After this call, the key is
    permanently inactive — store.verify() returns None for any token
    derived from it. There is no un-revoke.

    Difference from api_keys_rotate:
        - revoke leaves the operator WITHOUT a working key under that
          label; rotate hands them a fresh one in the same call
        - revoke is for "this key should not exist anymore"
        - rotate is for "this key needs to keep working under the same
          name but with a new secret"

    If the operator says "the gh-actions key leaked", they almost
    certainly want rotate, not revoke — preserve the CI consumer's
    ability to authenticate by issuing a replacement at the same time.

    Args:
        key_id: canonical id from `api_keys_list`. Revoking an
            already-revoked key is a no-op that returns
            {revoked: False, error: "...already revoked"}.

    Returns {revoked: bool, key_id, label, revoked_at}. There is no
    bypass_approvals knob.
    """
    from usecase.api_keys import api_key_store
    from usecase.builtin_components._approval_gate import gate_and_execute
    s = api_key_store()
    if s is None:
        return {"error": "api key store not initialized on this MCP runtime"}

    def _exec() -> dict[str, Any]:
        old = next((k for k in s.list() if k.id == key_id), None)
        label = old.label if old else None
        ok = s.revoke(key_id, actor="agent")
        if not ok:
            return {
                "revoked": False, "key_id": key_id,
                "error": f"api key {key_id!r} not found or already revoked",
            }
        # Re-fetch to get the revoked_at timestamp.
        refreshed = next((k for k in s.list() if k.id == key_id), None)
        return {
            "revoked": True,
            "key_id": key_id,
            "label": label,
            "revoked_at": refreshed.revoked_at if refreshed else None,
        }

    try:
        return await gate_and_execute(
            tool_name="api_keys_revoke",
            args={"key_id": key_id},
            risk_tier="credential",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "api_keys_revoke"}


# ═════════════════════════════════════════════════════════════════════
# TIER 5 — multi-action batch (v0.3.10+)
#
# The operator pain that motivated this: when the agent has multiple
# mutations to make (e.g. "schedule a daily report job for each of
# my 5 skills"), pre-v0.3.10 every job_create fired its own approval
# card. Operators saw 5 sequential cards for what was conceptually one
# decision, and the agent often timed out on rows 2-5 because the
# operator had already mentally committed by the time card 1 cleared.
#
# v0.3.10's `agent_batch_propose` bundles N actions into ONE approval
# card. After the operator approves, the executor sets the
# approval-bypass contextvar and dispatches each action in sequence —
# each per-tool gate sees the bypass and executes immediately (with
# full audit trail), no further UI ceremony. If any action fails, the
# loop continues and partial-success is returned; the operator can
# review per-action results in the response.
#
# Design constraints:
#   1. The batch tool itself is approval-gated. Otherwise the agent
#      could chain unbounded actions without ever showing a card.
#   2. agent_batch_propose can NOT batch itself (no nesting). The
#      _BATCHABLE_TOOLS whitelist excludes it.
#   3. approvals_resolve is also excluded — resolving approvals as part
#      of a batch under approval would be a logical loop.
#   4. Connector tools (web.*, xsoar.*, etc.) are out of scope for
#      v0.3.10 because they need per-instance contextvar setup that
#      doesn't survive the simple await-loop here. v0.3.11+ may extend
#      coverage to connector tools via the connector_loader's instance
#      wrapper.
# ═════════════════════════════════════════════════════════════════════


_BATCHABLE_TOOLS: dict[str, Any] = {}


def _populate_batchable_tools() -> None:
    """Lazy-populate the batchable-tools dispatch table.

    Done lazily (and once) to dodge the forward-reference problem of
    referencing tool functions in a module-level dict before their
    definitions parse. Called inside `agent_batch_propose` on first use.

    The whitelist is intentionally narrower than `BUILTIN_TOOLS` in
    connector_loader: it includes only the WRITE tools (Tier 2-4
    self-mod ops) — reads don't need batching because they're not
    approval-gated. It also excludes `agent_batch_propose` (no nesting)
    and `approvals_resolve` (logical loop hazard).
    """
    if _BATCHABLE_TOOLS:
        return
    _BATCHABLE_TOOLS.update({
        # Tier 2 (soft writes)
        "jobs_create": jobs_create,
        "jobs_update": jobs_update,
        "jobs_run_now": jobs_run_now,
        "personality_update": personality_update,
        "personality_patch": personality_patch,
        "settings_update": settings_update,
        "notifications_dismiss": notifications_dismiss,
        "notifications_dismiss_all": notifications_dismiss_all,
        # Tier 3 (destructive)
        "jobs_delete": jobs_delete,
        "skills_delete": skills_delete,
        "personality_reset": personality_reset,
        "settings_reset": settings_reset,
        "instances_delete": instances_delete,
        "providers_delete": providers_delete,
        # Tier 4 (credential)
        "api_keys_create": api_keys_create,
        "api_keys_rotate": api_keys_rotate,
        "api_keys_revoke": api_keys_revoke,
    })


async def agent_batch_propose(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Bundle N self-modification actions into ONE approval ceremony.

    When the operator asks the agent to take multiple actions at once
    ("schedule a daily report job for each of my 5 skills",
    "delete these 3 instances", "rotate both gh-actions and ci-bot
    keys"), use this tool to present them as ONE approval card instead
    of firing N independent approvals. The operator sees the full plan
    inline and approves (or denies) the whole batch.

    Trigger phrases:
        "do all of these at once"
        "create jobs for all 5 skills with one approval"
        "I don't want to approve each one separately"
        ANY chat turn where the agent plans to make 2+ gated mutations
        in immediate succession with no operator dialogue between them

    Behavior:
        1. agent_batch_propose itself triggers ONE approval card.
        2. Card displays the action list (tool name + summarized args
           per row) so the operator sees the whole plan.
        3. On approve: bypass contextvar is set; actions execute in
           order. Each per-tool gate audits a "bypass" event but skips
           the UI ceremony.
        4. On deny: nothing executes.
        5. Per-action failures during execution don't abort the loop —
           the response reports partial success.

    Args:
        actions: list of {tool: str, args: dict}. Each action may be:
            - A built-in Tier 2/3/4 self-mod tool (`jobs_*`,
              `instances_*`, `providers_*`, `settings_*`,
              `personality_*`, `api_keys_*`, `notifications_*`,
              `skills_delete`). Dispatched directly for speed.
            - A connector tool registered on the running MCP (e.g.
              `xsoar.list_incidents`, `xsoar.get_incident`,
              `web.navigate`). Dispatched through the unified
              tool_dispatcher (same path the scheduler uses), which
              preserves per-instance contextvar setup, Pydantic
              marshalling, and result unwrapping. v0.3.11+.
            - A read tool (`*_list`, `*_get`, `audit_*`, etc.) — works
              but is rarely useful inside a batch since reads don't
              cost approvals; the agent should call them inline.

            Excluded (loop hazards): `agent_batch_propose` itself,
            `approvals_resolve`.

    Returns:
        {
          batch_id: str,
          ok: bool,                    # overall success flag
          approved: bool,
          executed: int,
          succeeded: int,
          failed: int,
          per_action_results: [
            {tool, args, ok: bool, result?, error?},
            ...
          ],
        }

    Errors raised:
        - ApprovalDeniedError if the operator denies the batch
        - ApprovalTimeoutError if no decision within the gate timeout
        - ValueError if `actions` is empty, malformed, or contains
          unbatchable tool names (raised BEFORE the approval card —
          the agent sees a clean validation error to fix and retry)
    """
    from usecase.audit_log import (
        set_current_approval_bypass,
        reset_current_approval_bypass,
    )
    from usecase.builtin_components._approval_gate import gate_and_execute

    # Eager validation BEFORE firing the approval card. Better UX: the
    # agent sees the error and can correct without burning operator
    # attention on a malformed card.
    if not isinstance(actions, list) or not actions:
        return {
            "ok": False,
            "error": "actions must be a non-empty list",
            "tool": "agent_batch_propose",
        }
    if len(actions) > 25:
        # Soft cap: a 25-action batch already shows a long approval
        # card. Larger batches likely indicate the agent should ask
        # the operator to chunk the request rather than ratify a wall
        # of actions in one go.
        return {
            "ok": False,
            "error": (
                f"batch too large ({len(actions)} actions); split into "
                f"multiple batches of ≤25"
            ),
            "tool": "agent_batch_propose",
        }

    _populate_batchable_tools()

    # v0.3.11: connector-tool batch coverage. Pre-v0.3.11 only the
    # built-in self-mod tools in _BATCHABLE_TOOLS could appear in a
    # batch. v0.3.11 extends coverage to any tool in the process-wide
    # tool_registry, dispatched through the same fastmcp.Client path
    # the job scheduler uses — so per-instance contextvar setup,
    # Pydantic marshalling, and CallToolResult unwrapping all work
    # identically to agent-driven calls.
    #
    # Two hard exclusions still apply (the v0.3.10 loop-hazard set):
    #   - agent_batch_propose itself (no nesting)
    #   - approvals_resolve (logical loop)
    from usecase.tool_dispatcher import get_tool_dispatcher
    dispatcher = get_tool_dispatcher()

    # We can read the tool_registry directly via the connector_loader's
    # private singleton — same one set_reload_state populates at boot.
    # Importing the private name is OK here because it's a tightly-
    # coupled pair within the same bundle.
    def _tool_in_registry(name: str) -> bool:
        try:
            from usecase import connector_loader  # type: ignore[attr-defined]
            state = getattr(connector_loader, "_reload_state", None)
            if not isinstance(state, dict):
                return False
            reg = state.get("tool_registry") or {}
            return name in reg
        except Exception:
            return False

    _UNBATCHABLE = {"agent_batch_propose", "approvals_resolve"}

    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(actions):
        if not isinstance(raw, dict):
            return {
                "ok": False,
                "error": f"action[{idx}] must be an object",
                "tool": "agent_batch_propose",
            }
        tool_name = raw.get("tool")
        action_args = raw.get("args") or {}
        if not isinstance(tool_name, str) or not tool_name:
            return {
                "ok": False,
                "error": f"action[{idx}].tool is required (string)",
                "tool": "agent_batch_propose",
            }
        if not isinstance(action_args, dict):
            return {
                "ok": False,
                "error": f"action[{idx}].args must be an object",
                "tool": "agent_batch_propose",
            }
        if tool_name in _UNBATCHABLE:
            return {
                "ok": False,
                "error": (
                    f"action[{idx}].tool {tool_name!r} cannot appear inside a "
                    f"batch (loop hazard). Excluded: {sorted(_UNBATCHABLE)}"
                ),
                "tool": "agent_batch_propose",
            }
        # Two dispatch routes:
        #   - Built-in self-mod tool (in _BATCHABLE_TOOLS): direct call,
        #     no fastmcp.Client overhead. Same path as v0.3.10.
        #   - Any other registered tool (connector tools, cognitive
        #     read tools, etc.): dispatch through tool_dispatcher().
        is_builtin = tool_name in _BATCHABLE_TOOLS
        is_registered = _tool_in_registry(tool_name)
        if not is_builtin and not is_registered:
            return {
                "ok": False,
                "error": (
                    f"action[{idx}].tool {tool_name!r} is not a known "
                    f"tool. Built-ins: {sorted(_BATCHABLE_TOOLS.keys())}. "
                    f"Connector tools must be registered in the tool "
                    f"registry — check that the corresponding connector "
                    f"has an instance configured."
                ),
                "tool": "agent_batch_propose",
            }
        if not is_builtin and dispatcher is None:
            return {
                "ok": False,
                "error": (
                    f"action[{idx}].tool {tool_name!r} requires the "
                    f"tool dispatcher, which isn't installed on this "
                    f"MCP runtime"
                ),
                "tool": "agent_batch_propose",
            }
        normalized.append({"tool": tool_name, "args": action_args})

    import uuid
    batch_id = str(uuid.uuid4())

    # Build the approval-card args payload. The UI keys on `actions`
    # being present to render the list view; if absent, falls through
    # to the standard single-action card layout. We also include a
    # concise summary so the audit log doesn't need to re-parse args.
    gate_args = {
        "batch_id": batch_id,
        "action_count": len(normalized),
        "actions": [
            {
                "tool": a["tool"],
                # Persist arg KEYS only on the audit row by default;
                # full args are persisted on the approval card so the
                # operator sees what's being proposed without grep'ing
                # the audit log. The approval bus already redacts known
                # credential fields per its sanitize pass.
                "args": a["args"],
            }
            for a in normalized
        ],
        "summary": _summarize_batch(normalized),
    }

    async def _execute_batch() -> dict[str, Any]:
        """Run each action in sequence under bypass-contextvar.

        Two dispatch paths:
          1. Built-in self-mod tool — direct fn call (faster).
          2. Connector tool / any other registered tool — dispatch via
             tool_dispatcher() which routes through fastmcp.Client and
             therefore preserves per-instance contextvar setup, Pydantic
             marshalling, and CallToolResult unwrapping. Same path the
             scheduler uses.

        Failure mode: per-action errors are captured and returned —
        they do NOT abort the loop. The operator gets a complete
        per-action result map so they can see what worked vs. didn't
        and decide whether to re-run the failed subset.
        """
        token = set_current_approval_bypass(True)
        per_action: list[dict[str, Any]] = []
        succeeded = 0
        failed = 0
        try:
            for action in normalized:
                tool_name = action["tool"]
                action_args = action["args"]
                try:
                    if tool_name in _BATCHABLE_TOOLS:
                        # Path 1: built-in. Direct call, no fastmcp
                        # round-trip. Existing v0.3.10 fast-path.
                        fn = _BATCHABLE_TOOLS[tool_name]
                        result = fn(**action_args)
                        import asyncio as _asyncio
                        if _asyncio.iscoroutine(result):
                            result = await result
                    else:
                        # Path 2: connector/other registered tool. Go
                        # through the unified dispatcher so per-instance
                        # contextvar wiring fires correctly. dispatcher
                        # was validated non-None during normalization
                        # for non-builtin paths.
                        assert dispatcher is not None  # mypy hint
                        result = await dispatcher(tool_name, action_args)
                    # Tools that internally fail (e.g. "settings store
                    # not initialized") return a dict with `error` —
                    # treat that as failure for the per-action count so
                    # the operator's audit trail surfaces the right
                    # success/failure breakdown.
                    if isinstance(result, dict) and result.get("error"):
                        per_action.append({
                            "tool": tool_name,
                            "args": action_args,
                            "ok": False,
                            "error": result["error"],
                        })
                        failed += 1
                        _emit_batch_action_metric(tool_name, "fail")
                    else:
                        per_action.append({
                            "tool": tool_name,
                            "args": action_args,
                            "ok": True,
                            "result": result,
                        })
                        succeeded += 1
                        _emit_batch_action_metric(tool_name, "success")
                except Exception as exc:  # noqa: BLE001
                    per_action.append({
                        "tool": tool_name,
                        "args": action_args,
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    failed += 1
                    _emit_batch_action_metric(tool_name, "fail")
        finally:
            reset_current_approval_bypass(token)
        # v0.3.15: batch was approved + executed — record the proposal
        # outcome + size histogram observation. Lazy-registers the
        # metrics if main.py's manifest-counter loop didn't already
        # (histograms aren't in the manifest declaration loop).
        _emit_batch_proposal_metric(approved=True, size=len(normalized))
        return {
            "batch_id": batch_id,
            "ok": failed == 0,
            "approved": True,
            "executed": len(normalized),
            "succeeded": succeeded,
            "failed": failed,
            "per_action_results": per_action,
        }

    try:
        return await gate_and_execute(
            tool_name="agent_batch_propose",
            args=gate_args,
            risk_tier="soft",  # The batch row inherits the highest
            # risk among its actions; the approvals UI may upgrade
            # severity from this baseline based on what's inside.
            executor=_execute_batch,
        )
    except Exception as exc:  # noqa: BLE001
        # v0.3.15: gate raised → denied/timeout/bus-error path. Record
        # the proposal outcome as not approved so dashboards can see
        # the deny-vs-approve ratio. Size is still meaningful (how big
        # was the rejected ask?).
        _emit_batch_proposal_metric(approved=False, size=len(normalized))
        return {
            "ok": False,
            "approved": False,
            "batch_id": batch_id,
            "error": str(exc),
            "tool": "agent_batch_propose",
        }


# ─── v0.3.15: batch metrics emission ─────────────────────────────────
#
# Three Prometheus metrics for agent_batch_propose. The first two are
# also pre-declared in manifest.observability.metrics[] so dashboards
# see them as 0-valued counters before any batch fires. The histogram
# is registered lazily on first call (histograms aren't in the
# manifest pre-registration loop).
#
# Metric design:
#   - guardian_batch_proposals_total{approved="true"|"false"}
#       counter — every agent_batch_propose call increments once. Lets
#       the operator see batch usage AND the deny-rate over time.
#   - guardian_batch_actions_total{tool="...",result="success"|"fail"}
#       counter — one inc per action inside a batch. The tool label
#       reveals which tools dominate batch traffic; the result label
#       splits success vs failure for per-tool reliability dashboards.
#   - guardian_batch_size (histogram, custom count-buckets 1/2/3/5/10/25)
#       distribution of batch sizes. Bucket choice matches the v0.3.10
#       25-action cap — a value above the top bucket would mean
#       validation regressed (the eager check should block it).


def _emit_batch_proposal_metric(*, approved: bool, size: int) -> None:
    """Increment proposals_total + observe size. Silent no-op when the
    metrics registry isn't installed (test harness, partial boot)."""
    try:
        from usecase.metrics_registry import metrics_registry  # type: ignore
        reg = metrics_registry()
        if reg is None:
            return
        c = reg.counter(
            "guardian_batch_proposals_total",
            "agent_batch_propose calls broken down by outcome (approved/denied)",
        )
        c.inc(approved=str(approved).lower())
        h = reg.histogram(
            "guardian_batch_size",
            "distribution of agent_batch_propose batch sizes",
            buckets=(1.0, 2.0, 3.0, 5.0, 10.0, 25.0),
        )
        h.observe(float(size))
    except Exception:  # noqa: BLE001
        # Metrics failures must NEVER affect the tool's primary path.
        # The agent's batch result is correct regardless of whether
        # observability collected the data point.
        pass


def _emit_batch_action_metric(tool_name: str, result: str) -> None:
    """Per-action counter with {tool, result} labels. Same silent-fail
    contract as _emit_batch_proposal_metric."""
    try:
        from usecase.metrics_registry import metrics_registry  # type: ignore
        reg = metrics_registry()
        if reg is None:
            return
        c = reg.counter(
            "guardian_batch_actions_total",
            "individual action executions inside batches, labeled by tool + result",
        )
        c.inc(tool=tool_name, result=result)
    except Exception:  # noqa: BLE001
        pass


def _summarize_batch(actions: list[dict[str, Any]]) -> str:
    """Generate a one-line operator-readable summary of the batch
    contents. Used in the approval-card title and audit-log metadata."""
    from collections import Counter
    counts = Counter(a["tool"] for a in actions)
    parts = [f"{n}× {t}" for t, n in sorted(counts.items())]
    return f"batch of {len(actions)} actions: " + ", ".join(parts)


# ─────────────────────────────────────────────────────────────────
# v0.5.0 marketplace tools (catalog operations — not credentials)
#
# Per the v0.4.0 agent credential guardrail (CLAUDE.md "Agent
# credential guardrail (MANDATORY)"), the agent cannot read/write/
# mint/rotate credentials. These 4 tools are CATALOG operations —
# install state, schema upload, registry membership — NOT
# credential operations. They legitimately belong in the agent's
# tool surface.
#
# The distinction codified for future maintainers:
#
#   * Credential boundary: anything that reads, writes, mints, or
#     rotates a SecretStore value. Forbidden for the agent.
#       Examples: instances_create (carries secrets), api_keys_*,
#       providers_create.
#
#   * Catalog boundary: anything that mutates the CONNECTOR-
#     CATALOG-LEVEL metadata — install state, connector schemas,
#     marketplace membership. Permitted for the agent.
#       Examples: marketplace_install, connector_upload.
#
# The two boundaries can move independently. v0.5.0 opens the
# catalog boundary; the credential boundary stays closed.
# ─────────────────────────────────────────────────────────────────


def marketplace_list() -> dict[str, Any]:
    """List marketplace connectors with install state + instance counts.

    READ-ONLY catalog operation. Same data the operator sees on
    /connectors → Marketplace tab. Use this when the operator asks
    "what connectors are available?", "which ones are installed?",
    "what's in the marketplace?".

    Returns {connectors: [{id, version, description, tools_count,
    tags, origin, installed, install, instances_count}], count}.

    `origin` is "bundle" (shipped in the image) or "user" (uploaded
    via connector_upload). `installed` is True only when the operator
    has explicitly installed the connector via marketplace_install
    (or the v0.5.0 upgrade migration installed it because instances
    already existed).
    """
    from usecase.marketplace_store import get_marketplace_store
    from api.marketplace import _scan_catalogue, _instances_count
    from usecase.instance_store import instance_store

    mp = get_marketplace_store()
    if mp is None:
        return {"error": "marketplace store not initialized on this MCP runtime"}
    s = instance_store()
    if s is None:
        return {"error": "instance store not initialized on this MCP runtime"}

    catalogue = _scan_catalogue()
    installs_by_id = {r.connector_id: r for r in mp.list_installed()}
    connectors: list[dict[str, Any]] = []
    for cid, summary in sorted(catalogue.items()):
        row = installs_by_id.get(cid)
        connectors.append(
            {
                **summary,
                "installed": row is not None,
                "install": (
                    {
                        "connector_id": row.connector_id,
                        "installed_at": row.installed_at,
                        "origin": row.origin,
                        "version": row.version,
                    }
                    if row
                    else None
                ),
                "instances_count": _instances_count(s, cid),
            }
        )
    return {"connectors": connectors, "count": len(connectors)}


def marketplace_install(connector_id: str) -> dict[str, Any]:
    """Mark a connector as installed — making it available for
    instance creation.

    Catalog operation. NOT a credential operation — installs a
    catalog entry, doesn't touch secrets. Per CLAUDE.md's catalog-
    vs-credential boundary distinction, this is in-bounds for the
    agent.

    Use when the operator says "install <name>", "make <name>
    available", "enable the <name> connector". Idempotent: installing
    an already-installed connector returns the existing row.

    Args:
        connector_id: the connector to install. Must exist in the
            marketplace catalogue (bundle or previously uploaded
            user connector). Returns {error} if unknown.

    Returns {ok, install: {connector_id, installed_at, origin,
    version}} or {error}. After successful install the operator can
    create an instance via the /connectors UI (the agent does NOT
    create instances — that's a credential operation requiring
    secrets, which the credential guardrail forbids).
    """
    from usecase.marketplace_store import get_marketplace_store
    from api.marketplace import _scan_catalogue
    from usecase.audit_log import record_event

    mp = get_marketplace_store()
    if mp is None:
        return {"error": "marketplace store not initialized on this MCP runtime"}
    if not isinstance(connector_id, str) or not connector_id:
        return {"error": "connector_id must be a non-empty string"}

    catalogue = _scan_catalogue()
    summary = catalogue.get(connector_id)
    if summary is None:
        return {
            "error": (
                f"connector {connector_id!r} not found in catalogue. "
                f"Available: {sorted(catalogue.keys())}"
            ),
        }
    origin = summary["origin"]
    row = mp.install(
        connector_id,
        origin=origin,
        version=summary.get("version", "0.0.0"),
    )
    record_event(
        action="marketplace_install",
        target=f"connector:{connector_id}",
        status="success",
        metadata={"origin": origin, "version": row.version, "by": "agent"},
    )
    return {
        "ok": True,
        "install": {
            "connector_id": row.connector_id,
            "installed_at": row.installed_at,
            "origin": row.origin,
            "version": row.version,
        },
        "next_step": (
            f"The connector is now available for instance creation. The "
            f"operator can create an instance via /connectors → {connector_id} "
            f"→ Create Instance (the agent itself can't create instances "
            f"because that's a credential operation — see CLAUDE.md's "
            f"agent credential guardrail)."
        ),
    }


def marketplace_uninstall(connector_id: str) -> dict[str, Any]:
    """Remove the install marker from a connector.

    Catalog operation. Refuses if instances exist for the connector
    (returns {error, instances_count}) — the operator must delete
    instances first via the /connectors UI. Instance deletion IS
    a credential operation (secret cleanup) so the agent can't do
    it; this is a guard that prevents a half-cleaned-up state.

    Use when the operator says "uninstall <name>", "remove <name>
    from the marketplace", "I don't need <name> anymore".

    Args:
        connector_id: the connector to uninstall. Returns {error} if
            unknown, not installed, or has live instances.

    Returns {ok, removed} or {error, instances_count}.
    """
    from usecase.marketplace_store import get_marketplace_store
    from api.marketplace import _instances_count
    from usecase.instance_store import instance_store
    from usecase.audit_log import record_event

    mp = get_marketplace_store()
    if mp is None:
        return {"error": "marketplace store not initialized on this MCP runtime"}
    if not isinstance(connector_id, str) or not connector_id:
        return {"error": "connector_id must be a non-empty string"}

    if not mp.is_installed(connector_id):
        return {"error": f"connector {connector_id!r} is not installed"}

    s = instance_store()
    if s is not None:
        n = _instances_count(s, connector_id)
        if n > 0:
            return {
                "error": (
                    f"connector {connector_id!r} has {n} instance(s); "
                    f"the operator must delete them first via /connectors → "
                    f"{connector_id} → Instances. The agent can't delete "
                    f"instances (per CLAUDE.md's credential guardrail)."
                ),
                "instances_count": n,
            }

    removed = mp.uninstall(connector_id)
    record_event(
        action="marketplace_uninstall",
        target=f"connector:{connector_id}",
        status="success" if removed else "noop",
        metadata={"by": "agent"},
    )
    return {"ok": True, "removed": removed}


def connector_upload(yaml_content: str) -> dict[str, Any]:
    """Upload a new connector schema (YAML content) into the marketplace.

    Catalog operation. The YAML content carries the connector's
    manifest — id, version, description, tools, config schema, secret
    slots, and the OCI image reference. No secrets, no credential
    material. Per CLAUDE.md's catalog-vs-credential distinction this
    sits firmly on the catalog side.

    Use when the operator says "upload this connector", "add a new
    connector to the marketplace", or pastes a YAML and asks "can you
    register this?".

    Validation pipeline (fail-fast on first error):
      1. yaml_content is non-empty and parses as a top-level YAML
         object.
      2. Spec validates against connector.schema.json (Phase B).
      3. spec.id does not collide with a bundle connector id.
      4. spec.id is not already an uploaded user connector.
      5. spec has an 'image' field — required for user connectors.

    On success: writes
    /app/data/user_connectors/<id>/connector.yaml, emits a
    `connector_uploaded` audit event, returns the parsed summary.

    Args:
        yaml_content: the YAML text the operator wants to upload.
            Full connector.yaml content. See
            bundles/spark/connectors/connector.schema.json for the
            shape.

    Returns {ok, connector: {id, version, description, ...},
    next_step} or {error, code}. After success the operator should
    install the connector via marketplace_install(<id>) then create
    an instance via /connectors (instance creation = secrets =
    operator-only per credential guardrail).
    """
    from pathlib import Path
    from usecase.connector_schema import (
        ConnectorSpecError,
        validate_connector_spec,
    )
    from usecase.marketplace_store import resolved_data_root
    from api.marketplace import (
        _scan_catalogue,
        _connector_summary,
    )
    from usecase.audit_log import record_event

    if not isinstance(yaml_content, str) or not yaml_content.strip():
        return {"error": "yaml_content must be a non-empty string"}

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {"error": "server missing pyyaml dep — cannot parse YAML"}

    try:
        spec = yaml.safe_load(yaml_content)
    except yaml.YAMLError as err:
        return {"error": f"YAML failed to parse: {err}"}
    if not isinstance(spec, dict):
        return {"error": "YAML must be a top-level object"}

    try:
        validate_connector_spec(spec, source_path="<connector_upload>")
    except ConnectorSpecError as err:
        return {"error": str(err), "code": "schema_validation_failed"}

    cid = spec.get("id")
    if not isinstance(cid, str):
        return {"error": "YAML missing valid id field"}

    catalogue = _scan_catalogue()
    existing = catalogue.get(cid)
    if existing is not None:
        if existing.get("origin") == "bundle":
            return {
                "error": (
                    f"connector id {cid!r} is reserved by a bundle "
                    f"connector; choose a different id"
                ),
                "code": "id_collides_with_bundle",
            }
        return {
            "error": (
                f"user connector {cid!r} already exists; the operator "
                f"must DELETE it via /connectors before re-uploading"
            ),
            "code": "id_already_exists",
        }

    image_ref = spec.get("image")
    if not isinstance(image_ref, str) or not image_ref.strip():
        return {
            "error": (
                "user connectors must declare an 'image' field with the "
                "OCI image reference of the published connector "
                "container (e.g. 'ghcr.io/your-org/your-connector:v1.0')"
            ),
            "code": "image_ref_required",
        }

    target_dir = resolved_data_root() / "user_connectors" / cid
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "connector.yaml").write_text(
            yaml_content, encoding="utf-8",
        )
    except OSError as err:
        return {"error": f"could not persist user connector: {err}"}

    record_event(
        action="connector_uploaded",
        target=f"connector:{cid}",
        status="success",
        metadata={
            "origin": "user",
            "version": spec.get("version", "0.0.0"),
            "image": image_ref,
            "tools_count": len((spec.get("spec") or {}).get("tools") or []),
            "by": "agent",
        },
    )

    return {
        "ok": True,
        "connector": _connector_summary(
            cid, target_dir / "connector.yaml", "user",
        ),
        "next_step": (
            f"Call marketplace_install({cid!r}) to make this connector "
            f"available for instance creation. The operator then creates "
            f"an instance via /connectors → {cid} → Create Instance."
        ),
    }


# ─── v0.5.33 / Issue #24 — benchmark runner tool ────────────────────


async def bench_run(
    manifest: str,
    router_preset_model: str | None = None,
    thinking_enabled: bool = False,
) -> dict[str, Any]:
    """Run a benchmark manifest against the chat route. Approval-gated.

    Dispatches each case in the manifest via the agent's /api/chat
    endpoint, collects tool calls + final response + cost + wall,
    scores via the 5-axis scorer, records to benchmark_runs.db.

    Args:
        manifest: Either a path to a YAML manifest file (absolute or
            relative to CWD on the agent container) OR a bundled-corpus
            id ("guardian-soc-v1" resolves to bench_cases/guardian-soc-v1.yaml
            packaged with the agent image). Concrete trigger phrases:
            "run the guardian-soc-v1 benchmark", "run the bench
            manifest at /tmp/my-bench.yaml".
        router_preset_model: Optional per-bench model override sent as
            body.model on every dispatched case. Use "gemini-2.5-flash"
            for a cheap-routing preset bench, "gemini-3.1-pro-preview"
            for a thinking-on-by-default preset, or omit to use the
            runtime default.
        thinking_enabled: Pass through to body.thinking on every case.
            Only honored on Pro models.

    Returns: { "run_id": str, "summary": {...} } on success;
             { "error": str } on manifest-parse failure.

    Trigger phrases: "run the guardian-soc-v1 benchmark", "bench the
    agent on flash routing", "run the bench manifest <path>".
    """
    from usecase.builtin_components._approval_gate import gate_and_execute
    from usecase.benchmark_runner import run_manifest as _run_manifest_async

    async def _exec() -> dict[str, Any]:
        try:
            summary = await _run_manifest_async(
                manifest,
                router_preset_model=router_preset_model,
                thinking_enabled=thinking_enabled,
                record=True,
            )
        except ValueError as exc:
            return {"error": str(exc)}
        return {
            "run_id": summary.run_id,
            "summary": summary.to_dict(),
        }

    try:
        return await gate_and_execute(
            tool_name="bench_run",
            args={
                "manifest": manifest,
                "router_preset_model": router_preset_model,
                "thinking_enabled": thinking_enabled,
            },
            risk_tier="soft",
            executor=_exec,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "bench_run"}
