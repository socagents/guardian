# Guardian — Codebase Map

A lightweight map of the repo so an agent can find where a feature lives
*before* it starts reading files. Layered: top-level groups first, then the
modules inside each. Keep this current when you add or move a service.

## Top level

| Path | What it is |
|------|------------|
| `mcp/agent/` | The chat UI + embedded MCP subprocess (the **`guardian-agent`** customer container). Next.js 15 + React 19 + Python 3.12. |
| `bundles/spark/` | Guardian's runtime bundle — manifest, the MCP server, the per-instance connectors, default skills, plugins, KBs, prompts, and providers. |
| `guardian-browser/` | Dockerfile only — headless Chromium for the `web` connector (CDP-accessed). |
| `guardian-connector-runtime/` | Shared base image for container-style per-instance connectors. |
| `updater/` | The **`guardian-updater`** customer container — manages per-instance connector container lifecycle + stack-level upgrades. |
| `installer/` | Customer installer template + docker-compose.yml. |
| `scripts/` | Maintainer + CI helper scripts (e.g. `refresh_cortex_baked_catalog.py`, the e2e tool batteries, backup/restore). |
| `tooling/` | Coding-agent harness (AI Layer) — plugin payload, validator, codebase-search MCP. See [`AI-LAYER.md`](AI-LAYER.md). |
| `docs/` | Long-form docs (`CICD.md` is the canonical CI/CD pipeline reference). |
| `logos/` | Brand assets (`guardian.svg`). |
| `a2ui/` | A2UI surface definitions — `manifest.json`, `catalogs/`, `schemas/`, JSONL surfaces. |
| `.github/` | Workflows + composite actions + issue templates + labels. |

<!-- [guardian v0.1.0] Retired: xlog/ top-level section — simulation subsystem removed -->

## bundles/spark/ — the Guardian runtime bundle

| Path | What it is |
|------|------------|
| `bundles/spark/manifest.yaml` | Bundle manifest — capability declarations, settings, jobs, runtime events (`rt.tool.failed`). |
| `bundles/spark/mcp/` | The Python FastMCP server that runs as a subprocess inside `guardian-agent`. Registers built-in + connector tools, exposes REST routes for the Next.js side. |
| `bundles/spark/connectors/` | Per-connector source: each subdir is one connector (`xsiam`, `cortex-xdr`, `cortex-docs`, `cortex-content`, `web`), plus the `_runtime` shared base and `connector.schema.json`. Each connector runs as its own image at customer release time. |
| `bundles/spark/mcp/skills/` | Default skills shipped with the agent (MD files with frontmatter). Volume-seeded on first boot; merged on per-release marker. |
| `bundles/spark/plugins/` | Built-in plugins (currently empty). |
| `bundles/spark/kbs/` | Knowledge base entries (`xql-examples` — curated XQL queries) seeded at boot. |
| `bundles/spark/prompts/` | System-prompt fragments (`system.md`). |
| `bundles/spark/providers/` | Provider-specific glue (`vertex`). |

<!-- [guardian v0.1.0] Retired: bundles/spark/caldera-content/ row — simulation subsystem removed -->

## mcp/agent/ — the agent UI + embedded MCP host

| Path | What it is |
|------|------------|
| `mcp/agent/app/` | Next.js App Router pages + API routes. Feature pages live directly under `app/` (`connectors`, `skills`, `jobs`, `knowledge`, `approvals`, …). |
| `mcp/agent/app/api/` | API routes — `auth`, `chat`, `skills`, `marketplace`, `agent`. The `/api/agent/*` set are thin proxies to the embedded MCP via `lib/mcp-proxy.ts`. |
| `mcp/agent/app/help/` | In-product help — `architecture/page.tsx` (canonical spec), `user/page.tsx` (operator guide), `journeys/` (click-paths), `api/` (REST reference), `cicd/`. |
| `mcp/agent/app/observability/` | Runtime introspection — `events`, `logs`, `metrics`, `traces`, `cost`, `pipeline`, `connectors`, `runtime-events`, `detections`, `bench`, `plugins`. |
| `mcp/agent/components/` | Shared React components. `sidebar.tsx` is the nav source of truth. |
| `mcp/agent/lib/` | Shared TS — `mcp-proxy.ts`, `journeys.ts`, `release-notes.ts`, `system-prompt.ts`, `runtime-config.ts`. |
| `mcp/agent/entrypoint.sh` | Container start: TLS proxy + skills seeding + MCP subprocess + Next.js. |
| `mcp/agent/tls-proxy.js` | Node.js sidecar terminating TLS in front of UI (3000) + MCP (8080). |

## bundles/spark/mcp/ — the embedded Python MCP server

