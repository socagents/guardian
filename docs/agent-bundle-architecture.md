# Phantom Agent Bundle Architecture

Phantom is moving from a Docker Compose application into a portable agent product that can be imported into an agentic orchestration platform or launched standalone.

The target model now has two compatible bundle surfaces:

- `bundles/spark/` is the Spark-compatible projection that follows the `spark-agents` schema v1.1 shape: `manifest.yaml`, `prompts/`, `skills/`, `kbs/`, and A2UI v0.8 surfaces.
- `bundles/phantom-agent.bundle.yaml` is the compose-native implementation bundle that knows how to run the current Phantom service stack: `phantom`, `phantom-mcp`, `phantom-agent`, and `caldera`.

The Spark bundle is the import contract for Spark-style orchestration. The compose bundle is the current standalone implementation path until the generic Spark runtime can host Phantom's MCP and service dependencies directly.

## Connector Resolution

Phantom follows the Spark bundle standard by declaring external services as `dependencies` and `instances` in `bundles/spark/manifest.yaml`.

- In standalone mode, XSIAM, Caldera, Xlog, and Phantom services are assumed to be running outside the agent. Operators provide connection settings such as `mcpUrl`, `calderaUrl`, `xsiamPapiUrl`, `webhookEndpoint`, `xlogEndpoint`, and `defaultLogDestination`, plus secret bindings for the declared secret paths.
- In Spark platform mode, Spark materializes the same connector declarations through connector-manager. The agent uses the same tool names and instance names, but the platform owns connector lifecycle, credentials, routing, and shared state.
- The `connectorResolution: auto` setting means "prefer Spark-managed connectors when attached to Spark; otherwise use standalone endpoint bindings."

This keeps the Phantom bundle portable without embedding XSIAM, Caldera, or log collector services inside the agent runtime.

## Diagram Mapping

| Spark diagram group | Phantom equivalent today | Missing or partial |
|---|---|---|
| Identity and config | `bundles/spark/manifest.yaml`, compose service names, repo metadata, UI auth, MCP token | Cosign signing still uses placeholder metadata |
| Cognitive layer | Spark model requirements, persistent sessions, bundled prompt, Vertex/Gemini orchestration | Full `AgentEnvironment` adapter for Phantom services still pending |
| Tool surface | FastMCP tools declared in Spark `tools.allow`, curated `bundles/tool-catalog.yaml`, generated `tool-snapshot.json` | Spark connector-manager adapter still pending |
| Memory | Spark memory declaration plus SQLite `/data/phantom.db`, MCP skills volume, Caldera volumes, optional state export/import | Spark-native state materialization pending |
| Knowledge bases | Spark `kbs/phantom-soc`, MCP skills, XQL resources, scenarios | Wider scenario-to-KB generation pending |
| Run state | Persistent simulations, workers, validations, artifacts | Restore/rebind workflows for imported bundles |
| Integration surface | Spark connector declarations for Phantom MCP plus optional Caldera MCP, XSIAM MCP, and Xlog MCP instances; MCP/REST/GraphQL endpoints | Marketplace connector packages still pending |
| UI bundle | Spark A2UI v0.8 setup/chat/settings/activity surfaces plus current Phantom Next.js renderer | Spark A2UI renderer implementation is tracked upstream |
| Secrets | Spark `requiredSecrets`, `secret-bindings.example.yaml`, generated `.env.secret-refs`, optional file/HTTP provider binding | Infisical/platform adapter still pending |
| Observability | Spark observability metrics/events plus Compose healthchecks, smoke tests, and `observability.contract.yaml` | OpenTelemetry instrumentation still pending |

## Bundle Objective

The import artifact should make Phantom understandable to an orchestration platform without reading the repository:

1. Verify bundle integrity.
2. Discover required Docker images and optional included image archives.
3. Materialize the agent runtime.
4. Rebind secrets from the target platform secret provider.
5. Register MCP, REST, GraphQL, UI, and webhook interfaces.
6. Restore persistent memory/state when included.
7. Run standalone when no orchestration platform is present.
8. Render the agent UI from A2UI JSON using either the platform renderer or Phantom's standalone renderer.

## Bundle Shape

The Spark-compatible bundle root is `bundles/spark/`.

The compose-native canonical file is `bundles/phantom-agent.bundle.yaml`.

The YAML is intentionally secret-free. It can reference:

