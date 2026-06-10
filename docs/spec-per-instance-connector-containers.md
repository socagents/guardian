# Spec patch: per-instance connector containers (v0.2 architecture)

> **Audience**: Guardian maintainers + Spark v1.3 spec contributors. This is
> a roadmap spec — code changes land across multiple v0.1.x → v0.2.0
> releases. Write-once / read-often.
>
> **Status**: Draft, pre-implementation. Phase 1 work begins after this
> spec is reviewed.
>
> **Date**: 2026-05-07.
>
> **Replaces**: nothing, but materially extends `agent-bundle-architecture.md`
> §"Connector runtime model".

## Why this spec exists

The `agent-bundle-architecture.md` defines the connector model as
"each connector ships in `bundles/<bundle>/connectors/<id>/` with a
`connector.yaml` declaring its tool surface, and the runtime
materializes connector tools in the agent's MCP at boot." The Spark
spec v1.2 hints at a per-call lifecycle ("connector functions are
spawned per-invocation in the runtime") without nailing down the
deployment shape. Guardian's v0.1.x implementation collapses this
distinction by running every connector's code **in-process inside the
guardian-agent container**, treating connectors as Python modules that
the embedded MCP imports at boot.

That choice was right for v0.1: lowest possible latency, simplest
debug story, no new infrastructure. As Guardian approaches v0.2 the
trade-offs are flipping:

- **Dependency footprint**: every new connector adds its deps into
  the guardian-agent image. v0.1.27 added playwright + trafilatura
  (~10 MB lib + ~250 MB if Chromium were inline). v0.1.x added
  google-auth + chromadb-clients-since-removed + pypdf. The image is
  growing monotonically.
- **Crash blast radius**: a buggy connector or runaway tool call
  takes down guardian-agent (and thus the chat UI + the embedded MCP
  + all other connectors).
- **Cross-instance state isolation**: web connector v0.1.27 has page
  registries keyed by session_id; if a customer ever runs two web
  connector instances (one for proxy A, one for proxy B), they share
  the same Python process and all that implies.
- **No third-party connector story**: the only way to add a
  connector today is to write Python in the Guardian monorepo and
  ship it bundled. There's no path for a customer or partner to
  ship their own connector image without a Guardian release.

Per-instance containers solve all four. The cost is non-trivial
engineering complexity, which is why this is a v0.2 program rather
than a v0.1.x patch.

## What runs where today

```
┌──────────────────────────────────────────────────────────────┐
│ guardian-agent container (Python 3.12, Next.js, single proc) │
│                                                               │
│  Embedded MCP (FastMCP, port 8080)                           │
│   ├─ xsiam connector code     ← bundles/spark/connectors/    │
│   │                             xsiam/src/*.py imported at   │
│   │                             boot via importlib            │
│   ├─ cortex-docs connector    ← same pattern                 │
│   └─ web connector code       ← same pattern (v0.1.27+)     │
│                                                               │
│  Per tool call:                                              │
│   1. agent → MCP /tools/call <connector>/<tool>              │
│   2. _wrap_with_instance sets instance config contextvar     │
│   3. wrapped Python function executes in-process             │
│   4. function makes outbound HTTP/WS to backend service:     │
│      - xsiam → https://api-tenant.../public_api/v1           │
│      - web → http://guardian-browser:9222 (CDP)               │
│   5. function returns; result wraps back through FastMCP     │
└──────────────────────────────────────────────────────────────┘
        │
        │ Docker network "guardian_default"
        ↓
┌──────────────────┐
│ guardian-browser  │
│ container        │
│ (chromedp/chrome)│
└──────────────────┘
```

**Key properties of today's model:**

- Connector code = Python modules in the agent's process.
- Per-instance config = ContextVar set by a wrapper at call time
  (see `connector_loader.py:_wrap_with_instance`).
- Per-tool latency = function-call cost (~ms).
- Resource overhead = negligible (no extra processes per
  connector or per instance).
- Crash scope = one connector bug → whole agent process.

## What we're moving to

```
┌──────────────────────────────────┐    ┌──────────────────────────────────┐
│ guardian-agent container          │    │ guardian-connector-xsiam-primary │
│                                   │    │ (one container per instance)    │
│  Embedded MCP (port 8080)        │    │                                  │
│   ├─ Routing table:              │←──→│  FastMCP (port 9000)            │
│   │   xsiam/* →                  │MCP │   ├─ tools/list returns xsiam/* │
│   │     xsiam-primary:9000       │    │   └─ tools/call executes xsiam  │
│   │   web/* → web-primary:9000   │    │                                  │
│   │   ...                        │    │  Outbound to XSIAM PAPI:        │
│   └─ Per call: forward to        │    │   POST https://api-tenant.../   │
│      connector instance's MCP    │    └──────────────────────────────────┘
└──────────────────────────────────┘                ↓
        │                                     (customer's XSIAM tenant,
        │                                      external SaaS, unchanged)
        │
        ↓
┌──────────────────────────────────┐
│ guardian-connector-web-primary    │
│ (FastMCP + playwright client)    │ ←—→ guardian-browser:9222 (CDP)
└──────────────────────────────────┘
```

**Key properties of the target model:**

- Connector code = an MCP server running in its own container.
- One container per instance (not per connector). Two web instances
  = two containers, each with its own browser context registry.
- Per-instance config + secrets = baked into container at start
  time (env + mounted secret volume from the existing SecretStore).
- Per-tool latency = MCP roundtrip cost over local Docker network
  (~10-30ms; meaningfully more than in-process but comfortably under
  human perception for SOC tool calls).
- Resource overhead = N_instances × (~50-100 MB RAM, idle CPU).
- Crash scope = one connector bug → only that instance's container
  restarts; agent unaffected.
- Communication = MCP-over-HTTP between agent's MCP and each
  connector instance's MCP.

## Design decisions

Each decision below was made by ruling out alternatives. Anywhere
the alternative is plausible enough to revisit, I've called it out
explicitly.

### D1: Lifecycle = persistent-per-instance, not per-call

**Chosen**: One long-lived container per connector instance, lives as
long as the instance does in `instance_store.db`.

**Alternatives ruled out**:

- *Cold-start per call*: 200-800 ms Docker spin-up cost dominates a
  SOC chat where the agent might call 5-10 tools per turn. Pure
  FaaS-style works for low-frequency triggers but not for chat
  latency.
- *Warm pool*: Pre-warm N containers per connector. Eliminates spin-up
  cost but adds pool-management complexity and resource overhead. The
  per-instance model achieves the same warmth without pool logic.
- *Persistent shared per connector* (the current shape): Brings back
  the cross-instance state-bleed problem we're trying to solve.

The persistent-per-instance choice maps cleanly onto Guardian's
existing instance-store mental model: an `instance` is a running
thing the operator manages. The container becomes the runtime
embodiment of that conceptual instance.

### D2: Communication protocol = MCP-over-HTTP between agent and connector

**Chosen**: Each connector container runs a FastMCP server on a
known port. The agent's embedded MCP becomes a router that proxies
`tools/call` requests to the right connector container's MCP.

**Why this is the right shape**:

1. **Reuses code paths**: agent already speaks MCP. The proxy logic
   is shorter than inventing a new RPC protocol.
2. **Standardizes the connector contract**: "a Guardian connector is
   an MCP server" — same surface, language-agnostic, testable with
   any MCP client.
3. **Streaming support**: MCP supports streaming responses out of
   the box, useful for long-running tools.
4. **Capability negotiation built-in**: connector containers
   advertise their tool catalog via `tools/list` at proxy-init time;
   agent doesn't need a separate config layer.
5. **Third-party connector story**: anyone writing a Guardian
   connector can deliver a standard MCP server in any language
   (Python, Go, Node, Rust). No custom Guardian SDK required.

**Alternatives ruled out**:

- *gRPC*: Strongly typed but adds protobuf compilation, debugging
  friction, and a new transport. The win over MCP-over-HTTP doesn't
  justify the cost in this codebase.
- *Unix domain sockets + custom framing*: Lower latency but harder
  to traverse container boundaries and impossible for the
  third-party-connector use case.
- *HTTP/REST*: Loses streaming + capability negotiation, no real
  win over MCP.

The agent's embedded MCP becomes a **proxy MCP**: it speaks MCP
upstream (to the agent's chat handler) and MCP downstream (to each
connector container). The proxy logic is simple — for any
`tools/call` whose name is namespaced `<connector>/<tool>`, look up
the routing table and forward.

### D3: Hosting = Docker, on the same Compose network

**Chosen**: Connector containers run on the same Docker daemon as
guardian-agent. guardian-updater (already in the stack with
docker.sock mounted) becomes the lifecycle manager.

**Why**:

- Guardian's customer-on-prem deployment is Docker Compose on a
  single VM. No Kubernetes, no Cloud Run.
- guardian-updater already has the docker.sock plumbing and
  authentication — extending it to manage connector containers is
  additive, not new infrastructure.
- The guardian-agent and connector containers share the
  `guardian_default` Docker network — networking "just works."

**Trade-offs accepted**:

- Single-host scaling limit. Guardian isn't multi-host today; this
  doesn't change that.
- N_instances containers on the host. Resource ceiling depends on
  customer deployment size; per-instance memory limits cap blast
  radius.

**Alternatives ruled out**:

- *Kubernetes*: would require k8s in every customer environment.
  Outside Guardian's deployment model.
- *Cloud Run / Lambda*: vendor lock-in; complicates customer-on-prem.
- *Compose service per instance*: docker-compose isn't designed for
  dynamic services. Generating compose at runtime defeats the
  point.

### D4: Image strategy = one image per connector, retagged per release

**Chosen**: Each connector ships as `ghcr.io/kite-production/guardian-connector-<id>:<version>`.
The release.yml conditional rebuild logic from v0.1.29 already knows
how to skip unchanged services — adding new entries here is purely
additive.

Image inheritance:
- A small `guardian-connector-runtime:<version>` base image holds
  the shared runtime: FastMCP, the SecretStore client library, the
  contextvar plumbing for per-instance config, observability
  (logging + audit hooks back to the agent's audit pipeline).
- Each connector's image is `FROM guardian-connector-runtime:<version>`
  + the connector's source + its specific deps.

**Why this shape**:

- Per-connector deps stay isolated. xsiam needs `httpx`; web needs
  `playwright + trafilatura`. None of these touch the agent's image.
- Conditional rebuild from v0.1.29 means the connector images
  retag (no real rebuild) when nothing in their source changed.
- Each connector image is independently pull-able by third
  parties — the open ecosystem story.

**Alternatives ruled out**:

- *One base + source mounted*: violates the immutable-artifact
  principle; operators would need filesystem coordination per
  release.
- *Per-instance image*: too many images for what's really
  per-instance configuration, not per-instance code.

### D5: Per-instance config delivery = SecretStore mount + env vars

**Chosen**: Container starts with:
- `GUARDIAN_SECRET_KEK` env var (the existing AES-256-GCM key).
- `guardian_secret_store` volume mounted read-only.
- `INSTANCE_ID` env var pointing the connector at its instance row.

At container boot, the connector reads its instance's config +
secrets from the SecretStore using the same library code that
guardian-agent uses today. No new secret-distribution mechanism.

**Why**:

- Reuses Guardian's existing Phase 5 SecretStore (encrypted-at-rest,
  KEK-bound). No new key plumbing.
- Operator UX: rotating a secret is the same operation
  whether the connector is in-process or in its own container.
- Read-only mount = container can't accidentally corrupt the store.

**Alternatives ruled out**:

- *Env-vars-only*: secrets visible to anyone with `docker inspect`.
- *Initial MCP handshake with secrets in the protocol*: works but
  adds protocol surface; SecretStore mount is simpler.
- *Operator-creds-style file-mount*: works for some categories, but
  SecretStore is the unified path.

### D6: Lifecycle management = guardian-updater extends to connectors

guardian-updater today handles agent + service updates via docker.sock.
Extending it to connector containers means:

- `POST /api/v1/connectors/<id>/instances/<name>/start` →
  guardian-updater pulls image, runs container, registers it on the
  Docker network, returns IP+port.
- `POST /api/v1/connectors/<id>/instances/<name>/stop` →
  guardian-updater stops + removes container.
- `GET /api/v1/connectors/<id>/instances/<name>/status` → reports
  container health, restart count, resource usage.
- `POST /api/v1/connectors/<id>/instances/<name>/restart` → forced
  restart (used by the operator when a container is wedged).

The agent's UI calls these via the existing guardian-updater proxy
path. Operators get a clean management surface without learning
docker commands.

**Container naming**: `guardian-connector-<id>-<instance-name>` (e.g.
`guardian-connector-xsiam-primary`, `guardian-connector-web-acme-vetted`).
Predictable, greppable, matches Guardian's existing container naming
(`guardian_agent`, `guardian_browser`).

**Network naming**: same `guardian_default` Docker network, so the
agent reaches connectors via container hostname + port:
`http://guardian-connector-xsiam-primary:9000/mcp`.

### D7: Failure modes

**Container crash**: Docker `restart: unless-stopped` (default).
Agent's MCP proxy keeps a connection per connector container; on
failure, it reconnects on next call (one retry, then surface error
to chat). Audit row records the crash.

**Container hang**: Per-call timeout in the agent's MCP proxy
(default 60 s, configurable). After timeout, agent surfaces
timeout error; guardian-updater optionally kills + restarts the
container.

**OOM**: Docker memory limit per container (default 256 MB,
configurable per connector via connector.yaml `runtime.memory`).
On OOM, container restarts, agent retries.

**Slow tool call (intentionally long-running)**: Long-running tools
(e.g. a tool that drives a long-running upstream job) MUST be
async-capable: return immediately with a job ID, agent polls. We
already do this for some tools; the per-container model makes it
mandatory for any tool exceeding the per-call timeout.

**Connector image pull failure** (first-time start with offline
deploy): guardian-updater retries with backoff; surfaces error to
the operator UI with actionable text ("guardian-connector-xsiam:0.2.0
not in local cache and registry unreachable; check network").

### D8: Observability

Each connector container's stdout/stderr lands in Docker's normal
log stream (greppable via `docker logs guardian-connector-xsiam-primary`).
Audit events from connector code → posted to the agent's audit
endpoint via HTTP (the connector container has an env var pointing
at the agent's audit URL). Same audit pipeline, no new sinks.

Per-container CPU + memory + network reachable via `docker stats`.
The agent's UI can surface these in `/connectors` per-instance.

## The runtime contract

A connector container must:

1. Start a FastMCP server on port 9000 (overridable via env).
2. Register its tools at boot. Tool names match the bare names from
   `connector.yaml`'s `spec.tools[]` — no functionPrefix needed
   anymore (the prefix was an in-process namespace trick; the
   container provides namespace isolation by construction).
3. Read its per-instance config via the SecretStore library at boot.
4. Implement `tools/list` and `tools/call` per the MCP spec (FastMCP
   does this automatically from registered tools).
5. Implement a `/health` HTTP endpoint that returns 200 when ready
   to serve. Used by Docker healthcheck + guardian-updater readiness.
6. Forward audit events via `POST <agent-audit-url>` for tools that
   want durable audit rows. Optional but encouraged.
7. Respect a `SHUTDOWN` signal cleanly (SIGTERM → drain in-flight
   calls → exit).

That's the entire contract. Anything else is connector-specific.

## What stays the same

This spec deliberately does NOT change:

- **`connector.yaml` schema**: configSchema, secretSlots, spec.tools[],
  runtimeMapping all preserved. The runtimeMapping field gains one
  new value (`style: "container"`) alongside the existing `module`,
  but old `module`-style connectors keep working until migrated.
- **Per-instance config + secrets shape**: same keys, same
  SecretStore. The only change is *who* reads them (the connector
  container instead of guardian-agent).
- **Approval gate**: still enforced agent-side (the approval bus
  lives in guardian-agent's MCP, where the chat session originates).
  Connector containers don't need approval logic; they just execute
  what the proxied call asks.
- **Audit log**: still one durable store in guardian-agent. Connector
  containers POST to the agent's audit endpoint; same rows, same
  queries.
- **Marketplace UX**: install/uninstall/instance-create flow stays
  the same shape from the operator's perspective. The "install"
  step pulls the connector image into the local Docker cache;
  "create instance" provisions a container.
- **Bundle structure**: `bundles/spark/connectors/<id>/` keeps the
  same layout. Adds an optional `Dockerfile` at the connector's
  root for the per-image build.

## Migration plan

Four phases, each independently shippable. Each phase preserves
backward compatibility — operators on N can run alongside operators
on N+1 without breakage.

### Phase 1 (v0.1.30): Foundation, no functional change

**Goal**: Build the runtime infrastructure without migrating any
connector. The agent still runs all connectors in-process; the new
machinery is dormant.

**Ships**:

- New base image `guardian-connector-runtime`: FastMCP +
  SecretStore client + audit forwarder + a "connector
  entrypoint" that loads the connector source and starts the MCP
  server.
- Empty per-connector image stubs (`guardian-connector-xsiam`,
  `guardian-connector-web`, `guardian-connector-cortex-docs`,
  `guardian-connector-cortex-content`) that build on the runtime +
  bundle the connector source. They're built and pushed by
  release.yml but no instance uses them yet.
- Agent's MCP gains a routing layer: tools whose connector has
  `runtime: container` in its connector.yaml are routed to the
  container's MCP; tools with `runtime: module` (the default for
  v0.1.30) keep the in-process path. Both paths supported
  side-by-side.
- guardian-updater gains the `/api/v1/connectors/<id>/instances/<name>/start`
  / stop / status / restart endpoints. Not yet exercised by any
  flow.
- A new `bundles/spark/connectors/_runtime/` skeleton showing
  exactly what a connector's Dockerfile + entrypoint look like.

**Acceptance**:

- `docker compose --profile dev up guardian-connector-xsiam` brings
  up the xsiam connector container in standalone mode; `curl
  http://localhost:9000/health` returns 200; `mcp tools/list`
  returns xsiam's tools.
- Existing in-process tools still work unchanged.
- release.yml builds + pushes the new per-connector images;
  conditional retag logic correctly handles them.

### Phase 2 (v0.1.31): Pilot — migrate `web` to container runtime

**Why web first**: it's new (no production customers depend on its
in-process behavior), it already has a sidecar (guardian-browser),
and its state model (per-session BrowserContext) is exactly the
kind of thing the per-container model handles cleanly.

**Ships**:

- Web connector's `connector.yaml` flips `runtimeMapping.style` to
  `"container"`.
- Web connector image gets a real implementation (FastMCP server
  wrapping the existing browser.py code).
- When operator creates a web instance via /connectors UI, agent
  calls guardian-updater to start a `guardian-connector-web-<name>`
  container. Tool calls flow through the proxy.
- /connectors UI surfaces container health (running / restarting /
  unhealthy) per instance.
- Operator UX: indistinguishable from in-process. Tools work the
  same; allowed_domains chip editor still works; bypass mode still
  routes correctly.

**Acceptance**:

- Smoke test on guardian-vm: create web instance → container
  starts → agent calls `web/navigate` → connector container
  executes Playwright → response flows back through the proxy.
- Latency observation: per-call overhead vs. v0.1.30 baseline.
  Acceptable if median per-call adds < 50 ms.
- Crash test: kill the connector container mid-call → agent
  surfaces timeout, container restarts, next call succeeds.
- Two web instances side-by-side: each has its own page registry,
  no cross-contamination.

### Phase 3 (v0.1.32+): Migrate the remaining first-party connectors

One per release. Order: simplest first.

**v0.1.32 — xsiam**: pure HTTP wrapper, no state, external
network. Fastest to migrate.

<!-- [guardian v0.1.0] Retired: the v0.1.33/v0.1.34 migration entries covered simulation-era connectors removed in the Guardian fork; the remaining Cortex-family connectors follow the same single-file flip. -->

Each migration is a single-file flip in the connector's
connector.yaml + the image build. The proxy machinery from
Phase 1 handles routing. No agent code changes per connector.

**Acceptance per release**: Smoke test of every tool in the
migrated connector against guardian-vm. Latency parity with the
v0.1.31 baseline (web).

### Phase 4 (v0.2.0): Drop in-process runtime

After all first-party connectors are container-mode in production use
for at least 4 weeks (v0.1.31 → v0.2.0 stretch), remove the
`runtime: module` code path entirely. Bundle architecture v2.0.

**Ships**:

- Removal of `_wrap_with_instance` + the in-process loader code in
  `connector_loader.py`. The loader becomes pure routing-table
  population.
- `connector.yaml.runtimeMapping.style` requires `"container"`;
  `"module"` rejected at bundle load.
- Documentation: bundle author guide pivots to "your connector is
  an MCP server in a container."
- Third-party connector path opens: docs explain how to ship a
  standalone connector image and reference it from a custom
  bundle.

**Acceptance**: All first-party connectors running in container
mode in production for ≥ 4 weeks with no fall-back to in-process
needed. v0.2.0 release tag.

## Open questions to validate during Phase 1

These are real uncertainties, not handwaving — each is something I
expect to learn the answer to during Phase 1 implementation.

1. **Per-call MCP latency in practice.** The 10-30 ms estimate is
   napkin math for HTTP-over-loopback. Need to measure actual MCP
   roundtrip latency including FastMCP overhead, JSON parse, etc.
   If it lands closer to 100 ms, may need to evaluate keep-alive
   connection pooling or switching to a binary transport for hot
   paths.

2. **Per-instance container memory floor.** Every container has a
   baseline (Python interpreter + FastMCP + per-connector deps).
   Need real measurements per connector to set sensible default
   memory limits in connector.yaml.

3. **Audit forwarding reliability.** Connectors POST audit events
   to the agent. What happens if the agent is down mid-call (e.g.
   during agent rolling restart)? Need a small retry/buffer
   mechanism; design TBD based on what fails first in testing.

4. **First-call cold-start cost when an instance container is
   newly started.** Tools advertise `tools/list` at proxy-init
   time; first `tools/call` after instance creation pays a one-time
   overhead. Measure; if > 1 s, consider warming the proxy
   connection at instance create time.

5. **SecretStore client library packaging.** Guardian's SecretStore
   today is a Python class in guardian-agent's source tree. Need
   to extract a `guardian-connector-runtime-py` library that
   connectors import. Decide: vendored copy or shared volume? Vendored
   is simpler, shared volume is DRY.

6. **Where does the routing table live?** Agent's MCP needs to know
   "for connector instance X, the container is at hostname Y port Z."
   Options: (a) guardian-updater pushes the table to the agent on
   instance create/destroy, (b) agent queries guardian-updater on
   demand, (c) the table lives in instance_store with the instance
   row. (c) is probably cleanest but Phase 1 will tell us.

7. **Resource accounting for the operator UI.** /connectors page
   currently shows status (connected / error / not_tested). With
   per-container deployment, we can show CPU / memory / restart
   count. Useful but optional for v0.2.0; defer to v0.2.x if it
   bloats Phase 2 scope.

## Out of scope

Things this spec deliberately doesn't address — each is a
legitimate concern but solving it here would balloon the program:

- **Multi-host / multi-node deployment.** Guardian is single-VM
  today. Per-instance containers don't preclude multi-host
  later, but the routing + service-discovery machinery for that
  is a separate spec.
- **Untrusted-connector sandboxing.** The spec assumes
  first-party trust for v0.2.0. True untrusted-third-party
  containers (egress filtering, no-internet-by-default,
  capability-bound) needs additional work — defer to a v0.3
  threat-model spec.
- **Per-call tracing across the proxy boundary.** OTel context
  propagation through MCP-over-HTTP is mostly free with
  starlette + httpx auto-instrumentation, but verifying it works
  end-to-end is Phase 1 testing, not spec'd here.
- **Hot-reload of connector code without container restart.**
  Possible (mount source as volume) but defeats the
  immutable-image story. Defer.
- **Connector containers running on different OS / arch than the
  host.** Multi-arch images (amd64 + arm64) for the Apple Silicon
  dev case may matter eventually but isn't blocking Phase 1.

## Acceptance criteria for the program

The per-instance container architecture is "done" when:

1. All first-party connectors (xsiam, cortex-xdr, web, cortex-docs,
   cortex-content) ship in container mode by default.
2. Operator UX in /connectors is unchanged from v0.1.x — install,
   create instance, configure, test, use. No new concepts the
   operator must learn.
3. guardian-agent image size is smaller in v0.2.0 than v0.1.29
   (specifically: connector-specific deps removed).
4. Per-call latency overhead vs. v0.1.x in-process baseline is
   < 50 ms median for the HTTP-wrapper connectors and < 100 ms
   median for web (which has CDP roundtrip cost regardless).
5. Crash isolation verified: killing one connector container
   does not affect the agent or other connectors.
6. Documentation in `agent-bundle-architecture.md` updated to
   describe the v0.2 model as the primary architecture, with v0.1
   in-process model archived as historical context.
7. At least one third-party connector example is published
   (probably a Splunk-or-equivalent SIEM connector) demonstrating
   that the open-ecosystem story works in practice.

## Why this spec, written now

Two motivations:

1. **The conversation that triggered this spec** correctly
   identified that the v0.1.x in-process model doesn't match what
   was originally pictured for the connector architecture. Writing
   it down forces precision: which parts of the original vision
   are still right (per-instance isolation, third-party
   connectors), which were never load-bearing (per-call
   container spin-up — too slow), and what the actual contract
   needs to be.

2. **Sequencing.** v0.1.x has a backlog of small UX fixes
   (install button, marketplace polish, etc.) that can ship
   sequentially without coupling. This architectural change
   needs a spec first because it touches every layer:
   release.yml, agent's MCP, guardian-updater, instance store,
   secret store, every connector's source layout. Doing it
   without writing it down means re-deciding the same questions
   on every PR review for the next 4-6 weeks.

This spec is the artifact future PR reviews can point at when the
question "why did we do it this way?" comes up. If a decision in
this doc is wrong, fixing it here is cheaper than re-doing it in
code six commits in.

---

## Phase 2 lessons learned (v0.1.31, web connector)

The first connector to flip to container-mode was the web
connector — chosen because it's the newest (smallest blast
radius), has the least production usage, and exercises the most
"foreign" code path (CDP to a sidecar Chromium). The flip
shipped on 2026-05-07 alongside v0.1.31. Five real bugs surfaced
during the smoke test on guardian-vm; all are documented here so
future connector migrations (xsiam → v0.1.32, then the remaining
Cortex-family connectors) don't re-discover them.

### 1. Schema drift between agent and runtime

**Symptom.** Container booted, called `InstanceStoreReader.get()`
in the runtime entrypoint, errored with `sqlite3.OperationalError:
no such column: config`. Restart loop; healthcheck never went
green.

**Root cause.** The agent's `InstanceStore` writes columns
named `config_json` + `secrets_json` (TEXT containing JSON).
The runtime's `InstanceStoreReader` was written against an older
spec draft that called them `config` + `secret_refs`. Both sides
share the same SQLite file by mount but neither reads a shared
schema definition.

**Fix.** Renamed the runtime client's SELECT columns +
JSON-decode keys to match the agent. See
`guardian-connector-runtime/runtime/instance_store_client.py`
commit 8ca7c0d.

**Going-forward.** For Phase 4 (third-party connectors), the
runtime should NOT read SQLite directly — it should call back
to the agent's HTTP API for instance + secret lookups. The
shared-file model is a v0.2 expedient that becomes a contract
liability once external authors write connectors.

### 2. FastMCP rejects `**kwargs` callables

**Symptom.** Agent crashed at boot with `ValueError: Functions
with **kwargs are not supported as tools` the moment a
container-style instance existed in the store.

**Root cause.** The container-mode proxy was originally a
thin closure: `async def _proxy(_tool_name=tool_name, **kwargs):
return await proxy_call_tool(...)`. FastMCP introspects each
tool function's signature via `inspect.signature()` to derive
a JSON Schema (one Pydantic field per parameter), and rejects
`**kwargs` because it can't enumerate the input space. The
intent of the **kwargs catch-all was "the container's own
FastMCP does the real validation, so we don't need to here" —
but you can't punt validation upstream past FastMCP's bouncer.

**Fix.** `_build_container_proxy()` in
`bundles/spark/mcp/src/usecase/connector_loader.py` now
synthesizes a function whose signature mirrors the
`connector.yaml` `args` declaration: one parameter per arg,
type annotations from a yaml→Python type map, optional args
default to `None`. The body packs bound parameters into a
dict, drops `None` values (so the container sees an absent
key rather than a null), and forwards via `proxy_call_tool`.

**Going-forward.** The yaml type map currently handles the
6 common types (string, integer, number, boolean, object,
array). Yaml unions, enums, and nested object schemas are
not yet expressed in `connector.yaml` `args` — when the first
connector wants them, extend the map. Today's connectors don't.

### 3. GUARDIAN_TLS_VERIFY not honored by updater

**Symptom.** Container started fine, but the
`PUT /api/v1/instances/{id}/container_url` callback from
guardian-updater to the agent failed with
`CERTIFICATE_VERIFY_FAILED: self-signed certificate`.
Container_url stayed `None` in the DB; tool calls failed
with "no container_url" until manually restarted.

**Root cause.** v0.1.27's TLS work flipped the agent's MCP
endpoint to HTTPS with a self-signed cert in the customer
compose. The agent honors `GUARDIAN_TLS_VERIFY=0` for its
own self-loopback calls. guardian-updater didn't — it built
its httpx clients with default `verify=True`, which fails
chain validation against a self-signed cert.

**Fix.** Updater now reads `GUARDIAN_TLS_VERIFY` (defaults to
verify-on; "0" disables) and passes `verify=verify_tls` to
both `_agent_set_container_url`'s PUT and the reconcile
endpoint's GET. Customer compose sets the env var on
guardian-updater the same way it does on guardian-agent.

**Going-forward.** A future cert-rotation feature should
issue compose-internal CA-signed certs to all services,
removing the need for verify-off mode entirely.

### 4. Tool-registry reload after container_url change

**Symptom.** Even after `container_url` propagated to the DB
correctly, tool calls kept failing with "connector 'web'
instance has no container_url — guardian-updater hasn't
started the container yet". A manual agent restart fixed
each occurrence.

**Root cause.** The agent caches `Instance` objects at
startup via `iter_registrations()`. The proxy closures close
over those `Instance` references. `merged_config()` is
called fresh on each tool call, but it reads
`self.container_url` from the cached `Instance`, which was
loaded with `container_url=None` before guardian-updater ran.
DB updates don't invalidate Python references.

**Fix.** `set_container_url` now triggers
`reload_tools_now()` after the DB write, which re-runs
`register_all_tools()` and rebuilds every closure with the
current `merged_config()`. Reload is best-effort — if it
fails, the PUT still returns 200 since the row IS updated;
operator can recover with an agent restart.

**Going-forward.** Reload latency on guardian-vm: ~860ms
(vs ~8ms for the row-only PUT). Acceptable for the relatively
infrequent container_url update events. If/when this becomes
hot (e.g. operators churning through 100s of instances per
minute), switch to per-instance closure invalidation rather
than re-registering everything.

### 5. Importing `os` in api modules

**Symptom.** `_connector_runtime_style()` and
`_updater_start()` referenced `os.environ.get` but the
module had no `import os`. POST /api/v1/instances 500'd
after `store.create()` had already succeeded — left an
orphan instance row in the DB with no container.

**Root cause.** Plain oversight. `__future__ import
annotations` defers annotation evaluation, so the
`type: ignore` style import wasn't strictly required, and
the function signatures didn't trigger an import-time error.

**Fix.** One-line `import os` added.

**Going-forward.** ruff/pyflakes catches this; running
linters in CI before merge would have caught it. Phase 3
should add a pre-merge lint gate to release.yml.

### Synthesis: drift is the dominant risk

Four of five bugs (1, 3, 4, 5) are forms of "two services
agreed on a contract but one side drifted." The schema column
names, the TLS verify env var, the tool-registry refresh
contract, the implicit "I'll need os later" — each is the kind
of thing that humans miss in code review because the change
that broke the contract looks innocuous in isolation.

Mitigations for v0.1.32+ migrations:
- **Schema:** runtime should call back to agent HTTP API
  for instance reads, removing the SQLite-shared-file
  contract entirely (Phase 4 work, but worth pulling forward
  if any subsequent connector has a non-trivial config
  shape).
- **TLS:** standard `verify=GUARDIAN_TLS_VERIFY` boilerplate
  in `pkg/agent_client.py` (new module) that all
  agent-callers (updater, future webhooks) import — no more
  scattered `httpx.AsyncClient(verify=True)` calls.
- **Reload contract:** any agent-side write that touches
  per-instance config should call `reload_tools_now()` — add
  a `# CONTRACT:` comment + grep for it in CI.
- **Lint gate:** add `ruff check` to release.yml before the
  build step. Cheaper than re-discovering the same class of
  bug each migration.
