"""
Phantom MCP Server Main Module

This module serves as the entry point for the Phantom MCP (Model Context Protocol) Server.
It handles server initialization, signal handling for graceful shutdown, and manages
the async event loop for the MCP server operations.
"""

import asyncio
import logging
import os
import signal
import tempfile
from functools import partial

import atexit
import uvicorn
from fastmcp import FastMCP

from pathlib import Path

import yaml

from api.approvals import register_approval_routes
from api.audit import register_audit_routes
from api.ui_auth import register_ui_auth_routes
from api.cognitive import register_cognitive_routes
from api.instances import register_instance_routes
from api.jobs import register_job_routes
from api.kb import register_kb_routes
from api.providers import register_provider_routes
from api.admin import register_admin_routes
from api.api_keys import register_api_key_routes
from api.media import register_media_routes
from api.metrics import register_metrics_routes
from api.notifications import register_notification_routes
from api.observability import register_observability_routes
from api.agent_definitions import register_agent_definition_routes
from api.connectors import register_connector_routes
from api.hooks import register_hook_routes
from api.bench import register_bench_routes
from api.personality import register_personality_routes
from api.plugins import register_plugin_routes
from api.plugin_entry_points_routes import register_plugin_entry_points_routes
from api.plugin_hook_invoke import register_plugin_hook_invoke_routes
from api.settings import register_settings_routes
from api.skills import register_skill_routes
from api.tasks import register_task_routes
# v0.4.0: api.setup retired. The /api/v1/setup endpoint that materialized
# connector instances from the Next.js setup-form payload has no callers
# (the Next.js client was deleted in v0.4.0 Phase 11). Connector instances
# are now created via /api/v1/instances directly from the operator UI.
from api.telemetry import register_telemetry_routes
from api.update import register_update_routes
from config.config import get_config
from pkg.setup_logging import setup_logging
from service.phantom_mcp.server import create_mcp_server
from usecase.approvals_bus import InProcessApprovalsBus, set_approvals_bus
from usecase.audit_log import SqliteAuditLog, set_audit_log
from usecase.connector_loader import (
    iter_registrations,
    register_all_tools,
    set_reload_state,
    tool_summary,
)
from usecase.context_assembler import ContextAssembler, set_context_assembler
from usecase.instance_store import InstanceStore
from usecase.job_scheduler import (
    CroniterJobScheduler,
    JobDefinition,
    make_tool_dispatcher,
    set_scheduler,
)
from usecase.kb_loader import load_bundled_knowledge
from usecase.kb_store import SqliteKnowledgeBase, set_knowledge_base
from usecase.benchmark import BenchRunStore, set_bench_store
from usecase.memory_store import SqliteMemoryStore, TextHashEmbedder, set_memory_store
from usecase.provider_loader import provider_summary
from usecase.provider_store import ProviderStore
from usecase.secret_store import SecretStore
from usecase.session_store import SqliteSessionStore, set_session_store
from usecase.api_keys import SqliteApiKeyStore, set_api_key_store
from usecase.notifications import (
    SqliteNotificationStore,
    TopicSpec,
    set_notification_store,
)
from usecase.event_log import SqliteEventLog, set_event_log
from usecase.media_store import SqliteMediaStore, set_media_store
from usecase.metrics_registry import MetricsRegistry, set_metrics_registry
from usecase.agent_definition_store import (
    SqliteAgentDefinitionStore,
    set_agent_definition_store,
)
from usecase.connector_state import (
    SqliteConnectorStateStore,
    set_connector_state_store,
)
from usecase.hook_store import SqliteHookStore
from usecase.plugin_loader import PluginLoader
from usecase.task_store import SqliteTaskStore, set_task_store
from usecase.personality_store import (
    SqlitePersonalityStore,
    set_personality_store,
)
from usecase.settings_store import SqliteSettingsStore, set_settings_store
from usecase.telemetry import SqliteTelemetryStore, set_telemetry_store

logger = logging.getLogger("Phantom MCP")


