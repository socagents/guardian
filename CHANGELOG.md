# Changelog

All notable changes to Guardian are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 releases bump the patch on every tagged release; minor bumps will resume after the v1.0.0 cut.

Each release section is written in operator language, not git-shortlog language. For commit-level granularity, run `git log vPREV..vNEW`.

<!-- [guardian v0.1.0] Retired: the upstream Phantom release history (v0.1.x–v0.17.x) — Guardian is a new product; the inherited changelog described subsystems that no longer exist here. -->

---

## [v0.1.2] (unreleased) — *XSOAR action toolset*

The XSOAR connector grows from 13 to 21 tools, adding a command-execution engine, indicator enrichment, XSOAR Lists management, incident creation, and playbook execution. Previously Guardian could read and triage cases but could not run an XSOAR command, enrich an IoC, manage allow/block lists, open a case, or run a playbook.

### What ships

- **Command engine** (needs `playground_id`) — `xsoar_run_command` runs any XSOAR `!command` synchronously in the playground War Room (`POST /entry/execute/sync`) and returns the war-room output plus optional context keys. `xsoar_enrich_indicator` layers the `!ip`/`!url`/`!domain`/`!file`/`!cve` map onto it for DBotScore reputation. `xsoar_complete_task` runs `!taskComplete` to advance a playbook task.
- **XSOAR Lists** — `xsoar_get_list` / `xsoar_set_list` / `xsoar_append_to_list` read, overwrite, and append to XSOAR Lists (allow/block lists, lookups) via `GET /lists/` + `POST /lists/save`.
- **Incident lifecycle** — `xsoar_create_incident` (`POST /incident`) opens a case; `xsoar_run_playbook` (`POST /inv-playbook/<pb>/<inv>`) assigns and starts a playbook on a case.
- **New `playground_id` config field** — an **optional** field on the XSOAR instance (the Playground / War Room investigation id). The 13 read/lifecycle tools and existing instances work unchanged; only the three command-engine tools require it, and they return a clean "playground_id not configured" message when it is blank.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — 8 new `xsoar_*` tools + the `_execute_command` / `_parse_war_room_entries` / `_get_playground_id` / `_find_list` helpers; connector version 0.1.0 → 0.2.0.
- `bundles/spark/connectors/xsoar/connector.yaml` — `playground_id` config field + 8 `spec.tools[]` entries.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — per-tool request-shape + envelope tests (v6 + v8).
- `mcp/agent/app/help/architecture/page.tsx` — `#xsoar-connector` gains an "Action toolset" subsection.
- `mcp/agent/app/help/user/page.tsx` — `#connectors` gains the command-tools + `playground_id` setup subsection.
- `mcp/agent/lib/journeys.ts` — `xsoar-run-command` journey.

### Change scenario

**Scenario 1** — code-only, installer unchanged. `playground_id` is a backwards-compatible optional config field; volumes preserved; customers re-run the existing installer.

### Forbidden post-v0.1.2

- No XSIAM-side tools smuggled in under "XSOAR" (XQL / datasets / issues / assets / vendor lookups) — Guardian is XSOAR-only.
- No credential / SecretStore reads added to these tools — they stay on the catalog/connector side of the guardrail.
- No `close_investigation` tool — `close_incident` already closes the investigation.

---

## [v0.1.1] (unreleased) — *Default chat-model picker*

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