- Docker image names/tags and local artifact paths.
- Secret names such as `MCP_TOKEN` or `GOOGLE_APPLICATION_CREDENTIALS`.
- Volume names and restore modes.
- Interface definitions and health probes.
- Tool groups and package capabilities.
- A2UI manifest, component catalog, surfaces, event schema, and data model schema.

For air-gapped or no-registry imports, the export script packages Docker images as tar archives beside the YAML. The YAML remains the import contract and points at those image archive paths. Embedding full image bytes directly into YAML is possible but not recommended because it makes the file huge and hard to sign or diff.

## Initial Gaps To Build

1. **Bundle manifest validation**
   - Add a schema or validator for `phantom.agentic/v1alpha1`.
   - CI should validate the manifest against Compose and known MCP tools.

2. **Tool catalog snapshot**
   - Current: curated tool catalog and allow/deny policy file.
   - Done: export live MCP tool names, descriptions, and Gemini-compatible sanitized schemas into `tool-snapshot.json`.
   - Done: validate snapshot drift against the curated allow/deny policy during bundle export.
   - Next: add a platform-side policy editor for allow/deny changes.

3. **State export and import**
   - Current: optional export copies SQLite, MCP skills, and Caldera state from running containers when `INCLUDE_STATE=1`.
   - Done: import can restore state artifacts into target Docker volumes when `RESTORE_STATE=1`.
   - Done: UI now exposes agent bundle readiness and platform health probes.
   - Next: add a UI or orchestrator confirmation flow before overwriting existing target volumes.

4. **Secrets rebinding**
   - Current: rebinding map from Phantom env vars to target orchestration secret references.
   - Done: import materializes `.env.secret-refs` with provider references, not raw values.
   - Done: optional file/HTTP provider adapter registers references with a target provider when `BIND_SECRET_PROVIDER=1`.
   - Next: add first-class adapters for the target orchestration platform and Infisical.

5. **Image packaging**
   - Save `phantom:local`, `phantom-mcp:local`, `phantom-agent:local`, and `caldera:local` as local image archives when requested.
   - Record SHA-256 checksums in the bundle output.

6. **Orchestrator interface**
   - Current: lifecycle commands for install/start/stop/restart/status/health/logs/export.
   - Done: Next.js runtime endpoints expose manifest, health, guided workflows, and report proxying under `/api/agent/*`.
   - Done: A2UI runtime endpoints expose UI manifest, Phantom component catalog, JSONL surfaces, and named UI events under `/api/a2ui/*`.
   - Next: add callback/webhook declarations and direct MCP invocation endpoints with policy enforcement.

7. **A2UI portable UI contract**
   - Done: bundle includes `a2ui/manifest.json`, `a2ui/catalogs/phantom-ui.v0.1.json`, surface JSONL files, data model schema, and event schema.
   - Done: bundle metadata declares A2UI as the importable UI contract and keeps `phantom-agent` as the standalone renderer.
   - Done: first-run setup is exposed as both a standalone Next.js setup page and an A2UI `setup` surface.
   - Next: map Phantom A2UI catalog components to renderer components in the target orchestration platform.

8. **Standalone first-run setup**
   - Done: `phantom-agent` opens a setup flow when required runtime values are missing.
   - Done: setup accepts a Google service account JSON upload, defaults `GEMINI_MODEL` to `gemini-3.1-pro-preview`, collects UI access, and binds MCP connector URLs/tokens. Downstream XSIAM, Xlog, and Caldera service secrets stay in their connector services.
   - Done: setup writes host-local runtime material under `.phantom-agent/` and emits `.phantom-agent/.env.generated` for Compose restarts.
   - Done: `scripts/agent_lifecycle.sh apply-setup` copies the generated env into `.env` and recreates the stack.

9. **Spark-compatible bundle projection**
   - Done: `bundles/spark/manifest.yaml` follows Spark schema v1.1.
   - Done: Spark bundle includes `prompts/`, `skills/`, `kbs/`, and A2UI v0.8 UI surfaces.
   - Done: validation and export helpers are available at `scripts/validate_spark_bundle.py` and `scripts/export_spark_agent_bundle.sh`.
   - Next: implement Phantom service adapters in the Spark runtime or connector-manager so the generic runtime can execute the declared tools directly.

10. **Signature and provenance**
   - Done: produce `bundle-manifest.json`, `checksums.sha256`, and optional `bundle-signature.json` using HMAC-SHA256.
   - Next: add cosign-style attestation or platform-native signing.

## Proposed Build Phases

### Phase 1: Bundle Contract

