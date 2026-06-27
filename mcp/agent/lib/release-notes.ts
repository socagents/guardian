/**
 * Release-notes history — bundled with the UI image so the About
 * modal works offline (customer environments may be air-gapped from
 * GitHub).
 *
 * Authoring contract:
 *   * Newest entry first. The modal renders in array order.
 *   * `version` is bare semver (no "v" prefix) so it compares
 *     directly with /api/agent/version.
 *   * `date` is ISO yyyy-mm-dd of the GHCR publish.
 *   * `highlights` are 3-7 bullets, operator-facing language. No
 *     internal commit shorthand. Aim for ~10-15 words each.
 *   * `categories` is optional structure for security-heavy releases
 *     where bullets-only flattens too much detail.
 *   * `headline` flags become visual badges in the modal — use
 *     sparingly. `security: true` adds a red shield. `breaking: true`
 *     adds a yellow warning.
 *
 * When you cut a release: prepend a new entry here in the same PR
 * that creates the tag. The image rebuilt for that tag will then
 * carry its own notes — no fetch from GitHub required.
 */

// [guardian v0.1.0] Retired: the upstream Phantom release history
// (0.1.x–0.17.x entries) — Guardian is a new product whose history
// starts at v0.1.0; the inherited entries described removed subsystems.

export interface ReleaseNote {
  version: string;
  date: string;
  title: string;
  highlights: string[];
  categories?: { name: string; items: string[] }[];
  security?: boolean;
  breaking?: boolean;
}

