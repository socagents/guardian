# Changelog

All notable changes to Guardian are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 releases bump the patch on every tagged release; minor bumps will resume after the v1.0.0 cut.

Each release section is written in operator language, not git-shortlog language. For commit-level granularity, run `git log vPREV..vNEW`.

<!-- [guardian v0.1.0] Retired: the upstream Phantom release history (v0.1.x–v0.17.x) — Guardian is a new product; the inherited changelog described subsystems that no longer exist here. -->

---

## [v0.2.83] (2026-06-25) — *`^tool` dispatch correlation: complete the trigger/chain fix (#86)*

- **An operator `^tool` direct dispatch is now correctly correlated in the audit log.** Its `tool_call` row records the operator-direct trigger and the dispatch's `chain_id` (and the real principal) instead of dropping to none. The fix forwards those markers on the session-creating `initialize` request — the embedded MCP runs the tool inside the session task it spawns there, so markers attached only to the later `tools/call` arrived too late. This completes the v0.2.82 same-task-middleware work for the one path it didn't reach; the chat and scheduled-job tool calls were already correlated.

## [v0.2.82] (2026-06-25) — *Audit attribution + correlation reliability (from the live interface-coverage pass)*

- **Tool calls attribute to the real principal.** An operator `^tool` dispatch or API-key-driven tool call previously recorded its audit row as `agent`, discarding the forwarded identity. The audit now records the true principal when one was forwarded, and falls back to `agent` only for genuinely model-internal calls — so "who ran this tool" is answerable.
- **Request-context middleware corrected to same-task (ASGI).** The middleware that stamps trigger / actor / `chain_id` was a `BaseHTTPMiddleware` that runs in a separate task from the endpoint; it is now a pure-ASGI middleware so the context reliably reaches per-request handlers. *(Known remaining gap: the operator `^tool` direct-dispatch path opens its own streamable-HTTP MCP session that runs the tool in a decoupled task, so those specific rows can still miss trigger/chain_id — tracked separately. The common chat + scheduled-job tool calls are correctly correlated.)*
- **Consistent principal format.** The API-key principal was recorded two ways (`apikey:<id>` vs `api_key:<id>`) across tiers, so a forensic filter missed half the rows — and the mismatched form actually broke the hook-delete owner check for API-key operators. Normalized to one form everywhere.
- **Knowledge-base audit hygiene.** A single KB doc read emitted two `kb_doc_read` rows and a search emitted two `kb_searched` rows (double-counting); each now emits once, and the active/REST search rows carry the same bounded query preview as the passive path.
- **Hook loopback fix.** A loopback hook fire whose payload omitted the inner event field was silently dropped; it now defaults to the dispatched event and matches.

*Verification: the live #57–72 interface-coverage run (16 sections, 517 stories) passed 289/289 executed with zero hard failures; these are the residual refinements it surfaced (false-positives excluded after re-checking against shipped code).*

## [v0.2.81] (2026-06-24) — *Hook hardening + audit chain correlation (final harness-coverage features)*

- **Hook deletes are origin-guarded.** Hooks now record who created them; a plugin- or system-contributed hook can no longer be deleted (or content-edited) by an operator — only its enabled toggle stays open. Operator-created and pre-existing hooks are unaffected.
- **Shell-hook secrets resolve through the managed store.** A hook's `secret:` reference is now resolved via the Secret Store (an audited read) instead of read raw from the container environment, and fails closed (the value is dropped, not leaked from an unmanaged env var) if it can't be resolved. The same fix applies to the Slack-approval hook.
- **Multi-step tool chains are correlatable.** Each chat turn now stamps a `chain_id` on the audit rows of the tool calls it makes, so a multi-step action chain (e.g. isolate → remediate → unisolate) can be followed end-to-end — and a partial-chain failure traced — in the audit log.
- Internal: the new `POST /api/v1/secrets/resolve` MCP endpoint is MCP-token-only (an API key can never resolve a secret); the hooks and audit tables gained backward-compatible `created_by` / `chain_id` columns via idempotent migrations.

This release closes the harness test-coverage Medium/Low tier (#84) at 195/195.

## [v0.2.80] (2026-06-24) — *Doc accuracy, version sync, honest tool status*

- **OpenAPI spec reports the real version.** The downloaded API spec carried a hardcoded `0.2.0`; it now reflects the running stack version, and both its JSON and YAML paths fail gracefully.
- **EDR/exclusion tools report honest status.** Several XSIAM write tools (IOC enable/disable, endpoint alias, hash blocklist, alert-exclusion delete) echoed input-derived "success" without checking the API reply; they now inspect the response and surface the real error on failure.
- **Bypass mode covers connector tools.** A job running with approvals bypassed no longer stalls on a connector-gated tool (e.g. web navigation) waiting for an approval that auto-resolves — it now auto-approves immediately and records an `auto_approved` trace, matching built-in tools.
- **Job round-trip fidelity.** A job's `bypass_approvals` / model / thinking / permission-policy settings now survive a YAML reload instead of silently reverting to defaults on boot.
- **Docs match reality.** The knowledge pages show the actual embedding model in use (not a hardcoded one); the observability Traces tile describes the audit-derived view honestly; connector/version pins, model lists, service counts, and several tool/docstring catalogs were corrected to match the code.

## [v0.2.79] (2026-06-24) — *No dead clicks: every affordance wired to real backing (or removed)*

- **Chat affordances are real.** A plan's "Approve & run" button now executes the reviewed plan in one informed step (single-use, prompt-matched bypass — not a standing setting); chat-session rename from the header works; reasoning and per-tool error state + durations now survive a reload; the export menu greys out YAML when the server lacks PyYAML.
- **Connectors & instances are operable from the UI.** Per-instance Restart and a Reconcile sweep are wired to the updater; the observability pipeline's connector lane is now derived from live connector state instead of sample data.
- **Knowledge, memory, skills.** Cross-KB search on the top Knowledge page; the memory "promoted" badge reflects real FTS promotion; the memory session tab lists real `session:` rows; deleted skills can be restored in-product; a dead skills-tab code path was removed.
- **Observability & telemetry.** A new Telemetry page (opt-in usage metrics) replaces a dead control; personality history is now reachable; job export and other client-only actions leave an audit trace via an allow-listed beacon.
- **Investigation & subagents.** Case-related / technique-issues / playbook-issues / issue-report links are backed by real routes; a `parent_session` subagent now actually inherits the parent's (trimmed) conversation; the escalation-threshold setting feeds the system prompt.
- **Removed dead controls.** The personality daily-summary settings (no subsystem behind them) and the orphaned skills-tab module were removed.
- Two items remain deferred as larger features: a credential-secret store for shell hooks (HOOK-F14) and origin-tracking for hook deletes (HOOK-F15).

## [v0.2.78] (2026-06-24) — *Input-validation hardening: path-traversal guard, deny-list enforcement, fail-closed rejections*

- **Skill paths can't escape the skills directory.** The skills read/update/enable/delete routes now resolve the path and reject anything absolute or traversing outside the skills tree (`../../…`) with a clear error — closing a path-traversal vector.
- **Denied connector tools are never registered.** A connector manifest's `tools.deny[]` is now enforced at registration time, so a denied tool (e.g. an XSIAM lookup-removal) can't be reached even by direct tool dispatch.
- **Subagents stay in their lane.** A subagent can no longer call the parent-only `subagent_create` meta-tool (dropped from its set regardless of allowlist), and `PreToolUse` hooks now run before a subagent's tool dispatch (deny/replace honored).
- **Clearer, earlier rejections.** Unknown API-key scopes now map correctly to read/write tiers (and unknown scopes grant nothing); reading a non-existent skill returns 404 (not 200); listing an unknown knowledge base returns an error with the valid names; a memory-store embed failure returns a friendly error; the Vertex/XSOAR/XSIAM instance probes now actually validate credentials instead of always reporting success.
- **Scheduling correctness.** A new job's timezone defaults to the browser's zone (matching the clock values shown); a job whose action type is unsupported now auto-disables on first fire instead of erroring forever; regenerating an unchanged report/diagram no longer collides on a duplicate job name; a partial backup is now detectable from response headers.

## [v0.2.77] (2026-06-24) — *Observability granularity, part 2: job runtime events, quieter-failure signals, proxy failure traces*

- **The runtime-events page reflects job activity.** Scheduled-job fire / complete / fail now mirror into the runtime event log (with per-event counters), so a healthy install's events view is no longer near-empty.
- **High-volume secret reads are tunable.** The per-tool-call `secret_read` success row (which can dominate the audit log) is now gated behind `GUARDIAN_AUDIT_SECRET_READ` (default on); *failed* reads are always audited.
- **Quieter failures get a voice.** A job that couldn't load its bound skill, an unavailable `<available_skills>` block in chat, a subagent task that failed to create, and a proxy request that errored or got a 5xx now each leave a signal; plugin install/uninstall failures persist fuller stdout/stderr for diagnosis.
- **Subagent reasoning streams.** A subagent's thinking is now streamed separately (and kept out of its stored transcript), matching the main loop.
- **Honest cost + turn signals.** The `/cost` page warns when it hits its row cap (totals are a floor); `chat_turn_cost` carries the finish reason, and a repeated compaction-checkpoint-save failure now backs off instead of re-paying for the same compaction every turn.

## [v0.2.76] (2026-06-24) — *Finer-grained observability: per-phase research, honest turn status, size guards, embedding accounting*

- **Deep-research shows its work.** A `deep_research` call previously collapsed its many searches + fetches + gap-checks into one event; the result now carries a per-phase breakdown (plan / search / fetch / gap-check / synthesize, with counts and timings) and any warnings, so partial-coverage failures are visible.
- **Chat turns report the true exit cause.** A turn that ended on a safety block, ran tools-only, or exhausted its budget is no longer mislabeled "completed"; the run status now reflects what actually happened. Auto-compaction checkpoint-save failures and `/cost` result truncation (when a session exceeds 1000 cost rows) are now surfaced instead of silent.
- **Screenshot size guard.** `guardian_web_screenshot` now accepts a `max_bytes` cap (default 4 MiB) and returns a bounded rejection instead of injecting a multi-megabyte image into context.
- **Embedding accounting.** A knowledge-base load now records how many documents used trusted pre-baked vectors vs were embedded live — so a normal zero-cost boot is distinguishable from one that paid for hundreds of Vertex calls.
- **Quieter failures get a voice.** Memory injection that errored or found nothing, an invalid built-in hook that would silently never fire (now badged in the Hooks page), and an SVG-too-large diagram rejection (now a specific message, not a generic timeout) each leave a signal.
- **Proxy latency.** The agent→MCP proxy now stamps a per-request duration + request-id header for latency triage.

## [v0.2.75] (2026-06-24) — *Forensic audit trail, part 3: chat-turn observability*

- **Chat-turn decisions are now traceable.** A turn auto-retry (recovering a leaked tool call or an empty response), a safety/recitation block, a context-window hard block, a turn-cache hit that skipped the MCP, and a suppressed repeat-failing tool call now each leave a distinct audit row — previously these were only in debug logs or invisible.
- **Slash commands and model switches are audited.** `/model` (set/clear), `/clear`, `/help`, and `/tasks` record audit rows attributed to the operator; read-only status queries are intentionally left out to keep the log signal-rich.
- **Turn origin is captured.** A turn started from a quick-action chip is now distinguishable from a typed message in both the audit trail and the live stream.
- **Operator-state attribution.** The operator-state (e.g. subagents-enabled) toggle now attributes to the real principal and its events are declared for the observability filter; the agent proxy forwards the actor/trigger headers it previously dropped.
- **Action recap completeness.** The end-of-turn "changes applied" recap now recognizes newly-shipped mutating tools (investigation / XSOAR / webhook) via a write-verb heuristic, so a side-effecting tool isn't silently omitted from the summary.

## [v0.2.74] (2026-06-24) — *Forensic audit trail, part 2: knowledge / memory / skills / subagents / hooks / providers / auth probes*

- **Knowledge & memory access leaves a trace.** Listing knowledge bases and their tags, and searches that fail to embed, now record audit rows; memory and KB search rows now carry a bounded query preview (and the active/passive mode + session) so "what was searched, by whom" is answerable.
- **Skill edits are verifiable.** Updating a skill records the body's before/after SHA-256, and a job that ran with a skill bound records which skill (and the effective model) it used.
- **Subagent & provider visibility.** Listing/reading agent definitions and operator-state is now audited; testing a Vertex credential records a `provider_probed` row (service-account email + project — never the private key); a provider config change uses a dedicated action.
- **Auth probing is visible.** A wrong-*username* login attempt and a rate-limit lockout now leave audit rows (attempted username + source IP, never the password), and a request presenting a stale/revoked session cookie to `/api/auth/status` is recorded — while ordinary successful polls are intentionally not, to keep the log signal-rich.
- **Hook & approval edge cases.** A self-resolve attempt on an approval is rejected and audited; the orphaned-approval reaper records what it swept; `hook_dispatched` rows now note whether the hook injected context. Fire-and-forget audit calls now retry once so a transient MCP blip no longer silently drops a row.
- **Attribution + accuracy.** Memory, skill, and notification mutation routes now attribute to the real principal (not a hardcoded `user:operator`); notification acknowledgement and benchmark-run starts are audited.

## [v0.2.73] (2026-06-24) — *Forensic audit trail: true actor attribution + missing-event coverage (investigation / connectors / XSOAR / jobs)*

- **Operator mutations now attribute to the real principal.** Connector, instance, marketplace and job mutation endpoints hardcoded the audit actor to `user:operator`, overwriting the authenticated identity — so an API-key admin's actions were indistinguishable from the console operator's. They now record the actual principal (`apikey:<id>` or `user:operator`) from the request.
- **Instance edits say *what* changed.** An `instance_updated` audit row previously recorded only counts; it now lists the *names* of the config keys and secret slots that changed (never the values) and whether the enabled bit flipped and in which direction — so a pure enable/disable toggle is no longer an invisible no-op in the log.
- **Investigation mutations leave a trail.** Setting a verdict, mapping an ATT&CK technique, patching an issue, relating cases, and deleting an issue/case now write timeline + audit events (including the title/kind of a deleted issue) instead of vanishing into a coarse proxy row.
- **Job auto-disable and interrupted sessions are audited.** When the scheduler auto-disables a job (run-once, unknown tool, or repeated failures) or marks a session interrupted, it now emits an audit row with the reason.
- **Connector audit accuracy.** `connector_disabled` is recorded as a success (not "skipped" — it really disabled), and a probe that only reset a connector to pending is recorded as "skipped" with `probe_implemented:false` rather than a misleading "success".
- **Multi-step XSOAR tools report partial steps.** `xsoar_add_note`, `xsoar_update_incident`, and `xsoar_run_playbook` now return a per-step breakdown so a partial failure (e.g. entry created but note-pin failed) is visible in the result.
- **`^tool` direct dispatch attributes correctly.** Operator `^tool` invocations now forward the principal to the MCP, so those audit rows show the operator instead of falling back to a generic `agent`.

## [v0.2.72] (2026-06-24) — *Honest verdict push-back, observable embedding drift, reliable approval cards, proxy audit trail*

- **Pushing a verdict to XSOAR now tells you the truth when part of it fails.** `push_verdict_to_xsoar` always reported success even when the war-room entry landed but the evidence tag or the timeline log failed. It now returns a per-step breakdown and reports overall failure — with `partial: true` when the verdict itself reached XSOAR but a secondary step didn't — so the operator knows exactly what landed.
- **A misbaked knowledge-base embedding model is now visible.** When a KB's pre-computed vectors were produced by a different embedding model than the running one, Guardian silently re-embedded every document live on every boot — a recurring, invisible cost buried in hundreds of log lines. That drift now increments a metric (`guardian_kb_embed_mismatch_total`) and emits a single audit event (`kb_embed_mismatch`) per process, pointing at the re-bake needed to stop it.
- **The inline approval card no longer occasionally fails to appear.** A gated tool whose approval resolved unusually fast — or a little slower than the old six-second watch window — could leave the chat without a card. Detection is now status-agnostic and watches for thirty seconds, and an already-resolved approval renders in its final state instead of a stuck "pending" card.
- **Every state-changing request through the agent now leaves an audit trace.** Writes (POST/PUT/PATCH/DELETE) admitted by the proxy tier previously had no record of their own; they now emit a `proxy_request_admitted` audit event (method, path, actor) and carry a correlation `x-request-id` header so a proxy request can be tied to the MCP-side actions it triggered. High-rate reads are excluded so the log stays useful.

## [v0.2.71] (2026-06-24) — *Skills: creatable categories, plugin skills in jobs, edits survive upgrades*

- **Creating/importing a skill in any of the four categories works.** The Create and Import dialogs offered foundation/scenarios/validation/workflows, but the backend only accepted foundation/workflows — so importing a plain Markdown file (which defaults to *scenarios*) or creating a scenarios/validation skill always failed with an "invalid category" error. The backend now accepts all four.
- **A scheduled job bound to a plugin skill now actually uses it.** The job runner couldn't resolve plugin-contributed skills (their `vendor.skill` name didn't map to the plugin's folder), so the job silently ran without the skill attached. Plugin skills now resolve correctly.
- **Your edits to built-in skills survive upgrades.** The startup skill sync overwrote bundled skills with the image defaults on every upgrade, silently discarding operator edits. It now snapshots an edited skill into the skill history before overwriting, so the change is recoverable.

## [v0.2.70] (2026-06-24) — *Bound database growth: memory TTL + audit retention*

- **Expired memories now disappear immediately.** The memory TTL cleanup only ran at startup, so an expired memory could still be returned by reads (and surface in search) until the next restart. Reads now exclude expired entries the moment they expire, a cleanup sweep runs hourly (not just at boot), and the cleanup leaves an audit row + a metric. (Also fixed a timezone bug in the expiry calculation.)
- **The audit log can now be size-bounded (opt-in) and its growth is observable.** `audit.db` had no retention and no size signal, so it grew without bound. It now exposes row-count and on-disk-size metrics, and supports an optional retention window via `AUDIT_RETENTION_DAYS` (a positive integer). Retention is **off by default** — the audit log is forensic, so history is never pruned unless an operator opts in; when it is, the pruning sweep itself is recorded as an `audit_reaped` event.

## [v0.2.69] (2026-06-24) — *Close two cache-staleness windows in auth + approvals*

- **A revoked API key now stops working immediately.** Deleting an API key only revoked it server-side; a warm validation cache on the agent could keep accepting the key for up to 30 seconds. The delete now evicts the key from that cache by id, so revocation takes effect on the next request.
- **Re-enabling approvals in a chat takes effect right away.** A session's approval mode (manual vs bypass) was cached for 30 seconds, and the cache was never cleared when the mode changed — so flipping a session back to *manual* could still auto-approve gated tools for up to 30 seconds. The session-update path now clears that cache immediately, and an uncertain read now defaults to *manual* (require approval) rather than risking a stale bypass.

## [v0.2.68] (2026-06-24) — *Lock down two exposed surfaces: metrics + plugin pip-install*

Security hardening of two over-exposed endpoints:

- **The Prometheus metrics endpoint now requires authentication.** `GET /api/v1/metrics` on the embedded MCP was open — anything that could reach the MCP port read every counter name and value without a credential. It now requires the MCP token or an API key. The in-app metrics panel is unaffected (it already authenticates through the agent proxy).
- **Installing a plugin package now requires admin rights and an explicit approval.** The plugin entry-point install/uninstall endpoints run `pip`, which executes arbitrary package code inside the agent container. Previously any valid API key could trigger it with no confirmation. Now it's restricted to the internal admin token (operator-minted API keys are refused) **and** gated behind a human approval — the request blocks until an operator confirms it in **Approvals** (or it's denied/times out). The install/uninstall audit events are now declared so they show up in the `/observability/events` filter chips.

## [v0.2.67] (2026-06-24) — *Close audit blind spots: reads, auth, and KB access now leave a trace*

Security/observability hardening — seven forensic gaps where an action left no audit row:

- **Memory reads are now recorded.** Listing the memory store (`GET /api/v1/memories`) and reading a memory by key (`GET /api/v1/memories/by-key/{key}`) previously wrote nothing — full enumeration or arbitrary-key probing was invisible. They now emit `memory_listed` / `memory_read`.
- **Knowledge-base access is now visible.** Listing or searching a KB (agent tool *or* the passive per-turn context injection) and reading a full KB doc now emit `kb_searched` / `kb_doc_read`. `kb_searched` carries a `mode` field (`active` = agent search, `passive` = automatic context injection, `list` = enumerate) so the two are distinguishable.
- **API-key authentication has a forensic trail.** A successful key use (`api_key_used`), invalid/revoked-key probing (`api_key_auth_failed`), scope denials (`api_key_scope_denied`), credential-route denials (`api_key_credential_route_denied`), and direct-to-MCP bearer failures (`mcp_bearer_auth_failed`) are now all recorded. Only key *prefixes* are logged — never secret material.
- **Password-change failure paths are recorded.** A failed credential write or a change-password attempt with a forged/expired session now leaves a `password_change_rejected` row (the success path was already audited). All authentication events (`password_changed_ui`, `login_success`, `login_failed`, `logout`, …) are now discoverable in the `/observability/events` filter chips.
- **Claude Code CLI turns are now audited.** The `/api/chat/cli` path claimed to write an audit row but didn't; it now emits `chat_cli_turn` (start + end) so CLI turns appear in observability.

