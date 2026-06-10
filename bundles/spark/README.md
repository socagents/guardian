# Guardian Spark Agent Bundle (v1.2)

This directory is the Spark-compatible bundle for Guardian, conforming
to **agent-bundle schema v1.2** as defined in
[`kite-production/spark-agents`](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md).

Guardian is an AI incident-response agent: it investigates security
incidents in integration with Cortex XSOAR / XSIAM — evidence
gathering, XQL queries, incident enrichment, and response
orchestration.

```
bundles/spark/
├── manifest.yaml                      schema 1.2 — declares connectors,
│                                      embedded MCP, setup-bound instances
├── prompts/system.md                  the agent's system prompt
├── kbs/xql-examples/                  bundled XQL knowledge base —
│                                      curated Cortex XQL queries served
│                                      via the runtime's knowledge_search
├── providers/vertex/                  model-provider plugin (Vertex AI)
├── plugins/                           operator-installed runtime plugins
├── mcp/                               embedded MCP server (Python FastMCP)
│   ├── src/                           server source — see mcp/CLAUDE.md
│   ├── skills/                        default skill cards baked into the
│   │                                  agent image, volume-seeded at boot
│   └── tests/                         pytest suite (~349 tests)
└── connectors/                        tool-providing connectors
    ├── connector.schema.json          JSON-Schema validator for every
    │                                  connector.yaml (boot + upload time)
    ├── _runtime/                      shared connector-runtime base
    ├── xsiam/                         Cortex XSIAM PAPI — XQL queries,
    │                                  cases, issues, datasets, lookups
    ├── cortex-xdr/                    Cortex XDR API — cases + issues
    ├── cortex-docs/                   Cortex documentation search
    ├── cortex-content/                Cortex content catalog (baked,
    │                                  zero outbound network at runtime)
    └── web/                           web browsing via Playwright +
                                       headless Chromium (browser sidecar)
```

## Connector model (v1.2)

The bundle follows the spec's split between two connector kinds:

- **Messaging connectors** (`manifest.yaml:messagingConnectors`) —
  Slack/Discord/Gmail-style services that route inbound chat to the
  agent. **Guardian uses none.** The agent is driven via its own A2UI
  surface, not inbound chat.

- **Tool-providing connectors** (`manifest.yaml:toolConnectors[]` +
  `connectors/<id>/connector.yaml`) — services the agent CALLS to do
  its work. Each connector lives entirely in this bundle (source under
  `connectors/<id>/src/`); the embedded MCP at `mcp/` aggregates their
  tool catalogs into one MCP endpoint the agent talks to. Tools
  dispatch to per-instance connector containers over HTTP — see
  [`connectors/CLAUDE.md`](connectors/CLAUDE.md) for the authoring
  pattern and runtime style.

## Per-connector summary

| Connector | Tool prefix | Backing service |
|---|---|---|
| `xsiam` | `xsiam_` | Cortex XSIAM tenant via PAPI (operator's own — no in-cluster service) |
| `cortex-xdr` | `xdr_` | Cortex XDR Public API (operator's own tenant) |
| `cortex-docs` | `cortex_` | Cortex documentation search |
| `cortex-content` | `cortex_` | Baked content catalog shipped inside the agent image — no backing service |
| `web` | `phantom_web_` | Headless-Chromium sidecar (CDP), profile-gated in compose |

No connector is required at setup time — tool advertisement is
instance-gated, so a connector's tools only appear in the agent's
catalog once the operator creates an instance via the `/connectors`
UI.

## Setup-bound instances

Per the v1.2 model, **no tool-connector instances are hardcoded in
the manifest**. Instead, `setup.bindsInstances[]` declares one
template per connector, and the runtime materializes one
`connector_instances` row per template when the operator submits the
setup form. The form fields each template references (e.g.
`${setup.xsiamPapiUrl}`) are auto-rendered by the standalone runtime
from each connector.yaml's `configSchema` + `secretSlots` — see spec
v1.2 §7.5 mode resolution for the standalone vs Spark-platform fork.

## Mode resolution (where the MCP runs)

Per spec §7.5, the same bundle behaves identically in both modes
**except** for who hosts the MCP and where instances are stored:

| | **Standalone** | **Spark-platform** |
|---|---|---|
| Embedded MCP | Spawned from `bundles/spark/mcp/` inside the agent container | NOT spawned — `connector-manager` MCP supersedes it |
| Tool connectors | Loaded into embedded MCP from `bundles/spark/connectors/<id>/` | For each entry: `gateway.PublishConnector` → admin approval → registered with `connector-manager` |
| Tool-connector instances | `data_root/instances.db` (from setup form) | Postgres `connector_instances` (from same form, server-side) |
| Setup UI | Bundle's standalone CLI hosts the A2UI surfaces | Spark workspace UI renders the same A2UI manifest |
| Tool namespace seen by the agent | `xsiam/*`, `cortex-xdr/*`, `web/*`, … | Same |

## References

- [Spark agent-bundle spec v1.2](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md)
- [Mode resolution (spec §7.5)](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md#75-mode-resolution)
- [Tool-connector schema (spec §7.4)](https://github.com/kite-production/spark-agents/blob/main/docs/spec.md#74-tool-connector-schema-connectorsidconnectoryaml)
- Reference example bundle: [`examples/incident-triage/`](https://github.com/kite-production/spark-agents/tree/main/examples/incident-triage)
- Upstream Spark connector schema source of truth:
  [`connector-manager/internal/mcp/pg_instance_store.go`](https://github.com/kite-production/spark/blob/main/services/connector-manager/internal/mcp/pg_instance_store.go)
