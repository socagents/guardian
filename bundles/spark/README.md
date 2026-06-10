# Phantom Spark Agent Bundle (v1.2)

This directory is the Spark-compatible bundle for Phantom, conforming
to **agent-bundle schema v1.2** as defined in
[`kite-production/spark-agents`](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md).

```
bundles/spark/
├── manifest.yaml                      schema 1.2 — declares connectors,
│                                      embedded MCP, setup-bound instances
├── prompts/system.md
├── skills/                            5 markdown skill cards
├── kbs/phantom-soc/                   bundled SOC knowledge base
├── ui/a2ui/                           A2UI v0.8 setup/chat/settings/activity surfaces
├── mcp/                               embedded MCP server (v1.2)
│   ├── server.yaml
│   └── README.md                      (impl source — phase 2 follow-up)
└── connectors/                        tool-providing connectors (v1.2)
    ├── caldera/connector.yaml         60+ tools — abilities, adversaries,
    │                                  operations, agents, facts, ...
    ├── xsiam/connector.yaml           15+ tools — XQL queries, cases,
    │                                  datasets, lookups, assets, issues
    └── xlog/connector.yaml            10+ tools — workers, scenarios,
                                       observables, validation, coverage
```

## Connector model (v1.2)

The bundle follows the spec's split between two connector kinds:

- **Messaging connectors** (`manifest.yaml:messagingConnectors`) —
  Slack/Discord/Gmail-style services that route inbound chat to the
  agent. **Phantom uses none.** The agent is driven via its own A2UI
  surface, not inbound chat.

- **Tool-providing connectors** (`manifest.yaml:toolConnectors[]` +
  `connectors/<id>/connector.yaml`) — services the agent CALLS to do
  its work. Phantom ships three: `caldera`, `xsiam`, `xlog`. Each
  connector lives entirely in this bundle (source under
  `connectors/<id>/src/` — phase 2 follow-up); the embedded MCP at
  `mcp/` aggregates their tool catalogs into one MCP endpoint the
  agent talks to.

## Per-connector summary

| Connector | Tools | Required at setup | Backing service |
|---|---|---|---|
| `caldera` | 60+ | No (agent degrades — no adversary emulation) | MITRE Caldera v5.x server (existing `caldera` compose service, `aymanam/caldera:5.3.0`) |
| `xsiam` | 15+ | No (agent degrades — no detection validation) | Cortex XSIAM tenant via PAPI (operator's own — no in-cluster service) |
| `xlog` | 10+ | **Yes** (log generation is the agent's core capability) | New `xlog` service — phase 2 will extract this from the existing GraphQL `phantom` service ([main.py](../../main.py) + [app/](../../app/)) into a standalone HTTP service |

## Setup-bound instances

Per the v1.2 model, **no tool-connector instances are hardcoded in
the manifest**. Instead, `setup.bindsInstances[]` declares one
template per connector, and the runtime materializes one
`connector_instances` row per template when the operator submits the
setup form. The form fields each template references (e.g.
`${setup.calderaBaseUrl}`, `${setup.xsiamPapiUrl}`,
`${setup.xlogApiToken}`) are auto-rendered by the standalone runtime
from each connector.yaml's `configSchema` + `secretSlots` — see spec
v1.2 §7.5 mode resolution for the standalone vs Spark-platform fork.

## Mode resolution (where the MCP runs)

Per spec §7.5, the same bundle behaves identically in both modes
**except** for who hosts the MCP and where instances are stored:

| | **Standalone** | **Spark-platform** |
|---|---|---|
| Embedded MCP | Spawned from `bundles/spark/mcp/` | NOT spawned — `connector-manager` MCP supersedes it |
| Tool connectors | Loaded into embedded MCP from `bundles/spark/connectors/<id>/` | For each entry: `gateway.PublishConnector` → admin approval → registered with `connector-manager` |
| Tool-connector instances | `data_root/instances.db` (from setup form) | Postgres `connector_instances` (from same form, server-side) |
| Setup UI | Bundle's standalone CLI hosts the A2UI surfaces | Spark workspace UI renders the same A2UI manifest |
| Tool namespace seen by the agent | `caldera/*`, `xsiam/*`, `xlog/*` | Same |

## Phase status

| | Stage | Status |
|---|---|---|
| 3A | Foundation: instance store + per-tool config injection via contextvar | ✅ |
| 3B | Instance-gated tool advertisement (objective 5) | ✅ |
| 3C-1 | MCP HTTP admin API (instance CRUD + setup-submit, bearer-auth) | ✅ |
| 3C-2 | Next.js setup form wired to MCP `/api/v1/setup` (objective 3) | ✅ |
| **3D** | **MCP runtime moves INTO the bundle** (objective 1) | ✅ |
| 3E | Spark-platform supersession (objective 6) | ⏳ |
| 3F | xlog service extraction (replaces legacy GraphQL phantom service) | ⏳ |

The bundle now genuinely owns its MCP runtime. `phantom-mcp` Docker
service builds from `./bundles/spark/mcp/`. The old
`mcp/server/` directory has been deleted. Connector-specific
shared infra (`pkg/caldera_factory` etc.) moved INTO each connector's
`src/` (as `_factory.py`, `_papi_client.py`, `_xql_enrichment.py`,
`_graphql_client.py`). The bundle is the deployment unit.

The legacy compose-native bundle at
[`bundles/phantom-agent.bundle.yaml`](../phantom-agent.bundle.yaml)
references the new paths; it predates the v1.2 spec but stays in
place as documentation of the compose-native deployment model.

## References

- [Spark agent-bundle spec v1.2](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md)
- [Mode resolution (spec §7.5)](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md#75-mode-resolution)
- [Tool-connector schema (spec §7.4)](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md#74-tool-connector-schema-connectorsidconnectoryaml)
- Reference example bundle: [`examples/incident-triage/`](https://github.com/kite-production/spark-agents/tree/main/examples/incident-triage)
- Upstream Spark connector schema source of truth:
  [`connector-manager/internal/mcp/pg_instance_store.go`](https://github.com/kite-production/spark/blob/main/services/connector-manager/internal/mcp/pg_instance_store.go)