## [v0.2.66] (2026-06-24) — *Remove a custom connector from the marketplace*

- **Uploaded connectors now appear in the Marketplace — and can be deleted there.** Previously a connector you uploaded was invisible on the Marketplace tab (only the five bundle connectors showed), so fully removing it meant a raw API call. The Marketplace tab now lists your uploaded connectors too, each with a **Custom** badge. Open one and its detail panel has a **Delete** button that permanently removes the connector's uploaded definition (with a confirmation step). Delete its instances first — Delete is refused while any instance exists and tells you so. Bundle connectors are unaffected: they have no Delete button and stay image-baked (use **Uninstall** to hide them).

## [v0.2.65] (2026-06-24) — *Upgrade Guardian from inside the app*

- **One-click stack upgrade in the About modal.** You no longer need to SSH in and run the installer for a routine update. Open **About** in the sidebar (or **Check for updates** in its menu): when a newer release exists you'll see an *Update available — v\<running\> → v\<latest\>* banner with an **Upgrade** button. Clicking it pulls the new images and swaps the containers in place, streaming live progress (fetching manifest → pulling images → swapping → healthcheck) into the modal. The agent restarts briefly during the swap — the page detects this, waits for it to come back, and reloads onto the new version automatically. The installer-binary path remains available for clean re-installs and pinning a specific version.
- **Safe to leave running.** Closing the modal or navigating away doesn't cancel an in-progress upgrade, and if one is already running (e.g. started from another tab) the modal attaches to it rather than starting a second.

## [v0.2.64] (2026-06-23) — *Connector lifecycle: self-heal user connectors, longer research runs*

- **Auto-restart now covers user-uploaded connectors.** The self-healing reconcile (which restarts a connector container that has died) previously only covered the built-in connectors; a custom connector you uploaded was skipped and stayed down. Reconcile now restarts user connectors too, using the image declared in their connector definition.
- **Deep research runs to completion via `^tool`.** The direct-tool-call path's timeout was raised from 150s to 300s so a full `deep_research` run (which can take 1–3 minutes) returns its complete result instead of being cut off mid-run.
- **Groundwork for removing user connectors from the UI.** Added the agent-side API to fully delete a user-uploaded connector (previously only reachable with a direct token call); the in-app button to surface and remove user connectors follows in the next release.

## [v0.2.63] (2026-06-23) — *Audit now records what a tool did, not just which fields it used*

- **Tool-call audit rows now capture argument values, with secrets redacted.** Previously the audit log recorded only the *names* of a tool's arguments — so the command an analyst ran, the XQL query, the IoC enriched, or the note added were forensically invisible. Audit rows now include the argument *values* (e.g. `arg_values: {command: "!whois ip=1.2.3.4"}`), so `/observability/events` shows what actually happened. Values are redacted at capture time: arguments that are credential/code/config blobs (script snippets, skill/playbook/connector content, memory/personality/settings/job payloads, XSOAR list contents) are stored as `[redacted]`, any argument whose name looks secret (token/password/key/…) is redacted regardless of type, and long values are truncated. This is on by default; set `GUARDIAN_AUDIT_ARG_VALUES=0` to disable for strict-data-policy deployments.
- **Hardened the shared secret-key redaction list** (added credential/passwd/session/cookie/private/client_secret/refresh/… variants) and consolidated three duplicated copies into one source of truth, which also strengthens the approval-card argument scrubber.

## [v0.2.62] (2026-06-23) — *Connector & updater actions are now in the audit trail*

Closing observability gaps around connector instances and the self-update service:

- **Testing a connector instance is now recorded.** Clicking "Test" on an instance — credential/reachability validation against XSOAR, Cortex docs, or the browser sidecar — now writes a `connector_probed` event (success / failure / skipped) to `/observability/events`, where before it left no trace.
- **The updater's container and stack actions are now audited.** Starting, stopping, and restarting connector containers, restarting the agent, and applying a stack update were previously visible only in the updater's own logs. They now appear in `/observability/events` (and `audit.db`) — attributed to `system:updater` so they're distinguishable from operator actions. Reconcile-driven container starts surface through the same container-start events.

## [v0.2.61] (2026-06-23) — *Web tool: gated, audited, and health-checkable*

Hardening the headless-browser connector:

- **A click that navigates off the allowlist is now blocked.** `web.navigate` already enforced the `allowed_domains` allowlist, but a click that triggered navigation slipped past it. Clicks that land on a domain outside the allowlist are now reverted and reported as an error, closing the bypass.
- **Where a click navigated to is now recorded in the audit trail**, not just in the live tool result — so an attempted off-allowlist navigation leaves a URL trace in `/observability/events`.
- **The web connector now has a real "Test" probe.** Testing a web instance previously reported a non-committal result without contacting anything; it now checks the Chromium sidecar's debugging endpoint, so a down sidecar shows as unreachable instead of looking fine. (The sidecar image itself is too minimal to carry a container-level healthcheck; the instance Test button is the supported reachability check.)

## [v0.2.60] (2026-06-23) — *Subagents: scoped, attributed, and tamper-resistant*

Hardening the subagent (custom-agent) subsystem so spawns are scoped, attributed, and protected:

- **A subagent must be given an explicit tool allowlist.** Creating or editing an agent with an empty allowlist is now rejected — previously it silently inherited the *full* parent tool catalog (including high-impact response tools) with no approval. Use `["*"]` to deliberately grant everything.
- **Builtin and plugin-provided agents can no longer be edited or deleted via the API/UI.** Only operator-created agents are mutable; the others are owned by their source and would be overwritten on reload. The UI now shows a lock on those rows, and the API returns a clear 403.
- **Renaming an agent to a name already in use returns a clean error** instead of a 500.
- **Spawning an agent by name is now case-insensitive** — `Case-Triage` resolves `case-triage`.
- **Failed and blocked subagent activity is now audited.** A spawn that fails before it starts (agent not found, disabled, or denied by a hook) writes a `chat_subagent_dispatch_failed` event, and a subagent attempting a tool outside its allowed scope writes a `subagent_tool_blocked` event (and records it in the sidechain transcript) — previously both were invisible in `/observability/events`.

## [v0.2.59] (2026-06-23) — *Hooks & approvals: honest signals, no silent traps*

Hardening the hooks subsystem and the approval queue so nothing fails silently:

- **Approval risk is now shown from the authoritative tier, not a guess.** The Approvals page badged danger by keyword-matching the tool name, so genuinely dangerous approvals (resetting personality, deleting an instance, minting an API key) could render LOW. It now uses the approval's real risk tier (destructive/credential → HIGH, soft → MEDIUM, read → LOW), falling back to the old heuristic only for legacy rows.
- **Notification and PermissionRequest hooks are now audited.** Hooks fired on the internal notification/approval path (e.g. a Slack-mirror or PagerDuty hook) wrote no audit row, so they were invisible in `/observability/events`. They now record a `hook_dispatched` event like every other hook. (The troubleshooting filter in the help guide is corrected to `action:hook_dispatched`.)
- **A PermissionRequest hook can now resolve the approval it answers.** When such a hook returns a definitive allow/deny, the matching approval is resolved immediately instead of leaving the gated tool blocked until the 5-minute timeout.
- **Unimplemented hook options are now rejected at creation instead of failing silently.** The reserved `agent` transport (which, mis-set to "block", silently denied every matching event) and the unenforced `matcher.tenantId` (which silently fired for *all* tenants) are now rejected with a clear error when you create or edit a hook, rather than installing a hook that quietly misbehaves.

## [v0.2.58] (2026-06-23) — *Every button does something: dead/stub UI swept*

A pass over UI affordances that looked clickable but did nothing (or led to a 404), so a customer never clicks and gets silence:

- **Skill enable/disable now persists and takes effect.** Toggling a skill off on the `/skills` page writes an `enabled` flag to the skill and drops it from the agent's prompt — it no longer reverts on refresh or stays silently loadable. Re-enabling restores it. Both are recorded in the audit log.
- **Memory search "Advanced" sliders now work.** The MMR (diversity) and temporal-decay (recency) sliders on `/memory` now actually re-rank results — previously they were sent but ignored by the search backend.
- **Personality "Reset Defaults" restores the true bundle default** via the server-side reset endpoint, instead of writing a copy of the UI's built-in defaults (which could drift from the shipped default over time).
- **Services panel — "View Logs" and "Restart Service" now function.** "View Logs" opens the observability log view filtered to the service (was a dead `/monitor/logs` link → 404). "Restart Service" restarts the agent via the updater after a confirmation; it's disabled for the in-process components that can't be restarted on their own.
- **Notifications toolbar wired up.** "Mark All Read" marks every unread notification read; "Load more" pages through history; the inert date-filter and gear buttons were removed. Approval notifications now link to the Approvals page (the place that can actually approve/deny) instead of showing buttons that did nothing.
- **Password recovery instructions corrected.** The backup/restore page now shows the in-container `reset-admin.mjs` command for recovering a lost UI password, replacing a "download" button that pointed at a removed endpoint.

## [v0.2.57] (2026-06-23) — *Audit attribution: who made the change*

- **Audit events now record the principal behind a change, not just `user:operator`.** Every authenticated request is now stamped with its principal — `apikey:<id>` for an API-key caller, `user:operator` for a UI session — and that flows through to the audit trail. Mutations made via the REST API and chat turns are attributed to the specific API key or operator session that made them, so a multi-admin / multi-key deployment can answer "who did this" in `/observability/events`. (A client cannot spoof the attribution; the server sets it after authentication.)

## [v0.2.56] (2026-06-23) — *Audit attribution: turn-start + direct tool calls*

- **Chat turns are now logged the moment they start.** Previously the first audit record for a turn was its end-of-turn cost row, so a turn that failed before the first model call (an auth/setup error, a hook denial, an unreachable provider) left no trace in `/observability/events`. Each turn now writes a `chat_turn_started` event up front.
- **Operator-typed `^tool` calls are distinguishable from the agent's own calls.** A direct tool dispatch from the chat input now tags its audit row with the `operator:direct` trigger, so you can tell an operator-run tool apart from a model-driven one in the events view.

## [v0.2.55] (2026-06-23) — *Approval gating for XSOAR actions*

- **XSOAR mutating/action tools now require approval.** Running an arbitrary integration command (`run_command`), running or importing a playbook, creating/updating/closing an incident, completing a playbook task, and editing XSOAR Lists now prompt for operator approval before they execute — on the chat path and the autonomous jobs path (a bypass session/job records an `auto_approved` audit row). Reads and routine War-Room documentation (entries, notes, evidence) are unaffected. This brings XSOAR in line with the XSIAM response-tool gating shipped in v0.2.51.

## [v0.2.54] (2026-06-23) — *Failed tool calls are recorded as failures*

- **A tool that fails without throwing is now logged as a failure.** Connector tools (XSOAR, XSIAM) and several built-ins report a problem by *returning* `{ok: false}` / `{error: …}` rather than raising an exception. The audit log and the job scheduler previously keyed status only on raised exceptions, so these showed up as `status=success` — a failed `close_incident`, a rejected XQL query, or a scheduled tool that errored all looked healthy in `/observability/events` and in the jobs run history. They're now correctly recorded as **failures**, which also means a repeatedly-failing scheduled tool trips the consecutive-failure auto-disable instead of firing silently forever.

## [v0.2.53] (2026-06-22) — *Remove the dead Detections surface*

- **Retired the non-functional Detection Inventory page.** `/observability/detections` (and its Detections nav entry, its `/api/agent/detections/*` routes, its API-reference entries, and its user-guide section) was a leftover from an earlier product stage — its backend was removed at the v0.1.0 carve-out, so every visit 404'd. The whole surface is now gone rather than dangling. The agent's investigation, hunt, and connector tooling are unaffected.

## [v0.2.52] (2026-06-22) — *Hooks fail closed*

- **Policy hooks no longer silently disable themselves during an outage.** Previously, if the hook store was briefly unreachable, the dispatcher treated it as "no hooks registered" and let the turn proceed — so a block-policy hook (e.g. "block writes to the production tenant") would quietly stop enforcing. Now a hook-store load failure **fails closed** on the events that can block an action (a tool call, a prompt, a compaction, a turn, a subagent spawn): the action is denied with a clear reason instead of slipping through unchecked. Non-blocking events (post-hoc, notifications) still proceed. Operators who prefer availability over this guarantee can set `GUARDIAN_HOOKS_FAIL_OPEN=true` to restore the previous behavior.

## [v0.2.51] (2026-06-22) — *Approval gating for high-impact actions*

A security-hardening pass that puts a human-approval gate in front of the actions that can change security posture or run code — closing gaps where the gate was declared but never actually fired.

- **XSIAM response/EDR actions now require approval.** Isolating or scanning an endpoint, running a script or an arbitrary snippet, quarantining a file, blocklisting a hash, pushing or toggling IOCs, creating alert exclusions, and similar high-impact XSIAM writes now prompt for operator approval before they run — on the chat path **and** the autonomous jobs path (a bypass session/job still records an `auto_approved` audit row). Read/investigation tools are unaffected. The marketplace and docs already described this behavior; the gate now matches the description.
- **Outbound webhook export now actually gates.** `export_to_webhook` was listed as approval-required but, due to how built-in tools were dispatched, the gate never ran — external data egress could happen without confirmation. It now gates correctly. `webhook_preview` stays read-only.
- **Creating or editing a skill now requires approval.** `skills_create` and `skills_update` join `skills_delete` behind the approval gate (the skill files become instructions the agent trusts on the next turn), and every create is now audited (`skill_created`).

## [v0.2.50] (2026-06-22) — *Audit coverage: nothing happens without a trace*

A security-hardening pass closing audit/observability blind spots — every consequential action now leaves a record in `/observability/events`.

- **Built-in tools are now traced.** Investigation, memory, jobs, knowledge, sessions, and skills tools previously executed without writing a `tool_call` audit row, so a session or job that used only built-ins was invisible in the events + traces views. They now emit the same audit row connector tools do (actor, status, duration, argument *names* — never values).
- **Job edits are audited.** Changing a job (cron, action, model, permission policy) — and especially toggling *bypass-approvals*, which arms unattended auto-approval — now records a `job_updated` event with the changed fields.
- **Backup + restore are audited and locked down.** Exporting a backup (which contains cleartext secrets) records `backup_exported`; applying a restore records `restore_applied`; and both endpoints are now session-only (API keys can no longer reach them, matching the other credential routes). Restore's `force=true` now actually overwrites a colliding connector instance instead of silently failing.
- **Skill deletions are audited.** Removing a skill now records `skill_deleted`, symmetric with the existing edit audit.

## [v0.2.49] (2026-06-21) — *In-product help refresh*

A clean-up pass over the in-product help (User Guide, Architecture, API reference, User Journeys) so every page reads as a description of the product as it is today, plus two coverage fixes operators will notice.

- **User Journeys catalog now shows every category.** The journeys browser previously hid the Authentication and Connectors categories; all categories and their click-paths are now listed, and journeys were added for the investigation Assessment/Report/Campaign tabs and STIX export.
- **REST API reference completed.** Added the investigation export endpoints that were missing from the reference — issue/case STIX bundles, the generated report, and related-case lookup — and replaced placeholder entries on the observability endpoints with real descriptions.
- **Guides clarified.** Every help page was rewritten to plain present-tense descriptions of current behavior; the Architecture page gained a concise Investigation-tools reference and a capability-oriented overview of the investigation module.

---

## [v0.2.48] (2026-06-21) — *Export + interop (stage D)*

The final stage of the investigation-model arc makes the structured record portable — exportable as STIX, renderable from report templates, and (opt-in) pushable to an external system — so Guardian's findings flow into the wider SOC ecosystem.

- **STIX 2.1 export.** `export_issue_stix` / `export_case_stix` (and a one-click **Export STIX 2.1** on the Report + Campaign tabs) emit a standard STIX bundle of the incident/campaign + ATT&CK techniques + indicators + their relationships — ready for any threat-intel platform or SIEM. Deterministic ids, pure assembly.
- **Report templates.** `generate_investigation_report` now takes a template — **technical** (the full write-up, default), **executive** (a brief), or **ioc-list** (machine-pasteable) — and `generate_campaign_report` renders the case level.
- **Outbound handoff — opt-in + approval-gated.** `export_to_webhook` POSTs the verdict + report + IOCs + STIX to an operator-configured webhook (SOAR / ticketing / chat ingress). It is the only investigation tool that sends data externally, so it is **off by default** (until you set `GUARDIAN_WEBHOOK_URL`), sends only to the URL you configure, and asks for approval before every send. `webhook_preview` shows exactly what would be sent first.
- This completes the structured-investigation arc (stages A–D): a machine-readable verdict, backed by multi-source evidence, rolled into campaigns, and now portable to the rest of your stack.

---

## [v0.2.47] (2026-06-21) — *Campaign / cross-incident analytics (stage C)*

Stage C lifts the structured single-incident records into fleet intelligence: related incidents roll up into a typed campaign, investigations are typed by the playbook they followed, cases link to prior campaigns, and the relationship graph suggests the edges and siblings you'd otherwise miss — so an analyst sees the bigger picture, not one alert at a time.

- **Campaign rollup.** A new `case_rollup` synthesizes a Case from its member issues — the combined ATT&CK techniques, the shared infrastructure (indicators seen on more than one issue), the overall severity, and the verdict mix — and shows it on the case's new **Campaign** tab (with a Roll-up button, or automatically when Guardian resolves an incident in a campaign).
- **Type investigations by playbook.** `issue_match_playbook` records which knowledge-base playbook an investigation followed, so cases become queryable by playbook ("show every ransomware-playbook incident").
- **Link related campaigns.** Typed cross-case edges (`case_relate` / `case_related`) connect a new case to a prior one — sibling, escalation, reopen, or same-campaign — and surface as links on the Campaign tab.
- **Relationship inference (suggest-only).** `infer_relationships` walks the indicator relationship graph to *suggest* missing transitive edges (a domain resolves to an IP that beacons to a C2 ⇒ suggest the domain→C2 link) and sibling issues that share a technique or an indicator. Guardian suggests; the analyst confirms — no silent writes.
- **The autonomous loop + judge** now roll campaigns up as part of every investigation and weigh campaign coherence.

---

## [v0.2.46] (2026-06-21) — *Multi-source defensible depth (stage B)*

Stage B of the investigation arc gives each investigation reach beyond the XSOAR case: it hunts the blast radius in telemetry, writes the verdict back to the source incident, and recommends containment — so the structured record (stage A) is backed by multi-source evidence and closes the loop where the SOC works.

- **Verdict pushback to the XSOAR war room.** A new `push_verdict_to_xsoar` tool writes a resolved Issue's structured verdict + key findings back to the upstream incident's war room as a pinned evidence entry — the disposition Guardian reached now lives where the SOC works the case. It writes through the governed tool path (per-instance routing, approval gate, audit all apply) and is a no-op for a standalone Issue (guarded on the tracked incident).
- **XQL telemetry blast-radius hunt.** When a case has a host/user/IP/domain/hash indicator, the investigation skill now pivots into XSIAM with an XQL hunt (`xql_examples_search` → `xsiam_run_xql_query`) to find every *other* endpoint or account that saw it, and folds the result into the structured blast radius. Degrades gracefully to XSOAR-only scoping when no XSIAM instance is configured.
- **`xsiam_run_xql_query` can now scope days, not 30 minutes.** Added a `lookback_hours` window (default 0.5 = backward-compatible; up to 7 days) and a bounded result-poll so wide blast-radius hunts return complete results instead of an empty early read.
- **Containment recommendations — recommend-only, approval-gated.** For true positives, Guardian attaches a structured recommended-containment step (isolate host / disable account / block indicator / run playbook) naming the exact action to approve. Guardian never executes containment on its own; it runs only when you approve it.
- **Autonomous loop deepened.** The investigation loop now hunts telemetry and pushes the verdict back as part of every case; the judge weighs cross-source depth and whether containment was considered for high/critical true positives.

---

## [v0.2.45] (2026-06-21) — *Structured investigation outcome (stage A)*

Guardian's investigation Issues gain a **structured outcome** alongside the prose write-up — a queryable verdict, confidence, blast radius, and ATT&CK technique mappings — plus a generated closure **report**. This is stage A of the cross-incident investigation-model arc: it makes a verdict machine-readable (not just a sentence in the summary) so it can drive the UI, the cross-incident pivot, and later campaign analytics.