| Path | What it is |
|------|------------|
| `bundles/spark/mcp/src/config/config.py` | `pydantic-settings` config — every env var goes through `validation_alias`. |
| `bundles/spark/mcp/src/service/` | FastMCP instance factory. |
| `bundles/spark/mcp/src/usecase/builtin_components/` | Built-in tool implementations — `cognitive_tools`, `skills_crud`, `self_mod_tools` (+ `_approval_gate`). |
| `bundles/spark/mcp/src/usecase/connector_loader.py` | Dynamic registration of connector tools at boot + the `_BUILTIN_LEGACY_TOOLS` list (the credential-guardrail boundary — see root `CLAUDE.md`). |
| `bundles/spark/mcp/src/api/` | REST routes that the Next.js side proxies (`instances.py`, `providers.py`, `audit.py`, `kb.py`, etc.). |
| `bundles/spark/mcp/src/pkg/` | Shared helpers — `connector_proxy.py`, `setup_logging.py`. |
| `bundles/spark/mcp/src/main.py` | Entry point — registers REST routes + tool catalogs inside `async_main`. |
| `bundles/spark/mcp/skills/` | Default runtime skills — `foundation/` (`cortex_kb_search`, `cortex_kb_search_patterns`, `cortex_kb_api_reference`, `cortex_xql_query_authoring`), `workflows/` (`build_xql_query`). |
| `bundles/spark/mcp/tests/` | pytest suite (~349 tests). Run with `PYTHONPATH=$PWD/src python3 -m pytest tests/ -x`. |

## bundles/spark/connectors/ — per-instance connectors

Each connector ships as its own image at release time. The agent dispatches to per-instance containers via HTTP, not in-process Python.

| Connector | What it does |
|-----------|--------------|
| `xsiam` | Cortex XSIAM PAPI — XQL queries (with RAG-backed example retrieval), datasets, cases, issues, assets, lookups, webhook log delivery. 13 tools, `xsiam_` prefix. |
| `cortex-xdr` | Cortex XDR cases + issues (`xdr_` prefix). |
| `cortex-docs` | Cortex documentation search (`cortex_` prefix). |
| `cortex-content` | Cortex content catalog — baked local catalog at `bundles/spark/connectors/cortex-content/baked/`, no network egress. |
| `web` | Web browsing via Playwright + headless Chromium (`guardian-browser` CDP), `guardian_web_` prefix. |
| `_runtime` | Shared connector-runtime source — pairs with the `guardian-connector-runtime/` base image at repo root. |

<!-- [guardian v0.1.0] Retired: xlog + caldera connector rows — simulation subsystem removed -->
<!-- [guardian v0.1.0] Retired: "xlog/ — the log-generation backend" section — simulation subsystem removed -->

## installer/ + updater/ — packaging + lifecycle

| Path | What it is |
|------|------------|
| `installer/docker-compose.yml` | Customer compose — image refs use `@${DIGEST_*}` for content-pinning. Services: `guardian-agent`, `guardian-browser`, `guardian-updater`. |
| `installer/build-guardian-installer.sh` | Builds the `guardian-installer` binary from `guardian-installer.template.sh`. |
| `installer/install.sh` + `installer/bootstrap.sh` | Customer install ceremony. |
| `updater/src/main.py` | The `guardian-updater` daemon — manages per-instance connector container lifecycle (port 8090). |
| `updater/Dockerfile` | Builds the `guardian-updater` image. |

## Finding a feature

- **A chat-UI page** → `mcp/agent/app/<feature>/page.tsx`.
- **A help-page section** → `mcp/agent/app/help/architecture/page.tsx` or `.../user/page.tsx`.
- **An API endpoint** → `mcp/agent/app/api/agent/<resource>/route.ts` (Next.js proxy) → `bundles/spark/mcp/src/api/<resource>.py` (MCP backend).
- **A built-in MCP tool** → `bundles/spark/mcp/src/usecase/builtin_components/<file>.py`, registered via `bundles/spark/mcp/src/usecase/connector_loader.py`.
- **A connector tool** → `bundles/spark/connectors/<connector>/src/` + the matching `spec.tools[]` entry in that connector's `connector.yaml`.
- **A skill** → `bundles/spark/mcp/skills/<category>/<name>.md`.
- **A knowledge base** → `bundles/spark/kbs/<kb>/`.
- **A CI/CD workflow** → `.github/workflows/<workflow>.yml`. Composite actions at `.github/actions/<name>/`.
- **A release entry** → `CHANGELOG.md` (long-form) + `mcp/agent/lib/release-notes.ts` (About modal).
- **A user journey** → `mcp/agent/lib/journeys.ts`.
- **An issue template** → `.github/ISSUE_TEMPLATE/release.md`.
