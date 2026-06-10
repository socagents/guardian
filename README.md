<table>
  <tr>
    <td width="180" valign="top">
      <img src="logos/phantom-white.gif" alt="PHANTOM logo" width="160">
    </td>
    <td valign="top">
      <h1>PHANTOM</h1>
      <p>Continuous SOC simulation. Test your detection coverage with synthetic logs, scenario-based MITRE ATT&amp;CK telemetry, and AI-orchestrated red/blue workflows.</p>
      <p><strong>Category:</strong> SOC SIMULATION</p>
    </td>
  </tr>
</table>

Phantom ships as a **spark-agents v1.2** bundle. It generates synthetic security logs, runs MITRE ATT&CK scenarios end-to-end against your detection stack, and exposes everything as MCP tools the agent can chain through skills + an A2UI-rendered chat surface.

## At a glance

| Service | Purpose | Port |
|---|---|---|
| `phantom-agent` | Next.js operator UI **+** embedded MCP (single trust boundary, single container, two processes) | 3000 (UI), 8080 (MCP) |
| `xlog` | Synthetic-log generator (FastAPI + Strawberry GraphQL) | 8000 |
| `caldera` | Red-team operations backend (MITRE Caldera 5.3.0) | 8888, 8443 |

The agent's behavior is entirely encoded in the bundle (`bundles/spark/`) — manifest, connectors, providers, prompts, skills, knowledge bases, and A2UI surfaces. The image is content-addressed; everything operator-supplied (URLs, credentials, settings) flows in through the **first-run setup form** at `http://<host>:3000`.

## Two deployment shapes

| Shape | When to use | Guide |
|---|---|---|
| **All-in-one** | Single operator, demo/POC, or you want xlog/caldera installed alongside the agent | [`docs/quickstart-all-in-one.md`](docs/quickstart-all-in-one.md) |
| **Split-deploy** | Agent on a small low-privilege host; xlog/caldera operated by another team on a beefier red-team box | [`docs/split-deploy.md`](docs/split-deploy.md) |

Switching between them is non-destructive: the `phantom_mcp_data` volume holding your audit log, KB, sessions, and instance configs is portable. See **Backup & restore** below.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for diagrams covering deployment topology, runtime data flow, and the CI/CD pipeline.

The short version:

- **One image, two processes**: `phantom-agent` runs Next.js (UI) and the embedded MCP (Python) in the same container. The MCP is part of the agent's trust boundary, not a sibling service. This is per the spark-agents v1.2 bundle spec and what makes the slim split-deploy bundle viable (one image to ship).
- **No env vars for behavior**: the operator fills out a setup form at first run. Form values write into the Phase-5 SecretStore (mode-0700 file vault for secret values; sqlite paths in the metadata stores). Container restarts preserve everything.
- **Tools are gated**: a connector's tools are advertised ONLY when at least one connector instance has been materialized via the setup form. Slim deploys before setup show only built-in cognitive tools.

## API surface

All operator + integration endpoints live at `/api/v1/*` on port 8080. See [`docs/api-reference.md`](docs/api-reference.md) for the full enumeration.

Highlights:

- `/setup`, `/instances`, `/providers` — first-run materialization + post-setup CRUD
- `/audit` — append-only forensic event log (per-event row with actor + duration + status)
- `/sessions`, `/memories`, `/context` — cognitive layer (Phase 8)
- `/kbs` — knowledge bases ingested from `bundles/spark/kbs/`
- `/jobs` — cron schedule introspection (manifest.jobs[])
- `/settings` — runtime overrides for manifest.settings.overridable
- `/api_keys` — operator-minted long-lived keys for external integrations (scoped, revocable, audit-logged)
- `/notifications` — manifest.notifications.topics[] dispatch + ack
- `/telemetry` — opt-in usage counters (privacy-by-default OFF)
- `/media` — file upload with content extraction
- `/metrics` — Prometheus 0.0.4 text exposition (UNAUTHENTICATED for scrape compatibility)
- `/ui/*` — A2UI v0.8 surface streaming for the renderer

## Bundle exports

```bash
# Full all-in-one bundle (~3 GB tarball: every image + compose + scenarios)
BUNDLE_MODE=full scripts/export_agent_bundle.sh

# Slim agent-only bundle (~3 GB tarball: just phantom-agent + agent-only compose)
BUNDLE_MODE=agent-only scripts/export_agent_bundle.sh
```

CI exports BOTH on every push to `main`; both are uploaded as artifacts with 1-day retention.

## Backup & restore

```bash
scripts/backup_phantom.sh --label pre-upgrade
# → ./phantom-backup-pre-upgrade-<UTC stamp>.tar.gz
# (sha256 + manifest of all volume + bind-mount state)

scripts/restore_phantom.sh phantom-backup-pre-upgrade-<UTC stamp>.tar.gz
# Refuses to clobber non-empty targets unless --force.
```

What's captured: `phantom_mcp_data` volume (audit log, instance store, secret paths, KB, sessions, memory, jobs, settings, api_keys, notifications, telemetry, media metadata), `phantom_mcp_skills` volume (skills library), and `./.phantom-agent/` (setup form values + generated env snapshot).

## Project layout

```
phantom/
├── bundles/spark/             # spark-agents v1.2 bundle source
│   ├── manifest.yaml          # capability declarations
│   ├── connectors/            # Caldera + XSIAM + xlog tool definitions
│   ├── providers/             # Vertex (Gemini chat + embeddings)
│   ├── prompts/               # System prompt + standing orders
│   ├── kbs/                   # Knowledge bases
│   ├── ui/a2ui/               # A2UI v0.8 surfaces (manifest, catalogs, JSONL)
│   └── mcp/                   # Embedded MCP server source
│       ├── src/
│       │   ├── api/           # /api/v1/* HTTP routes
│       │   ├── usecase/       # Stores (audit, instance, settings, …)
│       │   ├── pkg/           # Shared clients (graphql, papi, caldera, embeddings)
│       │   └── service/phantom_mcp/
│       └── tests/
├── mcp/agent/                 # Next.js UI (combined image with embedded MCP)
├── xlog/                      # Synthetic-log generator (FastAPI + Strawberry)
├── third_party/caldera/       # MITRE Caldera 5.3.0 source submodule
├── scripts/                   # Operator + CI helpers (export, backup, restore)
├── docs/                      # Operator-facing docs
└── docker-compose*.yml        # Two compose recipes (full + agent-only)
```

## Working on the codebase

The local repo is for editing + version control. Builds, deploys, tests, and container runs all happen on the remote `phantom` VM in GCP — see [`CLAUDE.md`](CLAUDE.md) for the IAP-tunnel + sshpass workflow.

Quick remote runs once your shell has `.env.vm` loaded:

```bash
# MCP server tests inside the freshly built image
… "cd $VM_REMOTE_REPO/bundles/spark/mcp && pytest"

# Agent lint + build
… "cd $VM_REMOTE_REPO/mcp/agent && npm run lint"

# Full Phase 5–11a smoke test (HTTP-driven, 31 assertions)
… "cd $VM_REMOTE_REPO && MCP_TOKEN=\$(docker compose exec -T phantom-agent printenv MCP_TOKEN) ./bundles/spark/mcp/scripts/smoke_test.sh"
```

## License

See [`LICENSE`](LICENSE).