- **Structured verdict + confidence + blast radius.** Each Issue can now carry a verdict from a fixed set (true positive, false positive, benign, needs escalation, inconclusive), a 0–100% confidence, and a blast-radius object (which hosts, accounts, and data the attack touched). The Issue detail's **Assessment** tab renders the verdict chip, a confidence meter, and the parsed blast-radius groups; the header verdict banner now prefers the structured verdict and shows its confidence.
- **ATT&CK technique mappings.** Confirmed techniques are recorded as structured rows (technique id + tactic + how it manifested + the evidence), shown as chips on the Assessment tab — not only mentioned in prose. A new cross-incident lookup answers "which incidents involved this technique."
- **Generated investigation report.** A new **Report** tab assembles the verdict, blast radius, techniques, indicators, and timeline into one shareable markdown document — generate or regenerate it on demand, and Guardian writes it when it finishes an investigation.
- **The agent records all of this automatically.** The `xsoar_case_investigation` skill now sets the structured verdict, maps each confirmed technique, and generates the report at resolve, on top of the existing summary/conclusions. The autonomous judge scores against the structured record; the *Block close without verdict* hook accepts either the structured verdict or the legacy `VERDICT:` line.
- **Backward-safe.** Existing `investigations.db` files upgrade in place (guarded `ALTER`/`CREATE TABLE IF NOT EXISTS`); the large report rides only on the issue-detail read, never the list.

---

## [v0.2.44] (2026-06-21) — *XQL knowledge base + authoring skill*

Guardian gains a Cortex XSIAM **XQL query** capability for analysts and the investigation agent: a knowledge base of example queries, a search tool that enriches results with syntax + schema context, and a skill that ties them to live Cortex docs.

- **New `xql-examples` knowledge base** — 201 curated Cortex XSIAM XQL examples: reusable query patterns and per-vendor alert-mapping queries, plus a new **ATT&CK-aligned IR/threat-hunting set** (48 hunts across initial access, execution, persistence, privilege escalation, defense evasion, credential access, discovery, lateral movement, C2, exfiltration, impact, and cloud) — each tagged with its technique. Searchable from chat via `knowledge_search` and browsable at `/knowledge`.
- **New `xql_examples_search` tool** — finds example queries by natural-language intent and enriches each hit with the **XQL stage syntax** and **dataset field lists** the example uses, so the agent can author a query without a lookup per stage.
- **New `cortex_xql_query_authoring` skill** — composes XQL by chaining the example KB with the live Palo Alto Cortex docs (`cortex-docs/xql_lookup`), and — mid-investigation — pivots from an incident's indicators to XQL hunts that scope blast radius, runnable via `xsiam_run_xql_query`.

---

## [v0.2.43] (2026-06-21) — *XSOAR playbook tools — fixed end-to-end on fetched incidents*

A full live smoke of all 27 Cortex XSOAR connector tools surfaced — and this release fixes — three bugs in the playbook tooling (the other tools were already correct). The headline fix lets **`run_playbook` actually run a playbook on a freshly-fetched, not-yet-investigated incident** — the path the autonomous investigation loop depends on.

- **Run a playbook by id *or* name.** `run_playbook` passed your identifier straight to XSOAR's `setPlaybook`, which only matches the playbook's *display name* — so passing the id (e.g. the one `import_playbook` returns) failed with "Playbook … not found". It now resolves an id to its name automatically and accepts either.
- **Run a playbook on a pending/fetched incident.** Assigning a playbook to an incident with no war room yet (status "pending", e.g. just fetched from Splunk) silently failed to open the investigation, so the playbook never started. `run_playbook` now opens the war room the way the XSOAR UI does — it works on fetched incidents, not only ones already under investigation.
- **`import_playbook` reports the imported playbook's id + name** instead of blank values, so you can hand them straight to `run_playbook`.
- **`get_playbook_state` now lists every task** (id, name, state, type), not just the count summary and failed tasks — see task-by-task progress and find a waiting manual task's id to advance with `complete_task`.

All verified against a live XSOAR 6 tenant: import → assign → run → monitor → complete, across the full 27-tool surface.

---

## [v0.2.42] (2026-06-20) — *Emulated services marketplace kind + Splunk mimic*

Guardian's marketplace gains a second entry **kind** — **emulated services** — alongside connectors, and ships the first one: **Splunk (Emulated)**. A service is *not* an agent integration: it runs as a container that Guardian publishes on a **host port** so an **external** system reaches it, and it advertises **zero agent tools**. The Splunk mimic speaks the slice of the splunkd REST API the XSOAR **SplunkPy** integration's `splunklib` SDK actually uses, returning simulated notable events — so SplunkPy commands run end-to-end with no real Splunk server. This is the companion to the `simulate_splunk_incidents` skill (v0.2.41): that one creates Splunk-shaped incidents *inside* XSOAR; this one lets SplunkPy's **fetch** and **playbooks** actually call "Splunk".

### What ships
- **Service marketplace kind** — `connector.yaml` gains an optional `kind: "connector" | "service"` (default `connector`) + a `service.ports[]` block. Purely additive; no existing connector changes meaning. Schema + `validate_connector_spec` enforce it (a connector needs ≥1 tool; a service needs ≥1 port). `bundles/spark/connectors/connector.schema.json`, `bundles/spark/mcp/src/usecase/connector_schema.py`.
- **Zero-tool dispatch** — `connector_loader.iter_registrations()` skips `kind:service`, so the agent never gets a handle to a service (the same boundary that keeps it away from credentials). The marketplace catalogue surfaces `kind`. `bundles/spark/mcp/src/usecase/connector_loader.py`, `bundles/spark/mcp/src/api/marketplace.py`.
- **UI** — a **Service** badge + the existing **Services** filter on `/connectors`; service cards show an "Emulated" type instead of a misleading "Tools: 0"; service instances show a "Service endpoint" chip and suppress the agent's Test Connection (a service is reached by external systems, not the agent). `mcp/agent/app/connectors/page.tsx`.
- **Published host port lifecycle** — guardian-updater publishes a host port for `kind:service` container starts (connectors stay internal-only). Port resolution covers all three paths: operator-create (from `connector.yaml`), digest-drift reconcile (inherit the running container's bindings), and boot-spawn of a missing container (a known-default fallback). `updater/src/main.py`, `bundles/spark/mcp/src/api/instances.py`.
- **Splunk (Emulated) service** — `bundles/spark/connectors/splunk-mimic/`: a standalone `python:3.12-slim` HTTPS server on `:8089` (self-signed TLS by default, mountable operator cert) that emulates `auth/login`, `search/jobs` (oneshot + create), job status, results, and `notable_update`, backed by a notable-event generator + a small SPL interpreter. Byte-compatibility with the real `splunklib` SDK is proven by a live round-trip test.
- **Rotating notables (so fetch keeps getting NEW incidents)** — notables live on a **fixed absolute time grid** (one every `SPLUNK_MIMIC_NOTABLE_INTERVAL_S` seconds, default 60), with each notable's identity + content derived purely from its grid instant. An advancing fetch window therefore exposes fresh `event_id`s each cycle (XSOAR creates new incidents), while re-querying the same window is byte-identical (no duplicates). Rules/urgencies/domains/entities rotate across the grid for a realistic mix. The oneshot path honours `offset` (SplunkPy paginates windows over `FETCH_LIMIT`) and reads index-time windows. Verified against the SplunkPy fetch+dedup contract.
- **SplunkPy fetch-time fix** — the mimic now answers SplunkPy v2's pre-fetch time probe (`get_current_splunk_time` runs `| gentimes start=-1 | eval clock = strftime(time(), …)` before every fetch). Without it the SDK aborted every fetch with `ValueError: Could not fetch Splunk time` — Test passed, Fetch failed. `run_query` now parses the `eval` field + strftime format from the query and returns the current time. `bundles/spark/connectors/splunk-mimic/src/splunk_state.py`.
- **Full SplunkPy command surface against the mimic** — validated every SplunkPy command that uses the splunkd **REST API** by driving the mimic with the real `splunklib` SDK exactly as the integration does (HEC + KV-store-data + ES-mirroring commands are out of scope). Closed the byte-compat gaps that surfaced: management collections (`data/indexes`, `saved/searches`, `storage/collections/config`) now emit **ATOM** with per-entry `<link rel="alternate">` (splunklib `Collection` parses them — fixes `splunk-get-indexes`, `splunk-kv-store-*`); a single-index entity route `GET /services/data/indexes/{name}` (fixes `splunk-submit-event`'s `service.indexes[name]` lookup); a `POST /services/search/jobs/{sid}/acl` ack (fixes `splunk-job-share`); and a `| rest .../data/indexes` branch in the SPL interpreter (fixes `splunk-get-indexes`' primary path). `splunk-search` (oneshot + create→poll→results), `splunk-job-create`/`splunk-results`/`splunk-job-status`, `splunk-submit-event`, and `splunk-update-notable-events` all round-trip. `bundles/spark/connectors/splunk-mimic/src/{server,responses,splunk_state}.py`.
- **XSOAR integration-troubleshooting tools** — three new tools on the Cortex XSOAR connector so a failing integration (e.g. the SplunkPy fetch above) can be diagnosed from Guardian instead of SSHing to read logs: `get_integration_status` (each configured instance's enabled state + last fetch error, read from the `/settings/integration/search` `health` map — the v6 surface), `test_integration_instance` (re-runs the UI "Test" button and surfaces the exact error; guarded on XSOAR 8, whose public API doesn't expose the generic test-module), and `get_integration_fetch_history` (recent fetch runs incl. last error from `/settings/integration/fetch-history` — the XSOAR 8 fetch-error source, also XSOAR 6.8+). `bundles/spark/connectors/xsoar/src/connector.py`, `bundles/spark/connectors/xsoar/connector.yaml`, `mcp/agent/app/api/marketplace/connectors/route.ts`.
- **Playbook-state monitoring** — `get_playbook_state` reports a running playbook's per-task state on an incident (bucketed completed/error/waiting/…, recursing sub-playbooks), whether it `ran_to_success`, and each failed task's error message (pulled from the war room) — the monitoring companion to `run_playbook` for proving a Splunk playbook runs clean against the mimic. v6 reads `GET /investigation/{id}/workplan` directly; v8 via the Core REST API passthrough. The connector's marketplace card now reflects all **27 tools**. `bundles/spark/connectors/xsoar/src/connector.py`.
- **`run_playbook` works on fetched incidents; `list_incidents` source filter** — `run_playbook` now opens the incident's war room first when it has none, so it can assign + start a playbook on a freshly **fetched / pending** incident (previously it failed with "investigation not found" because a fetched incident is pending with no war room). `list_incidents` gains `source_brand` / `source_instance` filters (the `sourceBrand:"SplunkPy v2"` Lucene fields) to find the cases a specific integration instance created. Both are the operator's "do it through a Guardian tool, not ad-hoc API" path. `bundles/spark/connectors/xsoar/src/connector.py`.
- **`import_playbook` no longer drops task command bindings; correct war-room endpoint** — fixed against the documented XSOAR API (no assumptions). `import_playbook` posted to `POST /playbook/import`, which **is not a real XSOAR path** — it fell through the proxy (303) to the lossy JSON `/playbook/save`, which re-serializes through the Playbook model and **silently dropped every task's `script` / `iscommand`** binding, so imported playbooks ran as empty manual tasks that hang in `Waiting` forever. Now uses the real **`POST /playbook/save/yaml`** (swagger `importPlaybook`) — the server parses the native YAML and preserves all bindings. And `run_playbook` opens the war room via the documented **`POST /incident` + `createInvestigation`** (reading the incident's current `version` for the optimistic lock) instead of the internal `/incident/investigate`, which 500s on the public API. `bundles/spark/connectors/xsoar/src/connector.py`.
- **CI + catalogue** — manifest entry, a standalone image build (`guardian-connector-splunk-mimic`), dev-installer + release digest pinning, and a marketplace card.

### Capability acceptance criteria (all verified on the deployed xsoar-v6 install)
- [x] Install + enable **Splunk (Emulated)** from the marketplace; guardian-updater starts `guardian-connector-splunk-mimic-<name>` with `0.0.0.0:8089->8089/tcp` published on the Guardian VM.
- [x] From the Guardian VM: `curl -k https://localhost:8089/services/server/info` returns a version entry; the SplunkPy `auth/login` round-trips.
- [x] A SplunkPy instance on xsoar-v6 runs every REST-API command against the mimic via `xsoar_run_command` — `splunk-search`, `splunk-job-create`/`results`/`status`/`share`, `splunk-get-indexes`, `splunk-submit-event`, `splunk-update-notable-events` — all return generated rows / succeed.
- [x] fetch-incidents on that instance → XSOAR creates Splunk Finding incidents from the mimic's notables (`sourceBrand:"SplunkPy v2"`; required the SplunkPy fetch-time fix, before which fetch aborted with "Could not fetch Splunk time").
- [x] A mimic-safe Splunk playbook (`validation/splunk_notable_triage_mimic.yml`) imported via `import_playbook`, assigned + started with `run_playbook`, runs to completion — all tasks Completed, zero failures — and `get_playbook_state` reports `ran_to_success: true`.
- [x] From Guardian: `xsoar_get_integration_status(brand="splunk")` returns the SplunkPy instance healthy; `xsoar_test_integration_instance("<name>")` re-runs the Test and returns `success: true`.

### Forbidden going forward
- A `kind:service` connector MUST advertise zero agent tools — never `mcp.tool()`-register a service.
- Never hard-code TLS-verification-off inside the mimic's own code; verification-off is purely the XSOAR-side `unsecure` toggle.
- Service containers publish a host port; connectors stay internal-only.

Refs #56.

---

## [v0.2.41] (unreleased) — *New skill: simulate Splunk incidents in XSOAR*

A new workflow skill, **`simulate_splunk_incidents`**, lets the agent create synthetic Splunk incidents in Cortex XSOAR *as if the SplunkPy integration had fetched and mapped them from Splunk Enterprise Security* — useful for testing layouts/playbooks, exercising the Guardian investigation loop, or demos.

### What ships
- **`bundles/spark/mcp/skills/workflows/simulate_splunk_incidents.md`** — carries the SplunkPy content-pack schema baked in: the three Splunk incident **types** (`Splunk Notable Generic`, `Splunk Finding`, `Splunk Investigation`) and, per type, the **post-mapping** XSOAR incident-field `cliName`s + valid select values (e.g. `splunkurgency`, `splunkstatus`, `splunkdisposition`, `notableid`, `splunksecuritydomain`). The agent creates each incident with `xsoar_create_incident` populating `custom_fields` with the *mapped* field names — never the raw Splunk fields — so the cases render in the Splunk layouts and drive the Splunk playbooks identically to real fetched events.
- The skill enforces: post-mapping cliNames only; singleSelect values from the allowed lists; pass `instance=` (the connector is multi-instance — `primary-xsoar` v8, `xsoar-v6` v6); and a one-incident install probe (if the `splunk*`/`notable*` fields don't persist on read-back, SplunkPy isn't installed on that tenant).
- No code/tool change — the existing `xsoar_create_incident` tool already supports `incident_type` + `custom_fields`. Verified live on `xsoar-v6`: a `Splunk Finding` created with the mapped fields round-tripped cleanly (type + all `splunk*` CustomFields persisted).

### Files
- `bundles/spark/mcp/skills/workflows/simulate_splunk_incidents.md` (new skill; auto-seeded to `/skills` on boot, live on the Skills page).

---

## [v0.2.40] (unreleased) — *Chat sidebar: hide autonomous-loop sessions so your own conversations are findable*

Follow-up to v0.2.39. With the loop now reliable, the remaining problem was discoverability: the chat session rail was dominated by autonomous-loop sessions (skill-tick + seeder + judge runs — hundreds of them on a busy install), burying the operator's own conversations.

### Root cause
The sidebar already filtered out scheduled-job sessions (`meta.scheduled_by`), but that tag was only stamped by the auto-title PATCH at **turn end** — so any tick that failed/timed out mid-turn never got tagged and slipped through the filter (~200 untagged orphans flooding the list).

### What ships
- **`scheduled_by` is now stamped at session creation**, not turn end — so every job-driven session is tagged the moment it's created, even if the turn later fails. The auto-title step at turn end now only titles.
- **Boot backfill for legacy sessions** — an idempotent, reversible migration tags pre-v0.2.40 autonomous-job sessions that escaped tagging. It matches the bundled seeder/investigation-loop/judge prompt signatures against **both the title AND the first message's content** — the latter catches the untitled `message_count=1` orphans (timed-out ticks whose auto-title never ran), which are the bulk of the residue.
- **Subagent sessions are hidden too.** `exclude_scheduled` now also drops sessions tagged `meta.subagent_origin` (spawned by a parent turn). Operator forks keep `parent_session_id` but not `subagent_origin`, so they stay visible.
- **"Automated sessions" sidebar toggle** — under the New Chat button, defaults to `HIDDEN` (your conversations only). Flip to `SHOWN` to inspect loop + subagent runs. Remembered per browser (localStorage).

### Files
- `mcp/agent/app/api/chat/route.ts` (tag at create), `bundles/spark/mcp/src/usecase/session_store.py` + `bundles/spark/mcp/src/main.py` (backfill), `mcp/agent/app/page.tsx` + `mcp/agent/components/chat/session-sidebar.tsx` (toggle), `bundles/spark/mcp/tests/test_session_store_backfill.py`, `mcp/agent/app/help/user/page.tsx` (`#chat`).

---

## [v0.2.39] (unreleased) — *Autonomous loop: stop the silent timeouts + mark interrupted sessions*

The autonomous investigation loop was silently failing ~60% of its ticks. Clicking those sessions in the chat sidebar showed only the seed prompt and nothing else — which read as "previous sessions won't load."

### Root cause
The `guardian-investigation-loop` job streams the agent's `/api/chat` response with a hard-coded **300-second** read timeout. A full `xsoar_case_investigation` turn makes 30–47 tool calls plus diagram generation and routinely runs longer than 5 minutes. When the timeout fired, the turn was aborted **after** the user prompt was persisted but **before** the assistant turn — leaving a silent `message_count=1`, `ended_at=null` orphan session. 24 of 40 recent loop runs failed this way (every one: `RuntimeError: agent /api/chat timed out after 300s`).

### What ships
- **The chat-action read timeout is now configurable and generous.** `JOB_CHAT_ACTION_TIMEOUT_S` (default **1200s / 20 min**, comfortably under the `*/30` cron) replaces the hard-coded 300s. The timeout is applied as the inter-event read gap (`connect`/`write`/`pool` stay short so a genuinely unreachable agent still fails fast). This alone lets long investigations actually finish.
- **Failed ticks no longer leave silent orphans.** On timeout (or a chat-error event), the scheduler appends a `system` "⚠️ Investigation interrupted — …" message and **closes the session** (`ended_at` set). Opening one now shows a warning banner explaining it was interrupted (and that the loop resumes the partial investigation on its next tick), instead of a bare seed prompt.
- The chat thread renders the new `interrupted` system row as a warning banner (the transcript loader keeps it alongside compaction-checkpoint + plan-proposed rows).

### Not in this release
- The chat sidebar is still dominated by autonomous-loop sessions (loop machinery floods the 500-row window). Hiding/grouping those + a source filter is the next change (the operator-experience pass).

### Files
- `bundles/spark/mcp/src/config/config.py`, `bundles/spark/mcp/src/usecase/job_scheduler.py`, `bundles/spark/mcp/tests/test_job_scheduler_interrupted.py`, `mcp/agent/lib/api/sessions.ts`, `mcp/agent/components/chat/message-list.tsx`, `mcp/agent/app/help/architecture/page.tsx` (`#jobs-subsystem`).

---

## [v0.2.38] (unreleased) — *API reference completed: 65 stub endpoints filled + 28 uncataloged endpoints added*

The in-product API reference (`/help/api`, the try-it-out tool, and the generated OpenAPI 3.0 spec) was ~62% complete — 65 entries carried the placeholder text *"Auto-added v0.7.1. Full request/response schema is a follow-up"* and ~28 real endpoints weren't listed at all. This release finishes the catalog: every entry's request body, query/path params, response shapes, and risk tier was reconciled against its actual Next.js route handler **and** the embedded-MCP handler it forwards to — no guessed schemas.

### What ships
- **65 stub descriptions replaced** with grounded documentation (sessions fork/messages/delete, skills CRUD, hooks CRUD, marketplace, plugins, tasks, bench, agent-definitions, operator-state, backup/restore, auth, providers, tool/call, openapi, and more) — full body schemas + realistic examples + the actual success/error status codes each handler emits.
- **28 uncataloged endpoints added**, including the entire **Investigation** surface (cases, issues, indicators with their `/events` and `/issues` sub-resources), `POST /api/agent/instances`, `GET/PUT /api/agent/providers/config`, `POST /api/chat/cli`, `GET /api/agent/connectors/{id}/tools`, and the global `POST /api/agent/knowledge/search`.
- **New "Investigation" API category** for the cases / issues / indicators endpoints — a first-class group on `/help/api` alongside Cognitive, Configuration, Operations, Observability, Identity, Workflows, and Self-Modification.
- **Bug fix:** the `providers/config` entry was cataloged as `POST` but the route exposes `GET` (read, secrets redacted) + `PUT` (write provider credentials). Corrected, and the PUT is now flagged credential-tier.
- **Risk tiers + redaction** are now accurate throughout: credential-bearing routes (instance create, provider config write, auth, backup/restore) are tagged `credential`; destructive deletes are tagged `destructive`.
- The architecture page `#rest-api` section now points to the comprehensive catalog (138 endpoints across 8 categories) and the `GET /api/agent/openapi` export.

