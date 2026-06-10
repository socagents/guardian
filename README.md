<table>
  <tr>
    <td width="180" valign="top">
      <img src="logos/guardian-white.gif" alt="GUARDIAN logo" width="160">
    </td>
    <td valign="top">
      <h1>GUARDIAN</h1>
      <p>The agentic security platform. Securing autonomous tools across the cognitive, integration, and runtime layers to ensure flawless execution.</p>
      <p><strong>Category:</strong> AGENTIC SECURITY</p>
    </td>
  </tr>
</table>

Guardian ships as a **spark-agents v1.2** bundle. It connects to your Cortex XSIAM/XSOAR tenant, runs XQL investigations, enriches cases and issues, and exposes everything as MCP tools the agent chains through skills, knowledge bases, and an A2UI-rendered chat surface.

## At a glance

| Service | Purpose | Port |
|---|---|---|
| `guardian-agent` | Next.js 15 operator UI **+** embedded Python FastMCP subprocess (single trust boundary, single container, two processes, TLS proxy in front) | 3000 (UI), 8080 (MCP) |
| `guardian-browser` | Headless-Chromium sidecar for the `web` connector (CDP-accessed, profile-gated) | internal |
| `guardian-updater` | Container-lifecycle daemon — per-instance connector containers + stack upgrades | 8090 |
| connector containers | One per materialized connector instance, created at runtime by the updater | internal |

The agent's behavior is entirely encoded in the bundle (`bundles/spark/`) — manifest, connectors, providers, prompts, skills, knowledge bases, and A2UI surfaces. The image is content-addressed; everything operator-supplied (URLs, credentials, settings) flows in through the **first-run setup form**.

## Connectors

| Connector | What it does |
|---|---|
| `xsiam` | Cortex XSIAM PAPI — XQL queries (with RAG-backed example retrieval), datasets, cases, issues, incidents, alerts, assets, lookups, webhook log delivery. 59 tools, `xsiam_` prefix. |
| `cortex-xdr` | Cortex XDR incidents, alerts, cases + issues. 50 tools, `xdr_` prefix. |
| `cortex-docs` | Cortex documentation search (`cortex_` prefix). |
| `cortex-content` | Cortex content catalog — fully baked local data, no network egress. |
| `web` | Web browsing via Playwright through the `guardian-browser` CDP sidecar (`guardian_web_` prefix). |

Connector source lives under [`bundles/spark/connectors/`](bundles/spark/connectors/); each ships as its own image on the shared [`guardian-connector-runtime`](guardian-connector-runtime/) base.

## Architecture

The canonical, always-current spec lives **in the product** at `/help/architecture`. The short version:

- **One image, two processes**: `guardian-agent` runs Next.js (UI) and the embedded MCP (Python) in the same container. The MCP is part of the agent's trust boundary, not a sibling service — per the spark-agents v1.2 bundle spec.
- **No env vars for behavior**: the operator fills out a setup form at first run. Form values write into the SecretStore (mode-0700 file vault for secret values; sqlite metadata stores for the rest). Container restarts preserve everything.
- **Tools are gated**: a connector's tools are advertised ONLY when at least one connector instance has been materialized via the setup form.
- **Credential guardrail**: the chat agent never holds credential-management tools (provider/instance/API-key create, update, delete, rotate). Those operations are REST-only, gated behind `MCP_TOKEN`.

## Quickstart

Guardian installs from a single self-contained installer binary that pins every image by digest — see [`installer/`](installer/) (built by [`installer/build-guardian-installer.sh`](installer/build-guardian-installer.sh)). Each release ships all images at one `vX.Y.Z` tag; the pipeline mechanics are in [`docs/CICD.md`](docs/CICD.md).

## Repo layout

See [`CODEBASE_MAP.md`](CODEBASE_MAP.md) for the structural map — top-level groups first, then the modules inside each.

## Working on the codebase

- [`CLAUDE.md`](CLAUDE.md) — repo-wide agent-behavior contracts + critical gotchas (Claude Code).
- [`AGENTS.md`](AGENTS.md) — the same briefing for other coding agents, including the remote-VM workflow.
- [`AI-LAYER.md`](AI-LAYER.md) — the coding-agent harness (hooks, skills, MCP servers, subagents, plugin marketplace).

Quick local pre-deploy gate:

```bash
cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build
cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x
```

## License

See [`LICENSE`](LICENSE).