async def shutdown(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
    """
    Handle graceful shutdown of the Phantom MCP Server.

    Args:
        sig: The signal that triggered the shutdown (SIGINT or SIGTERM)
        loop: The current asyncio event loop to be stopped
    """
    logger.info(f"Received exit signal {sig.name}...")

    # Get all running tasks except the current shutdown task
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    logger.info("Cancelling outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Stopping the event loop")
    loop.stop()


async def async_main(transport: str):
    """
    Main async function that initializes and runs the Phantom MCP Server.

    Args:
        transport: The transport mechanism for the MCP server ('stdio' or 'streamable-http')
    """
    config = get_config()
    setup_logging(config)
    logger.info("Starting Phantom MCP Server")

    loop = asyncio.get_running_loop()

    # Add signal handlers for SIGINT and SIGTERM for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, partial(lambda s: asyncio.create_task(shutdown(s, loop)), sig))

    # Create MCP server. Connector config resolves lazily from the
    # InstanceStore at each tool call (see connector_loader's per-
    # instance contextvar wrapping). No env-var capture at boot.
    mcp = create_mcp_server()

    # Register tools via the v1.2 bundle-aware loader.
    #
    # Each entry from iter_registrations() yields a v1.2 namespaced
    # name (`<connector_id>/<tool_name>`) and, when MCP_LEGACY_TOOL_NAMES
    # is true (default), a legacy flat alias (`<connector_id>_<tool_name>`)
    # so existing skills/prompts authored against the pre-v1.2 catalog
    # keep working without modification. Set MCP_LEGACY_TOOL_NAMES=false
    # to register only the namespaced names (preview of phase 2B).
    legacy_flag = os.getenv("MCP_LEGACY_TOOL_NAMES", "true").lower()
    include_legacy = legacy_flag in {"1", "true", "yes", "on"}

    # v1.2 Phase 6 — SqliteAuditLog (spec capability §6.10 row 14,
    # local sqlite-backed standalone variant of the platform's
    # `OpenSearchAuditLog`). Wired FIRST because Phase-5 stores below
    # call `record_event()` from inside their CRUD methods — the
    # singleton has to exist before those methods first run.
    #
    # Append-only contract: there is no DELETE/UPDATE on the schema.
    # Even with admin token, an operator can't tamper with the log via
    # HTTP. Forensic-grade by construction.
    audit = SqliteAuditLog()
    set_audit_log(audit)

    # Observability — Prometheus-format metrics registry, built-in
    # counters/gauges/histogram registered first. Manifest-declared
    # counters get pre-registered AFTER the manifest is parsed below
    # (deferred because observability_cfg isn't available yet at this
    # point in the function — Python's local-variable scoping treats
    # any later `observability_cfg = ...` assignment as an UnboundLocal
    # error if we read it here).
    metrics = MetricsRegistry()
    set_metrics_registry(metrics)
    metrics.counter(
        "phantom_mcp_http_requests_total",
        "Total HTTP requests served by the embedded MCP.",
    )
    metrics.histogram(
        "phantom_mcp_http_request_duration_seconds",
        "HTTP request duration in seconds, bucketed.",
    )
    metrics.counter(
        "phantom_mcp_tool_calls_total",
        "Total tool dispatches. Labels: tool, status.",
    )
    metrics.gauge(
        "phantom_mcp_active_sessions",
        "Currently active operator sessions.",
    )

    # v1.2 Phase 7 — InProcessApprovalsBus (spec capability §6.10 row
    # "approvals", standalone variant of `KafkaApprovalsBus`). Wired
    # alongside the audit log because the tool wrapper needs both
    # available before the first connector tool registers. The bus's
    # boot-time orphan reaper marks zombie pending rows from a prior
    # process as STATUS_TIMEOUT so the UI doesn't show them as live.
    approvals = InProcessApprovalsBus()
    set_approvals_bus(approvals)

    # v1.2 Phase 5 — SecretStore (spec capability §6.10 row 17,
    # file-backed standalone variant of `_EnvSecretStore`/`InfisicalSecretStore`).
    # Holds secret VALUES; the connector + provider stores hold only
    # PATHS into this store. Passed to both stores so create() routes
    # secret values to the store and merged_config() resolves paths
    # back to values at tool-call time.
    secret_store = SecretStore()

    # v1.2 stage 3A — InstanceStore wired to SecretStore (Phase 5).
    # On first init, the migration moves any legacy literal-value rows
    # into the SecretStore and updates the rows in place to use paths.
    store = InstanceStore(secret_store=secret_store)
    # Self-modification tools (instances_list, instances_get) look up
    # the store via singleton accessor — same convention as memory/audit/etc.
    from usecase.instance_store import set_instance_store
    set_instance_store(store)

    # v1.2 §7.6 — ProviderStore (same Phase-5 migration).
    provider_store = ProviderStore(secret_store=secret_store)
    from usecase.provider_store import set_provider_store
    set_provider_store(provider_store)

    # v0.5.0 — marketplace install state lives in a sqlite DB owned by
    # MCP (was a Next.js-written JSON file pre-v0.5.0). Constructor
    # runs the one-shot migration from marketplace_installs.json (if
    # present) then deletes the legacy file. Idempotent on subsequent
    # boots. See usecase/marketplace_store.py for the full contract.
    from usecase.marketplace_store import MarketplaceStore, set_marketplace_store
    marketplace_store = MarketplaceStore()
    set_marketplace_store(marketplace_store)

    # v0.5.1 — operator workflow state lives in MCP (was browser
    # localStorage pre-v0.5.1, which made volume wipes incomplete +
    # broke cross-device + cross-browser consistency). Holds
    # tested-journeys + metrics-bookmarks; future workflow concerns
    # (saved filters, favorite skills) follow the same key-value
    # pattern without schema changes. See
    # usecase/operator_state_store.py for the full contract.
    from usecase.operator_state_store import (
        OperatorStateStore,
        set_operator_state_store,
    )
    operator_state_store = OperatorStateStore()
    set_operator_state_store(operator_state_store)

    # v0.5.0 upgrade migration — for v0.4.x customers carrying
    # instances in the persisted phantom_data volume: every connector
    # that already has an instance gets auto-installed. Otherwise
    # v0.5.0's "install gate" would refuse to register their tools.
    # Idempotent (re-running just no-ops). See marketplace_store
    # .upgrade_install_existing_instances for the contract. Replaces
    # the deleted connector_loader._AUTO_MIGRATION (Rule 2 of
    # canonical-state discipline).
    _existing_cids = list({inst.connector_id for inst in store.list_all()})
    _auto_installed = marketplace_store.upgrade_install_existing_instances(
        _existing_cids,
    )
    if _auto_installed:
        logger.info(
            "v0.5.0 upgrade migration: auto-installed %d connector(s) "
            "carrying existing instances from a pre-v0.5.0 install: %s",
            len(_auto_installed),
            ", ".join(sorted(_auto_installed)),
        )

    # v0.5.0 — connector.yaml schema validation. Every bundle
    # connector.yaml validates against the canonical schema at
    # bundles/spark/connectors/connector.schema.json. Drift fails
    # boot fast with a path-into-the-field error. See
    # usecase/connector_schema.py for the rationale + regression
    # history this guards against (v0.1.x camelCase/snake_case slot-
    # name drift, v0.1.27 missing version field, v0.3.x silent typo
    # in runtimeMapping.style). Same schema applies to user-uploaded
    # connectors in Phase E.
    from pathlib import Path as _Path
    from usecase.connector_schema import validate_all_bundle_connectors
    _bundle_root_candidates = [
        _Path(os.environ.get("BUNDLE_ROOT") or ""),
        _Path("/app/bundle"),
        _Path(__file__).resolve().parents[3],
    ]
    _bundle_root_path = next(
        (p for p in _bundle_root_candidates if p and (p / "manifest.yaml").is_file()),
        None,
    )
    if _bundle_root_path is None:
        logger.error(
            "v0.5.0 connector-schema validator could not locate bundle root; "
            "skipping pre-boot validation"
        )
    else:
        _schema_errors = validate_all_bundle_connectors(_bundle_root_path)
        if _schema_errors:
            for _err in _schema_errors:
                logger.error("connector.yaml validation: %s", _err)
            raise RuntimeError(
                f"v0.5.0 connector-schema validator rejected "
                f"{len(_schema_errors)} bundle connector(s); see logs above. "
                f"Fix the offending connector.yaml file(s) or revert the "
                f"breaking change before booting."
            )
        logger.info(
            "v0.5.0 connector-schema validator: all bundle connectors "
            "passed (root=%s)", _bundle_root_path,
        )

    # v1.2 Phase 8 — sessions + memory + context. The three capabilities
    # together form the agent's "cognitive layer":
    #
    #   - SessionStore: persistent conversation history (episodic memory).
    #     Retention from manifest.sessions.retention.
    #   - MemoryStore:  semantic key-value store with embedding-backed
    #     search (semantic memory). Embedder is currently the
    #     deterministic TextHashEmbedder; a future VertexEmbedder
    #     calling out to the configured Google provider is a drop-in
    #     replacement (same Embedder protocol).
    #   - ContextAssembler: per-turn working memory — bounded slice of
    #     the above two within manifest.context.budgetTokens.
    #
    # The stores are wired as module-level singletons (set_*_store)
    # so the built-in cognitive tools (memory_*, sessions_*) can
    # access them without explicit per-tool dependency injection.
    bundle_root = Path(os.getenv("BUNDLE_ROOT", "/app/bundle")).resolve()
    manifest_path = bundle_root / "manifest.yaml"
    sessions_cfg: dict = {}
    memory_cfg: dict = {}
    context_cfg: dict = {}
    knowledge_cfg: dict = {}
    settings_cfg: dict = {}
    notifications_cfg: dict = {}
    telemetry_cfg: dict = {}
    media_cfg: dict = {}
    observability_cfg: dict = {}
    if manifest_path.is_file():
        try:
            manifest_data = yaml.safe_load(manifest_path.read_text("utf-8")) or {}
            sessions_cfg = manifest_data.get("sessions") or {}
            memory_cfg = manifest_data.get("memory") or {}
            context_cfg = manifest_data.get("context") or {}
            knowledge_cfg = manifest_data.get("knowledge") or {}
            settings_cfg = manifest_data.get("settings") or {}
            notifications_cfg = manifest_data.get("notifications") or {}
            telemetry_cfg = manifest_data.get("telemetry") or {}
            media_cfg = manifest_data.get("media") or {}
            observability_cfg = manifest_data.get("observability") or {}
        except Exception as exc:
            logger.warning(
                "Phase 8/10: could not parse manifest %s for cognitive config (%s); "
                "using defaults", manifest_path, exc,
            )

    # Now that observability_cfg is populated from the manifest, finish
    # registering the metrics counters declared there. Pre-registering
    # them as Counters with value 0 means dashboards don't see "metric
    # not found" gaps in the warm-up window after a fresh boot before
    # the first tool call increments anything.
    declared_metrics: list[str] = []
    raw_metrics = observability_cfg.get("metrics") or []
    if isinstance(raw_metrics, list):
        for name in raw_metrics:
            if isinstance(name, str) and name:
                # Prometheus identifiers can't contain "."; the manifest
                # uses dotted names for readability. Map dot → underscore.
                pname = name.replace(".", "_")
                metrics.counter(pname, f"manifest-declared metric {name}")
                declared_metrics.append(pname)
    logger.info(
        "Metrics registry: %d total metric(s) (builtin=4, manifest=%d)",
        len(metrics.names()), len(declared_metrics),
    )

    # Observability — runtime structured event log. Distinct from the
    # forensic audit log: events are operational telemetry like
    # `rt.tool.failed` declared in manifest.observability.events.
    # Default 7-day retention sweep; old rows reaped at boot.
    declared_events: list[str] = []
    raw_events = observability_cfg.get("events") or []
    if isinstance(raw_events, list):
        declared_events = [str(e) for e in raw_events if isinstance(e, str)]
    events_store = SqliteEventLog(declared_events=declared_events)
    set_event_log(events_store)
    logger.info(
        "Runtime event log: %d declared event(s) (retention=7d)",
        len(declared_events),
    )

    # Translate manifest.sessions.retention "30d" → days int (best-effort).
    retention_days: int | None = None
    raw_retention = sessions_cfg.get("retention")
    if isinstance(raw_retention, str) and raw_retention.endswith("d"):
        try:
            retention_days = int(raw_retention[:-1])
        except ValueError:
            retention_days = None
    elif isinstance(raw_retention, int):
        retention_days = raw_retention

    embed_dims = int(memory_cfg.get("embeddingDims") or 768)
    embed_provider_id = str(memory_cfg.get("embeddingProvider") or "")
    embed_model = str(memory_cfg.get("embeddingModel") or "text-embedding-004")
    budget_tokens = int(context_cfg.get("budgetTokens") or 24000)
    strategy = str(context_cfg.get("strategy") or "hybrid")

    session_store = SqliteSessionStore(retention_days=retention_days)
    set_session_store(session_store)

    # Choose the embedder.
    #
    # POLICY: Vertex is authoritative for memory + KB embedding. Operator
    # explicitly requested no local-ML embedders (resource-constrained VM).
    # TextHashEmbedder is NOT a local ML model — it's a deterministic
    # SHA-256 + dim-bucketing stub (~zero compute, no model weights). It
    # exists ONLY to keep the agent UI bootable BEFORE the operator has
    # supplied Vertex creds, so they can navigate to /setup and complete
    # configuration. Once Vertex is live, no per-call fallback to TextHash
    # is allowed (see usecase/vertex_embedder.py).
    fallback_embedder = TextHashEmbedder(dims=embed_dims)
    embedder: Any = fallback_embedder
    embedder_mode = "stub"  # stub | vertex — surfaces in /api/v1/health
    if embed_provider_id == "google":
        try:
            vertex_instances = [
                p for p in provider_store.list_all() if p.provider_id == "vertex"
            ]
            if vertex_instances:
                # Pick the first materialized vertex instance — multi-
                # instance routing would attach per-tenant identity;
                # today there's one vertex configuration per deploy.
                inst = vertex_instances[0]
                from providers.vertex.src.provider import Provider as VertexProvider
                from usecase.vertex_embedder import VertexEmbedder
                # Resolve Phase-5 secret-store paths to literal values
                # for the provider __init__. Keep config + secrets split
                # to match the provider's two-arg constructor.
                resolved_secrets: dict[str, Any] = {}
                for slot, ref in inst.secret_refs.items():
                    if isinstance(ref, str) and ref.startswith("/") and secret_store:
                        try:
                            resolved_secrets[slot] = secret_store.read(ref)
                        except Exception as e:
                            logger.warning(
                                "vertex secret resolve failed for %s: %s", slot, e,
                            )
                            resolved_secrets[slot] = ""
                    else:
                        resolved_secrets[slot] = ref
                provider_obj = VertexProvider(
                    config=dict(inst.config), secrets=resolved_secrets,
                )
                # Note: we no longer pass `fallback=` — VertexEmbedder
                # ignores it and raises on per-call failure. The kwarg is
                # accepted for back-compat but elicits an info log.
                embedder = VertexEmbedder(
                    provider=provider_obj, model_id=embed_model,
                    dims=embed_dims,
                )
                embedder_mode = "vertex"
                # Stash the live embedder so /api/v1/metrics can pull
                # stats() at scrape time — see api/metrics.py.
                from usecase.vertex_embedder import set_embedder
                set_embedder(embedder)
                logger.info(
                    "Embedder=Vertex (model=%s, dims=%d) — authoritative; "
                    "no per-call demotion to TextHash. Failures will raise.",
                    embed_model, embed_dims,
                )
            else:
                # Setup not complete yet — agent is bootable but search
                # quality will be poor until the operator submits creds.
                # WARN-level so the message shows up in operational dashboards.
                logger.warning(
                    "Embedder=TextHash (DEGRADED). manifest.memory.embeddingProvider="
                    "google but no vertex provider instance is materialized. "
                    "Memory + KB search returns hash-similarity scores, NOT semantic "
                    "matches. Submit Vertex creds via /setup to upgrade.",
                )
        except Exception as exc:
            # Setup ostensibly complete but Vertex init blew up. This is
            # closer to a config bug than a transient outage — surface as
            # ERROR so it shows up in alerts.
            logger.error(
                "Embedder=TextHash (DEGRADED). Could not initialize VertexEmbedder: "
                "%s. Inspect provider config + secrets and restart.",
                exc,
            )
    else:
        # No embedding provider declared in manifest. Bundle author probably
        # forgot — flag it.
        logger.warning(
            "Embedder=TextHash (DEGRADED). manifest.memory.embeddingProvider not "
            "set — bundle has no declared embedding model. Set "
            "manifest.memory.embeddingProvider=google + embeddingModel="
            "text-embedding-004 to enable Vertex.",
        )

    # Stash mode for /api/v1/health to surface to the UI.
    import os as _os
    _os.environ["PHANTOM_EMBEDDER_MODE"] = embedder_mode

    memory_store = SqliteMemoryStore(embedder=embedder)
    set_memory_store(memory_store)

    # v1.2 Phase 10 — knowledge base. Same Embedder protocol as memory
    # (in fact we share the same instance, since dims must match for
    # any future cross-store comparison). The KbLoader walks the
    # bundle's knowledge.bundled[] directories at boot, parses each
    # markdown/JSON file, validates frontmatter against schema.json,
    # and upserts into the store. Hash-based change detection skips
    # re-embedding unchanged docs.
    kb = SqliteKnowledgeBase(embedder=embedder)
    set_knowledge_base(kb)
    bundled_kbs = knowledge_cfg.get("bundled") or []
    if isinstance(bundled_kbs, list) and bundled_kbs:
        try:
            kb_summary_counts = load_bundled_knowledge(
                kb=kb, bundle_root=bundle_root, bundled=bundled_kbs,
            )
            logger.info(
                "Knowledge bases loaded from bundle: %s", kb_summary_counts,
            )
        except Exception as exc:
            logger.warning("Phase 10: KB loader raised %s — continuing without bundled KBs", exc)
    else:
        logger.info("No knowledge.bundled[] in manifest — KB store empty")

    assembler = ContextAssembler(
        budget_tokens=budget_tokens,
        strategy=strategy,
    )
    set_context_assembler(assembler)

    # v1.2 — settings runtime store. Reads manifest.settings.{defaults,
    # overridable} from the bundle and persists overrides in
    # <data_root>/settings.db. Audit log is wired so every set/clear
    # records the manifest-declared `settings_changed` event with the
    # actor identity and old/new values (settings are non-secret so safe
    # to log). The store is reachable via settings_store() accessor for
    # tools that want to consult the effective config (e.g. the
    # `requireHumanApprovalForOperations` gate could be wired here in
    # a future tightening pass).
    settings_defaults = settings_cfg.get("defaults") or {}
    settings_overridable = settings_cfg.get("overridable") or []
    if not isinstance(settings_defaults, dict):
        logger.warning(
            "manifest.settings.defaults is not a mapping; settings store will boot empty"
        )
        settings_defaults = {}
    if not isinstance(settings_overridable, list):
        logger.warning(
            "manifest.settings.overridable is not a list; settings store will refuse all writes"
        )
        settings_overridable = []
    settings = SqliteSettingsStore(
        defaults=settings_defaults,
        overridable=settings_overridable,
        audit_log=audit,
    )
    set_settings_store(settings)

    # v1.2 Phase 11 — personality store. Migrated from agent-side
    # setup.json on first boot; subsequent boots are a no-op.
    personality = SqlitePersonalityStore()
    set_personality_store(personality)

    # Round-15 / Phase H — operator-registered lifecycle hooks. The
    # chat-route loads hooks fresh from this store at every event
    # fire-site (PreToolUse, PostToolUse, etc.) and dispatches them
    # through their declared transport.
    hook_store = SqliteHookStore()

    # Round-15 / Phase T — durable task registry. Long-running
    # workers and compaction summarizers flow through this store so
    # they're visible in /tasks and abortable from the chat header
    # drawer.
    task_store = SqliteTaskStore()
    set_task_store(task_store)

    # Round-15 / Phase M — connector state machine. Tracks per-
    # connector lifecycle (connected | failed | needs-auth |
    # pending | disabled) so operators can diagnose auth /
    # connectivity issues without parsing raw tool errors.
    connector_state_store = SqliteConnectorStateStore()
    set_connector_state_store(connector_state_store)

    # Round-15 / Phase S — agent definition registry. Operator-
    # authored AND plugin-contributed AgentDefinitions live here.
    # The chat-route's subagent_create tool resolves names via
    # this store; /agents UI reads + writes.
    agent_definition_store = SqliteAgentDefinitionStore()
    set_agent_definition_store(agent_definition_store)

    # Round-15 / Phase X — plugin loader. Discovers plugin
    # directories under bundles/spark/plugins/ at boot and applies
    # their contributions (skills, scenarios, memory seeds).
    # Idempotent — re-running just refreshes file copies and adds
    # any new memory seeds without overwriting operator edits.
    bundle_root_for_plugins = Path("/app/bundle")
    if not bundle_root_for_plugins.exists():
        # Dev paths: try repo-relative and ../ locations.
        for guess in (
            Path(__file__).resolve().parent.parent.parent,  # bundles/spark/
            Path("bundles/spark"),
        ):
            if (guess / "plugins").exists() or (guess / "manifest.yaml").exists():
                bundle_root_for_plugins = guess
                break
    plugin_loader = PluginLoader(
        plugins_root=bundle_root_for_plugins / "plugins",
        skills_dest_root=Path("/app/skills"),
        scenarios_dest_root=Path("/app/scenarios/ready"),
    )
    # Apply contributions at boot. Memory seeds skip already-present
    # keys, so this is safe to run on every restart. Phase S — also
    # passes the agent_definition_store so plugin-contributed agents
    # land in the registry on boot.
    try:
        applied = plugin_loader.apply_all(
            memory_store=memory_store,
            agent_definition_store=agent_definition_store,
        )
        if applied:
            logger.info(
                "plugin_loader: applied %d plugin(s); seeded %d "
                "memories",
                len(applied),
                sum(p.seeded_count for p in applied),
            )
    except Exception as exc:
        logger.warning("plugin_loader: boot apply failed: %s", exc)

    logger.info(
        "Settings store ready: %d defaults, %d overridable, %d existing overrides",
        len(settings_defaults),
        len(settings_overridable),
        len(settings.overrides()),
    )

    # API keys for external integrations. Wired AFTER audit so create()/
    # revoke() can record `api_key_created` / `api_key_revoked` events.
    # Set as a module-level singleton so api/auth.py's require_bearer()
    # can verify presented `phantom_ak_...` tokens against the store
    # without needing per-route dependency injection.
    api_keys = SqliteApiKeyStore(audit_log=audit)
    set_api_key_store(api_keys)
    active_count = sum(1 for k in api_keys.list() if k.revoked_at is None)
    logger.info("API key store ready: %d active key(s)", active_count)

    # Notifications dispatch from manifest.notifications.topics[]. Each
    # declared topic is loaded as a TopicSpec; publish() against an
    # undeclared topic is rejected (spec compliance).
    declared_topics: list[TopicSpec] = []
    raw_topics = notifications_cfg.get("topics") or []
    if isinstance(raw_topics, list):
        for raw in raw_topics:
            if not isinstance(raw, dict):
                continue
            try:
                declared_topics.append(TopicSpec.from_manifest(raw))
            except ValueError as exc:
                logger.warning("Skipping invalid manifest topic: %s", exc)
    # Phase 13 — channel:* webhook fan-out. Reads
    # PHANTOM_NOTIFICATION_CHANNEL_<NAME> env vars at construction;
    # channels with no URL configured raise a clear "no webhook
    # URL" error per dispatch (folded into dispatch_status=failed
    # by publish()). Operators add a new channel by setting the env
    # var + restarting; channels in the manifest with no URL stay
    # silent rather than blocking publishes.
    from usecase.notification_dispatcher import WebhookDispatcher
    notifications = SqliteNotificationStore(
        topics=declared_topics, audit_log=audit,
        dispatch_hook=WebhookDispatcher(),
    )
    set_notification_store(notifications)
    logger.info(
        "Notifications store ready: %d declared topic(s)", len(declared_topics)
    )

    # Telemetry — opt-in usage counters per manifest.telemetry.events[].
    # Privacy-by-default: starts disabled when manifest.telemetry.default
    # == "off" (the bundle's chosen posture). Persists the toggle so
    # operator opt-in survives container restarts.
    declared_telemetry_events: list[str] = []
    raw_te = telemetry_cfg.get("events") or []
    if isinstance(raw_te, list):
        declared_telemetry_events = [str(e) for e in raw_te if isinstance(e, str)]
    default_enabled = (str(telemetry_cfg.get("default") or "off").lower() == "on")
    telemetry = SqliteTelemetryStore(
        declared_events=declared_telemetry_events,
        default_enabled=default_enabled,
        audit_log=audit,
    )
    set_telemetry_store(telemetry)
    logger.info(
        "Telemetry store ready: %d declared event(s), enabled=%s",
        len(declared_telemetry_events), telemetry.is_enabled(),
    )

    # Media uploads — operator file uploads (PDFs, text), bounded by
    # manifest.media.uploadMaxMb, optionally processed by named
    # extractors from manifest.media.processors[]. Today only
    # text_passthrough is fully wired; pdf_text is a stub awaiting a
    # `pypdf` dep. Bytes live at <data_root>/media/<id>/<filename>;
    # metadata + extracted text live in media.db.
    upload_max_mb = int(media_cfg.get("uploadMaxMb") or 25)
    raw_processors = media_cfg.get("processors") or []
    declared_proc_list: list[str] = (
        [str(p) for p in raw_processors if isinstance(p, str)]
        if isinstance(raw_processors, list) else []
    )
    media = SqliteMediaStore(
        upload_max_mb=upload_max_mb,
        declared_processors=declared_proc_list,
        audit_log=audit,
    )
    set_media_store(media)
    logger.info(
        "Media store ready: max=%d MB, processors=%s",
        upload_max_mb, declared_proc_list,
    )

    # v1.2 stage 3C — register HTTP admin endpoints for instance CRUD,
    # provider CRUD (§7.6), and setup-form materialization. Endpoints
    # are auth-gated by the MCP_TOKEN env var (see api/auth.py). These
    # stay live in BOTH standalone and Spark-platform mode — the
    # platform's install pipeline calls them to introspect bundle
    # connector + provider definitions before publishing them to the
    # workspace marketplace + provider registry.
    register_instance_routes(mcp, store)
    register_provider_routes(mcp, provider_store)
    # v0.4.0: register_setup_routes retired (see import comment above).
    # v1.2 Phase 6 — read-only audit query endpoints. Append-only at
    # the storage layer; this just exposes filter/summary read paths.
    register_audit_routes(mcp, audit)
    # v0.1.31 — UI password verify + change endpoints, backed by the
    # SecretStore (AES-256-GCM at rest when PHANTOM_SECRET_KEK is set).
    # The Next.js login route calls /verify; the /profile page calls
    # /password to rotate. Stays bundle-internal (MCP_TOKEN bearer)
    # so an attacker who steals an operator browser session can't
    # change the password — they'd need the agent's process secrets.
    register_ui_auth_routes(mcp)
    # v1.2 Phase 7 — approvals query + resolve endpoints. Operators
    # use these to unblock tools that the bundle's
    # approvals.humanRequired list flagged as needing human consent.
    register_approval_routes(mcp, approvals)
    # v1.2 Phase 8 — cognitive endpoints (sessions, memories, context).
    # The agent UI uses these to render conversation history, manage
    # semantic memory, and inspect what context will be sent to the LLM.
    register_cognitive_routes(mcp, session_store, memory_store, assembler)
    # v1.2 Phase 10 — knowledge-base endpoints (READ-ONLY at the API
    # surface; matches manifest.kbWrites: []).
    register_kb_routes(mcp, kb)
    # v1.2 — runtime settings overrides for manifest.settings.overridable.
    # Audit-logged via the wired SqliteAuditLog (Phase 6) using the
    # manifest-declared `settings_changed` event.
    register_settings_routes(mcp, settings)
    register_personality_routes(mcp, personality)
    # v0.3.4 — operator-direct skills CRUD over REST (bypasses the
    # Phase-11 `skills_delete` gated tool path that exists for chat-
    # driven self-mod). The Next.js `/skills` page proxies to these
    # endpoints; clicks from the operator UI ARE the approval.
    register_skill_routes(mcp)
    # Round-15 / Phase H — hooks API (list / get / upsert /
    # toggle / delete). The chat-route loads hooks at every event
    # fire-site; the /settings/hooks UI is the operator surface.
    register_hook_routes(mcp, hook_store, audit)
    # v0.5.35 / Issue #24 UI — bench run history + per-run detail +
    # invoke. BenchRunStore was added in v0.5.29; v0.5.33 wired the
    # runner; v0.5.35 wires the HTTP surface + UI page so operators
    # browse runs without sqlite-digging.
    bench_run_store = BenchRunStore()
    set_bench_store(bench_run_store)
    register_bench_routes(mcp, bench_run_store)
    # v0.5.36 / Issue #29 — plugin discovery at MCP startup. v0.5.31
    # shipped the discovery scaffolding (plugin_entry_points.py) but
    # left the boot-time call wire deferred. v0.5.36 wires it: at
    # startup, walk all five reserved entry-point groups and log
    # per-group counts. Fresh installs see zero plugins (expected —
    # no third-party packages target these groups yet); future
    # installs see counts in the boot log + audit trail.
    try:
        from usecase.plugin_entry_points import log_discovery
        log_discovery()
    except Exception:
        logger.exception(
            "plugin_entry_points: boot-time log_discovery() failed — "
            "continuing without plugin discovery (existing image-baked "
            "builtins / skills / connectors are unaffected)"
        )
    # v0.5.44 / Issue #29 UI gap fill — register /api/v1/plugin-entries
    # HTTP endpoint so the /observability/plugins UI page can query the
    # discovered entry-point plugin catalog. Distinct from the older
    # api/plugins.py (filesystem-discovered Phase X plugins, registered
    # below with its full 5-arg signature). Two systems coexist; the
    # naming distinguishes them so the routes don't collide.
    # v0.5.47 — same module hosts POST /install + DELETE /{dist_name}
    # for pip-driven plugin lifecycle.
    register_plugin_entry_points_routes(mcp)
    # v0.5.48 / Issue #29 final wire — plugin handler invocation
    # bridge. Plugin-contributed handlers in the phantom.hooks
    # entry-point group become callable from the agent's hook-
    # runner via /api/v1/plugin-hooks/{name}/invoke. Closes the
    # cross-language hook-handler bridge.
    register_plugin_hook_invoke_routes(mcp)
    # Round-15 / Phase T — task registry API (list / get / create /
    # transition / abort). Long-running workers write progress here;
    # /tasks UI reads.
    register_task_routes(mcp, task_store, audit)
    # Round-15 / Phase M — connector state API. Surfaces per-
    # connector lifecycle for /connectors UI and the chat-route's
    # post-tool-error needs-auth signaling.
    register_connector_routes(mcp, connector_state_store, store, audit)

    # v0.5.0 — marketplace catalogue + install state surface. Routes
    # at /api/v1/marketplace/* — see api/marketplace.py. Next.js
    # routes under app/api/agent/marketplace/* proxy to these
    # (same pattern as auth, audit, instances).
    from api.marketplace import register_marketplace_routes
    register_marketplace_routes(mcp, marketplace_store, store)

    # v0.5.1 — operator workflow state surface. Routes at
    # /api/v1/operator-state/* — see api/operator_state.py. Next.js
    # hooks (use-tested-journeys, metrics-bookmarks) proxy to these.
    from api.operator_state import register_operator_state_routes
    register_operator_state_routes(mcp, operator_state_store)
    # Round-15 / Phase X — plugin inventory + reload API. Phase S
    # extends this with agent_definition_store so a Reload click
    # also re-applies plugin-contributed agents.
    register_plugin_routes(
        mcp,
        plugin_loader,
        memory_store,
        audit,
        agent_definition_store=agent_definition_store,
    )
    # Round-15 / Phase S — agent-definition registry API.
    register_agent_definition_routes(mcp, agent_definition_store, audit)
    # Operator-minted API keys for external integrations. These routes
    # require MCP_TOKEN — the api-key minting surface itself is admin-
    # only, otherwise an attacker with one scoped key could mint wider
    # ones for themselves.
    register_api_key_routes(mcp, api_keys)
    # Admin endpoints (operator-driven runtime reloads). Today this
    # is just /api/v1/admin/reload_tools, which the setup endpoint
    # also calls automatically after replace:true so the operator
    # doesn't need to restart phantom-agent for new tools to surface.
    register_admin_routes(mcp)
    # Update introspection — exposes manifest.update + current build
    # provenance. autoUpdate machinery itself is documented future work
    # (see api/update.py docstring); this endpoint makes the deploy's
    # update posture inspectable today.
    register_update_routes(mcp)
    # Notifications publish/list/ack/topics. Tools call publish() to
    # emit; the agent UI's notification bell calls list/unread_count
    # to render badges.
    register_notification_routes(mcp, notifications)
    # Opt-in telemetry endpoints. Privacy-by-default: telemetry is OFF
    # at first boot (manifest.telemetry.default = "off"); toggle is
    # operator-driven via /api/v1/telemetry/enable.
    register_telemetry_routes(mcp, telemetry)
    # Media uploads. Multipart form receive on POST; raw download on
    # GET /raw; metadata + extracted text on GET /{id}. Useful for
    # the agent's chat composer attaching context files.
    register_media_routes(mcp, media)
    # Observability — Prometheus exposition + JSON snapshot. /metrics
    # is intentionally unauthenticated (Prometheus scrape standard).
    register_metrics_routes(mcp, metrics)
    # Observability — runtime structured event endpoints.
    register_observability_routes(mcp, events_store)
    logger.info(
        "Admin HTTP endpoints registered: /api/v1/instances/*, "
        "/api/v1/providers/*, /api/v1/models, /api/v1/setup, "
        "/api/v1/audit/*, /api/v1/approvals/*, /api/v1/sessions/*, "
        "/api/v1/memories/*, /api/v1/context, /api/v1/jobs/*, "
        "/api/v1/kbs/*, /api/v1/settings, /api/v1/api_keys, "
        "/api/v1/notifications/*, /api/v1/telemetry/*, "
        "/api/v1/media/*, /api/v1/metrics, /api/v1/observability/events*, "
        "/api/v1/admin/*, /api/v1/update/*, "
        "/api/v1/ui/* (Phase 11)"
    )

    # v1.2 stage 3E — Spark-platform supersession (objective 6).
    #
    # When SPARK_PLATFORM_GATEWAY is set, the platform's central
    # connector-manager MCP is the agent's tool surface — this
    # embedded MCP MUST NOT register connector tools, otherwise the
    # agent would see two namespaces serving the same tool names.
    # Per spec §7.5: tool gating + auto-migration still happen, but
    # against `connector_instances` rows materialized server-side
    # from the bundle's setup.bindsInstances[] templates by the
    # platform install pipeline.
    #
    # Admin HTTP endpoints registered above stay live so the platform
    # can:
    #   1. GET /api/v1/setup → introspect bundle connector definitions
    #   2. push them to the workspace marketplace via
    #      gateway.PublishConnector, gated on admin approval
    #
    # Non-tool-related capabilities (sessions, audit, observability,
    # heartbeat) remain the runtime's concern in either mode.
    platform_mode = bool(os.getenv("SPARK_PLATFORM_GATEWAY"))
    if platform_mode:
        logger.info(
            "Spark-platform mode detected (SPARK_PLATFORM_GATEWAY=%s). "
            "Embedded MCP yields connector tool advertisement to the "
            "platform's connector-manager. See spec §7.5 for the "
            "supersession contract.",
            os.environ["SPARK_PLATFORM_GATEWAY"],
        )

    # v1.2 Phase 9 — keep a parallel registry of (name → wrapped callable)
    # so the scheduler can dispatch tool calls without poking into FastMCP
    # internals. Built up by register_all_tools() below.
    tool_registry: dict[str, Any] = {}
    if not platform_mode:
        # First-pass registration: covers every connector instance that
        # exists at boot. Idempotent — additional instances materialized
        # later via /api/v1/setup will be picked up by reload_tools_now()
        # without needing a process restart (Phase 13 hot-reload).
        namespaced_count, legacy_count = register_all_tools(
            mcp=mcp,
            store=store,
            secret_store=secret_store,
            tool_registry=tool_registry,
            include_legacy=include_legacy,
        )
        # Stash the wiring so /api/v1/admin/reload_tools and the post-
        # setup auto-reload can invoke register_all_tools() without
        # threading the args through every callsite.
        set_reload_state(
            mcp=mcp,
            store=store,
            secret_store=secret_store,
            tool_registry=tool_registry,
            include_legacy=include_legacy,
        )

        summary = tool_summary(store=store)
        logger.info(
            "MCP tools registered: %d namespaced + %d legacy aliases "
            "(per-connector counts: %s, legacy aliases: %s)",
            namespaced_count,
            legacy_count,
            summary,
            "ON" if include_legacy else "OFF",
        )
        prov_summary = provider_summary(store=provider_store)
        logger.info(
            "Active model provider catalog (per-provider model counts: %s)",
            prov_summary,
        )
    else:
        logger.info(
            "MCP tool registration skipped (Spark-platform mode); "
            "platform's connector-manager + /api/v1/models are the "
            "active tool + model surfaces."
        )

    # v1.2 Phase 9 — jobs scheduler. Wired AFTER tool registration so
    # the dispatcher can resolve action.name to a wrapped callable.
    # Disabled in platform mode (the platform's central scheduler runs
    # the bundle's manifest.jobs[] as Kubernetes CronJobs and dispatches
    # back through its connector-manager — same path, different host).
    sched: CroniterJobScheduler | None = None
    if not platform_mode:
        manifest_jobs_raw = []
        if manifest_path.is_file():
            try:
                manifest_data2 = yaml.safe_load(manifest_path.read_text("utf-8")) or {}
                manifest_jobs_raw = manifest_data2.get("jobs") or []
            except Exception as exc:
                logger.warning(
                    "Phase 9: could not read manifest.jobs[]: %s", exc
                )

        defs: list[JobDefinition] = []
        for j in manifest_jobs_raw:
            if not isinstance(j, dict):
                continue
            name = j.get("name")
            cron_expr = j.get("cron")
            if not isinstance(name, str) or not isinstance(cron_expr, str):
                continue
            defs.append(JobDefinition(
                name=name,
                cron=cron_expr,
                timezone=str(j.get("timezone") or "UTC"),
                action=j.get("action") or {},
            ))

        # v0.3.11: build the tool dispatcher unconditionally and install
        # it via the process-wide singleton so agent_batch_propose can
        # reach connector tools through the same fastmcp.Client path the
        # scheduler uses. Pre-v0.3.11 the dispatcher only existed inside
        # the `if defs:` branch; batch dispatch needs it regardless of
        # whether the bundle declared any cron jobs.
        from usecase.tool_dispatcher import set_tool_dispatcher  # noqa: PLC0415
        dispatcher = make_tool_dispatcher(tool_registry, mcp=mcp)
        set_tool_dispatcher(dispatcher)

        # v0.6.21 — always construct the scheduler + register routes,
        # even when manifest.yaml has `jobs: []` and no runtime YAML
        # job exists yet. Pre-v0.6.21 the scheduler was only built
        # inside `if defs:` (line 1037 below pre-fix); on fresh installs
        # where the bundle ships `jobs: []` (the default for spark/),
        # `register_job_routes()` was never called, so the /api/v1/jobs
        # GET endpoint AND the POST endpoint for creating new runtime
        # jobs both returned 404 — meaning the operator's first attempt
        # to create a runtime job via the /jobs/new UI page 404'd
        # silently. Catch-22: routes don't exist until a job exists,
        # but the only way to create a job is through the routes.
        #
        # Same fix-shape as the v0.3.11 dispatcher fix (lines 1027-1035
        # above): build the singleton unconditionally so the proxy paths
        # work even with an empty manifest. Scheduler start is still
        # conditional — no point firing the asyncio scheduler loop if
        # there are no jobs to schedule. The loop spins up when the
        # first job lands (via POST /api/v1/jobs or a manifest update).
        sched = CroniterJobScheduler(definitions=defs, dispatcher=dispatcher)
        set_scheduler(sched)
        register_job_routes(mcp, sched)
        # v0.6.21 — start the scheduler unconditionally. The loop is
        # cheap when there's nothing to fire (just a periodic
        # poll for due jobs). Starting it always means a POST
        # /api/v1/jobs that adds a runtime job mid-process picks up the
        # fire-cycle immediately, without an MCP restart. Pre-v0.6.21
        # the start was gated on `if defs:` so if the manifest was
        # empty AND no YAML runtime jobs existed at boot, the scheduler
        # never started — a runtime job created later via POST would
        # land in SQLite but no loop would fire it.
        await sched.start()
        logger.info(
            "Job scheduler started; manifest=%d, total=%d job(s): %s",
            len(defs),
            len(sched.list_jobs()),
            [r.name for r in sched.list_jobs()],
        )
    else:
        logger.info(
            "Job scheduler skipped (Spark-platform mode); platform runs "
            "the bundle's manifest.jobs[] as Kubernetes CronJobs."
        )

    # Start server with appropriate transport configuration.
    # Phase 9: shutdown the scheduler cleanly when the server exits so
    # we don't leave dangling asyncio tasks complaining at process exit.
    async def _shutdown_scheduler() -> None:
        if sched is not None:
            sched.stop()
            t = sched.task
            if t is not None:
                try:
                    await asyncio.wait_for(t, timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    t.cancel()

    if transport == "stdio":
        try:
            await mcp.run_async(transport=transport)
        finally:
            await _shutdown_scheduler()
    else:
        # Use uvicorn for HTTP transport
        app = mcp.http_app(path=config.mcp_path, transport=transport)

        # Observability — request-log middleware. One structured access
        # log line per HTTP call + metrics observation
        # (phantom_mcp_http_requests_total / _duration_seconds). Toggle
        # off via PHANTOM_REQUEST_LOG=0 if an operator wants silence.
        from api.request_log import install as install_request_log
        install_request_log(app)

        # Trigger-context middleware — reads `X-Phantom-Trigger` from
        # the inbound request and sets a contextvar that audit_log's
        # record() picks up. This is what tags audit rows with the
        # source of activity (e.g. `job:nightly-report`) so
        # operators can filter the audit feed by trigger. The header
        # flows from job_scheduler → /api/chat → MCP tool dispatch
        # in one continuous chain.
        from api.trigger_context import install as install_trigger_context
        install_trigger_context(app)

        # OTel tracing — opt-in via PHANTOM_OTEL=1 + OTEL_EXPORTER_OTLP_
        # ENDPOINT. No-op when either is unset. Auto-instruments the
        # Starlette app + outbound httpx (Vertex, XSIAM
        # PAPI) so operators get a per-request waterfall in Jaeger /
        # Honeycomb / Tempo / etc. without any tool-side annotation.
        from api.tracing import install as install_tracing
        install_tracing(app)

        ssl_keyfile = config.ssl_key_file
        ssl_certfile = config.ssl_cert_file

        # Handle SSL via PEM content if files are not provided
        def normalize_pem(pem_str: str) -> str:
            """Normalize PEM content for proper formatting."""
            content = pem_str.replace("\\n", "\n").replace("\\r", "")
            content = content.replace("-----BEGIN CERTIFICATE-----", "-----BEGIN CERTIFICATE-----\n")
            content = content.replace("-----END CERTIFICATE-----", "\n-----END CERTIFICATE-----")
            content = content.replace("-----BEGIN PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----\n")
            content = content.replace("-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----")
            content = content.replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----\n")
            content = content.replace("-----END RSA PRIVATE KEY-----", "\n-----END RSA PRIVATE KEY-----")
            while "\n\n" in content:
                content = content.replace("\n\n", "\n")
            return content.strip() + "\n"

        temp_files = []
        if not ssl_keyfile and config.ssl_key_pem:
            key_temp = tempfile.NamedTemporaryFile(delete=False, mode="w")
            key_temp.write(normalize_pem(config.ssl_key_pem))
            key_temp.close()
            ssl_keyfile = key_temp.name
            temp_files.append(key_temp.name)

        if not ssl_certfile and config.ssl_cert_pem:
            cert_temp = tempfile.NamedTemporaryFile(delete=False, mode="w")
            cert_temp.write(normalize_pem(config.ssl_cert_pem))
            cert_temp.close()
            ssl_certfile = cert_temp.name
            temp_files.append(cert_temp.name)

        # Register cleanup on exit
        def cleanup_temp_files():
            for f in temp_files:
                if os.path.exists(f):
                    os.unlink(f)

        atexit.register(cleanup_temp_files)

        server_config = uvicorn.Config(
            app=app,
            host=config.mcp_host,
            port=config.mcp_port,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            log_level=config.log_level.lower(),
        )
        server = uvicorn.Server(server_config)
        try:
            logger.info(f"Starting HTTP server on {config.mcp_host}:{config.mcp_port}")
            await server.serve()
        finally:
            await _shutdown_scheduler()
            cleanup_temp_files()


def main():
    """
    Entry point for the Phantom MCP Server application.
    """
    try:
        asyncio.run(async_main(get_config().mcp_transport))
    except Exception as e:
        logger.exception(f"Main loop stopped: {e}")
    finally:
        logger.info("Phantom MCP Server has shut down.")


if __name__ == "__main__":
    main()
