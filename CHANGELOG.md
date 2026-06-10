# Changelog

All notable changes to Guardian are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 releases bump the patch on every tagged release; minor bumps will resume after the v1.0.0 cut.

Each release section is written in operator language, not git-shortlog language. For commit-level granularity, run `git log vPREV..vNEW`.

<!-- [guardian v0.1.0] Retired: the upstream Phantom release history (v0.1.x–v0.17.x) — Guardian is a new product; the inherited changelog described subsystems that no longer exist here. -->

---

## [v0.1.0] (unreleased) — *Guardian initial release: an AI incident-response agent for Cortex XSIAM/XSOAR*

Guardian is derived from the Phantom agent platform, cut down to one job: **AI-assisted incident response against a live Cortex XSIAM/XSOAR tenant.** Everything in Phantom that existed to *generate* security telemetry is gone; everything that *investigates* it stays, rebranded and refocused.

**What was removed from the Phantom baseline:** the synthetic log-generation backend, the red-team adversary-emulation stack, the data-source validation catalog (the per-vendor marketplace of parser/modeling-rule shapes), and the log-destination subsystem. None of these surfaces — services, connectors, UI pages, MCP tools, CI workflows — ship in Guardian. The full `phantom → guardian` rename runs through service names, image names, env vars, tool prefixes, and the installer.

**What Guardian is:** an operator chats with (or schedules) an agent that pulls cases, issues, and assets from the tenant, authors and runs XQL queries grounded in a curated example KB, consults Palo Alto Cortex documentation, and browses the web through a sandboxed Chromium sidecar — with IR-focused agent semantics throughout (an incident-response system prompt, plan mode for multi-step investigations, and quick actions for the common triage moves).

### What ships

- **The `guardian-agent` container** — Next.js 15 UI (port 3000, TLS proxy in front) + an embedded Python FastMCP subprocess (port 8080, bearer-token auth). The agent's chat, jobs, observability, and help surfaces all live here. ~349 embedded-MCP tests pass.
- **5 connectors** (`bundles/spark/connectors/`), each running as a per-instance container on the shared connector runtime (`guardian-connector-runtime/`):
  - **xsiam** — 59 tools (`xsiam_` prefix): XQL queries (`run_xql_query`, `get_xql_examples`, `find_xql_examples_rag`), datasets + dataset fields, cases, issues, incidents, alerts, assets, lookups, webhook log delivery, and the wider PAPI investigation surface.
  - **cortex-xdr** — 50 tools (`xdr_` prefix): cases + issues, incidents, alerts, and Cortex XDR tenant investigation paths.
  - **cortex-docs** — Palo Alto Cortex documentation lookup (`cortex_` prefix).
  - **cortex-content** — baked content catalog, no outbound network.
  - **web** — Playwright browsing (`guardian_web_` prefix) through the browser sidecar.
- **Embedded MCP builtins** (`bundles/spark/mcp/`) — cognitive tools, skills CRUD, and self-modification tools, plus 5 on-disk skills (`cortex_kb_search`, `cortex_kb_search_patterns`, `cortex_kb_api_reference`, `cortex_xql_query_authoring`, `build_xql_query`) and the bundled XQL-examples knowledge base (`bundles/spark/kbs/xql-examples`) that grounds query authoring in curated, working queries.
- **The `guardian-browser` sidecar** — headless Chromium driven over CDP, profile-gated, the only path the web connector uses to touch the internet.
- **The `guardian-updater` daemon** (port 8090) — container-lifecycle management for connector instances and image rollouts.
- **IR agent semantics** — incident-response system prompt, plan mode, and quick actions tuned for triage/investigation flows rather than telemetry authoring.
- **Credential guardrail (unchanged from upstream)** — the agent has **no** MCP tool that reads, writes, mints, or rotates credentials; `providers_*`, `instances_*` (create/update/delete), and `api_keys_*` management stay REST-only.
- **Observability** — the manifest declares one runtime event family, `rt.tool.failed`, emitted for every MCP tool that raises.
- **AI-layer tooling** — the bundle validator passes 19/19 checks, and a codebase-search MCP server supports agent-assisted development on the repo itself.
- **Release plumbing** — `github.com/kite-production/guardian` with a registered self-hosted runner; a customer release ships **9 images at one version tag**.

### Files

- `mcp/agent/` — Next.js UI + embedded-MCP host (the `guardian-agent` container)
- `bundles/spark/mcp/` — Python FastMCP server, builtin tools, skills, tests
- `bundles/spark/connectors/{xsiam,cortex-xdr,cortex-docs,cortex-content,web,_runtime}/` — the 5 connectors + shared runtime base
- `bundles/spark/kbs/xql-examples/` — curated XQL knowledge base
- `guardian-connector-runtime/` — shared connector base image
- `guardian-browser/` — Chromium CDP sidecar
- `updater/` — `guardian-updater` lifecycle daemon
- `installer/` — customer installer template
- `docker-compose.yml`, `.github/workflows/` — stack topology + build/release pipeline

First Guardian release — fresh install via the customer installer; there is no upgrade path from any Phantom version.