export const RELEASE_NOTES: ReleaseNote[] = [
  {
    version: "0.2.88",
    date: "2026-06-27",
    title: "XSIAM lookup datasets create + populate correctly.",
    highlights: [
      "Removed the broken create_dataset tool — it called a Cortex endpoint that doesn't exist and hung.",
      "add_lookup_data now both creates and populates a lookup dataset (it auto-creates on first write).",
      "Fixed the row payload shape — one object per write, not an array — which was the cause of the hang.",
    ],
  },
  {
    version: "0.2.87",
    date: "2026-06-27",
    title: "Sharper xdr_data XQL authoring (from a live tenant pilot).",
    highlights: [
      "The cortex_xql_query_authoring skill now teaches xdr_data's conventions: event_type is an ENUM (event_type = ENUM.PROCESS, not the string \"PROCESS\").",
      "Resolve exact field names from the schema before authoring; direct dataset=xdr_data queries use flat fields (actor_process_image_name), while xdm.* dotted paths are the datamodel view only.",
      "Surfaced + fixed via a live XSIAM pilot where the agent's XQL syntax was strong but it fumbled dataset-specific field names + enum literals.",
    ],
  },
  {
    version: "0.2.86",
    date: "2026-06-26",
    title: "XSIAM connector: Standard + Advanced API key auth.",
    highlights: [
      "The Cortex XSIAM connector now supports both Standard and Advanced API keys via a new “API key security level” setting (Standard default, Advanced opt-in).",
      "An Advanced key is signed per request with a SHA-256 nonce+timestamp; a Standard key is sent verbatim. A level mismatch is what causes a 401 “Public API request unauthorized”.",
    ],
  },
  {
    version: "0.2.85",
    date: "2026-06-26",
    title: "Create-instance reliability: no phantom “already exists” error.",
    highlights: [
      "Creating a connector instance no longer shows a false “this instance already exists” error when the instance was actually created.",
      "Root cause: the UI client auto-retried the create request after the container start exceeded the 15s proxy timeout; the retry hit the existing row and 409'd.",
      "Fix: the API client never auto-retries a state-changing request (only idempotent reads), and the per-instance container now starts in the background so create returns immediately.",
    ],
  },
  {
    version: "0.2.84",
    date: "2026-06-25",
    title: "Playbook Builder: standard object-page + recorded build history.",
    highlights: [
      "/playbooks/build is now a standard object-list page like Skills: stat cards (Total / Deployed / Validated / Failed), status tabs, search, and a grid of past builds.",
      "A New playbook button opens the builder panel; clicking a build card opens a detail panel with its YAML, validation, and deploy result.",
      "Every build is recorded with a lifecycle status (drafted → validated → deployed → tested, or failed) and stays browsable — download the .yml or delete it any time.",
      "New audit events — playbook_drafted, playbook_deployed, playbook_test_run, playbook_build_deleted — surface in /observability/events and the activity log.",
      "The agent can manage your build history via five catalog-side tools (list / get / record / update / delete) — build metadata only, no secrets.",
    ],
  },
  {
    version: "0.2.83",
    date: "2026-06-25",
    title: "^tool dispatch correlation: complete the trigger/chain fix (#86).",
    highlights: [
      "An operator ^tool direct dispatch now records the operator:direct trigger + the dispatch chain_id (and real principal) on its tool_call audit row, instead of dropping to none.",
      "Root cause: the embedded MCP runs the tool inside the streamable-HTTP session task spawned at `initialize`, so the markers had to be forwarded on that request — not only on the later tools/call. Completes the v0.2.82 same-task-middleware work for the path it didn't reach.",
    ],
  },
  {
    version: "0.2.82",
    date: "2026-06-25",
    title: "Audit attribution + correlation reliability (from the live interface-coverage pass).",
    highlights: [
      "Tool-call audit rows now attribute to the real principal for ^tool/API-key dispatches (was always 'agent', discarding the forwarded identity); model-internal calls still record 'agent'.",
      "The request-context middleware (trigger/actor/chain_id) is now pure-ASGI (same-task), reliable for per-request handlers. (The ^tool direct-dispatch path uses a decoupled streamable-HTTP session and can still miss trigger/chain_id — tracked; chat + scheduled-job tool calls are correctly correlated.)",
      "Normalized the API-key principal to one format (apikey:<id>) across tiers — a forensic ?actor= filter no longer misses half the rows, and the hook-delete owner check works for API-key operators.",
      "KB audit hygiene: a doc read / search no longer double-emits kb_doc_read / kb_searched, and active+REST searches carry the same bounded query preview as the passive path.",
      "A loopback hook fire missing the inner event field now defaults to the dispatched event and matches instead of being silently dropped.",
    ],
  },
  {
    version: "0.2.81",
    date: "2026-06-24",
    title: "Hook hardening + audit chain correlation (final harness-coverage features).",
    highlights: [
      "Hooks record their creator; a plugin/system-contributed hook can't be deleted or content-edited by an operator (enabled toggle stays open). Operator-created + pre-existing hooks unaffected.",
      "A shell hook's secret: reference resolves through the managed Secret Store (audited read) instead of raw container env, and fails closed if unresolvable (no env leak). Same fix for the Slack-approval hook.",
      "Each chat turn stamps a chain_id on its tool-call audit rows so a multi-step action chain (isolate → remediate → unisolate) is followable end-to-end and partial failures are traceable.",
      "Internal: POST /api/v1/secrets/resolve is MCP-token-only (an API key can never resolve a secret); hooks + audit tables gained backward-compatible created_by / chain_id columns via idempotent migrations.",
    ],
  },
  {
    version: "0.2.80",
    date: "2026-06-24",
    title: "Doc accuracy, version sync, honest tool status.",
    highlights: [
      "The downloaded OpenAPI spec now reports the real stack version (was a hardcoded 0.2.0) and both its JSON/YAML paths fail gracefully.",
      "XSIAM write tools (IOC enable/disable, endpoint alias, hash blocklist, alert-exclusion delete) now inspect the API reply and surface the real error instead of echoing input-derived success.",
      "A bypass-approvals job no longer stalls on a connector-gated tool — it auto-approves immediately with an auto_approved trace, matching built-in tools.",
      "A job's bypass_approvals/model/thinking/permission-policy settings survive a YAML reload instead of reverting to defaults on boot.",
      "Docs corrected to match the code: knowledge pages show the real embedding model, the Traces tile describes the audit-derived view, and connector/version pins + model lists + service counts + tool catalogs were synced.",
    ],
  },
  {
    version: "0.2.79",
    date: "2026-06-24",
    title: "No dead clicks: every operator affordance now wires to real backing or is retired.",
    highlights: [
      "Plan mode delivers on its promise — an \"Approve & run\" button on the plan card executes the whole plan with a one-shot per-tool-approval bypass; the inline chat title edit now persists like the sidebar rename.",
      "Reloaded chats show the truth: failed tool calls render as errors (not silent successes), and a turn's reasoning re-renders in its Thinking section.",
      "Connectors page gains per-instance Restart + a Reconcile sweep to self-heal wedged containers; the /approvals page now enforces the CONFIRM ceremony for credential-tier tools.",
      "Knowledge gains a cross-KB search box; the pipeline graph renders your actual connectors; a new Telemetry page exposes the opt-in usage-counter posture; deleted skills are restorable in-product.",
      "Memory: the session tab lists real session-scoped entries and FTS-promoted hits show their badge. Personality: the escalation threshold now shapes the agent's prompt; the unused daily-summary toggle was removed.",
      "New proxy routes surface previously MCP-only endpoints (investigation report / related cases / technique + playbook issues, personality history, telemetry) to the UI and API catalog; job exports leave an audit trail.",
    ],
  },
  {
    version: "0.2.78",
    date: "2026-06-24",
    title: "Input-validation hardening: path-traversal guard, deny-list enforcement, fail-closed rejections.",
    highlights: [
      "Skill read/update/enable/delete reject paths that are absolute or escape the skills directory (../../…) — closes a path-traversal vector.",
      "A connector manifest's tools.deny[] is enforced at registration, so a denied tool can't be reached even by direct dispatch; subagents can't call the parent-only subagent_create and PreToolUse hooks run before subagent dispatch.",
      "Unknown API-key scopes map to read/write tiers correctly (unknown→nothing); reading a missing skill returns 404; listing an unknown KB returns valid names; memory-store embed failures return a friendly error.",
      "Vertex / XSOAR / XSIAM instance probes now validate credentials instead of always reporting success.",
      "New-job timezone defaults to the browser zone; an unsupported-action job auto-disables on first fire; regenerating an unchanged report/diagram no longer collides on a duplicate job name; a partial backup is detectable from response headers.",
    ],
  },
  {
    version: "0.2.77",
    date: "2026-06-24",
    title: "Observability granularity, part 2: job runtime events, quieter-failure signals, proxy failure traces.",
    highlights: [
      "Scheduled-job fire/complete/fail now mirror into the runtime event log (with counters) so the events view isn't near-empty on a healthy install.",
      "The high-volume secret_read success row is tunable via GUARDIAN_AUDIT_SECRET_READ (default on); failed reads always audit.",
      "Quieter failures now leave a signal: job skill-skip, unavailable skills block, subagent task-uncreated, proxy_request_failed (fetch error / 5xx); plugin install/uninstall persist fuller stdout/stderr.",
      "Subagent reasoning streams separately (kept out of the stored transcript), matching the main loop.",
      "The /cost page warns when it hits its row cap (totals are a floor); chat_turn_cost carries finish reason; repeated compaction-checkpoint failures back off instead of re-paying every turn.",
    ],
  },
  {
    version: "0.2.76",
    date: "2026-06-24",
    title: "Finer-grained observability: per-phase research, honest turn status, size guards, embedding accounting.",
    highlights: [
      "deep_research results now carry a per-phase breakdown (plan/search/fetch/gap-check/synthesize + counts + timings) and warnings, so partial coverage is visible instead of one opaque event.",
      "Chat-turn status reports the true exit cause (safety block / tools-only / budget-exhausted) instead of mislabeling 'completed'; compaction-checkpoint save failures and /cost truncation (>1000 rows) are surfaced.",
      "guardian_web_screenshot accepts a max_bytes cap (default 4 MiB) and returns a bounded rejection instead of a multi-MB image in context.",
      "KB load records pre-baked vs live-embedded document counts — a zero-cost boot is distinguishable from one that paid for hundreds of Vertex embeds.",
      "Memory-injection errors/zero-hits, invalid built-in hooks (now badged in the Hooks page), and SVG-too-large diagram rejections each leave a signal; the agent→MCP proxy stamps per-request latency + request-id.",
    ],
  },
  {
    version: "0.2.75",
    date: "2026-06-24",
    title: "Forensic audit trail, part 3: chat-turn observability.",
    highlights: [
      "Chat-turn auto-retries (leaked tool call / empty response), safety/recitation blocks, context-window hard blocks, turn-cache hits, and suppressed repeat-failing tool calls now each leave a distinct audit row.",
      "Slash commands (/model set+clear, /clear, /help, /tasks) and model switches are audited to the operator; read-only status queries are not, to keep the log signal-rich.",
      "A turn started from a quick-action chip is now distinguishable from a typed message in the audit + live stream.",
      "Operator-state toggles attribute to the real principal (proxy now forwards actor/trigger headers); their events are declared for the observability filter.",
      "The end-of-turn 'changes applied' recap now recognizes newly-shipped mutating tools via a write-verb heuristic so a side-effecting tool isn't omitted.",
    ],
  },
  {
    version: "0.2.74",
    date: "2026-06-24",
    title: "Forensic audit trail, part 2: knowledge / memory / skills / subagents / hooks / providers / auth probes.",
    highlights: [
      "Knowledge-base list/tag reads, embed-failed searches, and memory/KB search query previews (+ active/passive mode) are now audited — 'what was searched, by whom' is answerable.",
      "Skill updates record the body's before/after SHA-256; a job records which skill it ran with. Agent-definition + operator-state reads are audited.",
      "Testing a Vertex credential records provider_probed (SA email + project — never the private key); provider config changes use a dedicated action.",
      "Wrong-username logins and rate-limit lockouts now leave audit rows (username + IP, never the password); a stale/revoked cookie hitting /api/auth/status is recorded while ordinary polls are not.",
      "Approval self-resolve is rejected + audited; the orphan-approval reaper records its sweep; hook_dispatched notes injected context; fire-and-forget audit retries once so a transient MCP blip doesn't drop a row. Memory/skill/notification routes now attribute to the real principal.",
    ],
  },
  {
    version: "0.2.73",
    date: "2026-06-24",
    title: "Forensic audit trail: true actor attribution + missing-event coverage.",
    highlights: [
      "Operator mutations now attribute to the real principal. Connector/instance/marketplace/job mutation routes hardcoded the audit actor to user:operator, overwriting the authenticated identity; they now record the actual apikey:<id> or user:operator from the request.",
      "instance_updated rows now name the changed config keys + secret slots (names only, never values) and record the enabled delta, so an enable/disable toggle is no longer invisible.",
      "Investigation mutations (verdict, technique, patch, case-relate, delete) now write timeline + audit events instead of vanishing into a coarse proxy row.",
      "Scheduler auto-disable + interrupted-session events are now audited with their reason; connector_disabled is recorded as success and a reset-to-pending probe as skipped (probe_implemented:false).",
      "Multi-step XSOAR tools (add_note / update_incident / run_playbook) return a per-step breakdown; ^tool direct dispatch now forwards the principal so its rows attribute to the operator.",
    ],
  },
  {
    version: "0.2.72",
    date: "2026-06-24",
    title: "Honest verdict push-back, observable embedding drift, reliable approval cards, proxy audit trail.",
    highlights: [
      "Pushing a verdict to XSOAR now reports the truth on partial failure. push_verdict_to_xsoar always returned ok even when the war-room entry landed but the evidence tag or timeline log failed; it now returns a per-step breakdown and reports overall failure (partial: true when the verdict reached XSOAR but a secondary step didn't).",
      "A misbaked knowledge-base embedding model is now observable. When a KB's pre-computed vectors didn't match the running embedder, Guardian silently re-embedded every doc on every boot (recurring cost). That drift now increments guardian_kb_embed_mismatch_total and emits one kb_embed_mismatch audit event per process.",
      "The inline approval card no longer occasionally fails to appear. Detection is now status-agnostic and watches for 30s (was 6s); an approval that resolved before the first poll renders in its final state instead of a stuck 'pending' card.",
      "Every state-changing request through the agent now leaves an audit trace. Writes (POST/PUT/PATCH/DELETE) admitted by the proxy emit a proxy_request_admitted audit event and carry a correlation x-request-id; high-rate reads are excluded.",
    ],
  },
  {
    version: "0.2.71",
    date: "2026-06-24",
    title: "Skills: creatable categories, plugin skills in jobs, edits survive upgrades.",
    highlights: [
      "Create/Import a skill in any of the four categories now works. The dialogs offered foundation/scenarios/validation/workflows but the backend accepted only foundation/workflows, so importing a plain .md (defaults to scenarios) or creating a scenarios/validation skill always 400'd. create_skill now accepts all four.",
      "A scheduled job bound to a plugin skill now uses it. The job runner's _load_skill_body couldn't resolve a plugin's vendor.skill canonical name (it searched only category dirs), so the job ran unbound; it now resolves plugins/<vendor>/<stem>.md.",
      "Operator edits to built-in skills survive upgrades. The boot skill-sync overwrote bundled skills with image defaults on every upgrade, silently discarding edits; it now snapshots an edited file into .history before overwriting.",
    ],
  },
  {
    version: "0.2.70",
    date: "2026-06-24",
    title: "Bound database growth: memory TTL + audit retention.",
    highlights: [
      "Expired memories now disappear immediately. The TTL cleanup was boot-only, so expired rows kept being returned by get/list/search until restart. Reads now filter expired entries, an hourly sweep deletes them (not just at boot), and the sweep emits an audit row + metric (plus a timezone-math fix in the expiry calc).",
      "audit.db is now size-observable + optionally retention-bounded. It exposes row-count + on-disk-size metrics, and supports an opt-in retention window via AUDIT_RETENTION_DAYS. Retention is OFF by default (the audit log is forensic — history is never pruned unless an operator opts in); when enabled, the prune itself is recorded as an audit_reaped event.",
    ],
  },
  {
    version: "0.2.69",
    date: "2026-06-24",
    title: "Close two cache-staleness windows in auth + approvals.",
    security: true,
    highlights: [
      "Revoked API keys stop working immediately. Deleting a key only revoked it server-side; a warm 30s validation cache on the agent could keep accepting it. Delete now evicts the key from that cache by id (bustApiKeyCacheByKeyId).",
      "Re-enabling approvals in a chat takes effect right away. The per-session approval mode was cached 30s and never invalidated on change, so flipping a session back to 'manual' could keep auto-approving gated tools. The cache moved to a shared module that the session-update path now invalidates on every PATCH; an uncertain read defaults to 'manual' (require approval) instead of a stale bypass.",
    ],
  },
  {
    version: "0.2.68",
    date: "2026-06-24",
    title: "Lock down two exposed surfaces: metrics + plugin pip-install.",
    security: true,
    highlights: [
      "The Prometheus metrics endpoint (GET /api/v1/metrics on the embedded MCP) now requires authentication — it was open, so anything reaching the MCP port read all counter names+values uncredentialed. The in-app metrics panel is unaffected (it authenticates through the agent proxy).",
      "Plugin pip-install/uninstall is now admin-only + approval-gated. These endpoints run pip (arbitrary package code execution in the agent container); previously any valid API key could trigger them with no confirmation. Now restricted to the internal admin token AND blocked until an operator confirms in Approvals (deny/timeout refuses the install).",
      "plugin_install / plugin_uninstall audit events are now declared so they appear in the /observability/events filter chips.",
    ],
  },
  {
    version: "0.2.67",
    date: "2026-06-24",
    title: "Close audit blind spots: reads, auth, and KB access now leave a trace.",
    security: true,
    highlights: [
      "Memory reads are now audited: listing the store (memory_listed) and reading a key (memory_read) previously left no trace — full enumeration / key probing was invisible.",
      "Knowledge-base access now emits kb_searched / kb_doc_read, with a mode field (active agent search vs passive per-turn context injection vs list) so the two are distinguishable.",
      "API-key auth has a forensic trail: api_key_used (every successful use), api_key_auth_failed (invalid/revoked-key probing), api_key_scope_denied, api_key_credential_route_denied, and mcp_bearer_auth_failed. Only key prefixes are logged, never secret material.",
      "Password-change failure paths (bad credential write, forged/expired session) now record password_change_rejected; all auth events (login/logout/password) are discoverable in the /observability/events filter chips.",
      "Claude Code CLI turns (/api/chat/cli) now emit chat_cli_turn (start + end) — they were invisible to observability despite a docstring claiming otherwise.",
    ],
  },
  {
    version: "0.2.66",
    date: "2026-06-24",
    title: "Remove a custom connector from the marketplace.",
    highlights: [
      "Uploaded connectors now appear on the Marketplace tab (with a 'Custom' badge) alongside the five bundle connectors — previously they were invisible there, so removing one needed a raw API call.",
      "A connector's detail panel now has a Delete button for Custom (user-uploaded) connectors that permanently removes its uploaded definition, guarded by a confirmation. Delete its instances first — Delete is refused (with a clear message) while any instance exists.",
      "Bundle connectors are unaffected: they show no Delete button and remain image-baked (use Uninstall to hide them from instance creation).",
    ],
  },
  {
    version: "0.2.65",
    date: "2026-06-24",
    title: "Upgrade Guardian from inside the app.",
    highlights: [
      "One-click stack upgrade in the About modal: open About (or 'Check for updates' in its menu) and, when a newer release exists, an 'Update available — v<running> → v<latest>' banner offers an Upgrade button — no SSH.",
      "Upgrade pulls the new images and swaps containers in place, streaming live progress (fetching manifest → pulling → swapping → healthcheck). The agent restarts during the swap; the page waits for it to come back and reloads onto the new version automatically.",
      "Safe to leave running: closing the modal won't cancel an in-progress upgrade, and if one is already running (e.g. from another tab) the modal attaches to it instead of starting a second. The installer-binary path remains for clean re-installs and version pinning.",
    ],
  },
  {
    version: "0.2.64",
    date: "2026-06-23",
    title: "Connector lifecycle — user-connector self-heal + longer research runs.",
    highlights: [
      "The self-healing reconcile now restarts user-uploaded connector containers too (was bundle-connectors-only); the agent surfaces each instance's image_ref on /api/v1/instances so the updater can start the right image.",
      "The ^tool direct-call timeout raised 150s→300s so a full deep_research run (1–3 min) returns its complete deliverable instead of a proxy timeout.",
      "Added the agent-side delete API for a user-uploaded connector (DELETE /api/agent/marketplace/{id}) — previously only reachable via a raw MCP_TOKEN call. The in-app UI affordance to surface + remove user connectors follows next release.",
    ],
  },
  {
    version: "0.2.63",
    date: "2026-06-23",
    title: "Audit captures tool argument values (secrets redacted).",
    security: true,
    highlights: [
      "Tool-call audit rows now include argument VALUES (arg_values) — the command run, XQL query, IoC enriched, note added — not just the argument names, closing a forensic gap in /observability/events.",
      "Secrets are redacted at capture time: credential/code/config-blob args (snippet_code, skill/playbook/connector content, memory/personality/settings/job payloads, XSOAR list contents) → [redacted]; any secret-named arg (token/password/key/…) → [redacted] regardless of type; long values truncated to 512 chars. Forensic action data (command/query/IoC) is captured, not redacted.",
      "On by default; GUARDIAN_AUDIT_ARG_VALUES=0 disables it. The shared secret-key redaction list was hardened and de-duplicated (one source of truth), strengthening the approval-card scrubber too.",
    ],
  },
  {
    version: "0.2.62",
    date: "2026-06-23",
    title: "Connector & updater actions now in the audit trail.",
    security: true,
    highlights: [
      "Testing a connector instance now writes a connector_probed audit event (success/failure/skipped) — credential/reachability validation against XSOAR / Cortex docs / the browser sidecar previously left no trace in /observability/events.",
      "The guardian-updater's container lifecycle (start/stop/restart), managed-service restart, and stack-update completion are now audited (posted to the MCP, attributed to system:updater) — previously visible only in the updater's own logs. Reconcile-driven container starts surface through the same container_started events.",
    ],
  },
  {
    version: "0.2.61",
    date: "2026-06-23",
    title: "Web tool — gated, audited, health-checkable.",
    security: true,
    highlights: [
      "web.click that triggers navigation now re-checks the allowed_domains allowlist and reverts + errors if the click landed off-list — previously a click bypassed the allowlist + the web.navigate approval gate entirely.",
      "A click's navigation destination is now recorded in the audit row metadata (navigated_to / blocked_navigation_to), not just the live result — off-allowlist nav attempts leave a URL trace in /observability/events.",
      "The web connector now has a real instance Test probe (hits the Chromium CDP /json/version endpoint); previously the test reported probe_implemented:false without contacting the sidecar, so a down browser looked healthy.",
    ],
  },
  {
    version: "0.2.60",
    date: "2026-06-23",
    title: "Subagents — scoped, attributed, and tamper-resistant.",
    security: true,
    highlights: [
      "Subagent definitions now require an explicit tools_allowed allowlist; an empty/missing one is rejected instead of silently inheriting the FULL parent tool catalog (incl. high-impact response tools) with no approval. Use ['*'] to deliberately grant all.",
      "Builtin and plugin-provided agents are no longer editable/deletable via API or UI (only operator-created agents are mutable; others are owned by their source). The API returns 403 and the UI shows a lock.",
      "Renaming an agent to an existing name returns a clean error instead of a 500; spawning an agent by name is now case-insensitive.",
      "Failed spawns (not-found / disabled / hook-denied) write a chat_subagent_dispatch_failed audit event, and a subagent's out-of-scope tool attempt writes subagent_tool_blocked (and is persisted to the sidechain) — previously both left no trace in /observability/events.",
    ],
  },
  {
    version: "0.2.59",
    date: "2026-06-23",
    title: "Hooks & approvals — honest signals, no silent traps.",
    security: true,
    highlights: [
      "Approvals page badges danger from the authoritative risk tier (destructive/credential → HIGH, soft → MEDIUM, read → LOW) instead of keyword-guessing the tool name — dangerous approvals (personality_reset, instances_delete, api_keys_create) no longer mis-render LOW.",
      "Notification + PermissionRequest hooks (Slack-mirror, PagerDuty, etc.) now write a hook_dispatched audit row — previously they fired on the loopback path with no trace in /observability/events.",
      "A PermissionRequest hook that returns a definitive allow/deny now resolves the matching approval immediately, instead of leaving the gated tool blocked until the 5-minute timeout.",
      "Unimplemented hook options are rejected at create/edit with a clear error rather than failing silently: the reserved 'agent' transport (could silently deny everything under failurePolicy:block) and matcher.tenantId (was unenforced — silently fired for ALL tenants).",
    ],
  },
  {
    version: "0.2.58",
    date: "2026-06-23",
    title: "Every button does something — dead/stub UI affordances fixed or removed.",
    highlights: [
      "Skill enable/disable on /skills now persists (writes an `enabled` flag to the skill) and actually drops a disabled skill from the agent's prompt — it no longer reverts on refresh or stays silently loadable. Audited as skill_enabled / skill_disabled.",
      "Memory search Advanced sliders (MMR diversity, temporal-decay recency) on /memory now re-rank results — they were previously sent but ignored by the search backend.",
      "Services panel: 'View Logs' opens the observability log view filtered to the service (was a dead /monitor/logs 404); 'Restart Service' restarts the agent via the updater behind a confirmation (disabled for in-process components).",
      "Notifications: 'Mark All Read' and 'Load more' now work; the inert date-filter and gear buttons were removed; approval notifications link to /approvals (which can actually approve/deny) instead of dead buttons.",
      "Personality 'Reset Defaults' now restores the server-side bundle default; backup/restore password-recovery shows the in-container reset-admin.mjs command instead of a download button pointing at a removed endpoint.",
    ],
  },
  {
    version: "0.2.57",
    date: "2026-06-23",
    title: "Audit attribution — events record which API key / session made the change.",
    security: true,
    highlights: [
      "Audit events now record the authenticated principal — apikey:<id> for an API-key caller, user:operator for a UI session — instead of a blanket user:operator. The server stamps it after auth (clients can't spoof it) and it flows through the proxy to the MCP audit log.",
      "REST-API mutations and chat turns are attributed to the specific key/session, so a multi-admin or multi-key deployment can answer 'who did this' in /observability/events.",
    ],
  },
  {
    version: "0.2.56",
    date: "2026-06-23",
    title: "Audit attribution — turn-start events + operator-direct tool calls.",
    highlights: [
      "Chat turns now write a chat_turn_started event up front, so a turn that fails before the first model call (auth/setup error, hook denial, unreachable provider) is visible in /observability/events instead of leaving no trace.",
      "Operator-typed ^tool calls now tag their audit row with the operator:direct trigger, so a direct tool dispatch is distinguishable from a model-driven one in the events view.",
    ],
  },
  {
    version: "0.2.55",
    date: "2026-06-23",
    title: "Approval gating for XSOAR actions — command exec, playbooks, incident state.",
    security: true,
    highlights: [
      "XSOAR mutating/action tools now require operator approval before running: run_command (arbitrary integration command exec), run_playbook, import_playbook, create/update/close_incident, complete_task, and List edits (set_list/append_to_list). Enforced on the chat AND autonomous jobs paths (a bypass session/job records an auto_approved audit row).",
      "Reads and routine War-Room documentation (add_entry/add_note/save_evidence) and enrichment/search stay ungated — no friction on low-risk work.",
      "Brings XSOAR in line with the XSIAM response-tool gating shipped in v0.2.51.",
    ],
  },
  {
    version: "0.2.54",
    date: "2026-06-23",
    highlights: [
      "Failed tool calls are now recorded as failures. Connector tools (XSOAR/XSIAM) + several built-ins report problems by RETURNING {ok:false}/{error} instead of raising; audit + the job scheduler keyed status only on raised exceptions, so a failed close_incident, a rejected XQL query, or an errored scheduled tool showed status=success. They're now correctly logged as failures in /observability/events and the jobs run history.",
      "A repeatedly-failing scheduled tool now trips the consecutive-failure auto-disable instead of firing silently forever.",
    ],
    title: "Failed tool calls are recorded as failures — no more green-on-error.",
  },
  {
    version: "0.2.53",
    date: "2026-06-22",
    title: "Removed the dead Detections surface — no more 404 nav item.",
    highlights: [
      "Retired /observability/detections (the Detection Inventory page), its sidebar nav entry, its /api/agent/detections/* routes, its API-reference entries, and its user-guide section. The backend was removed at the v0.1.0 carve-out, so the page had 404'd ever since — it's now gone rather than left dangling.",
      "No impact to the agent's investigation, hunt, or connector tooling.",
    ],
  },
  {
    version: "0.2.52",
    date: "2026-06-22",
    title: "Hooks fail closed — a hook-store outage no longer silently disables policy.",
    security: true,
    highlights: [
      "Policy hooks no longer fail OPEN: if the hook store was briefly unreachable the dispatcher used to treat it as 'no hooks' and let the turn through, silently disabling block-policy hooks. A load failure now fails CLOSED on the events that can block an action (PreToolUse, UserPromptSubmit, PreCompact, RunStart, SubagentStart) — denied with a clear reason instead of slipping through.",
      "Non-blocking events (post-hoc, notifications) still proceed on an outage — there's nothing to enforce there.",
      "Escape hatch for availability-over-policy: set GUARDIAN_HOOKS_FAIL_OPEN=true to restore the previous proceed-without-hooks behavior.",
    ],
  },
  {
    version: "0.2.51",
    date: "2026-06-22",
    title: "Approval gating for high-impact actions — endpoint response, egress, skill authoring.",
    security: true,
    highlights: [
      "XSIAM response/EDR actions now require operator approval before running: endpoint isolate/unisolate/scan/scan-all, script + arbitrary-snippet execution, file quarantine, hash blocklist, IOC push/disable/enable, alert exclusions, dataset/distribution create. Enforced on the chat AND autonomous jobs paths (a bypass session/job records an auto_approved audit row). Read/investigation tools are unaffected.",
      "Outbound webhook export now actually gates: export_to_webhook was listed as approval-required but the gate never fired for built-in tools, so external data egress could happen unconfirmed. Fixed. webhook_preview stays read-only.",
      "Creating or editing a skill now requires approval (skills_create / skills_update join skills_delete behind the gate) — skill files are instructions the agent trusts next turn — and every create is audited (skill_created).",
    ],
  },
  {
    version: "0.2.50",
    date: "2026-06-22",
    title: "Audit coverage — every consequential action now leaves a trace.",
    security: true,
    highlights: [
      "Built-in tools are now audited: investigation, memory, jobs, knowledge, sessions and skills tools previously wrote no tool_call row, so a session or job using only built-ins was invisible in /observability/events + /traces. They now emit the same row connector tools do (actor, status, duration, argument names — never values).",
      "Job edits are audited: changing a job — and especially toggling bypass-approvals (which arms unattended auto-approval) — now records a job_updated event with the changed fields.",
      "Backup + restore audited and locked down: backup_exported + restore_applied events are written, and both endpoints are now session-only (API keys can't reach them, matching the credential routes). Restore force=true now actually overwrites a colliding instance instead of silently failing.",
      "Skill deletions are audited (skill_deleted), symmetric with the existing skill-edit audit.",
    ],
  },
  {
    version: "0.2.49",
    date: "2026-06-21",
    title: "In-product help refresh — clearer guides, complete journeys + API reference.",
    highlights: [
      "User Journeys catalog now lists every category — the Authentication and Connectors click-paths were previously hidden; added journeys for the investigation Assessment/Report/Campaign tabs and STIX export.",
      "REST API reference completed: added the investigation export endpoints (issue/case STIX bundles, generated report, related-case lookup) and gave the observability endpoints real descriptions.",
      "Every help page (User Guide, Architecture, API, Journeys) rewritten to plain present-tense descriptions of current behavior; the Architecture page gained an Investigation-tools reference and a capability-oriented module overview.",
    ],
  },
  {
    version: "0.2.48",
    date: "2026-06-21",
    title: "Export + interop — STIX 2.1, report templates, opt-in webhook handoff.",
    highlights: [
      "STIX 2.1 export: export_issue_stix / export_case_stix (+ a one-click Export STIX 2.1 on the Report + Campaign tabs) emit a standard bundle — incident/campaign + ATT&CK techniques + indicators + relationships — for any TIP/SIEM. Deterministic, pure assembly.",
      "Report templates: generate_investigation_report now takes a template — technical (full, default), executive (brief), or ioc-list (machine-pasteable); generate_campaign_report renders the case level.",
      "Outbound handoff (opt-in + approval-gated): export_to_webhook POSTs the verdict + report + IOCs + STIX to an operator-configured webhook. Off by default (until you set GUARDIAN_WEBHOOK_URL), sends only to your configured URL, asks for approval before every send. webhook_preview shows what would be sent first.",
      "Completes the structured-investigation arc (A–D): a machine-readable verdict, backed by multi-source evidence, rolled into campaigns, and now portable to the rest of your stack.",
    ],
  },
  {
    version: "0.2.47",
    date: "2026-06-21",
    title: "Campaign / cross-incident analytics — roll up, type by playbook, link & infer.",
    highlights: [
      "Campaign rollup: new case_rollup synthesizes a Case from its member issues (combined ATT&CK techniques, shared infrastructure — indicators on >1 issue — overall severity, verdict mix) and shows it on the case's new Campaign tab (Roll-up button, or automatic when Guardian resolves an incident in a campaign).",
      "Type investigations by playbook: issue_match_playbook records which KB playbook an investigation followed, so cases are queryable by playbook (e.g. all ransomware-playbook incidents).",
      "Link related campaigns: typed cross-case edges (case_relate / case_related) connect a case to a prior one — sibling / escalation / reopen / same-campaign — surfaced on the Campaign tab.",
      "Relationship inference (suggest-only): infer_relationships walks the indicator graph to suggest missing transitive edges (domain→IP→C2 ⇒ domain→C2) and sibling issues sharing a technique/indicator. Guardian suggests; the analyst confirms — no silent writes.",
      "The autonomous loop + judge now roll campaigns up and weigh campaign coherence.",
    ],
  },
  {
    version: "0.2.46",
    date: "2026-06-21",
    title: "Multi-source defensible depth — telemetry hunt, verdict pushback, containment rec.",
    highlights: [
      "Verdict pushback: new push_verdict_to_xsoar writes a resolved Issue's structured verdict + findings back to the upstream XSOAR incident's war room as pinned evidence — the disposition lives where the SOC works the case. Goes through the approval gate + audit; no-op for standalone Issues.",
      "XQL telemetry blast-radius hunt: the investigation skill pivots into XSIAM (xql_examples_search → xsiam_run_xql_query) to find the other hosts/accounts a bad indicator touched, and folds them into the structured blast radius. Degrades gracefully when no XSIAM instance is configured.",
      "xsiam_run_xql_query now takes lookback_hours (default 0.5 = backward-compatible 30 min; up to 7 days) + polls to completion — so blast-radius hunts scope days, not minutes.",
      "Containment recommendations (recommend-only): for true positives Guardian attaches a structured isolate-host / disable-account / block-indicator / run-playbook step with the exact action to approve. It never auto-contains — containment runs only when you approve it.",
      "Autonomous loop deepened: investigations now hunt telemetry + push the verdict back; the judge weighs cross-source depth and whether containment was considered for high/critical true positives.",
    ],
  },
  {
    version: "0.2.45",
    date: "2026-06-21",
    title: "Structured investigation outcome — verdict, blast radius, ATT&CK, report.",
    highlights: [
      "Investigation Issues gain a structured outcome: a verdict from a fixed set (true/false positive, benign, needs escalation, inconclusive), a 0-100% confidence, and a blast-radius object (hosts/accounts/data the attack touched). The Assessment tab renders the verdict chip, confidence meter, and blast-radius groups.",
      "ATT&CK technique mappings: confirmed techniques are recorded as structured rows (id + tactic + manifestation + evidence) and shown as chips — not only in prose. A cross-incident lookup answers 'which incidents involved this technique'.",
      "New Report tab: assembles the verdict, blast radius, techniques, indicators, and timeline into one shareable markdown report — generate/regenerate on demand.",
      "The agent does it automatically: the xsoar_case_investigation skill sets the structured verdict, maps techniques, and generates the report at resolve; the autonomous judge scores against the structured record; the Block-close-without-verdict hook accepts either the structured verdict or the legacy VERDICT: line.",
      "Backward-safe: existing investigations.db upgrades in place; the large report rides only on the issue-detail read.",
    ],
  },
  {
    version: "0.2.44",
    date: "2026-06-21",
    title: "XQL knowledge base + authoring skill for Cortex XSIAM.",
    highlights: [
      "New xql-examples knowledge base: 201 curated Cortex XSIAM XQL examples — reusable patterns + per-vendor alert-mapping queries, plus a new ATT&CK-aligned IR/threat-hunting set (48 hunts, technique-tagged). Browse at /knowledge; search from chat with knowledge_search.",
      "New xql_examples_search tool: finds example queries by intent and enriches each with the XQL stage syntax + dataset field lists it uses — author a query without a lookup per stage.",
      "New cortex_xql_query_authoring skill: chains the example KB with live Palo Alto Cortex docs (cortex-docs/xql_lookup) to compose pattern- and syntax-correct XQL.",
      "Investigation pivot: mid-case, go from an incident's indicators to XQL hunts that scope blast radius across XSIAM datasets, runnable via xsiam_run_xql_query.",
    ],
  },
  {
    version: "0.2.43",
    date: "2026-06-21",
    title: "XSOAR playbook tools — fixed end-to-end on fetched incidents.",
    highlights: [
      "run_playbook now works on a freshly-fetched, not-yet-investigated incident — it opens the war room the way the XSOAR UI does (the path the autonomous investigation loop relies on).",
      "run_playbook accepts a playbook id OR name — it resolves the id to the display name XSOAR's setPlaybook needs, so the id from import_playbook just works.",
      "import_playbook now returns the imported playbook's id + name (was blank) — hand them straight to run_playbook.",
      "get_playbook_state now lists every task (id, name, state, type), not just counts — see task-by-task progress and find a waiting manual task's id for complete_task.",
      "Verified against a live XSOAR 6 tenant: all 27 connector tools pass end-to-end (import → assign → run → monitor → complete).",
    ],
  },
  {
    version: "0.2.42",
    date: "2026-06-20",
    title: "Emulated services in the marketplace — first up: Splunk.",
    highlights: [
      "New marketplace kind: emulated SERVICES (alongside connectors). A service runs as a container Guardian publishes on a host port so an EXTERNAL system reaches it — the agent never calls it.",
      "Splunk (Emulated) ships as the first one: it speaks the splunkd REST API the XSOAR SplunkPy integration uses, returning simulated notable events. Point a real SplunkPy instance at it (host = your Guardian host, port 8089, unsecure=true).",
      "splunk-search + fetch-incidents + the Indicator Hunting playbook run end-to-end against the mimic with no real Splunk server.",
      "The mimic emits a rotating stream of notables on a fixed time grid (~1/min), so each XSOAR fetch picks up NEW simulated incidents (varied rules/urgencies/domains) while re-queries dedup cleanly.",
      "Services show a 'Service' badge + a Services filter on /connectors; they advertise zero agent tools and skip the agent's Test Connection (they're reached by external systems, not the agent).",
      "XSOAR connector gains 4 operational tools: check an integration instance's health + last fetch error, re-run its Test button, read its fetch-run history (diagnose a failing fetch from Guardian, not by reading XSOAR logs), and monitor a running playbook's per-task state to confirm it ran to success.",
      "Every SplunkPy command that uses the splunkd REST API (search, job-create/results/status/share, get-indexes, submit-event, notable-update) now round-trips against the Splunk mimic — verified with the real splunklib SDK.",
    ],
  },
  {
    version: "0.2.41",
    date: "2026-06-19",
    title: "New skill: simulate Splunk incidents in XSOAR.",
    highlights: [
      "Added the simulate_splunk_incidents workflow skill — creates synthetic Splunk incidents in XSOAR as if SplunkPy fetched + mapped them from Splunk ES.",
      "Covers all three Splunk incident types (Notable Generic, Finding, Investigation) with the exact post-mapping field names + valid select values baked in.",
      "Creates incidents with the MAPPED XSOAR fields (splunkurgency, splunkstatus, splunkdisposition, notableid, …), not the raw Splunk fields — so cases drive the Splunk layouts/playbooks.",
      "Requires the SplunkPy pack installed on the target tenant; the skill probes once and tells you if it isn't. Verified live on the v6 tenant.",
    ],
  },
  {
    version: "0.2.40",
    date: "2026-06-19",
    title: "Chat sidebar: your own conversations are findable again.",
    highlights: [
      "Autonomous-loop sessions are hidden from the chat session rail by default, so operator conversations aren't buried under scheduled-job churn.",
      "Scheduled-job sessions are now tagged at create time (not turn end), so even failed/timed-out ticks are correctly hidden.",
      "A boot backfill tags pre-existing loop sessions too, so the historical flood clears — reversible + idempotent.",
      "New 'Automated sessions' toggle under New Chat: HIDDEN (default) vs SHOWN to inspect loop runs. Remembered per browser.",
    ],
  },
  {
    version: "0.2.39",
    date: "2026-06-19",
    title: "Autonomous loop: fixed the silent timeouts behind empty sessions.",
    highlights: [
      "Root cause: the investigation loop's chat turn hit a hard 300s timeout (~60% of ticks), saving the prompt but not the assistant turn — so the session opened to just the seed prompt.",
      "The chat-action timeout is now configurable (JOB_CHAT_ACTION_TIMEOUT_S) and defaults to 20 min, so long investigations actually finish.",
      "Interrupted ticks no longer leave silent empty sessions: the session is closed and shows a '⚠️ Investigation interrupted' banner explaining it'll resume next tick.",
      "Next up: filtering autonomous-loop sessions out of the chat sidebar so your own conversations are easy to find.",
    ],
  },
  {
    version: "0.2.38",
    date: "2026-06-17",
    title: "API reference completed — every endpoint now fully documented.",
    highlights: [
      "Filled 65 placeholder ('schema is a follow-up') entries with real request bodies, params, response shapes, and risk tiers on /help/api.",
      "Added 28 endpoints that weren't listed at all — including the full Investigation surface (cases, issues, indicators) under a new 'Investigation' API category.",
      "Every entry was reconciled against its actual route handler + the embedded-MCP handler it forwards to — no guessed schemas.",
      "Fixed providers/config: was mislabeled POST; it's GET (read, secrets redacted) + PUT (write credentials, now flagged credential-tier).",
      "The OpenAPI 3.0 export (GET /api/agent/openapi) now reflects the complete 138-endpoint catalog. Docs only — no behavior change.",
    ],
  },
  {
    version: "0.2.37",
    date: "2026-06-16",
    title: "Help docs reconciled — architecture, user guide, journeys, API caught up.",
    highlights: [
      "Architecture: restored the XSIAM connector section (it was wrongly marked retired but returned in v0.2.27 as a 54-tool connector); fixed false 'no bundled KB' claims (6 KBs ship); documented the v0.2.31–36 XSOAR connector refinements.",
      "User guide: new 'Evidence on XSOAR 6 vs 8' explainer; corrected connector count/wording.",
      "Journeys: added starter 'Create an XSOAR instance' and 'Create a Cortex XSIAM instance' walkthroughs.",
      "API reference: fixed mislabeled catalog entries (instance test, connector lifecycle action, get-single-instance) + a real /api/chat schema. No behavior change — docs only.",
    ],
  },
  {
    version: "0.2.36",
    date: "2026-06-16",
    title: "Connector read-path polish: leaner XSIAM results + XSOAR v8 evidence read.",
    highlights: [
      "XSIAM tools no longer attach the full raw API response to every result (44 sites) — pure token bloat nothing consumed; results are now just the projected fields.",
      "xsoar_search_evidence now works on XSOAR 8: since Cortex 8's /evidence/search doesn't return tag-based evidence, it reads the war room filtered to the 'evidence' tag. Evidence is now listable on both v6 and v8.",
      "No installer change; xsiam + xsoar connector images rebuild.",
    ],
  },
  {
    version: "0.2.35",
    date: "2026-06-15",
    title: "XSOAR evidence: save_evidence works on v6 + compact evidence search.",
    highlights: [
      "Fixed save_evidence on XSOAR 6 — it used the entry-tag path, which optimistic-locked and never round-tripped into the evidence board; v6 now uses the formal POST /evidence (verified create → search).",
      "search_evidence returns a compact summary per item {id, entry_id, incident_id, description, marked_by, marked_date, tags} instead of the raw verbose record.",
      "Cortex 8 keeps the tag path (its /evidence POST isn't on the public API); documented that v8 /evidence/search won't list tag-based evidence (it's UI-only there).",
      "No installer change.",
    ],
  },
  {
    version: "0.2.34",
    date: "2026-06-15",
    title: "XSOAR indicator search actually filters now (+ compact, scored results).",
    highlights: [
      "Fixed a real bug: xsoar_search_indicators sent its query in a {filter:{…}} envelope, but /indicators/search takes a flat body — so XSOAR ignored the query, size AND page and returned the whole unfiltered store. Queries now actually filter.",
      "type:IP returns IPs, reputation:Bad / verdict:Malicious returns malicious indicators, size is honored. Verified live on the v6 tenant.",
      "Results are now a compact summary per indicator {id, type, value, score, reputation, source, …} instead of raw verbose store objects — much smaller payloads, score/reputation surfaced directly.",
      "Bug-family audited all xsoar tools; search_evidence (same pattern) tracked as a follow-up. No installer change.",
    ],
  },
  {
    version: "0.2.33",
    date: "2026-06-15",
    title: "Sharper XSOAR investigations — platform reference skill + lighter read path.",
    highlights: [
      "New xsoar_platform_reference skill: the agent now has an authoritative War Room / !command catalog + exact incident & indicator query-syntax tables, so it stops probing syntax variants and stops web-searching XSOAR concepts.",
      "'List active incidents + severity breakdown' now uses one query per severity bucket instead of a dozen syntax-variant calls; 'what is the War Room / what does !Print do' is answered from the skill, not a web search.",
      "Read-only requests (list / show / summarize / count) take a lighter path — no full local Issue/Case is created unless you actually enrich, decide a verdict, or write to the case.",
      "Skill content only — no installer change. Re-run your existing installer.",
    ],
  },
  {
    version: "0.2.32",
    date: "2026-06-15",
    title: "XSOAR v8 one-click playbook import via the Core REST API.",
    highlights: [
      "Playbook import into a Cortex 8 tenant now works one-click when the Core REST API integration is installed (previously always reported 'import unavailable').",
      "The connector imports via core-api-post /playbook/save (run in the instance's playground) when the direct v6 endpoint 405s; verified live on Cortex 8.",
      "Requires the Core REST API integration + the instance's playground_id; otherwise a clear guided-manual message. XSOAR 6 import is unchanged.",
    ],
  },
  {
    version: "0.2.31",
    date: "2026-06-15",
    title: "Fix: XSOAR list tools now actually create lists.",
    highlights: [
      "set_list / append_to_list now create a list if it doesn't exist (use !createList instead of !setList, which only updates existing lists).",
      "List writes now report real failures instead of returning ok=true when the underlying command errored.",
      "Found during the live XSOAR v6 smoke; affected both v6 and v8. No installer change.",
    ],
  },
  {
    version: "0.2.30",
    date: "2026-06-15",
    title: "Smarter XSOAR create form — Version first, version-aware fields.",
    highlights: [
      "The XSOAR instance form now leads with the Version dropdown; the fields below adapt to your choice.",
      "API key ID appears only for v8 (v6 uses the API key alone) — it's hidden, not-required, and not submitted for v6.",
      "Added the previously-missing Playground / War Room ID field — needed to run commands + the list tools on both versions.",
      "No installer change — re-run your existing installer.",
    ],
  },
  {
    version: "0.2.29",
    date: "2026-06-15",
    title: "Two tenants, one connector — multi-active instances + XSOAR v6/v8.",
    highlights: [
      "A connector can now run multiple enabled instances at once — e.g. an XSOAR 6 (on-prem) and an XSOAR 8 (cloud) tenant live simultaneously.",
      "The agent picks which tenant a tool acts on via an 'instance' argument, inferred from your request; ambiguous calls error with the valid choices instead of hitting the wrong tenant.",
      "Creating an XSOAR instance now has an explicit Version dropdown (v6 / v8) instead of inferring from api_id.",
      "Single-instance connectors are unchanged. No installer change — re-run your existing installer.",
    ],
  },
  {
    version: "0.2.28",
    date: "2026-06-15",
    title: "Connector instances start reliably + tell you what happened.",
    highlights: [
      "Creating an instance now shows explicit feedback: success closes the dialog, an error gets a red banner, and a container that needs a moment shows a 'still starting' notice.",
      "Connector containers self-heal — a container that failed to start is restarted automatically within ~5 minutes, instead of staying down.",
      "Fixed hyphenated connector ids (cortex-docs) being dropped from container reconcile + the digests listing.",
      "No installer change — re-run your existing installer; volumes preserved.",
    ],
  },
  {
    version: "0.2.27",
    date: "2026-06-15",
    title: "Cortex XSIAM connector — investigation + EDR response.",
    highlights: [
      "New Cortex XSIAM connector in the marketplace — add an instance with your tenant API host + the Cortex public-API key pair, then investigate and respond from chat (mirrors XSOAR).",
      "54 tools: XQL queries, incidents/alerts/issues, assets, audit, datamodel — plus EDR response (endpoint isolate/scan/quarantine, script execution, IOC + hash blocklisting).",
      "Every write/response tool is approval-gated; the destructive remove_lookup_data is denied outright.",
    ],
  },
  {
    version: "0.2.26",
    date: "2026-06-14",
    title: "Deploy + test-run playbooks — close the builder loop.",
    highlights: [
      "Playbook Builder gains a Deploy + test-run button: import a drafted playbook into your XSOAR tenant, run it on a throwaway test incident, see the outcome, and auto-close the incident.",
      "New xsoar_import_playbook connector tool — approval-gated, uses the instance API key.",
      "Generation-aware: direct one-click import on XSOAR 6 (or Cortex 8 + Core REST API); on a plain Cortex 8 tenant Guardian gives manual-import guidance and still runs the test.",
    ],
  },
  {
    version: "0.2.25",
    date: "2026-06-14",
    title: "Knowledge detail pages show the full entry count + render code and tables.",
    highlights: [
      "Large KBs now show their true entry count (mitre-attack-enterprise: 697, soar-playbooks: 798) with a Load more button to browse them all.",
      "MITRE code snippets in entry bodies render as code blocks instead of raw <code> text.",
      "Agent comparison tables now render as real tables in chat and the KB drawer (GitHub-flavored markdown).",
    ],
  },
  {
    version: "0.2.24",
    date: "2026-06-14",
    title: "Playbook Builder — draft a Cortex XSOAR playbook from a use-case.",
    highlights: [
      "New /playbooks/build page: describe what a playbook should do and the agent drafts it, grounded in the ~800 real playbooks in the soar-playbooks KB.",
      "Every draft is structurally validated (required fields + task-graph integrity) and downloadable as YAML, with the example playbooks cited.",
      "The first generative use of the knowledge layer — the agent uses real playbooks as worked examples.",
      "Output is a draft to review + import into Cortex XSOAR; the builder never deploys to a tenant.",
    ],
  },
  {
    version: "0.2.23",
    date: "2026-06-14",
    title: "Sharper KB grounding — specialist matrices stay out of IT investigations' context.",
    highlights: [
      "With six KBs, the per-turn context occasionally pulled an ICS or Mobile technique into an IT case; that's fixed.",
      "Passive context now excludes the specialist ecosystems (OT/Mobile/AI); the agent still searches them directly when a case calls for it.",
      "Configurable per deployment via manifest.context.passiveExcludeEcosystems.",
    ],
  },
  {
    version: "0.2.22",
    date: "2026-06-14",
    title: "MITRE ATT&CK ICS + Mobile knowledge bases complete the matrix family.",
    highlights: [
      "New mitre-attack-ics KB (97 docs): the ATT&CK for ICS / OT matrix — SCADA, PLC, HMI attacks.",
      "New mitre-attack-mobile KB (124 docs): the ATT&CK for Mobile matrix (Android/iOS).",
      "Same generator + baked embeddings as ATT&CK Enterprise; six bundled KBs now, ~1,973 docs total.",
      "Always loaded; scope to mitre-attack-enterprise or the ecosystem tag for IT-only investigations.",
    ],
  },
  {
    version: "0.2.21",
    date: "2026-06-14",
    title: "SOAR Playbooks knowledge base — ~800 Cortex XSOAR response playbooks.",
    highlights: [
      "New soar-playbooks KB: ~800 out-of-the-box Cortex XSOAR playbooks from the MIT-licensed demisto/content repo (SOC-relevant packs, ~77 products).",
      "Search by what a playbook DOES — the embedded text is a reviewed description; the raw playbook YAML is kept in each entry.",
      "Dual-labeled by product/pack and investigation-type, both filterable with the tag chips.",
      "The agent can now find an existing response playbook during a case; later, these are worked examples for building playbooks.",
    ],
  },
  {
    version: "0.2.20",
    date: "2026-06-14",
    title: "Filter knowledge bases by tag — tactic, platform, and more.",
    highlights: [
      "Open any KB on /knowledge and click tag filter chips to narrow the entries (e.g. Windows credential-access techniques).",
      "Both browsing and semantic search respect the selected tags (AND filter).",
      "Big MITRE KBs are now easy to navigate by tactic/platform; the substrate also powers the upcoming playbook KB's product/use-case labels.",
      "The agent's knowledge_search can now scope a search by tag too.",
    ],
  },
  {
    version: "0.2.19",
    date: "2026-06-14",
    title: "MITRE ATLAS (AI security) is now a built-in knowledge base.",
    highlights: [
      "New mitre-atlas KB: the ATT&CK-style framework for attacks on AI/ML systems — prompt injection, model evasion, data poisoning, agent hijacking.",
      "227 docs: 170 techniques + sub-techniques plus 57 real-world AI-incident case studies.",
      "AI techniques cross-link to their ATT&CK Enterprise mapping; embeddings baked in (zero Vertex calls at boot).",
      "Guardian now grounds investigations of AI-targeting incidents — apt as it's itself an AI agent.",
    ],
  },
  {
    version: "0.2.18",
    date: "2026-06-14",
    title: "Full MITRE ATT&CK Enterprise is now a built-in knowledge base (~697 techniques).",
    highlights: [
      "New mitre-attack-enterprise KB: the complete ATT&CK Enterprise matrix — every technique + sub-technique, with detection analytics and mitigations.",
      "Generated faithfully from the official MITRE STIX bundle (v19.1); regenerates on each MITRE release.",
      "Embeddings baked into the bundle, so all ~697 docs load instantly with zero Vertex calls at boot.",
      "Investigations now ground in the authoritative technique definition; soc-investigation stays as the curated 'how to investigate' guide.",
      "ATT&CK® © The MITRE Corporation, reproduced under the ATT&CK Terms of Use.",
    ],
  },
  {
    version: "0.2.17",
    date: "2026-06-14",
    title: "Knowledge bases can ship embeddings baked in — large KBs install in seconds, not minutes.",
    highlights: [
      "Infrastructure keystone for the knowledge-base expansion (full MITRE ATT&CK, ATLAS, SOAR playbooks).",
      "A KB can ship pre-computed embeddings in the bundle, so it loads with zero Vertex calls at boot.",
      "Baked vectors are trusted only when the model + dimensions match the runtime embedder — otherwise it re-embeds (self-healing).",
      "New authoring tool kb_embed.py bakes embeddings into a KB at build time.",
    ],
  },
  {
    version: "0.2.16",
    date: "2026-06-14",
    title: "SOC Investigation knowledge base — the agent now grounds cases in curated tradecraft.",
    highlights: [
      "New bundled knowledge base 'soc-investigation' (30 docs): 20 MITRE ATT&CK technique investigation guides + 10 IR playbooks.",
      "The /knowledge page is no longer empty — browse all 30 entries and search them semantically (Vertex text-embedding-004).",
      "Every investigation now consults the KB first: technique manifestation signals, ordered investigation steps, and the matching response playbook.",
      "Knowledge vs memory: knowledge is curated, read-only reference shipped in the bundle; memory is the agent's mutable, accumulated org facts.",
    ],
  },
  {
    version: "0.2.15",
    date: "2026-06-13",
    title: "Docs synced with the harness after a 20-incident end-to-end test.",
    highlights: [
      "Architecture page now documents the autonomous investigation loop (seeder → loop → judge), the self-improving judge with rollback, and subagent tool-result truncation.",
      "User guide gains an 'Autonomous investigation loop' section under Jobs, incl. how to review/roll back autonomous skill edits.",
      "list_integrations documented as the discovery step in the XSOAR tool family.",
    ],
  },
  {
    version: "0.2.14",
    date: "2026-06-13",
    title: "Subagent investigations scale on busy tenants.",
    highlights: [
      "Subagent tool results are now truncated like the main agent's — a single broad XSOAR read can no longer blow the subagent's context window (the Vertex 1M-token limit).",
      "Threat-hunter blast-radius hunts and other subagent investigations now complete on busy tenants instead of failing on overflow.",
    ],
  },
  {
    version: "0.2.13",
    date: "2026-06-13",
    title: "Guardian can now discover which SOAR integrations + commands are available.",
    highlights: [
      "New xsoar_list_integrations tool: lists the integrations configured on the Cortex XSOAR tenant and the commands each one exposes.",
      "Pairs with run_command — the agent learns which !commands actually exist (and their arguments) instead of guessing.",
      "Filter to one integration with brand=... to get full command argument specs.",
    ],
  },
  {
    version: "0.2.12",
    date: "2026-06-13",
    title: "Autonomous investigation self-improvement — with audited, reversible skill edits.",
    security: true,
    highlights: [
      "The investigation loop now evaluates its own resolved cases against a SOC rubric and improves the investigation skill automatically (the new guardian-investigation-judge).",
      "Every skill edit — operator OR agent — now writes a timestamped rollback snapshot under skills/.history and a skill_updated audit row visible in /observability/events.",
      "The judge is tightly scoped (reads investigations + edits only the investigation skill) and bounded (one additive, lifecycle-preserving edit per run).",
    ],
  },
  {
    version: "0.2.11",
    date: "2026-06-13",
    title: "Investigation loop hardening + codification.",
    highlights: [
      "The Issues list can now filter to only incident-tracking Issues (source_ref_not_null) and sort oldest-first — used by the autonomous loop to deterministically pick the oldest open case.",
      "The investigation-loop + incident-seeder jobs are now codified in scripts/bootstrap_loop_jobs.sh, so the loop survives a fresh install / volume wipe.",
      "The loop now groups related incidents into Cases as it investigates.",
    ],
  },
  {
    version: "0.2.10",
    date: "2026-06-13",
    title: "Connector instance config edits take effect immediately.",
    highlights: [
      "Editing a connector instance's config or secrets (e.g. XSOAR playground_id, a URL, an API key) now applies within seconds — no manual container restart.",
      "Saving the instance form recreates the connector container so it re-reads the new config at boot.",
      "Only fires when config/secrets actually changed and the instance is enabled; renames and tool-toggles don't trigger a restart.",
    ],
  },
  {
    version: "0.2.9",
    date: "2026-06-13",
    title: "Hooks & policies now reliably match connector tools.",
    security: true,
    highlights: [
      "Fixed: hook tool-globs, job permission policies, and subagent tool scopes silently missed connector tools the model named in dotted form (xsoar.close_incident vs xsoar_close_incident).",
      "The 'Block close without verdict' hook now actually denies a no-verdict close — with an audit row.",
      "A subagent's deny glob now reliably blocks the connector tools it shouldn't reach (privilege-scoping gap closed).",
      "Tool globs everywhere are now separator-insensitive — author them with either '.' or '_'.",
    ],
  },
  {
    version: "0.2.8",
    date: "2026-06-13",
    title: "Tasks page — clearer purpose + modernized presentation.",
    highlights: [
      "The /tasks page now states what it's for: long-running background work the agent or you spawned (enrichment sweeps, compactions, subagent hunts, hook runs).",
      "Added summary cards (total/running/succeeded/failed) and a cleaner status filter.",
      "Slimmer task rows with status + kind badges; progress, abort, and details retained.",
    ],
  },
  {
    version: "0.2.7",
    date: "2026-06-13",
    title: "Agents page modernized — subagent CRUD with a tabbed, scoped-tools editor.",
    highlights: [
      "The /agents page gets summary cards, origin + name filters, and slimmer definition rows.",
      "The create/edit drawer is wider and tabbed: Definition · Tools (allow/deny globs) · Execution.",
      "Define a subagent (e.g. a threat-hunting agent) with a scoped tool catalog, then the chat agent can spawn it.",
    ],
  },
  {
    version: "0.2.6",
    date: "2026-06-13",
    title: "Fixes — /jobs page loads, job chat sessions render, hooks UI polish.",
    highlights: [
      "Fixed the /jobs page 'unable to load jobs' error (a stale session-cookie name in the server-side fetch).",
      "Chat sessions created by scheduled jobs now show the real request + response (the skill body collapses into a chip).",
      "Hooks editor drawer widened to ~50%; the title description renders as a compact subtitle.",
    ],
  },
  {
    version: "0.2.5",
    date: "2026-06-13",
    title: "Two built-in incident-response hooks — verdict gate + malicious-indicator flag.",
    highlights: [
      "Block close without verdict: denies xsoar_close_incident when the Guardian Issue has no recorded VERDICT — install from /settings/hooks, no code.",
      "Flag malicious indicator: injects a confirmed-bad flag when an enrichment returns DBotScore 3, nudging containment.",
      "Both are in-process built-ins (no subprocess, no host scripts) and never touch secrets — install via dropdown + a tool glob.",
    ],
  },
  {
    version: "0.2.4",
    date: "2026-06-13",
    title: "Hooks page modernized — stat cards, filters, tabbed editor.",
    highlights: [
      "The /settings/hooks page gets summary cards (total / enabled / disabled / fail-closed) and an event + name filter.",
      "Hook rows are slimmer — event, transport, and fail-closed at a glance.",
      "The create/edit drawer is now a glass panel with tabbed fields (Metadata · Matching · Transport · Execution).",
      "Pure UI polish — no change to the hook engine, transports, or events.",
    ],
  },
  {
    version: "0.2.3",
    date: "2026-06-13",
    title: "Investigation diagram hardening — no more silent spinners.",
    highlights: [
      "Generate/Regenerate now reports an error instead of spinning silently for 3 minutes if the agent run fails.",
      "Diagram-SVG sanitizer hardened to also strip <foreignObject> and unquoted event handlers.",
      "Small correctness + documentation-accuracy fixes from a post-release code review.",
    ],
  },
  {
    version: "0.2.2",
    date: "2026-06-13",
    title: "Case-view diagrams — campaign-level attack chain + relations canvas.",
    highlights: [
      "Case detail is now tabbed: Issues · Attack chain · Relations.",
      "The Attack chain tab draws one causal diagram across all the case's issues — the campaign kill-chain.",
      "The Relations tab draws one STIX graph over the union of the case's indicators — the shared infrastructure, techniques, and actors.",
      "Both generate on demand, the same way as the per-issue diagrams.",
    ],
  },
  {
    version: "0.2.1",
    date: "2026-06-13",
    title: "Relations canvas — STIX indicator attribution + a relationship graph per issue.",
    highlights: [
      "New Relations tab on each issue: a STIX graph of its indicators and how they relate to techniques, malware, campaigns, and actors.",
      "Guardian attributes indicators — resolves-to, indicates, uses, attributed-to — using STIX verbs that round-trip with XSOAR + MITRE ATT&CK.",
      "Each indicator's detail now lists its relationships (source → verb → target).",
      "Draw the relations canvas on demand from the tab, just like the attack chain.",
    ],
  },
  {
    version: "0.2.0",
    date: "2026-06-13",
    title: "Indicators — a deduped IoC record across investigations.",
    highlights: [
      "New Investigation → Indicators page: every IoC Guardian sees, deduped by value + type.",
      "Guardian records the IoCs it enriches and imports the indicators XSOAR already extracted on case fetch.",
      "Click an indicator to see its reputation, enrichment, and every issue it appears in (cross-case correlation).",
      "Each issue gains an Indicators tab; per-issue-type layouts tailor the view to phishing / malware / lateral-movement / access-violation.",
    ],
  },
  {
    version: "0.1.10",
    date: "2026-06-13",
    title: "Attack-chain diagrams — tactic colors, MITRE mapping, attribution, animation.",
    highlights: [
      "Attack chains are now color-coded by ATT&CK tactic, with a legend.",
      "Each stage shows its tactic; each arrow shows the technique id + name (no more clipped labels).",
      "Adds an attribution line (actor/campaign) and subtle animated arrows.",
    ],
  },
  {
    version: "0.1.9",
    date: "2026-06-13",
    title: "Investigation text renders as markdown; Activity is filterable.",
    highlights: [
      "Issue fields + activity + case descriptions now render as formatted markdown (like the chat window).",
      "Activity timeline: filter by event type (action / finding / note) and sort oldest/newest.",
    ],
  },
  {
    version: "0.1.8",
    date: "2026-06-13",
    title: "Attack-chain diagrams — Guardian draws the causality chain.",
    highlights: [
      "Each investigation gets an SVG attack chain on the issue's 'Attack chain' tab.",
      "Generated automatically when an investigation resolves; regenerate on demand.",
      "Shows the causal path: entry → pivots → action → impact, with technique-labelled arrows.",
      "Rendered sandboxed (SVG-in-img) so agent-produced markup can never execute.",
    ],
  },
  {
    version: "0.1.7",
    date: "2026-06-13",
    title: "Investigation pages redesigned — full-width, tabbed, faster cases.",
    highlights: [
      "Issues + Cases pages now full-width with summary stats, filter chips, and glass cards (matching Skills/Jobs).",
      "Issue detail split into tabs: Overview · Assessment · Activity · Attack chain.",
      "Issue summaries show a derived VERDICT banner at a glance.",
      "Cases list loads much faster — the per-case issue count is now one query instead of N+1.",
    ],
  },
  {
    version: "0.1.6",
    date: "2026-06-13",
    title: "Investigation skill — scope the blast radius before resolving.",
    highlights: [
      "Investigations now enumerate blast radius in-investigation instead of deferring it to next-steps.",
      "Every confirmed-bad indicator/principal is pivoted outward (other affected hosts + co-sighting cases).",
      "Each Issue states scope as a one-line count ('seen on N hosts / M cases') or 'contained to this host'.",
    ],
  },
  {
    version: "0.1.5",
    date: "2026-06-12",
    title: "Investigation skill hardening — sharper, more complete case write-ups.",
    highlights: [
      "Investigation skill now teaches the full XSOAR tool surface (enrich_indicator, run_command, lists, playbooks).",
      "Every investigation builds an IoC/principal ledger — no case resolves with indicators left un-enriched.",
      "Resolution gate: a case isn't 'resolved' while competing root causes are undiscriminated.",
      "Each Issue leads with an explicit VERDICT line + MITRE ATT&CK technique tags.",
      "Fixed a frontmatter bug that silently disabled the skill's auto-load trigger in chat.",
    ],
  },
  {
    version: "0.1.4",
    date: "2026-06-12",
    title: "Agent chat resilience — long investigations survive transient Vertex socket resets.",
    highlights: [
      "Scheduled investigation jobs no longer die mid-run with 'chat error event: fetch failed'.",
      "Model-call retry now covers transient socket resets (UND_ERR_SOCKET / ECONNRESET / timeouts), not just 429 quota.",
      "Same exponential backoff + jitter as the existing 429 retry; real errors still surface immediately.",
    ],
  },
  {
    version: "0.1.3",
    date: "2026-06-12",
    title: "Investigation module — local Issues & Cases for every investigation.",
    highlights: [
      "New Investigation area (sidebar): Issues + Cases — Guardian's own record of its investigations.",
      "Guardian opens a local Issue when it works a case, logs each step + finding, and records the verdict.",
      "Rich issue layout: summary, scope, recommendations, conclusions, next steps + an activity timeline.",
      "Group related Issues into Cases; create Issues + Cases yourself too.",
      "guardian-updater reconcile/digests no longer crashes when a connector image was pruned.",
    ],
  },
  {
    version: "0.1.2",
    date: "2026-06-12",
    title: "XSOAR action toolset — run commands, enrich indicators, manage lists, create cases.",
    highlights: [
      "XSOAR connector grows to 21 tools: run any !command in a configured playground War Room.",
      "Enrich IPs/URLs/domains/files/CVEs → DBotScore reputation, inline in chat.",
      "Manage XSOAR Lists (allow/block) — read, overwrite, append.",
      "Create incidents and run playbooks on cases directly from Guardian.",
      "New optional playground_id field on the XSOAR instance powers the command tools.",
    ],
  },
  {
    version: "0.1.1",
    date: "2026-06-12",
    title: "Default chat-model picker — set a default model on Settings → Models.",
    highlights: [
      "Set a default chat model on Settings → Models; new chats use it automatically (no more 'auto').",
      "Chat dropdown chip shows 'Default — <model>' when an operator default is active.",
      "Per-chat model override still works; the next new chat resets to the default.",
      "Resolution chain: per-chat override → operator default → GEMINI_MODEL env → hardcoded fallback.",
    ],
  },
  {
    version: "0.1.0",
    date: "2026-06-11",
    title: "Guardian initial release — AI incident-investigation agent for Cortex XSOAR.",
    highlights: [
      "Guardian debuts: an AI agent that monitors, investigates, documents, and closes Cortex XSOAR cases.",
      "New XSOAR connector — 13 tools for the case lifecycle; supports XSOAR 6 and XSOAR 8 / Cortex cloud.",
      "Focused roster: XSOAR + Cortex docs + web research. XSIAM, Cortex XDR, content catalog, and XQL removed.",
      "IR agent semantics: an investigation system prompt driving monitor → fetch → investigate → update/close.",
      "Two XSOAR skills — case investigation (end-to-end) and case triage — plus Cortex-docs research skills.",
      "Credential guardrail intact: the agent holds no credential tools; secret management stays REST-only.",
    ],
  },
];

/** Convenience: fetch the entry for a specific version, if present. */
export function findRelease(version: string): ReleaseNote | undefined {
  return RELEASE_NOTES.find((r) => r.version === version);
}

/** Convenience: most-recent entry — used as a fallback when the
 *  running version doesn't appear in the static history (e.g. dev
 *  builds, or a release that ships before the notes get committed). */
export function latestRelease(): ReleaseNote {
  return RELEASE_NOTES[0];
}