- Add `bundles/phantom-agent.bundle.yaml`.
- Add a remote-side export script that packages manifest, Compose file, and local Docker images.
- Keep secret-bearing volumes, such as Caldera `conf`, out of state exports.
- Keep GitHub Actions as the authoritative remote build path.

### Phase 2: Runtime Import

- Add an import/materialize script for target hosts. **Done for standalone image loading and env template generation.**
- Recreate volumes and load image archives. **Image archive loading and opt-in volume restore done.**
- Apply target secret bindings. **Template, provider-reference materialization, and optional file/HTTP provider registration done.**

### Phase 3: Agent Orchestrator API

- Add REST endpoints for lifecycle and package metadata. **Runtime manifest, health, workflow, and report endpoints done.**
- Add a MCP tool for exporting the current agent bundle.
- Add a UI panel for “Export Agent Bundle”. **Readiness panel done; direct export trigger still pending.**

### Phase 4: Signed Product Bundle

- Generate checksums.
- Sign bundle metadata. **Optional HMAC signing done.**
- Verify before import. **Checksum and optional signature verification done.**

## Connector Runtime Model — v0.1 (in-process) vs v0.2 (per-instance container)

### v0.1 (current default, all 4 bundled connectors)

Every connector's Python source is imported into the phantom-agent
container at MCP boot via `connector_loader.py:_resolve_callable`
when `connector.yaml`'s `runtimeMapping.style: module` (the default).
Tool calls execute in-process: FastMCP routes
`tools/call <connector>/<tool>` to the imported function. The
function reads per-instance config via `from config.config import
get_config` whose contextvar is set by `_wrap_with_instance` for
each call. Network egress to backend services (xlog, caldera,
external APIs) happens with phantom-agent's own outbound HTTP
client (httpx).

Properties:
- Latency: ms (function-call cost).
- Resource overhead: zero per connector.
- Crash scope: connector bug → whole agent process down.
- Dependency footprint: every new connector's deps land in the
  phantom-agent image. Image size grows monotonically.
- Isolation: weak. Two instances of the same connector share
  Python globals + module-level caches.

### v0.2 (foundation shipped in v0.1.30; first connector flips in v0.1.31)

When `runtimeMapping.style: container`, each connector instance
runs as its own container (`phantom-connector-<id>:<version>`,
inheriting from `phantom-connector-runtime`). The agent's MCP
becomes a routing proxy that forwards `tools/call` over MCP-over-
HTTP to the connector container's own MCP server (FastMCP on port
9000 by default). See `docs/spec-per-instance-connector-containers.md`
for the architectural rationale + design decisions.

Lifecycle is managed by phantom-updater's new endpoints:
`POST /api/v1/connectors/<id>/instances/<name>/{start,stop,restart}`
+ `GET .../status`. Each `start` pulls the image (with retry/
backoff for offline-deploy), launches the container on the
compose network with `phantom_mcp_data` mounted read-only at
`/app/data`, and notifies the agent via
`PUT /api/v1/instances/<id>/container_url` to update the routing
entry the loader's container branch reads at the next tool call.

Properties:
- Latency: ~10-30 ms per call (HTTP roundtrip + MCP handshake on
  local Docker network).
- Resource overhead: ~50-100 MB RAM per container, idle CPU.
- Crash scope: connector bug → only that container restarts via
  `restart: unless-stopped`; agent unaffected.
- Dependency footprint: each connector's deps live in its own
  image; agent image stays lean.
- Isolation: strong. Each container has its own FastMCP server,
  its own contextvar state, its own filesystem.
- Third-party connector story: anyone can ship a Phantom connector
  as a standalone MCP-server container — no monorepo PR required.

### Migration phases

| Release | Phase | What changes for operators |
|---|---|---|
| v0.1.29 | (baseline) | All connectors style: module |
| v0.1.30 | Phase 1: Foundation | Infrastructure ships dormant; no behavior change |
| v0.1.31 | Phase 2: Pilot | `web` connector flips to style: container |
| v0.1.32 | Phase 3a | `xsiam` flips |
| v0.1.33 | Phase 3b | `xlog` flips |
| v0.1.34 | Phase 3c | `caldera` flips |
| v0.2.0  | Phase 4 | In-process loader removed; third-party support opens |

### How to write a new connector under v0.2

See `bundles/spark/connectors/_runtime/README.md` for the runtime
contract + a working reference skeleton with `Dockerfile`,
`connector.yaml`, and one demo tool.