### Known gap (tracked separately)
- The 5 `/detections` endpoints were **deliberately left as stubs**. The Detection Inventory backend (`detections.py`, `detection_inventory.py`) was removed in the v0.1.0 carve-out, but the UI page, sidebar entry, agent routes, and docs were left behind — so `/observability/detections` has 404'd since v0.1.0. Cataloging those endpoints (or deleting them) pre-judges a restore-vs-retire product decision, which ships as its own contained release.

### Files
- `mcp/agent/lib/api-catalog.ts` (the catalog + the new `investigation` category + `INVESTIGATION` array), `mcp/agent/app/help/architecture/page.tsx` (`#rest-api` note).

---

## [v0.2.37] (unreleased) — *Documentation reconciliation: architecture · user guide · journeys · API*

A dedicated docs catch-up: the in-product help surfaces had drifted behind ~10 releases of shipped features (v0.2.27–v0.2.36). This release reconciles all four the operator reviews — no behavior change, help-page content only.

### Architecture (the spec)
- **Restored the XSIAM connector section.** The page had *retired* XSIAM during the XSOAR pivot, but v0.2.27 brought it back as a live 54-tool connector (investigation + EDR response). New `#xsiam-connector` section (dispatch/container, tool families, Cortex public-API auth) + added to the render list.
- **Fixed false KB claims.** The bundle-layout said "No bundled KB ships today" (6 ship) and the pipeline lead-in said "four KBs" (it's six: soc-investigation, mitre-attack-{enterprise,ics,mobile}, mitre-atlas, soar-playbooks).
- **Added a `#xsoar-connector` refinements subsection** for the v0.2.31–v0.2.36 generation-specific behavior (indicator flat-body fix + compact scored output, evidence v6 POST vs v8 war-room-tag, playbook import Core-API path, list create-or-overwrite).

### User guide
- New "Evidence on XSOAR 6 vs 8" subsection (how save/search evidence differs by generation, in operator language).
- Corrected the connectors subsection ("the three connectors" → the xsoar/cortex-docs/web trio, XSIAM noted above; XSOAR tool count 21 → 23).

### Journeys
- Two new starter flows: `ops-create-xsoar-instance` (version-aware create form) and `ops-create-xsiam-instance` (the prerequisite the XSIAM hunt-and-respond journey assumed).

### API reference
- Fixed verifiably-wrong catalog entries: `instances/{id}/test` ("Create a new connector instance" → "Test connectivity"), `connectors/{id}/{action}` ("Create connectors" → enable/disable/probe), `GET instances/{id}` ("List" → "Get a single"), and a real `/api/chat` SSE body/response schema.
- **Known debt (tracked separately):** ~69 inherited "Auto-added" catalog entries still carry placeholder descriptions and ~90 endpoints aren't cataloged. Filling those is a dedicated pass — not faked here.

### Files
- `mcp/agent/app/help/architecture/page.tsx`, `mcp/agent/app/help/user/page.tsx`, `mcp/agent/lib/journeys.ts`, `mcp/agent/lib/api-catalog.ts`.

---

## [v0.2.36] (unreleased) — *Connector read-path output: xsiam compact + XSOAR v8 evidence read*

Closes the last two items from the post-arc gap sweep — both connector read-tool output correctness.

### What ships

- **XSIAM tools no longer dump the full raw API response.** All 44 XSIAM tool returns carried `raw_response: <entire PAPI response>` next to their projected fields — pure token bloat on every call. A repo-wide check confirmed **nothing** consumed it (not the agent, skills, UI, connector.yaml, or tests), so it's removed across the board; tools now return only their projected fields (`incidents`/`alerts`/`endpoints`/`action_id`/…). Extends the v0.2.34/35 compact-output discipline to xsiam.
- **`xsoar_search_evidence` now works on XSOAR 8.** Cortex 8's `/evidence/search` doesn't return tag-based evidence (documented in v0.2.35). On v8 the tool now reads the war room filtered to the `evidence` tag — the same entries `save_evidence` tags on v8 — and projects them into the same compact shape. **Verified live:** a tagged entry round-trips. Evidence is now listable on BOTH generations (v6 via `/evidence/search`, v8 via the war-room tag); returns carry `via` (`evidence-api` | `war-room-tag`).

### Operator impact

- No installer change (Scenario 1). The xsiam + xsoar connector images rebuild on this tag; guardian-updater pulls the new digests.
- Behavior change: xsiam tool results are smaller (no `raw_response`); v8 `search_evidence` now returns results where it previously returned empty.

### Files

- `bundles/spark/connectors/xsiam/src/connector.py` — dropped `raw_response` from all 44 tool returns.
- `bundles/spark/connectors/xsoar/src/connector.py` — `_summarize_evidence_entry`; `search_evidence` v8 war-room-tag branch; `save_evidence`/`search_evidence` docstrings.
- `bundles/spark/connectors/xsoar/connector.yaml` — search_evidence description.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — v8 evidence-read + entry-projector tests (83 pass); xsiam suite 12 pass.

### Not shipped here (verification outcome)

- The hooks gap from the same sweep was **verified, not a bug**: all current scheduled jobs are `prompt`-type → they route through `/api/chat` → PreToolUse/PostToolUse hooks fire (the autonomous investigation loop, 195 runs, included). `tool_call`-type jobs would bypass the TS-layer hooks, but none are registered (latent, cross-layer) — documented, no code change.

---

## [v0.2.35] (unreleased) — *XSOAR evidence flow: save works on v6 + compact search*

Closing the bug-family sibling from v0.2.34 (#49). Investigating it (a live in-container probe against the v6 + v8 tenants) uncovered that **`xsoar_save_evidence` was broken on XSOAR 6** — a bigger bug than the cosmetic one #49 originally tracked.

### What ships

- **`save_evidence` now works on XSOAR 6.** It used `/entry/tags` for both generations, but on v6 that returns `errOptimisticLock` on a fresh entry AND the tagged entry never round-trips into `/evidence/search`. Fix: v6 now uses the formal `POST /evidence` create endpoint — verified live (create → search returns it). XSOAR 8 keeps the tag path (its `/evidence` POST 303-redirects — not exposed on the public API).
- **`search_evidence` returns a compact summary** per item `{id, entry_id, incident_id, description, occurred, marked_by, marked_date, tags}` — grounded in a live v6 evidence object — instead of the raw verbose record. Mirrors the v0.2.34 indicator + incident summarizers.
- **Documented Cortex 8 limitation:** on v8, tag-based evidence is **not** returned by `/evidence/search` (a public-API constraint) — the entry is still marked on the case's Evidence board in the UI. The `save_evidence`/`search_evidence` docstrings + the connector card spell this out, so the agent doesn't treat an empty v8 result as a failure.

### Operator impact

- No installer change (Scenario 1). The connector image rebuilds on this tag; guardian-updater pulls the new digest.
- Behavior change: v6 evidence saves now actually land on the evidence board + appear in `search_evidence` (previously they silently failed).

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — generation-aware `save_evidence` (v6 `POST /evidence`, v8 tag); `_summarize_evidence`; `search_evidence` compact output; docstrings.
- `bundles/spark/connectors/xsoar/connector.yaml` — save/search_evidence descriptions.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — 4 new tests (v6 save path, v8 save path, compact search, empty store).

---

## [v0.2.34] (unreleased) — *XSOAR indicator search actually filters now (+ compact, scored results)*

Follow-up to v0.2.33. The v6 harness smoke showed the agent flailing on "how many IP indicators / top by reputation" — `search_indicators` → `!findIndicators` → docs → timeout. Investigating it (a deterministic in-container probe against the live v6 tenant) uncovered a **real, long-standing bug**: `xsoar_search_indicators` sent its query wrapped in a `{"filter": {...}}` envelope (copied from the `/incidents/search` pattern), but `/indicators/search` takes a **flat** body — so XSOAR **silently ignored the query, size, AND page** and returned the full 1.18M-indicator store at the default page size, unsorted and unscored. Every indicator query (`type:IP`, `reputation:Bad`, …) was a no-op; the agent flailed because the tool genuinely returned arbitrary junk.

### What ships

- **Request-shape fix (the real bug): `xsoar_search_indicators` now POSTs a flat `{query, size, page}` body.** Queries actually filter now — `type:IP` returns IPs, `reputation:Bad` / `verdict:Malicious` returns the score-3 indicators, `size` is honored. Verified live on v6 (probe: filter-nested returned 100 unscored Certificate IDs ignoring `size:5`; flat returned 5 score-3 IPs). The correct reputation field is `reputation:`/`verdict:` — there is no `score:N` query field.
- **Compact, scored output: `xsoar_search_indicators` returns a summary per indicator** — `{id, type, value, score (0-3), reputation (Unknown/Good/Suspicious/Bad), source, created, modified, investigation_ids, expiration_status}` — mirroring `xsoar_list_incidents`. Payloads shrink dramatically (no more `CustomFields`/`sortValues`/`comments` dumps); the score/reputation are surfaced directly.
- **Bug-family audit** across all xsoar tools (the v0.2.33 retrospective discipline): exactly three returned raw upstream objects. `search_indicators` is fixed here; `xsoar_get_incident` is intentionally a full record (its drill-in contract — `version` must survive for `update_incident`); `xsoar_search_evidence` is the same pattern and is tracked for a follow-up (issue #49) with an inline code comment.
- The `xsoar_platform_reference` skill now documents the correct query (`reputation:Bad`/`verdict:Malicious`, no `score:N`) + that `search_indicators` returns score/reputation directly.

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.
- The connector image rebuilds on this tag; guardian-updater pulls the new digest.
- **Behavior change:** any prior workflow that relied on `search_indicators` returning the whole store (because the filter was a no-op) will now get a correctly-filtered, smaller result. This is the intended fix.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — flat `/indicators/search` body (was `{"filter": {...}}`); `_DBOT_SCORE_LABELS`, `_first_source`, `_summarize_indicator`; updated docstring; inline deferral note at `search_evidence`.
- `bundles/spark/connectors/xsoar/connector.yaml` — search_indicators description notes the compact scored shape.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — 5 new tests incl. a flat-body regression guard (`"filter" not in body`).
- `bundles/spark/mcp/skills/foundation/xsoar_platform_reference.md` — correct reputation query + direct score/reputation surfacing.

---

## [v0.2.33] (unreleased) — *Sharper XSOAR investigations: platform reference skill + lighter read path*

A 20-prompt live smoke against the XSOAR **v6** tenant (chat agent, deployed dev install) passed broadly — instance routing, full incident lifecycle, commands/enrich/lists, memory, ATT&CK knowledge, skills, and jobs all work. It surfaced one reproducible defect class: the agent had no authoritative XSOAR **platform** reference, so it burned turns probing query-syntax variants and flailed to the open web on concept questions.

### What ships

- **New `xsoar_platform_reference` foundation skill.** The agent now has a single authoritative reference for the XSOAR platform itself: War Room / playground / indicator-store / Lists concepts, the `!command` catalog (with the `xsoar_*` tool that wraps each), and the **definitive incident + indicator query-syntax tables** — including the per-severity **count recipe** (read `total` per bucket, don't page-scan) and the v6-vs-v8 differences. Cross-linked from `xsoar_case_triage` + `xsoar_case_investigation`.
- **Lighter read-only path.** The `xsoar_case_investigation` workflow now scopes the request first: a pure read-only ask (list cases, show/summarize one, count by severity, read the War Room, look up a value) is answered from the read tools without spinning up a full local Guardian Issue/Case. The local Issue record becomes mandatory the moment you enrich, decide a verdict, document onto the case, or mutate it.

### Why (from the smoke)

- "List active incidents + severity breakdown" → the agent had the right per-bucket approach but fired `list_incidents` **14×** probing syntax variants (`severity:[1]` vs `severity:low` vs `severity:Low` vs `severity:1`).
- "What is the XSOAR War Room / what does `!Print` do?" → no concept reference existed, so the agent flailed across docs/knowledge, hit the wrong tenant, tried a web search, and timed out with no answer.
- "Summarize the highest-severity case" (read-only) → auto-created a full local Issue/Case for a request that only asked to read.

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.
- Skill content is image-baked and volume-seeded on boot — the new skill auto-appears on `/skills` after upgrade.

### Files

- `bundles/spark/mcp/skills/foundation/xsoar_platform_reference.md` — new skill.
- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md` — Step 0 scope gate + read-only carve-out in the description; platform-reference cross-link.
- `bundles/spark/mcp/skills/foundation/xsoar_case_triage.md` — syntax pointer + cross-link.
- `mcp/agent/app/skills/page.tsx` — new skill card.
- `mcp/agent/app/help/architecture/page.tsx`, `mcp/agent/app/help/user/page.tsx` — skill-catalogue + foundation-list updates.

---

## [v0.2.32] (unreleased) — *XSOAR v8 one-click playbook import via the Core REST API*

Importing a playbook into a **Cortex 8 (XSOAR v8)** tenant now works one-click when the Core REST API integration is installed — previously it always reported "import unavailable," because the connector only tried the v6 endpoint and never actually used the Core REST API integration it told you to enable.

### What ships

- **Cortex 8 playbook import works.** When the direct `POST /playbook/import` 405s (Cortex 8's public API doesn't expose it), the connector now imports through the **Core REST API integration** — `core-api-post` → `/playbook/save` (a JSON array of playbooks), run in the instance's playground. Verified live on a Cortex 8 tenant.
- **Requirements:** the Core REST API integration installed on the tenant **and** the instance's `playground_id` set (the v0.2.30 form field). Without either, you get a clear guided-manual message — no longer the misleading "enable the Core REST API integration" suggestion the connector couldn't act on.
- XSOAR 6 import is unchanged (direct multipart upload).

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.
- This completes the Playbook Builder's deploy + test-run loop on Cortex 8.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — `_import_via_core_api` fallback (parses YAML→dict, array-wraps, `core-api-post /playbook/save` via the playground); `import_playbook` calls it on 405.
- `bundles/spark/connectors/xsoar/{requirements.txt,Dockerfile}` — declare PyYAML (used to parse the playbook).
- `bundles/spark/connectors/xsoar/{connector.yaml,tests/test_connector.py}` — tool description + Core-API fallback tests.

---

## [v0.2.31] (unreleased) — *Fix: XSOAR list tools now actually create lists*

`set_list` and `append_to_list` reported success but didn't create a new XSOAR list — so the value silently went nowhere and a later `get_list` returned "not found." Fixed.

### What ships

- **`set_list` / `append_to_list` now create the list** if it doesn't exist (they use the XSOAR `!createList` create-or-overwrite command instead of `!setList`, which only *updates* an existing list).
- **List writes report real failures.** The connector previously returned `ok: true` even when the underlying command errored; it now inspects the command output and returns a clean `ok: false` with the error detail when a write fails.
- Found during the live XSOAR v6 smoke (on-prem tenant). Affected both v6 and v8 — not version-specific.

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — `set_list` + `append_to_list` use `!createList`; new `_command_reported_error()` surfaces failed writes.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — updated command assertions + a regression test for the silent-success path.

---

## [v0.2.30] (unreleased) — *Smarter XSOAR create form — Version first, version-aware fields*

The XSOAR instance-create form now leads with the **Version** dropdown, and the fields below adapt to it: **API key ID** appears only for **v8** (v6 uses the API key alone). The form also exposes the previously-missing **Playground / War Room ID** field — you need it to run commands.

### What ships

- **Version is the first field.** Pick v6 or v8 up front; the rest of the form follows.
- **`API key ID` is v8-only.** Selecting **v6** hides it (and doesn't require or submit it); selecting **v8** shows + requires it.
- **`Playground / War Room ID` field added.** It was missing from the form entirely — it's optional, but required to run `run_command` and the list tools (`get_list`/`set_list`/`append_to_list`) on **both** v6 and v8. The field help explains where to find it.
- Generic, reusable form mechanics: config fields now support an `order` (render position) and a `showWhen` (conditional visibility) hint — any connector can use them.

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.

### Files

- `mcp/agent/app/api/marketplace/connectors/route.ts` — reordered XSOAR fields; `order` + `showWhen` on the fields; added `playground_id`.
- `mcp/agent/app/connectors/page.tsx` — `ConfigParam` gains `order`/`showWhen`; `visibleConfig` sorts + conditionally filters; required-check + submit payload honor visibility; field descriptions render as help text.
- `mcp/agent/lib/api/marketplace.ts` — config type carries the new hints.
- User guide.

---

## [v0.2.29] (unreleased) — *Two tenants, one connector — multi-active instances + XSOAR v6/v8*

A connector can now run **multiple instances at the same time**, and the agent picks which one a tool acts on. First use: an **XSOAR 6** (on-prem) tenant and an **XSOAR 8** (cloud) tenant live simultaneously — ask the agent about a v6 case and it works the v6 tenant; ask about v8 and it targets v8.

### What ships

- **Multiple enabled instances per connector.** The old "one active instance per connector" limit is gone. Create as many as you need (distinct names); enable any number of them.
- **The agent selects the tenant via an `instance` argument.** When 2+ instances of a connector are enabled, every tool for that connector gains an `instance` parameter; the agent sets it from your request. If it's ambiguous, the tool returns an error listing the valid instances instead of silently hitting the wrong tenant. With a single instance, nothing changes — tools look and behave exactly as before.
- **Explicit XSOAR Version dropdown.** Creating an XSOAR instance now offers a **Version** dropdown (`v6` / `v8`) instead of inferring the generation from whether you filled in `api_id`. Existing instances keep working (the old inference is the fallback).
- **connector.yaml `enum` fields render as dropdowns** automatically now — no UI hardcoding required.
- The agent's guidance was updated so it knows to pass `instance` and infer the right tenant/version from your wording.

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.
- To run v6 + v8 together: create two XSOAR instances (e.g. `xsoar-v6`, `xsoar-v8`), pick the Version on each, enable both. Each gets its own connector container.

### Files

- `bundles/spark/mcp/src/usecase/instance_store.py` — lifted the one-enabled-per-connector guard (+ tests).
- `bundles/spark/mcp/src/usecase/connector_loader.py` — register a shared tool set per connector; add the `instance` selector + call-time routing only when 2+ enabled (single-instance byte-identical) (+ tests).
- `bundles/spark/mcp/src/api/instances.py` — enable/disable toggles a tool-catalog reload.
- `bundles/spark/connectors/xsoar/` — explicit `version` field + generation override (+ tests).
- `mcp/agent/app/api/marketplace/connectors/route.ts` — connector.yaml `enum` → dropdown.
- `mcp/agent/lib/system-prompt.ts` — multi-instance routing guidance.
- Architecture + user guide + journeys + connectors/CLAUDE.md.

---

## [v0.2.28] (unreleased) — *Connector instances start reliably + tell you what happened*

Creating a connector instance could "do nothing" — the dialog spun, then closed with no confirmation, and sometimes the connector's container never actually started and stayed down. This release makes instance creation self-healing and adds explicit feedback at every step.

### What ships

- **Create-instance feedback (`/connectors`).** The form now reports the outcome instead of silently closing: it closes and shows the new instance card on success, a **red banner** if the create itself fails (e.g. a duplicate name), and an **amber "still starting" notice** when the instance was created but its container needs a moment. The button reads **"Creating…"** while it works.
- **Containers self-heal.** guardian-updater now reconciles *missing* connector containers — not just stale ones — at boot and every ~5 minutes. If a container fails to start at create time (a transient docker/registry hiccup), it is started automatically within one reconcile interval instead of staying down until the next updater restart.
- **Hyphenated connector ids fixed.** Container-name parsing now round-trips ids that contain a hyphen (`cortex-docs`), so those containers are no longer dropped from the digests listing and digest-drift reconcile.
- The MCP create response now carries a structured `container_start` (`{started, container_url, error}`) so the UI can react precisely.

### Operator impact

- No installer change (Scenario 1). Re-run your existing installer; volumes preserved.
- Instances whose containers went missing recover automatically after upgrade — or immediately via `POST /api/v1/connectors/reconcile`.

### Files

- `updater/src/main.py` — boot + periodic missing-container reconcile; `_split_connector_container_name` longest-prefix parser; xsiam added to the connector roster.
- `updater/tests/test_periodic_reconcile.py`, `updater/tests/test_connector_name_parse.py` — coverage for the self-heal loop + the parser.
- `bundles/spark/mcp/src/api/instances.py` — `_updater_start` / `create_instance` return structured `container_start`.
- `mcp/agent/lib/api/marketplace.ts` — `CreateInstanceResponse` type.
- `mcp/agent/app/connectors/page.tsx` — create-outcome banners + Done button + "Creating…" state.
- `mcp/agent/app/help/architecture/page.tsx` — guardian-updater reconciliation section rewritten (missing-container self-heal + digest drift).
- `mcp/agent/app/help/user/page.tsx` — "What happens when you click Create" subsection.

---

## [v0.2.27] (unreleased) — *Cortex XSIAM connector — investigation + EDR response*

Guardian can now connect to a **Cortex XSIAM** tenant the same way it does Cortex XSOAR — create an instance, then investigate and respond from chat. Ported back from Phantom and adapted to Guardian, minus the simulation-only pieces.

### What ships

- **New `Cortex XSIAM` connector** in the marketplace (`/connectors`). Add an instance with your tenant API host + the Cortex public-API key pair (`api_id` → `x-xdr-auth-id`, `api_key` → `Authorization`); the connector appends `/public_api/v1`.
- **54 tools** across the investigate-to-respond lifecycle:
  - *Investigation:* XQL queries, incidents, alerts, issues, assets, audit logs, datamodel describe, parsers, broker, distributions, hash analytics, lookups.
  - *EDR response:* endpoint isolate / unisolate / scan / scan-all / quarantine-file / retrieve-file / set-alias, script run / snippet, IOC insert / disable / enable, hash blocklist, alert exclusions, create dataset.
- **Safety:** every write/response tool is approval-gated by the connector wrapper (same as XSOAR); the one destructive lookup mutation (`remove_lookup_data`) is denied outright in the manifest.
- Tools advertise to the agent only once you create an instance.

### What was dropped vs the Phantom connector

The synthetic webhook **log-injection** tool (`send_webhook_log`) and the **xql-examples RAG** tools (`find_xql_examples_rag` / `get_xql_examples` / `get_dataset_fields`) — both belonged to the Phantom *simulation* (the latter depended on the `xql-examples` KB Guardian removed in the XSOAR pivot). XQL syntax reference lives in the `cortex-docs` connector.

### Files

- `bundles/spark/connectors/xsiam/` — connector.yaml (54 tools) + src (PAPI client + connector.py) + Dockerfile + tests.
- `bundles/spark/manifest.yaml` — `toolConnectors[]` + `tools.allow: xsiam.*` / deny `xsiam.remove_lookup_data`.
- `mcp/agent/app/api/marketplace/connectors/route.ts` — marketplace card.
- `.github/workflows/build-connectors.yml` + `release.yml` — CI build/release for `guardian-connector-xsiam`.
- `mcp/agent/app/help/{architecture,user}/page.tsx`, `mcp/agent/lib/journeys.ts` — docs + a create-instance journey.

---

## [v0.2.26] (unreleased) — *Deploy + test-run playbooks — close the builder loop*

The Playbook Builder no longer stops at a draft. From `/playbooks/build` (or by asking the agent), Guardian can now **import** a drafted playbook into the connected Cortex XSOAR tenant, **run** it on a disposable test incident, show the **outcome**, and **close** the test incident — the operator's "build the playbook, then prove it works" loop.

### What ships

- **`Deploy + test-run` button** on the Playbook Builder, behind an explicit confirm (it writes to your tenant). It drives the agent through: validate → import → create a `[Guardian test]` incident → run → read the war room → close the incident → report. The agent can do the same conversationally.
- **New connector tool `xsoar_import_playbook`** — uploads the playbook definition to XSOAR. Approval-gated like every connector write; uses the instance's API key (never a stored credential).
- **Generation-aware.** Direct import works on XSOAR 6 (and on Cortex 8 with the Core REST API integration). On a Cortex 8 tenant without it, the public API doesn't expose playbook import — so Guardian returns clear **manual-import guidance** (Settings → Playbooks → Import) and still runs the automated test-run once the playbook exists. No silent failure.
- The `build_xsoar_playbook` skill gained the **Deploy + test-run lifecycle (D1–D7)**.

### Known limitation

One-click *auto-import* requires XSOAR 6 or the Core REST API integration on Cortex 8. On a plain Cortex 8 tenant the import step is guided-manual; the test-run automation is unaffected.

### Files

- `bundles/spark/connectors/xsoar/` — `import_playbook` tool + `post_multipart` client method + tests + connector v0.2.1.
- `bundles/spark/mcp/skills/workflows/build_xsoar_playbook.md` — Deploy + test-run lifecycle.
- `mcp/agent/app/playbooks/build/page.tsx` — Deploy + test-run button, confirm, result panel.
- `mcp/agent/app/help/{architecture,user}/page.tsx`, `mcp/agent/lib/journeys.ts` — docs + journey.

---

## [v0.2.25] (unreleased) — *Knowledge detail page + markdown rendering fidelity*

Three display-fidelity fixes surfaced during the v0.2.24 UI smoke. No KB regeneration, no storage change — purely how the existing content is fetched and rendered.

### What ships

- **Full entry count + browse on large KBs.** The KB detail page (`/knowledge/<name>`) now reads the true `total_count` the MCP already returns instead of the 500-row slice — so `mitre-attack-enterprise` reads **697 entries** (was "500") and `soar-playbooks` reads **798**. A **Load more** button pages through the rest. Search and tag/category filters already covered the full corpus.
- **MITRE code snippets render as code.** ATT&CK descriptions embed literal `<code>…</code>` / `<br>` HTML that showed as raw `<code>` text in the entry drawer. They now render as code spans/blocks (display-time transform — the stored content + its embedding are untouched).
- **Tables render as tables.** The shared markdown renderer (chat + KB drawer) now enables GitHub-flavored markdown, so the agent's comparison tables (e.g. `T1003.001` vs `T1003.002`) render as real tables instead of raw `|` pipes. Strikethrough + autolinks come along too.

### Files

- `mcp/agent/app/knowledge/[name]/page.tsx` — `total_count` wiring, Load-more pagination, `<code>`/`<br>` → markdown transform.
- `mcp/agent/components/markdown-content.tsx` — `remark-gfm` plugin (activates the existing table overrides).
- `mcp/agent/app/help/user/page.tsx` — note on browsing large KBs.

---

## [v0.2.24] (unreleased) — *Playbook Builder — draft Cortex XSOAR playbooks from examples*

The first *generative* use of the knowledge layer: a new **Playbook Builder** that drafts a Cortex XSOAR playbook from a plain-English use-case, grounded in the ~800 real playbooks in the `soar-playbooks` KB. The operator's flagged "the agent helps build playbooks" use case.

### What ships

- **`/playbooks/build` page** (sidebar → Command → Playbook Builder). Describe what the playbook should do (+ optional product/integration) → the agent drafts it → you get validated YAML with **Validate structure** + **Download .yml** and the example playbooks it grounded on.
- **`build_xsoar_playbook` skill** — the retrieval-augmented authoring lifecycle: `knowledge_search` `soar-playbooks` for the closest examples (their full `raw_yaml` is in the KB) → draft following those task-graph patterns → validate → present as a reviewable draft with citations.
- **`playbook_validate` MCP tool** + `POST /api/v1/playbooks/validate` (proxied at `/api/agent/playbooks/validate`) — deterministic structural check: required fields, `starttaskid` exists, every `nexttasks` reference resolves, reachability. Agent-safe (no secrets, no catalog mutation).
- The builder **never deploys to a tenant** — output is a draft to review + import (Playbooks → Import), tested in a playground first.

### Files

- `bundles/spark/mcp/src/usecase/builtin_components/playbook_tools.py` — `playbook_validate` + tests (8).
- `bundles/spark/mcp/src/api/playbooks.py`, `src/main.py`, `src/usecase/connector_loader.py` — REST route + registration.
- `bundles/spark/mcp/skills/workflows/build_xsoar_playbook.md` — the authoring skill.
- `mcp/agent/app/playbooks/build/page.tsx` + `app/api/agent/playbooks/validate/route.ts` + `components/sidebar.tsx` — UI page + proxy + nav.
- `mcp/agent/app/help/{architecture,user}/page.tsx`, `mcp/agent/lib/journeys.ts` — docs + `playbook-builder` journey.

---

## [v0.2.23] (unreleased) — *Keep specialist KBs out of IT investigations' passive context*

Tuning pass after the KB expansion. With six KBs and ~1,973 docs, the **passive** per-turn context injection (the `ContextAssembler` puts the top-K KB hits into every turn) started leaking specialist matrices into IT investigations — a measured IT-ransomware turn surfaced an ICS technique (`T0809`, OT) *above* the correct Enterprise `T1486`. The noise is mid-cosine (~0.6), so a score floor can't separate it.

### What ships

- Passive per-turn KB injection now **excludes the specialist ecosystems** (OT / Mobile / AI). Docs with no ecosystem (`soc-investigation`, `soar-playbooks`) and IT (`mitre-attack-enterprise`) stay in; `mitre-attack-ics` / `mitre-attack-mobile` / `mitre-atlas` are **active-pull only** — the agent still reaches them via `knowledge_search(kb_name=…)` when a case is OT/Mobile/AI (the investigation skill already scopes by KB).
- Overridable per deploy via **`manifest.context.passiveExcludeEcosystems`** (e.g. `[]` for an OT-first install).
- Verified on the real KBs: the IT queries that previously leaked ICS/Mobile/AI docs now return zero specialist hits; the active path still reaches ICS.

### Files

- `bundles/spark/mcp/src/usecase/context_assembler.py` — over-fetch + ecosystem filter on the passive KB injection; `kb_passive_exclude_ecosystems` param.
- `bundles/spark/mcp/src/main.py` — wire the `context.passiveExcludeEcosystems` manifest override.
- `bundles/spark/mcp/tests/test_context_assembler_kb_filter.py` — 2 tests.
- `mcp/agent/app/help/architecture/page.tsx` — "Passive vs active KB use" subsection.

---

## [v0.2.22] (unreleased) — *MITRE ATT&CK ICS + Mobile knowledge bases*

Rounds out the MITRE ATT&CK matrix family with the **ICS** (OT / Industrial Control Systems) and **Mobile** (Android/iOS) matrices, so Guardian can ground OT and mobile incidents the same way it does IT ones.

### What ships

- **`mitre-attack-ics` KB — 97 docs** (79 techniques + 18 sub) — the ATT&CK for ICS matrix (SCADA/PLC/HMI; ICS-only tactics like Inhibit Response Function, Impair Process Control).
- **`mitre-attack-mobile` KB — 124 docs** (77 techniques + 47 sub) — the ATT&CK for Mobile matrix (Android/iOS).
- Both from ATT&CK STIX v19.1 via the same `gen_mitre.py --domain ics|mobile` generator; embeddings pre-computed (boot with zero Vertex calls); MITRE attribution bundled.
- **Always loaded** alongside the other KBs (operator decision). An IT-only investigation scopes to `mitre-attack-enterprise` or filters by the `ecosystem` tag so OT/mobile techniques don't add noise.
- Also wired the **cross-KB search HTTP proxy** (`POST /api/agent/knowledge/search` → MCP `/api/v1/kbs/search`) so "search every loaded KB at once" is reachable over HTTP, mirroring the MCP surface (surfaced during the full-KB smoke).

### Files

- `bundles/spark/kbs/mitre-attack-ics/`, `bundles/spark/kbs/mitre-attack-mobile/` — new: `schema.json`, `README.md`, `NOTICE.txt`, `entries/*.md` (97 + 124 docs with baked embeddings).
- `bundles/spark/manifest.yaml` — `knowledge.bundled[]` declares both.
- `mcp/agent/app/help/{architecture,user}/page.tsx` — docs (six-KB family, ~1,973 docs).

---

## [v0.2.21] (unreleased) — *SOAR Playbooks knowledge base (~800 Cortex XSOAR playbooks)*

Guardian now has a knowledge base of **response playbooks**. ~800 Cortex XSOAR out-of-the-box playbooks from the MIT-licensed `demisto/content` repo are searchable by *what they do*, so the agent can find an existing playbook for a response — and, later, use them as worked examples for building playbooks.

### What ships (exactly the operator's design)

- **`soar-playbooks` KB — ~800 playbooks** across ~77 products, filtered to SOC-relevant pack categories (Endpoint, Network Security, Email, Forensics & Malware, Threat-Intel, Case Management, IAM, Vuln-Mgmt, Cloud Security, SIEM); deprecated playbooks skipped.
- **The embedded text is a reviewed DESCRIPTION** of each playbook (its purpose + inputs/outputs + the integrations it calls + product/use-case), so semantic search matches *intent*, not raw YAML. **The raw playbook YAML is KEPT** in each entry (`raw_yaml`), retrievable from the doc.
- **Dual-labeled** — AXIS A product/pack/support-tier (`product:crowdstrike`, `support:partner`), AXIS B investigation-type/use-case (`phishing`, `endpoint`, `threat-intel`). Both are filterable via the v0.2.20 tag chips.
- **MIT attribution** bundled (`NOTICE.txt`): playbook YAML © Palo Alto Networks / Demisto under the MIT License; product names nominative; no vendor binaries.
- Generated by `kbs/_tools/gen_soar_playbooks.py` from a blobless sparse clone of `demisto/content`; embeddings pre-computed (boots with zero Vertex calls). `xsoar_case_investigation` wired to search it in Step 6 (Resolve).

### Files

- `bundles/spark/kbs/soar-playbooks/` — new: `schema.json`, `README.md`, `NOTICE.txt`, `entries/*.json` (~800 docs with baked embeddings).
- `bundles/spark/kbs/_tools/gen_soar_playbooks.py` — content-repo → docs generator.
- `bundles/spark/manifest.yaml` — `knowledge.bundled[]` declares `soar-playbooks`.
- `mcp/agent/app/help/{architecture,user}/page.tsx`, `mcp/agent/lib/journeys.ts` — docs + `soar-playbooks-search` journey.

### Note

Descriptions are assembled deterministically from each playbook's own fields (faithful, no hallucination). An optional LLM-polish pass is a documented follow-up (`soar-playbooks/README.md`).

---

## [v0.2.20] (unreleased) — *Filter knowledge bases by tag (label faceting)*

KBs are now **filterable by any label**, not just `category`. Open a KB on `/knowledge` and click the **tag filter chips** — tactic, platform, product, investigation-type — to narrow the entries; both browse and semantic search respect the selection. This makes the big MITRE KBs navigable (e.g. show only Windows credential-access techniques) and is the substrate the SOAR-playbooks KB's dual-labels will use.

### What ships

- **`kb_doc_tags` index** — each doc's front-matter `tags` are normalized into a queryable table at upsert (re-synced on every load, so it backfills existing KBs). `list_docs` / `search` / `knowledge_search` accept a `tags[]` filter (AND semantics — a doc must carry every selected tag).
- **`GET /api/v1/kbs/{name}/tags`** — tag facets + per-tag counts, driving the UI chips.
- **`/knowledge/{name}` filter chips** — click tags to AND-filter the entries + search; "clear" resets. Chip cloud is server-side so it's complete on large KBs.
- **Search pagination** — `search` gained an `offset` for paging through results.
- The agent's `knowledge_search` tool gained a `tags` arg so it can scope a search by label (e.g. tactic).

### Files

- `bundles/spark/mcp/src/usecase/kb_store.py` — `kb_doc_tags` table + `_sync_tags`/`_tag_clause`/`kb_tags`; `tags`/`offset` on `list_docs`/`count_docs`/`search`.
- `bundles/spark/mcp/src/api/kb.py` — `tags` on docs+search routes; new `/tags` route.
- `bundles/spark/mcp/src/usecase/builtin_components/cognitive_tools.py` — `knowledge_search(tags=...)`.
- `mcp/agent/app/knowledge/[name]/page.tsx` + `app/api/agent/knowledge/[name]/tags/route.ts` — filter-chip UI + proxy.
- `bundles/spark/mcp/tests/test_kb_tags.py` — 7 tests (AND filter, backfill, retag, remove, pagination).

---

## [v0.2.19] (unreleased) — *MITRE ATLAS knowledge base (AI / ML security)*

Guardian can now ground investigations of **attacks on AI systems** — the bundle ships **MITRE ATLAS**, the ATT&CK-style framework for adversarial threats to AI/ML (prompt injection, model evasion, data poisoning, model theft, agent hijacking). Strategically apt: Guardian is itself an AI agent, and customers increasingly run AI/LLM workloads.

### What ships

- **`mitre-atlas` KB — 227 docs**: **170 techniques + sub-techniques** (`category: attack-technique`, e.g. `AML.T0051` LLM Prompt Injection) with description, tactics, mitigations, and the mapped ATT&CK Enterprise id where ATLAS declares one (cross-links into `mitre-attack-enterprise`); plus **57 real-world AI-incident case studies** (`category: case-study`, `AML.CS####`) — each a documented attack with its step-by-step procedure, target, and actor.
- **Generated deterministically** by `kbs/_tools/gen_atlas.py` from the official ATLAS data (v5.6.0); `framework_version` pins the source. **Embeddings baked into the bundle** (v0.2.17 keystone) → boots with zero Vertex calls.
- Third bundled KB alongside `soc-investigation` (curated narrative) and `mitre-attack-enterprise` (full IT matrix) — together ~954 docs of reference the agent searches to ground investigations.

### Files

- `bundles/spark/kbs/mitre-atlas/` — new: `schema.json`, `README.md`, `NOTICE.txt`, `entries/*.md` (227 docs with baked embeddings).
- `bundles/spark/kbs/_tools/gen_atlas.py` — ATLAS YAML→docs generator.
- `bundles/spark/manifest.yaml` — `knowledge.bundled[]` declares `mitre-atlas`.
- `mcp/agent/app/help/{architecture,user}/page.tsx`, `mcp/agent/lib/journeys.ts` — docs + `atlas-ai-search` journey.

### Note

Ships under the same customer release tag as v0.2.17 + v0.2.18 (the MITRE-KB family + keystone), unless tagged separately.

---

## [v0.2.18] (unreleased) — *MITRE ATT&CK Enterprise knowledge base (full matrix, ~697 techniques)*

The complete MITRE ATT&CK **Enterprise** matrix now ships as a bundled knowledge base — every technique and sub-technique, semantically searchable, so the agent grounds investigations in the authoritative technique definition (and customers see it populated on `/knowledge`).

### What ships

- **`mitre-attack-enterprise` KB — ~697 docs** (222 techniques + 475 sub-techniques), one per ATT&CK id. Each doc carries the technique's **description, tactics, platforms, detection analytics + log sources, and mitigations**, machine-extracted from the official ATT&CK STIX bundle (framework v19.1).
- **Generated deterministically** by `kbs/_tools/gen_mitre.py` (walks the v19 Detection-Strategy → Analytic → data-component graph for detection, since `x_mitre_detection` was removed). Never hand-edited — regenerates faithfully on each MITRE release; `framework_version` pins the source.
- **Embeddings pre-computed and baked into the bundle** (the v0.2.17 keystone + `kbs/_tools/kb_embed.py`), so all 697 docs load with **zero Vertex calls** at boot — no multi-minute first-boot indexing.
- **Investigation skill wired** — `xsoar_case_investigation` now searches `mitre-attack-enterprise` for the authoritative technique id + detection + mitigations (and `soc-investigation` for the curated "how to investigate well" guide), and prefers the Enterprise KB for MITRE technique-id tagging.
- **Complements, not replaces, `soc-investigation`**: that KB is hand-written narrative tradecraft; this is exhaustive reference. The small technique-id overlap is intentional.
- **MITRE attribution** bundled (`NOTICE.txt`): ATT&CK® © The MITRE Corporation, reproduced under the ATT&CK Terms of Use; Guardian is not endorsed or certified by MITRE.

### Files

- `bundles/spark/kbs/mitre-attack-enterprise/` — new: `schema.json`, `README.md`, `NOTICE.txt`, `entries/*.md` (697 docs with baked embeddings).
- `bundles/spark/kbs/_tools/gen_mitre.py` — STIX→docs generator.
- `bundles/spark/manifest.yaml` — `knowledge.bundled[]` declares `mitre-attack-enterprise`.
- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md` — both KBs wired into Step 3 + Step 5.
- `mcp/agent/app/help/{architecture,user}/page.tsx`, `mcp/agent/lib/journeys.ts` — docs + `mitre-enterprise-search` journey.

### Note

Ships together with the **v0.2.17 keystone** (pre-computed embeddings) under one customer release tag — the keystone has no standalone customer-visible change; this KB is where its benefit (fast install of a large corpus) is first realized.

---

## [v0.2.17] (unreleased) — *Knowledge bases can ship embeddings baked in (large-KB keystone)*

Infrastructure release — the keystone for the knowledge-base expansion arc (full MITRE ATT&CK, ATLAS, SOAR playbooks). No new corpus; no operator-visible UI change beyond **much faster installs** once large KBs land.

### Why

Today the boot loader embeds every KB doc one-by-one against Vertex (~200ms each, no batch API). The hand-written `soc-investigation` KB is 30 docs (fine), but full ATT&CK Enterprise alone is ~691 docs and the whole arc is ~5k — that's **16+ minutes on a fresh-volume install, plus a Vertex bill every time**. This release lets a KB ship its embeddings **baked into the bundle** so a pre-computed KB boots with **zero Vertex calls**.

### What ships

- **Pre-computed embedding support** — a doc may carry `embedding` (base64 little-endian float32) + `embedding_model` in its front-matter/JSON. `kb_loader` decodes it and `kb_store.upsert` trusts it **only when** the model matches the runtime embedder's `model_id` and the length matches `dims`; any mismatch logs a warning and falls back to a live embed (a stale bake is self-healing, never silently wrong).
- **`kbs/_tools/kb_embed.py`** — authoring tool that bakes embeddings into a KB dir (`--embedder stub` for CI/tests, `--embedder vertex --sa-json … --project …` for the real bake). Reuses the loader's parsing so the embedded content is byte-for-byte what the loader stores.
- **Embedder `model_id`** — the `Embedder` protocol, `TextHashEmbedder`, and `VertexEmbedder` now expose a stable `model_id` so a baked vector's provenance can be verified before it's trusted.

### Files

- `bundles/spark/mcp/src/usecase/kb_store.py` — `upsert(precomputed_embedding=, precomputed_model=)` + `_resolve_embedding` trust logic.
- `bundles/spark/mcp/src/usecase/kb_loader.py` — `_extract_precomputed_embedding` (decode + pop) wired into the ingest loop.
- `bundles/spark/mcp/src/usecase/{memory_store,vertex_embedder}.py` — `model_id` on the protocol + both embedders.
- `bundles/spark/kbs/_tools/kb_embed.py` — new authoring tool.
- `bundles/spark/mcp/tests/test_kb_precomputed_embeddings.py` — 9 tests (trust logic, loader decode, full author→load round-trip with zero embed calls).
- `mcp/agent/app/help/architecture/page.tsx` — Knowledge Pipeline → "Pre-computed embeddings" subsection.

---

## [v0.2.16] (unreleased) — *SOC Investigation knowledge base (Vertex-embedded vector search)*

Guardian's knowledge subsystem was fully built but shipped **empty** — the `/knowledge` page had nothing to show. v0.2.16 ships the first bundled knowledge base, **`soc-investigation`**, and wires it into the investigation workflow so the agent grounds every case in curated tradecraft instead of recalling from memory.

### What this is — and how it differs from memory

**Knowledge** is *curated reference material* — how to investigate an attack technique, what a response playbook looks like — authored in the bundle, version-controlled, indexed at boot, and **read-only** at the agent surface. **Memory** is the agent's *accumulated, mutable org facts* (crown-jewel hosts, prior-incident outcomes) it writes as it works. Same Vertex embedder (`text-embedding-004`, 768-dim), deliberately opposite write paths: the agent **reads** knowledge to know the method; it **writes** memory to remember this environment.

### What ships

- **30-doc curated corpus** at `bundles/spark/kbs/soc-investigation/entries/`:
  - **20 MITRE ATT&CK technique investigation guides** (`category: attack-technique`, id = the ATT&CK id, e.g. `T1071.004` DNS C2, `T1486` ransomware, `T1558.003` Kerberoasting). Each gives how the technique manifests in telemetry, the ordered investigation steps, the data sources to pull, and pivot/related techniques.
  - **10 IR playbooks** (`category: playbook`, id = `pb-<slug>`, e.g. `pb-phishing`, `pb-ransomware`, `pb-lateral-movement`). Each gives triage, blast-radius scoping, containment, evidence to collect, and TRUE/FALSE-positive verdict criteria.
- **Manifest declaration** — `knowledge.bundled[]` now declares `soc-investigation` with its schema, so `kb_loader` embeds + indexes all 30 docs into `kb.db` at boot via the same Vertex embedder memory uses.
- **Investigation skill wiring** — `xsoar_case_investigation` now calls `knowledge_search` as its **first research step** on every case (`category=attack-technique` by observed behavior, `category=playbook` by case kind), uses the doc's manifestation signals + ordered steps to drive the investigation, cites the matching doc id in the case Issue, and prefers the KB for MITRE technique-id tagging.
- **Already-present surfaces now light up** — the `/knowledge` browser, `/knowledge/soc-investigation` detail page, semantic-search box, and `knowledge_search` / `knowledge_list` agent tools were all built earlier and were waiting for a corpus. They now render 30 entries and return semantically-ranked results.

### Files

- `bundles/spark/kbs/soc-investigation/` — new: `schema.json`, `README.md`, `entries/*.md` (30 docs).
- `bundles/spark/manifest.yaml` — `knowledge.bundled[]` declares `soc-investigation`.
- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md` — KB-grounding as Step 3's first move; KB-first MITRE tagging in Step 5; `knowledge_search`/`knowledge_list` in the research-connectors list.
- `mcp/agent/app/help/architecture/page.tsx` — Knowledge Pipeline section: shipped-corpus layout + *"Knowledge vs memory — the boundary"* subsection.
- `mcp/agent/app/help/user/page.tsx` — `#knowledge`: *"Bundled KB — SOC Investigation"* subsection + KB-first research flow.
- `mcp/agent/lib/journeys.ts` — `knowledge-browse` journey now walks the concrete 30-doc corpus with semantic-search assertions.

---

## [v0.2.15] (unreleased) — *Harness documentation sync (post-campaign)*

Documentation pass after a 20-incident end-to-end harness smoke campaign that validated the whole stack (investigations, hooks, subagents, skills, jobs, memory, observability) and shipped v0.2.10–v0.2.14. Brings the canonical docs up to date with the current harness.

### What ships

- **Architecture page** — new *"Autonomous investigation loop (seeder → loop → judge)"* subsection documenting the three scheduler jobs (codified in `scripts/bootstrap_loop_jobs.sh`), the structural `issues_list` Issue-pick, the judge's bounded self-improvement with `.history` rollback + `skill_updated` audit, and the v0.2.14 subagent tool-result truncation. Added `xsoar_list_integrations` as the *Discover* step in the XSOAR tool-family.
- **User guide** — new *"Autonomous investigation loop (demo harness)"* subsection under Jobs, explaining the three jobs + how to review/roll back autonomous skill edits via `/observability/events`.

### Files

- `mcp/agent/app/help/architecture/page.tsx`, `mcp/agent/app/help/user/page.tsx`, `CHANGELOG.md`, `lib/release-notes.ts`. (Finer API-catalog entries for the Investigation REST surface tracked as a follow-up.)

### Change scenario

**Scenario 1** — docs-only (agent image help pages); volumes preserved. Patch bump (v0.2.15).

---

## [v0.2.14] (unreleased) — *Subagent investigations scale on busy tenants (tool-result truncation)*

Found by the 20-incident harness smoke campaign: broad **subagent** hunts (e.g. a threat-hunter scoping blast radius) on a busy XSOAR tenant failed with the Vertex 1M-token error — a single broad XSOAR read returned a payload large enough to blow the subagent's context window. The main agent already truncated tool results; subagents didn't.

### What ships

- **Subagent tool results are now truncated** with the same `applyTruncation` policy the main agent uses (default 16 KB head+tail+marker, operator-tunable via `EVIDENCE_TRUNCATION_*`). One oversized tool result can no longer blow a subagent's context — so threat-hunter blast-radius hunts and other subagent investigations complete on busy tenants instead of failing on overflow.

### Files

- `mcp/agent/app/api/chat/route.ts` (`runSubagent` tool loop now applies `applyTruncation` to `resultText`). Docs: `CHANGELOG.md`, `lib/release-notes.ts`. See [#28](https://github.com/kite-production/guardian/issues/28).

### Change scenario

**Scenario 1** — code-only (agent image); volumes preserved. Patch bump (v0.2.14).

---

## [v0.2.13] (unreleased) — *Discover configured SOAR integrations + their commands*

Guardian can now **see what's actually wired up in Cortex XSOAR** before it acts. The agent already had `xsoar_run_command` (run any `!command`) but no way to know which integrations are configured or which commands they expose — so it had to guess. A new `xsoar_list_integrations` tool answers exactly that.

### What ships

- **`xsoar_list_integrations`** (xsoar connector) — lists the integration instances configured on the tenant and, for each, the commands it exposes. One call to `POST /settings/integration/search` joins the configured instances to their integration definitions' command catalog (`integrationScript.commands[]`). No `playground_id` needed.
  - `brand="virustotal"` focuses one integration and returns each command's **arguments** (name / required / description) so the agent can build the exact `!command arg=value` string for `xsoar_run_command`.
  - `enabled_only` (default true — only runnable instances), `include_commands` (default true), `command_detail` (default false; on when `brand` is set), `size`.
  - Returns `{ ok, integrations: [{ brand, instance_name, enabled, category, command_count, commands: [{name, description, arguments?}] }], total }`.
- **The discovery → run pattern**: the agent calls `xsoar_list_integrations` to learn `{integration → commands}`, then `xsoar_run_command` with a command it now *knows* exists — no more guessing at the SOAR's command surface.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` (`xsoar_list_integrations` + `__all__`), `bundles/spark/connectors/xsoar/connector.yaml` (`spec.tools[]`), `bundles/spark/connectors/xsoar/tests/test_connector.py` (4 tests). Docs: `app/help/user/page.tsx`, `CHANGELOG.md`, `lib/release-notes.ts`. See [#27](https://github.com/kite-production/guardian/issues/27).

### Change scenario

**Scenario 1** — code-only (xsoar connector image rebuilds; new digest); storage unchanged; volumes preserved. Patch bump (v0.2.13).

---

## [v0.2.12] (unreleased) — *Autonomous investigation self-improvement (evaluate→enhance)*

Closes the autonomous investigation loop's final phase: it now **evaluates its own work and improves the investigation skill** without a human in the path. A new `guardian-investigation-judge` job scores recent resolved investigations against a SOC rubric and, on a systematic weakness, edits the `xsoar_case_investigation` skill via `skills_update`. Because that's autonomous self-modification, every skill edit is now **reversible and audited**.

### What ships

- **Skill edits are now audited + versioned** (the safety substrate, applies to ALL skill edits — operator and agent): `skills_update` writes a timestamped snapshot of the prior content under `skills/.history/` (multi-generation rollback, on top of the existing single-level `.md.bak`) and records a `skill_updated` audit event (file path, bytes before/after, backup location) visible at `/observability/events`. The actor distinguishes operator vs agent edits, so an autonomous self-edit is plainly attributable. The `.history` snapshots never appear in the skills listing.
- **`guardian-investigation-judge`** (dev/demo harness, codified in `scripts/bootstrap_loop_jobs.sh`): every 6h it rubric-scores the 5 most-recent resolved investigations (VERDICT / MITRE / blast-radius / recommendations) and, only on a systematic weakness (≥3 of 5 score ≤1), makes ONE bounded, additive edit to the investigation skill. Tightly whitelisted (reads Issues/Cases/indicators + `skills_read`/`skills_update` only — no incident, credential, or skill-create/delete access). The bounded-edit contract (preserve the 6-step lifecycle, additive-only, ≤~25 lines, one edit/run) plus audit + `.history` make a bad self-edit catchable and revertible.

### Files

- `bundles/spark/mcp/src/usecase/builtin_components/skills_crud.py` (`update_skill` history + audit; `.history` excluded from listings), `bundles/spark/mcp/tests/test_skills_crud_history.py` (new), `scripts/bootstrap_loop_jobs.sh` (the judge job), `scripts/CLAUDE.md`. Docs: `app/help/architecture/page.tsx` (self-improvement loop + rollback), `CHANGELOG.md`, `lib/release-notes.ts`. See [#26](https://github.com/kite-production/guardian/issues/26).

### Change scenario

**Scenario 1** — code-only (agent image); no schema change (`.history` is a new on-disk dir under the skills volume, additive); volumes preserved. Patch bump (v0.2.12).

---

## [v0.2.11] (unreleased) — *Investigation loop hardening + codification*

Hardens the autonomous investigation loop (the demo/training harness that seeds synthetic XSOAR incidents and investigates them) and makes it reproducible. The loop's "take the oldest open Issue that tracks an incident" pick was previously a prose instruction the model had to follow correctly — a sourceless/manual Issue could jam it. That pick is now **structural**, and the two scheduler jobs that drive the loop are now **codified in git** instead of living only in the deployed install's `jobs.db`.

### What ships

- **`issues_list` gains two structural filters** (also on `GET /api/v1/issues`): `source_ref_not_null` (return only Issues that track an XSOAR incident — skip manual/standalone ones) and `order` (`asc` = oldest-first; `desc` default = unchanged). The loop now calls `issues_list(status='open', source_ref_not_null=True, order='asc')` and takes `issues[0]` — deterministic, no longer dependent on the model skipping sourceless Issues by hand. Operators filtering the Issues list benefit too.
- **`scripts/bootstrap_loop_jobs.sh`** — the canonical, version-controlled definition of the `guardian-incident-seeder` + `guardian-investigation-loop` jobs. Idempotent upsert via the agent jobs API; re-run to (re)provision the loop after a fresh install / volume wipe. Previously these jobs existed only at runtime and were lost on a `WIPE_VOLUMES=true` reinstall.
- **Loop prompt now groups campaigns into Cases** — the codified investigation-loop prompt instructs grouping a related incident under an existing Case (or opening one) as part of each tick, closing the "group into Cases" step.

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (`list_issues` filters), `bundles/spark/mcp/src/usecase/builtin_components/investigation_tools.py` (`issues_list` tool args + docstring), `bundles/spark/mcp/src/api/investigation.py` (`GET /api/v1/issues` query params), `bundles/spark/mcp/tests/test_investigation_tools.py` (regression test), `scripts/bootstrap_loop_jobs.sh` (new), `scripts/CLAUDE.md` (catalogue). Docs: `CHANGELOG.md`, `lib/release-notes.ts`. See [#25](https://github.com/kite-production/guardian/issues/25).

### Change scenario

**Scenario 1** — code-only (agent image); `investigations.db` schema unchanged (new params are query-only, backward-compatible); volumes preserved. Patch bump (v0.2.11).

---

## [v0.2.10] (unreleased) — *Connector instance config edits take effect immediately*

Editing a connector instance's config or secrets (e.g. the XSOAR `playground_id`, a base URL, or an API key) now takes effect within seconds — no manual container restart. Previously the edit was written to the store but the running connector container kept serving the old values until it was restarted by hand, because a per-instance connector container reads its config **once at boot** (into an in-memory ContextVar; there is no in-process reload by design). The fix makes `PATCH /api/v1/instances/<id>` recreate the connector container on a config/secret change — the same path the create flow already used.

### What ships

- **Config/secret edits auto-propagate** — saving the instance form on `/connectors/[id]` recreates the connector container (idempotent: the old one is removed first), so the new values are live within seconds. The PATCH response now echoes `container_restarted` so the UI can reflect "reconfiguring…".
- **Gated correctly** — the recreate fires only when a `config` or `secrets` field actually changed, the instance is **enabled** (a disabled instance has no running container — it picks up the edit when next enabled), and the connector is container-style. Renames / enable-toggles / tool-disables don't trigger an unnecessary restart.
- **Non-fatal on failure** — the row is updated regardless; the operator can still retry the start manually. Matches the create path's behavior.

### Files

- `bundles/spark/mcp/src/api/instances.py` (`patch_instance` now calls the existing `_updater_start` helper on config/secret change). Docs: `app/help/architecture/page.tsx#setup-wiring` (spec corrected — it claimed edits "take effect at the next tool call"; they now genuinely do, via auto-recreate), `CHANGELOG.md`, `lib/release-notes.ts`. See [#24](https://github.com/kite-production/guardian/issues/24).

### Change scenario

**Scenario 1** — code-only (agent image); `instances.db` schema unchanged; volumes preserved. Patch bump (v0.2.10).

---

## [v0.2.9] (unreleased) — *Hook & policy tool-globs now match connector tools reliably*

A correctness + safety fix. Hook tool-globs, job permission policies, and subagent allow/deny scopes matched tool names with an exact pattern — so a rule written as `xsoar_close_incident` silently failed to match the same tool when the model invoked it in its dotted connector form `xsoar.close_incident`. Different Gemini variants emit one form or the other, so the failure was intermittent and hard to spot. The result: the **"Block close without verdict" hook never fired** on a real close, job `denied_tools` rules could be bypassed, and a deny-scoped subagent could still reach a connector tool. Matching is now separator-insensitive (`.` and `_` treated as the same), so a rule authored either way matches a call emitted either way.

### What ships

- **Verdict-gate hook now actually blocks** — closing an XSOAR incident whose Guardian Issue has no recorded `VERDICT:` line is denied, with a `hook_dispatched` audit row, regardless of which name form the model used.
- **Job permission policies** (`denied_tools` / `require_approval` / `allowed_tools`) now match connector tools by either name form — a `denied_tools` of `xsoar_close_incident` blocks `xsoar.close_incident` too.
- **Subagent tool scoping** — a subagent's deny glob now reliably blocks connector tools it shouldn't reach (a real privilege-scoping gap is closed).
- One matcher behind all three: a new dependency-free `lib/tool-name-glob.ts`. The previously-duplicated matcher in `lib/permission-policy.ts` is removed (so was the duplicated bug).
- Tool globs in the `/settings/hooks`, `/jobs` policy editor, and `/agents` scope fields are now **separator-insensitive** — author with either `.` or `_`.

### Files

- `mcp/agent/lib/tool-name-glob.ts` (new — the shared matcher), `mcp/agent/lib/hooks.ts` (`globMatch` delegates), `mcp/agent/lib/permission-policy.ts` (`matchesGlobList` delegates; dup removed), `mcp/agent/lib/hook-runner.ts` + `mcp/agent/app/api/chat/route.ts` (temporary diagnostic removed). Docs: `CHANGELOG.md`, `lib/release-notes.ts`, `app/help/user/page.tsx`. See [#23](https://github.com/kite-production/guardian/issues/23).

### Change scenario

**Scenario 1** — code-only (agent image); stable data contract; volumes preserved. Patch bump (v0.2.9).

---

## [v0.2.8] (unreleased) — *Tasks page — framing + modernization*

The `/tasks` page gets a clear use-case framing and the same polished glass/Material-3 treatment as the hooks, agents, and investigation pages. Pure UI; the task store + API are unchanged.

### What ships

- **Use-case framing** — a one-line description names what tasks *are*: long-running background work Guardian spawns (enrichment sweeps, context compactions, subagent hunts, hook runs) kicked off by you or the agent — watch progress, abort what's stale, review results. (Distinct from Issues = findings and Jobs = scheduled/recurring.)
- **Summary cards** — total · running · succeeded · failed.
- **Restyled status filter** (All · Active · Succeeded · Failed · Aborted) + an N-of-M count.
- **Slimmer task rows** — title + status `Badge` + kind `Badge`, the progress bar / label / elapsed / abort button retained, and the expand panel (timestamps · id · output · metadata) kept. Tasks stay grouped by kind.
- Shared glass empty-state.

### Files

- `mcp/agent/app/tasks/page.tsx` (reuses `components/investigation/ui.tsx` primitives). Docs: `CHANGELOG.md`, `lib/release-notes.ts`. See [#22](https://github.com/kite-production/guardian/issues/22).

### Change scenario

**Scenario 1** — code-only (agent image); stable data contract; volumes preserved. Patch bump (v0.2.8).

---

## [v0.2.7] (unreleased) — *Agents (subagents) CRUD modernization*

The `/agents` page — where subagent definitions (system prompt + scoped tool catalog) are managed — gets the same polished glass/Material-3 treatment as the hooks + investigation pages. Pure UI; no change to the agent-definition store, the dispatch path, or the API.

### What ships

- **Summary cards** — total agents · enabled · operator-defined · plugin/built-in.
- **Filter bar** — origin chips (All · Operator · Plugin · Built-in) + a name/description filter with an "N of M" count.
- **Slimmer agent rows** — lead with badges (origin · model · ≤N turns) and a muted tool-scope line; the "no allowlist → sees ALL tools" warning is preserved as an inline hint.
- **Wider, tabbed editor drawer** (~50% of page, was a narrow `max-w-2xl`) — fields grouped into tabs: **Definition** (name · description · system prompt), **Tools** (allowed/denied globs + the all-tools warning), **Execution** (max turns · isolation · model override). Validation jumps to the offending field's tab; the plugin-origin warning is preserved.
- Shared glass empty-state with a "New agent" CTA.

### Files

- `mcp/agent/app/agents/page.tsx` (reuses `components/investigation/ui.tsx` primitives). Docs: `app/help/user/page.tsx`, `CHANGELOG.md`, `lib/release-notes.ts`. See [#21](https://github.com/kite-production/guardian/issues/21).

### Change scenario

**Scenario 1** — code-only (agent image); stable data contract; volumes preserved. Patch bump (v0.2.7).

---

## [v0.2.6] (unreleased) — *Post-v0.2.5 fixes: /jobs auth, chat-session viewer, hooks UI*

Fixes for issues found right after v0.2.5 shipped.

### What ships

- **`/jobs` page loads again.** The Jobs page (and the job-detail page) are server components that authenticated their internal data fetch by reading a **stale `spark-token` cookie** — a leftover from the pre-Guardian baseline that was never re-pointed during the v0.4.0 auth rename to `guardian_session`. They now read `guardian_session` and forward it as a **Cookie header** (the middleware validates the session cookie; it does not accept the session token as a bearer). The same dead literal was fixed in two siblings: the unused `lib/auth/cookie-config.ts` export and the **Verify-pipeline** server action on the observability page (which was silently unauthenticated).
- **Chat sessions from scheduled jobs render their request + response.** A job binds a skill by prepending the entire skill markdown to the prompt; the chat viewer rendered that verbatim, so a job session looked like "just the skill name" with the real request and the response buried far below the fold. The user bubble now **collapses the `<skill>…</skill>` wrapper into a "Skill: \<name\>" chip + expander** and shows the operator's actual request inline. Fixes already-recorded sessions too.
- **Hooks page polish.** The create/edit drawer is widened to ~50% of the page (was too narrow at `max-w-xl`); the title description renders as a compact one-line subtitle.

### Files

- `mcp/agent/lib/auth.ts` (`getToken` → `guardian_session` + new `getSessionFetchHeaders`), `app/jobs/page.tsx`, `app/jobs/[id]/page.tsx`, `lib/auth/cookie-config.ts`, `app/observability/pipeline/actions.ts`, `components/chat/message-list.tsx` (skill-wrapper collapse), `app/settings/hooks/page.tsx` (drawer width + description). See [#20](https://github.com/kite-production/guardian/issues/20).

### Change scenario

**Scenario 1** — code-only (agent image); no storage change; volumes preserved. Patch bump (v0.2.6).

---

## [v0.2.5] (unreleased) — *Two incident-response hooks (built-in)*

Two Guardian-specific policy hooks ship as **built-ins** — in-process, agent-image, no subprocess and no host scripts. Install either from `/settings/hooks` with a dropdown pick + the tool glob; no code, no installer change.

### What ships

- **Block close without verdict** (`block-close-without-verdict`, PreToolUse) — denies `xsoar_close_incident` when the local Guardian Issue tracking that incident has no recorded `VERDICT:` line. Enforces a documented disposition before any incident is closed — the single most damaging analyst mistake is closing with no recorded verdict. Reads only investigation metadata (`GET /api/v1/issues`); never a secret. Conservative by default (untracked incidents pass); a `block_if_untracked` toggle makes it strict. Pair with `failurePolicy: block` (fail-closed) + tool glob `xsoar_close_incident`.
- **Flag malicious indicator** (`flag-malicious-indicator`, PostToolUse) — scans an `xsoar_enrich_indicator` result for a DBotScore at/above the malicious threshold (3) and injects a confirmed-bad flag into the agent's next turn, nudging it to record the IOC + recommend containment. Inspect-only (reads the result already in the payload, no external call). Pair with `failurePolicy: warn` + tool glob `xsoar_enrich_indicator`.

Both are on the catalog/workflow side of the credential guardrail — they read investigation metadata or inspect a tool result, and never read, write, or emit a SecretStore value. Builtins run in-process (no arbitrary command execution), the safest of the hook transports.

### Files

- `mcp/agent/lib/hook-builtins/block-close-without-verdict.ts` + `flag-malicious-indicator.ts` + `index.ts` (registry). They auto-appear in the `/settings/hooks` built-in dropdown via `/api/agent/hooks/builtins`. Docs: `app/help/user/page.tsx#hooks-ux`, `CHANGELOG.md`, `lib/release-notes.ts`. See [#19](https://github.com/kite-production/guardian/issues/19).

### Change scenario

**Scenario 1** — code-only (agent image); no storage/installer change; volumes preserved. Patch bump (v0.2.5).

---

## [v0.2.4] (unreleased) — *Hooks page modernization*

The `/settings/hooks` CRUD views get the same polished, glass, Material-3 treatment as the Investigation pages. Pure UI — no change to the hook engine, transports, events, or the stored hook shape.

### What ships

- **Summary cards** — the page opens with four stat cards: total hooks · enabled · disabled · fail-closed (computed from the existing hook list, no new fetch).
- **Filter bar** — event-group chips (Tool · Prompt · Compaction · Run · Subagent · Other) + a name filter over the in-memory list, with an "N of M" count.
- **Slimmer hook rows** — each row now leads with three at-a-glance badges (event · transport · fail-closed), demoting the tool glob / trigger / priority to a muted second line; shared glass styling.
- **Tabbed editor drawer** — the create/edit drawer is now a glass panel with its fields grouped into tabs (Metadata · Matching · Transport · Execution), so a hook is configured one concern at a time instead of one long column. Validation jumps to the tab holding the offending field.
- **Shared empty state** — the "no hooks" view uses the standard glass empty-state with an "Add your first hook" CTA.
- The descriptive one-liner under the title is unchanged in wording but renders as a tight single descriptor rather than a wrapped block.

### Files

- `mcp/agent/app/settings/hooks/page.tsx` (reuses `components/investigation/ui.tsx` primitives: `glassStyle`, `Badge`, `StatCard`, `EmptyState`, `InvestigationTabBar`). Docs: `app/help/user/page.tsx#hooks-ux`, `CHANGELOG.md`, `lib/release-notes.ts`. See [#18](https://github.com/kite-production/guardian/issues/18).

### Change scenario

**Scenario 1** — code-only (agent image); no storage/engine change; volumes preserved. Patch bump (v0.2.4).

---

## [v0.2.3] (unreleased) — *Investigation diagram hardening*

Hardening pass over the v0.2.1/v0.2.2 diagram + relations work, from a post-release adversarial code review. No new feature surface — correctness, robustness, and doc-accuracy fixes.

### What ships

- **Regenerate no longer hangs silently.** The diagram Generate/Regenerate flow (issue + case tabs) now checks the job-submission response and surfaces an error if it fails, instead of leaving a "Regenerating…" spinner running to the 3-minute timeout. The one-shot job name is now collision-proof, and a timeout shows an actionable message + refreshes to the latest state.
- **SVG sanitizer closes two gaps.** The agent-produced-SVG cleaner now also strips `<foreignObject>` and unquoted `on*=` event handlers (it already stripped `<script>` + quoted handlers). The diagrams render sandboxed as `<img>` data-URIs (a no-script context) so there was no live exploit, but the stored markup now matches the documented contract.
- **Relationship validation.** `add_relationship` rejects an empty `source_type` (the column is `NOT NULL`), matching the schema.
- **Type + doc accuracy.** `IndicatorDetail.relationships` is now non-optional (the REST endpoint always populates it). The architecture page's `investigations.db` schema diagram is corrected to match the code (`issue_events` columns, `cases`/`issues` column lists).

### Files

- `bundles/spark/mcp/src/usecase/builtin_components/investigation_tools.py` (`_clean_svg` foreignObject + unquoted-handler strips) + `usecase/investigation_store.py` (`add_relationship` guard). +2 tests.
- `mcp/agent/app/investigation/issues/[id]/page.tsx` + `app/investigation/cases/[id]/page.tsx` (regenerate error-handling + timeout feedback), `lib/api/investigation.ts` (`relationships` non-optional), `app/help/architecture/page.tsx` (schema-diagram corrections). See [#17](https://github.com/kite-production/guardian/issues/17).

### Change scenario

**Scenario 1** — code-only (agent image); no storage change; volumes preserved. Patch bump (v0.2.3).

---

## [v0.2.2] (unreleased) — *Case-view attack chain + relations canvas*

The on-demand diagrams come to **Cases**: a multi-issue case now gets a campaign-level attack chain and relations canvas, synthesized across all the issues grouped under it.

### What ships

- **Case detail is now tabbed** — Issues · Attack chain · Relations (it was a flat issue list before). The Issues tab is the previous grouped-issue view.
- **Campaign-level attack chain** — the Case's Attack chain tab draws ONE causal diagram spanning all the case's issues (the shared kill-chain across the campaign), generated on demand like the issue-level chain.
- **Campaign-level relations canvas** — the Case's Relations tab draws ONE STIX graph over the union of the case's issues' indicators, surfacing the shared infrastructure / techniques / actors that tie the campaign together.
- **Agent tools** (catalog side — no secrets): `case_set_attack_chain` · `case_set_relation_graph` (mirror the issue tools; all four diagram tools now share one `_clean_svg` validator). The two skills (`svg_attack_chain`, `svg_relation_graph`) gained a case-level (campaign) variant.
- The SVGs ride on the existing case detail REST + proxy; the `DiagramTab` component was lifted into the shared module so the issue + case pages render diagrams identically.

### Storage

Additive to `investigations.db`: `attack_chain_svg` + `relations_canvas_svg` columns on `cases` (via `ALTER TABLE … ADD COLUMN`; existing data untouched). Kept off the lean Case DTO/list — read only on the case detail.

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (cases columns + migration + `set/get_case_attack_chain` + `set/get_case_relations_canvas`) + `builtin_components/investigation_tools.py` (`_clean_svg` helper + `case_set_attack_chain` + `case_set_relation_graph`) + `connector_loader.py` + `api/investigation.py` + `skills/workflows/svg_attack_chain.md` + `skills/workflows/svg_relation_graph.md` (case-level variants). +6 tests.
- `mcp/agent/components/investigation/ui.tsx` (shared `DiagramTab`), `app/investigation/cases/[id]/page.tsx` (tabs + diagram tabs + case regenerate), `app/investigation/issues/[id]/page.tsx` (imports shared `DiagramTab`), `lib/api/investigation.ts` (`CaseDetail` SVG fields). See [#16](https://github.com/kite-production/guardian/issues/16).

### Change scenario

**Scenario 1** — code-only (agent image); additive columns (volumes preserved); no installer change. Patch bump (v0.2.2).

---

## [v0.2.1] (unreleased) — *Relations canvas + STIX indicator attribution*

A STIX relationship layer over the Investigation module: Guardian records typed edges between indicators and other entities, attributes IoCs to techniques / malware / campaigns / actors, and draws an on-demand **Relations canvas** per issue — the relational companion to the causal Attack chain.

### What ships

- **Relations canvas** — the issue detail gains a **Relations** tab: a self-contained, layered STIX graph of the issue's indicators and how they relate to each other and to ATT&CK techniques, malware, campaigns, and threat-actors. Generated on demand (button) like the Attack chain, via a one-shot agent pass; rendered sandboxed as an `<img>` data-URI.
- **Indicator attribution** — a new agent action `indicator_relate` records a STIX-style edge from an indicator to a target (another IoC, an ATT&CK technique, a malware/tool, a campaign, an intrusion-set, or a threat-actor). The verb (`resolves-to`, `indicates`, `attributed-to`, `uses`, …) is a STIX verb stored verbatim, so it round-trips with XSOAR's EntityRelationship enum + MITRE ATT&CK. Edges are deduped by (source, verb, target).
- **Relationships on the indicator** — the Indicator detail gains a **Relationships** section listing every edge from that IoC (source → verb → target, with the target's STIX type).
- **Skill wiring** — the `xsoar_case_investigation` lifecycle now records relationships as it attributes (Step 6) and draws the relations canvas at resolve; a new `svg_relation_graph` skill carries the layout + safety contract (mirrors `svg_attack_chain`).
- **Agent tools** (catalog side — no secrets): `indicator_relate` · `issue_set_relation_graph`. The relations canvas SVG + the indicator's relationships ride on the existing issue/indicator detail REST + proxies.

### Storage

Additive to `investigations.db`: a new `relationships` table (STIX edges, unique on `(source_id, relationship_type, target_value, target_type)`) + a `relations_canvas_svg` column on `issues`, both created on boot via `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN` (no destructive migration; existing data untouched).

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (`relationships` table + `relations_canvas_svg` column + `add_relationship`/`list_relationships`/`set_relations_canvas`/`get_relations_canvas`) + `builtin_components/indicator_tools.py` (`indicator_relate` + relationships on `indicator_get`) + `builtin_components/investigation_tools.py` (`issue_set_relation_graph`) + `connector_loader.py` + `api/investigation.py` + `skills/workflows/svg_relation_graph.md` (new) + `skills/workflows/xsoar_case_investigation.md` (attribution + canvas wiring). +9 tests.
- `mcp/agent/lib/api/investigation.ts` (`Relationship` type + `relations_canvas_svg` + target-type/verb helpers), `app/investigation/issues/[id]/page.tsx` (Relations tab + shared `DiagramTab` + generalized regenerate), `app/investigation/indicators/[id]/page.tsx` (Relationships section). See [#15](https://github.com/kite-production/guardian/issues/15).

### Change scenario

**Scenario 1** — code-only (agent image); additive table + column (volumes preserved); no installer change. Patch bump (v0.2.1).

---

## [v0.2.0] (unreleased) — *Indicators module + per-issue-type layouts*

A third Investigation object — **Indicators** (IoCs) — plus issue layouts tailored to each incident type. Guardian now keeps a deduped, cross-referenced record of every indicator it sees.

### What ships

- **Indicators** — a new Investigation subpage (Issues · Cases · **Indicators**). An indicator is an IoC (ip · domain · url · file_hash · email · cve · host · account) deduped by `(value, type)`; re-seeing one updates its last-seen and links the new issue rather than duplicating. The list shows type, reputation (DBotScore), source, #issues, and last-seen; the detail shows the enrichment, first/last seen, and **every issue the indicator appears in** (cross-case correlation).
- **Two feeds** — (1) Guardian records each IoC it enriches during an investigation (`source="guardian"`); (2) when it fetches an XSOAR case, the indicators the SOAR already extracted are imported (`source="xsoar"`), so XSOAR's enrichment carries into Guardian.
- **Extracted-indicators on the issue** — each issue detail gains an **Indicators** tab listing the IoCs linked to that issue, with the types that matter for the case kind highlighted.
- **Per-issue-type layouts** — the issue detail adapts to the kind: a kind-specific glyph + accent, a one-line investigative "focus" (what to look at for phishing vs malware vs lateral-movement vs access-violation), and IoC-type emphasis on the Indicators tab.
- **Agent tools** (catalog side — no secrets): `indicator_upsert` · `indicators_list` · `indicator_get`. **REST**: `/api/v1/indicators*` + Next proxies.

### Storage

Additive to `investigations.db`: new `indicators` + `indicator_issues` (M:N) tables created on boot via `CREATE TABLE IF NOT EXISTS` (no column migration; existing issues/cases untouched).

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (Indicator DTO + tables + upsert/list/get/per-issue) + `builtin_components/indicator_tools.py` + `connector_loader.py` + `api/investigation.py` + `skills/workflows/xsoar_case_investigation.md` (extraction wiring).
- `mcp/agent/app/api/agent/indicators/**`, `lib/api/investigation.ts`, `components/investigation/ui.tsx` (IndicatorRow + KIND_LAYOUT), `app/investigation/indicators/**`, `app/investigation/issues/[id]/page.tsx` (Indicators tab + per-type header), `components/sidebar.tsx`. +6 tests. See [#14](https://github.com/kite-production/guardian/issues/14).

### Change scenario

**Scenario 1** — code-only (agent image); additive tables (volumes preserved); no installer change. Minor bump (v0.2.0).

---

## [v0.1.10] (unreleased) — *Attack-chain diagram — richer, ATT&CK-mapped, animated*

The auto-generated attack chain is upgraded from a plain node→arrow flow to a tactic-colored, MITRE-mapped diagram.

### What ships (skill-only — `svg_attack_chain`)

- **No more clipped labels** — wider 250px node pitch gives each arrow a 70px gap; the technique id + short name sit terse above the arrow.
- **Tactic color-coding** — each stage is colored by its ATT&CK tactic (Initial Access · Execution · Lateral Movement · C2 · Impact · …), with a per-diagram legend.
- **Tactics + techniques** — every node carries a tactic pill; every arrow carries the technique id + name.
- **Attribution** — an attribution strip (threat actor / campaign, or "unattributed").
- **Subtle animation** — flowing dashed arrows + a gentle pulse on the impact node, via an inline `<style>` + CSS keyframes (declarative, so it plays even in the sandboxed `<img>` render — no script).

No code change: the renderer + `issue_set_attack_chain` already accept any valid SVG; the new template passes the sanitizer unchanged.

### Files

- `bundles/spark/mcp/skills/workflows/svg_attack_chain.md`. See [#13](https://github.com/kite-production/guardian/issues/13).

### Change scenario

**Scenario 1** — skill-only (agent image, volume-seeded on boot); no installer change; volumes preserved. Patch bump (v0.1.10).

---

## [v0.1.9] (unreleased) — *Investigation content — markdown rendering + Activity filter/sort*

The investigation text now renders as formatted markdown (the same as the chat window), and the Activity timeline is filterable + sortable.

### What ships

- **Markdown rendering** — the issue fields (Summary · Scope · Recommendations · Conclusions · Next steps), the activity event content, and the case description render through the shared `MarkdownContent` component the chat uses (react-markdown + remark-gfm + syntax highlighting). The agent already writes these fields as markdown; now they display formatted. Editing a field still shows the raw textarea.
- **Activity filter + sort** — the Activity tab gets type filter chips (all / action / finding / note …, derived from the events present), an Oldest/Newest sort toggle, and an "N of M" visible count.

### Files

- `mcp/agent/components/investigation/ui.tsx` (`EditableSection` → `MarkdownContent`) + `app/investigation/issues/[id]/page.tsx` + `app/investigation/cases/[id]/page.tsx`. See [#12](https://github.com/kite-production/guardian/issues/12).

### Change scenario

**Scenario 1** — code-only (agent image); no installer change; volumes preserved. Patch bump (v0.1.9).

---

## [v0.1.8] (unreleased) — *Attack-chain SVG diagram*

Guardian now draws a visual **attack chain** for each investigation — the causal path of the attack (entry → pivots → action → impact) — rendered on the issue's **Attack chain** tab. It generates automatically when an investigation resolves, and you can regenerate it on demand.

### What ships

- **Diagramming skill** (`svg_attack_chain`) — teaches the agent to emit a self-contained SVG of the attack chain (left-to-right nodes + labelled arrows, inline styling, own background, no scripts/external refs, XML-escaped labels), with a concrete template + palette.
- **Agent tool** `issue_set_attack_chain(issue_id, svg)` — validates the SVG (`<svg>…</svg>`, ≤256 KB), defensively strips `<script>`/`on*`, and stores it. On the catalog side of the credential guardrail (agent-callable, no secrets).
- **Automatic on resolve** — the `xsoar_case_investigation` skill now draws the chain at resolve time, so the autonomous loop produces one for every investigation.
- **Safe rendering** — the Attack-chain tab renders the SVG via an `<img>` data-URI, which is sandboxed (SVG-in-`<img>` never executes script or fetches external resources) — so agent-produced markup can't run code.
- **Regenerate** — a button on the tab redraws the diagram on demand (fires a one-shot agent pass; the tab polls until the new diagram lands).

### Files

- `bundles/spark/mcp/skills/workflows/svg_attack_chain.md` (new) + `xsoar_case_investigation.md` (resolve-step wiring).
- `bundles/spark/mcp/src/usecase/investigation_store.py` (`attack_chain_svg` column + set/get) + `builtin_components/investigation_tools.py` + `connector_loader.py` + `api/investigation.py`.
- `mcp/agent/lib/api/investigation.ts` + `app/investigation/issues/[id]/page.tsx`. +6 tests. See [#11](https://github.com/kite-production/guardian/issues/11).

### Change scenario

**Scenario 1** — code-only (agent image); the `attack_chain_svg` column is additive (migration preserves existing issues); no installer change; volumes preserved. Patch bump (v0.1.8).

---

## [v0.1.7] (unreleased) — *Investigation UI overhaul — full-width, tabbed, prettified*

The Investigation pages (Issues + Cases) now match the skills/jobs page standard, and the issue detail is split into tabs instead of one long page.

### What ships

- **Full-width, prettified layout** — all four pages (Issues list, Issue detail, Cases list, Case detail) use the `max-w-[1400px]` glass-card layout: summary stat cards, filter chips, glass rows with a per-kind glyph + status/severity/origin/XSOAR badges, and proper empty states. Shared primitives in `mcp/agent/components/investigation/ui.tsx` keep the list + detail visually consistent.
- **Tabbed issue detail** — **Overview** (Summary · Scope · Recommendations, with a derived VERDICT banner) · **Assessment** (Conclusions · Next steps) · **Activity** (the investigation timeline) · **Attack chain** (placeholder for the SVG causality diagram shipping in v0.1.8).
- **Cases-load performance fix** — `InvestigationStore.list_cases()` ran a correlated `(SELECT COUNT(*) FROM issues WHERE case_id = c.id)` *per case* (N+1 at the SQL level), which made the Cases list slower than Issues. Replaced with a single `LEFT JOIN issues … GROUP BY c.id` (one pass, identical response shape).
- **Manual analyst actions** — deferred; a disabled "Actions" control marks where they'll live in a later release.

### Files

- `mcp/agent/components/investigation/ui.tsx` (new shared primitives) + `app/investigation/{issues,issues/[id],cases,cases/[id]}/page.tsx` (rewritten).
- `bundles/spark/mcp/src/usecase/investigation_store.py` (`list_cases` LEFT JOIN). See [#10](https://github.com/kite-production/guardian/issues/10).

### Change scenario

**Scenario 1** — code-only (agent image); the `list_cases` query optimization preserves the response shape; no installer change; volumes preserved. Patch bump (v0.1.7).

---

## [v0.1.6] (unreleased) — *Investigation skill — blast-radius scoping gate*

A focused, evidence-driven increment on top of v0.1.5. A second structured evaluation of the autonomous loop's output (four investigations across lateral-movement, malware, data-exfiltration, and DNS-tunnel C2 — every proposed change adversarially verified and biased to reject churn) confirmed v0.1.5 is solid and surfaced exactly **one** recurring gap: investigations resolve the immediate finding but **defer blast-radius scoping to next-steps** instead of executing it.

### What ships

- **Blast-radius gate (Step 6)** — before an Issue can be marked `resolved`, the agent must enumerate the blast radius of every confirmed-malicious indicator and compromised principal *in-investigation*, not defer it: (1) follow every relationship enrichment already surfaced (a related hash, linked IP/domain, or co-sighting incident id) — enrich it or pull the named co-sighting and fold its hosts/accounts into scope; (2) pivot each confirmed-bad value outward via `xsoar_search_indicators` + `xsoar_list_incidents` (and the auth log via `xsoar_run_command` where `playground_id` exists) to find other affected hosts/cases; (3) state the scope as a one-line "N hosts / M cases" count or an explicit "contained to this host."
- **Matching constraint** — "Scope is part of resolution, not a next-step." A surfaced relationship left in prose is incomplete work.
- One general rule (no per-attack-type branches); complements — does not duplicate — the v0.1.5 resolution gate, which fires only on *competing root causes*.

### Files

- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`. See [#9](https://github.com/kite-production/guardian/issues/9).

### Change scenario

**Scenario 1** — skill-only (baked into the agent image, volume-seeded on boot); no installer change; volumes preserved. Patch bump (v0.1.6).

---

## [v0.1.5] (unreleased) — *Investigation skill hardening — IR rigor + tool-surface reconciliation*

Guardian's `xsoar_case_investigation` skill — the playbook that drives every autonomous and operator-initiated investigation — was upgraded from a structured evaluation of the autonomous loop's REAL output (two completed investigations scored against a SOC IR rubric, every proposed change adversarially verified against the connector source). The skill now teaches the full v0.2.0 tool surface, enforces complete IoC coverage, and gates "resolved" on a single supported root cause.

### What ships

- **Tool-family reconciliation** — the tool table listed only 9 of the connector's 21 tools and omitted every v0.2.0 command-engine tool the investigations actually used (`enrich_indicator`, `run_command`, `run_playbook`, the list tools, `create_incident`, `complete_task`). It now documents the full surface, grouped by phase, with the `playground_id` requirement flagged per tool.
- **Enrich step fixed** — `xsoar_enrich_indicator` (live DBotScore) is now the primary reputation tool; `xsoar_search_indicators` is for cross-case correlation. Previously the skill named only the store-search path.
- **Entity ledger + principal-first** — Step 2 now requires an explicit ledger of every IoC / account / host / email; the case isn't resolvable until every row has a result or a documented skip. Identity cases (access-violation, lateral-movement) characterize the ACCOUNT first, not the source IP.
- **Resolution gate** — don't mark an Issue `resolved` while competing root-cause hypotheses are undiscriminated; run the determinative query (e.g. recover the true client IP) FIRST rather than deferring it to next-steps.
- **Structured verdict + MITRE ATT&CK** — every Issue leads with a one-line `VERDICT:` and tags confirmed behaviors with ATT&CK technique IDs grounded in evidence.
- **Grounding rules** — quantitative claims (engine counts, scores) must trace to logged tool output; war-room citations quote the entry; blocklist recommendations check real list state via `get_list`.
- **Version-handling correction** — the skill previously said `xsoar_update_incident` *requires* the case `version`; the connector actually resolves the optimistic-lock version itself (the search-returned version is unreliable on Cortex 8). The skill now says leave `version` unset, and `xsoar_close_incident` takes `incident_ids` (array). Confirmed against `connector.py`.
- **Frontmatter parse fix** — the skill's YAML frontmatter carried a leaked shell-escape (`'\''` instead of YAML `''`) that made `yaml.safe_load` throw, so the loader silently discarded ALL frontmatter — including the `description` that auto-loads the skill when an operator asks to investigate a case. The loop masked this by binding the skill by name. Fixed; the auto-load trigger works again. Bug-family audit: no other skill carries the leak.

### How it was built

Evaluation → synthesis → adversarial verification ran as a multi-agent workflow; every proposed change was checked against the connector source before landing (two of eight needed correction). See [#8](https://github.com/kite-production/guardian/issues/8).

### Files

- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`.

### Change scenario

**Scenario 1** — skill-only (baked into the agent image, volume-seeded on boot via the per-release marker merge); no installer change; volumes preserved. Patch bump (v0.1.5).

---

## [v0.1.4] (unreleased) — *Agent chat resilience — retry transient Vertex socket resets*

Long agent turns — especially **scheduled investigation jobs** that run many tool calls against a real XSOAR tenant — no longer die mid-run with `chat error event: fetch failed`. The chat route already retried Vertex/Gemini **429 / quota** throttling; this release extends the same exponential-backoff retry to **transient socket resets** (`UND_ERR_SOCKET` / `ECONNRESET` / connect + body timeouts), which Vertex returns when it drops a long `generateContent` connection under load.

### What ships

- **Wider model-call retry** — the chat route's retry wrapper (renamed `withRateLimitRetry` → `withModelCallRetry`) now retries transient network failures in addition to 429s. A new `transientNetworkCode()` helper walks the `err.cause` chain (Node's fetch reports the real socket code on `cause`, not the top-level `fetch failed` message) and matches a set of retryable codes; a bare `fetch failed` / `socket hang up` / `other side closed` is treated as transient because undici only throws those for network-level errors (HTTP error statuses return a non-ok response, still handled by the 429 path).
- **Why it mattered** — the v0.1.3 autonomous investigation loop proved the Investigation module + skill work end-to-end (the agent opened a local Issue, `origin=agent`, the moment it began investigating) but every run then failed on a mid-investigation socket reset the retry predicate didn't cover. This is the fix that lets the loop *complete* an investigation. See [#7](https://github.com/kite-production/guardian/issues/7).

### Files

- `mcp/agent/app/api/chat/route.ts` — `transientNetworkCode()` + `TRANSIENT_NETWORK_CODES` + broadened `withModelCallRetry` (both Gemini-API-key and Vertex call sites).

### Change scenario

**Scenario 1** — code-only (agent image); no installer change; volumes preserved. Patch bump (v0.1.4).

---

## [v0.1.3] (unreleased) — *Investigation module — local Issues & Cases*

A new first-class **Investigation** area: Guardian (and the operator) open local **Issues** during investigations and group related ones into **Cases**. Distinct from upstream XSOAR incidents — an Issue is *Guardian's own* investigation record (what's being investigated, the activity timeline, recommendations, conclusions, summary, next steps), shown in the UI.

### What ships

- **Investigation store** (`investigations.db`) — issues + cases + per-issue activity timeline (`issue_events`). One-to-many issue→case. Catalog domain (not credentials).
- **Agent MCP tools** (catalog side of the credential guardrail — no SecretStore access): `issue_create` / `issue_update` / `issue_add_event` / `issue_get` / `issues_list` / `case_create` / `case_add_issue` / `cases_list` / `case_get`. The agent opens an Issue when it starts working a case (with `source_ref` = the XSOAR incident id), logs each step/finding, records the verdict, and groups related Issues into Cases.
- **REST API** (`/api/v1/issues|cases*`) + **Next.js proxies** (`/api/agent/issues|cases*`).
- **UI** — new sidebar **Investigation** group → **Issues** + **Cases**. Issues list (+ New Issue), rich issue detail (status/severity controls, editable Summary/Scope/Recommendations/Conclusions/Next-steps, activity timeline of what Guardian did, case assignment), cases list (+ New Case), case detail (grouped issues).
- **Skill + system prompt** — the `xsoar_case_investigation` skill + the agent's job description now drive opening + maintaining the local Issue + grouping Cases throughout every investigation.
- **Also in this release:** guardian-updater no longer crashes the `reconcile/digests` endpoint when a connector's running image was pruned (ImageNotFound → recreate). See [#6](https://github.com/kite-production/guardian/issues/6).

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py`, `src/api/investigation.py`, `src/usecase/builtin_components/investigation_tools.py` (+ `connector_loader.py`, `main.py` wiring) + tests.
- `mcp/agent/app/api/agent/{issues,cases}/**`, `lib/api/investigation.ts`, `app/investigation/{issues,cases}/**`, `components/sidebar.tsx`.
- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`, `mcp/agent/lib/system-prompt.ts`.
- `updater/src/main.py` (reconcile ImageNotFound fix).

### Change scenario

**Scenario 1** — code-only; `investigations.db` is created fresh on first boot (additive, no migration); no installer change; volumes preserved. Minor bump (v0.1.3).

### Forbidden going forward

- No SecretStore reads in the `issue_*` / `case_*` tools — they stay on the catalog side of the guardrail (that's why the agent may call them).
- Don't conflate a Guardian **Issue** with an upstream XSOAR **incident** — the Issue is Guardian's local record; `source_ref` links them.

---

## [v0.1.2] — 2026-06-12 — *XSOAR action toolset + default chat-model picker*

This release ships two concepts together (the default-model picker below was merged but never separately tagged, so it rides along here). The XSOAR connector grows from 13 to 21 tools, adding a command-execution engine, indicator enrichment, XSOAR Lists management, incident creation, and playbook execution. Previously Guardian could read and triage cases but could not run an XSOAR command, enrich an IoC, manage allow/block lists, open a case, or run a playbook.

### What ships

- **Command engine** (needs `playground_id`) — `xsoar_run_command` runs any XSOAR `!command` synchronously in the playground War Room (`POST /entry/execute/sync`) and returns the war-room output plus optional context keys. `xsoar_enrich_indicator` layers the `!ip`/`!url`/`!domain`/`!file`/`!cve` map onto it for DBotScore reputation. `xsoar_complete_task` runs `!taskComplete` to advance a playbook task.
- **XSOAR Lists** — `xsoar_get_list` / `xsoar_set_list` / `xsoar_append_to_list` read, overwrite, and append to XSOAR Lists (allow/block lists, lookups) via the `!getList` / `!setList` war-room commands. These need `playground_id` (the v6 `GET /lists/` REST endpoint returns HTTP 500 on Cortex 8 — verified live).
- **Incident lifecycle** — `xsoar_create_incident` (`POST /incident`) opens a case; `xsoar_run_playbook` runs `!setPlaybook` in the incident's *own* war room (an incident id is its investigation id, so no `playground_id` needed) to assign + start a playbook. The v6 `POST /inv-playbook/<pb>/<inv>` REST endpoint 303-redirects on Cortex 8 (verified live), so the war-room command path is used on both generations.
- **New `playground_id` config field** — an **optional** field on the XSOAR instance (the Playground / War Room investigation id). The 13 read/lifecycle tools and existing instances work unchanged; only the three command-engine tools require it, and they return a clean "playground_id not configured" message when it is blank. The field is surfaced in the **instance Create + Edit forms** so operators can set it (see the marketplace-overlay fix below).
- **Instance form surfaces newly-added config fields** — fixed a drift where the `/api/marketplace/connectors` catalogue hardcoded each connector's config-field list (and version), so a field added to a connector (like `playground_id`) never appeared in the UI. The catalogue now overlays the live `configSchema` + `version` from `connector.yaml` (the same overlay v0.15.5 added for `spec.tools[]`), and the Edit-Instance dialog seeds from the connector's full schema — so an existing instance's form shows fields added after it was created, empty + editable.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — 8 new `xsoar_*` tools + the `_execute_command` / `_parse_war_room_entries` / `_get_playground_id` / `_find_list` helpers; connector version 0.1.0 → 0.2.0.
- `bundles/spark/connectors/xsoar/connector.yaml` — `playground_id` config field + 8 `spec.tools[]` entries.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — per-tool request-shape + envelope tests (v6 + v8).
- `mcp/agent/app/help/architecture/page.tsx` — `#xsoar-connector` gains an "Action toolset" subsection.
- `mcp/agent/app/help/user/page.tsx` — `#connectors` gains the command-tools + `playground_id` setup subsection.
- `mcp/agent/lib/journeys.ts` — `xsoar-run-command` journey.
- `mcp/agent/app/api/marketplace/connectors/route.ts` — overlay live `configSchema` + `version` from `connector.yaml` onto the catalogue (append config fields the hardcoded list doesn't name).
- `mcp/agent/app/connectors/page.tsx` — Edit-Instance dialog seeds from the connector's full schema so newly-added fields surface.

### Change scenario

**Scenario 1** — code-only, installer unchanged. `playground_id` is a backwards-compatible optional config field; volumes preserved; customers re-run the existing installer.

### Forbidden post-v0.1.2

- No XSIAM-side tools smuggled in under "XSOAR" (XQL / datasets / issues / assets / vendor lookups) — Guardian is XSOAR-only.
- No credential / SecretStore reads added to these tools — they stay on the catalog/connector side of the guardrail.
- No `close_investigation` tool — `close_incident` already closes the investigation.

---

## [v0.1.1] (shipped within v0.1.2) — *Default chat-model picker*

Operators can now pin a default model for all new chats. Previously every chat opened on the runtime default (`GEMINI_MODEL` env or the hardcoded `gemini-3.1-pro-preview` fallback) and operators had to run `/model <name>` in every session to override it.

### What ships

- **Default model picker** — Settings → Models → open a model card → **Set as default**. The selection is persisted in `operator_state.db` under key `default_model = {provider, model}`.
- **Chat route default resolution** — the resolution chain is now: per-chat override → operator default (`operator_state.db`) → `GEMINI_MODEL` env → hardcoded fallback. New chats automatically pick up the operator default without any slash command.
- **Dropdown chip** — the model picker chip in the chat header shows **Default — \<model\>** when an operator default is active (previously showed "auto"). Picking a different model in the dropdown overrides for that chat only; the next new chat resets to the default.

### Files

- `mcp/agent/app/(main)/models/[id]/page.tsx` — "Set as default" button on model detail page
- `mcp/agent/app/(main)/models/page.tsx` — visual indicator on the default model card
- `mcp/agent/app/api/chat/route.ts` — operator-default step inserted in `resolveModelName`
- `mcp/agent/components/chat/model-picker.tsx` — chip shows "Default — \<model\>" vs "auto"
- `mcp/agent/app/help/architecture/page.tsx` — `#model-routing` updated with the new chain
- `mcp/agent/app/help/user/page.tsx` — `#models-providers` new "Default model" subsection
- `mcp/agent/lib/journeys.ts` — `set-default-chat-model` journey added
- `CHANGELOG.md`, `mcp/agent/lib/release-notes.ts` — this entry

Scenario 1 (code-only, no installer change).

---

## [v0.1.0] (unreleased) — *Guardian initial release: an AI incident-response agent for Cortex XSOAR*

Guardian is derived from the Phantom agent platform, cut down to one job: **AI-assisted incident investigation on Cortex XSOAR.** An operator points Guardian at their XSOAR tenant; the agent then monitors the cases (incidents) opening on the SOAR, fetches each case's full record and war-room narrative, investigates and enriches it, documents its findings back onto the case, and updates or closes it — autonomously or on request.

**What was removed from the Phantom baseline:** everything that existed to *generate* or *query telemetry* rather than *investigate cases*. Gone are the synthetic log-generation backend, the red-team adversary-emulation stack, the data-source validation catalog, the log-destination subsystem, **the XSIAM and Cortex XDR telemetry connectors, the Cortex content catalog, all XQL-authoring tooling, and the bundled XQL-examples knowledge base.** None of these surfaces — services, connectors, UI pages, MCP tools, CI workflows, skills, KBs — ship in Guardian. The full `phantom → guardian` rename runs through service names, image names, env vars, tool prefixes, and the installer.

**What Guardian is:** a focused XSOAR case-investigation agent. The operator chats with (or schedules) an agent that lists and triages open cases, pulls full case detail and the war-room conversation, enriches the case's indicators against XSOAR threat intel, researches CVEs/IOCs in Palo Alto Cortex documentation and on the open web through a sandboxed Chromium sidecar, writes its findings as war-room notes, and updates case severity/owner/fields or closes the case with a reason — with IR-focused agent semantics throughout (an incident-investigation system prompt, plan mode for multi-step investigations, and quick actions for the common case-triage moves).

### What ships

- **The `guardian-agent` container** — Next.js 15 UI (port 3000, TLS proxy in front) + an embedded Python FastMCP subprocess (port 8080, bearer-token auth). The agent's chat, jobs, observability, and help surfaces all live here. The embedded-MCP test suite passes (283 tests).
- **3 connectors** (`bundles/spark/connectors/`), each running as a per-instance container on the shared connector runtime (`guardian-connector-runtime/`):
  - **xsoar** — 13 tools (`xsoar_` prefix) covering the full case lifecycle: `xsoar_list_incidents`, `xsoar_get_incident`, `xsoar_get_war_room`, `xsoar_add_entry`, `xsoar_add_note`, `xsoar_update_incident`, `xsoar_close_incident`, `xsoar_list_incident_types`, `xsoar_get_incident_fields`, `xsoar_search_indicators`, `xsoar_save_evidence`, `xsoar_search_evidence`, `xsoar_health_check`. Supports **both** XSOAR 6 (on-prem, API key in the `Authorization` header) and XSOAR 8 / Cortex cloud (API key + key id via `x-xdr-auth-id`, `/xsoar/public/v1` path prefix) — detected from whether an `api_id` is configured.
  - **cortex-docs** — Palo Alto Cortex documentation lookup (`cortex_` prefix), for grounding investigation reasoning in authoritative product docs.
  - **web** — Playwright browsing (`guardian_web_` prefix) through the browser sidecar, for CVE/IOC/threat-intel research.
- **Embedded MCP builtins** (`bundles/spark/mcp/`) — cognitive tools, skills CRUD, and self-modification tools, plus on-disk skills: `cortex_kb_search`, `cortex_kb_search_patterns`, `cortex_kb_api_reference` (Cortex-docs research) and the two XSOAR investigation skills `xsoar_case_investigation` (the load-first end-to-end case workflow) and `xsoar_case_triage`.
- **The `guardian-browser` sidecar** — headless Chromium driven over CDP, profile-gated, the only path the web connector uses to touch the internet.
- **The `guardian-updater` daemon** (port 8090) — container-lifecycle management for connector instances and image rollouts.
- **IR agent semantics** — an incident-investigation system prompt that drives the monitor → fetch → investigate → document → update/close loop, plan mode, and quick actions tuned for case triage.
- **Credential guardrail (unchanged from upstream)** — the agent has **no** MCP tool that reads, writes, mints, or rotates credentials; `providers_*`, `instances_*` (create/update/delete), and `api_keys_*` management stay REST-only.
- **Observability** — the manifest declares one runtime event family, `rt.tool.failed`, emitted for every MCP tool that raises.
- **AI-layer tooling** — the bundle validator passes 18/18 checks, and a codebase-search MCP server supports agent-assisted development on the repo itself.
- **Release plumbing** — `github.com/kite-production/guardian` with a registered self-hosted runner; a customer release ships **7 images at one version tag** (guardian-agent, guardian-updater, guardian-browser, guardian-connector-runtime, and the xsoar / cortex-docs / web connector images).

### Files

- `mcp/agent/` — Next.js UI + embedded-MCP host (the `guardian-agent` container)
- `bundles/spark/mcp/` — Python FastMCP server, builtin tools, skills, tests
- `bundles/spark/connectors/{xsoar,cortex-docs,web,_runtime}/` — the 3 connectors + shared runtime base
- `guardian-connector-runtime/` — shared connector base image
- `guardian-browser/` — Chromium CDP sidecar
- `updater/` — `guardian-updater` lifecycle daemon
- `installer/` — customer installer template
- `docker-compose.yml`, `.github/workflows/` — stack topology + build/release pipeline

First Guardian release — fresh install via the customer installer; there is no upgrade path from any Phantom version. **Live XSOAR connectivity is configured at first-run setup** (the operator supplies the XSOAR server URL, API key, and — for XSOAR 8/Cortex — the API key id).
