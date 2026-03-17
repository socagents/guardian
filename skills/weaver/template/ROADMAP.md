# {{PROJECT_NAME}} Roadmap

Comprehensive build plan for the {{PROJECT_NAME}} AI agent orchestration platform.
Covers all 10 stages, 14 microservices, infrastructure, and cross-cutting concerns.

> **Architecture diagram:** [docs/architecture.svg](docs/architecture.svg)
> **Progress is scored by the deployment agent** after each build by comparing
> actual source code against deliverables listed here. Scores are 0–100%.

---

## Progress Summary

<!-- PROGRESS_START -->
| Stage | Name | Progress | Key Deliverables |
|-------|------|----------|------------------|
| 1 | Foundations, Contracts, Repo Layout | 78% | Repo skeleton, proto contracts, data model, deployment infra |
| 2 | API Gateway + Control Plane | 54% | api-gateway (Go), control-plane (Go), PostgreSQL persistence |
| 3 | Agent Runtime | 49% | agent-runtime (Python), prompt pipeline, run lifecycle |
| 4 | Model + Provider Services | 2% | Provider abstraction, multi-model support, fallback chains |
| 5 | Memory Service | 5% | memory-service (Python), LanceDB, semantic recall |
| 6 | Tool Execution + Skills | 4% | tool-execution (Go), plugin-runner (Go), skill packs |
| 7 | UI | 5% | Next.js operator interface, chat views, config editor |
| 8 | Connectors, Routing, Delivery | 7% | Slack, Gmail, Google Chat, Notion connectors (Go) |
| 9 | Plugins + Extensions | 1% | Plugin contracts, extension packaging, capability bundles |
| 10 | Automation, Devices, Media, Hardening | 5% | automation-service, device-node-service, media-service, OTel |
<!-- PROGRESS_END -->

---

## Stage 1: Foundations, Contracts, Repo Layout

**Objective:** Establish the clean-room project skeleton and service contracts before feature implementation.

| # | Deliverable | Progress | Spec / Notes |
|---|-------------|----------|--------------|
| 1.1 | Repository skeleton with service directories | 90% | [specs/repo-scaffold.md](specs/repo-scaffold.md) |
| 1.2 | Proto contracts foundation (buf config, base protos) | 85% | [specs/proto-contracts-foundation.md](specs/proto-contracts-foundation.md) |
| 1.3 | Data model foundation (PostgreSQL schema) | 85% | [specs/data-model-foundation.md](specs/data-model-foundation.md) |
| 1.4 | Deployment foundation (docker-compose, init scripts) | 85% | [specs/deployment-foundation.md](specs/deployment-foundation.md) |
| 1.5 | UI scaffold (Next.js hello-world) | 30% | [specs/ui-hello-world.md](specs/ui-hello-world.md) |
| 1.6 | Platform ownership rules (CODEOWNERS, contributing) | 55% | Repository governance |
| 1.7 | Session metadata contract | 85% | Proto contract for session lifecycle |
| 1.8 | Run request/response contract | 88% | Proto contract for run execution |
| 1.9 | Event envelope contract | 90% | Proto contract for NATS events |
| 1.10 | Tool descriptor contract | 85% | Proto contract for tool definitions |
| 1.11 | Model/provider descriptor contract | 70% | Proto contract for provider metadata |
| 1.12 | Connector inbound message envelope | 70% | Proto contract for connector messages |
| 1.13 | Transcript object reference contract | 80% | Proto contract for transcript storage |
| 1.14 | Attachment/blob reference contract | 65% | Proto contract for MinIO objects |
| 1.15 | Plugin execution request/response contract | 55% | Proto contract for plugin invocation |
| 1.16 | Transport rules (gRPC + NATS configuration) | 80% | Service-to-service transport setup |

**Capabilities:** service map, ownership boundaries, transport strategy, repo skeleton for staged delivery.

---

## Stage 2: API Gateway + Control Plane

**Objective:** Build the external entrypoint and internal orchestrator in Go.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 2.1 | `api-gateway` HTTP API | 70% | Go, external entrypoint |
| 2.2 | `api-gateway` WebSocket + SSE support | 60% | Primary real-time path |
| 2.3 | `api-gateway` auth + session handling | 55% | Local operator auth (v1) |
| 2.4 | `api-gateway` → control-plane proxying | 65% | gRPC internal routing |
| 2.5 | `control-plane` sessions registry | 70% | Session lifecycle management |
| 2.6 | `control-plane` config management | 65% | File-based + env defaults |
| 2.7 | `control-plane` health/readiness | 60% | Liveness + readiness probes |
| 2.8 | `control-plane` routing registry | 65% | Connector → session routing |
| 2.9 | `control-plane` approvals + operational state | 60% | Human-in-the-loop controls |
| 2.10 | `control-plane` run orchestration state machine | 65% | Run lifecycle: pending → active → done |
| 2.11 | PostgreSQL persistence (sessions, agents, config, routing, approvals) | 65% | Extends Stage 1 schema |
| 2.12 | MinIO object references (transcripts, artifacts, blobs) | 15% | Uses Stage 1 buckets |
| 2.13 | NATS runtime lifecycle events | 55% | JetStream durable streams |

**Capabilities:** external platform entrypoint, orchestrator service, canonical runtime metadata, UI-facing event backbone.

---

## Stage 3: Agent Runtime

**Objective:** Build the Python cognitive service behind a stable gRPC contract.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 3.1 | `agent-runtime` run execution entrypoint | 70% | gRPC server, consumes from control-plane |
| 3.2 | Prompt assembly pipeline | 60% | Context → prompt → model call |
| 3.3 | Session-aware transcript logic | 55% | Transcript payloads in MinIO, metadata in PostgreSQL |
| 3.4 | Reasoning/thinking controls | 40% | Extended thinking, chain-of-thought |
| 3.5 | Abort/cancel handling | 55% | Graceful run cancellation |
| 3.6 | Subagent execution model | 10% | Nested agent orchestration |
| 3.7 | Run event publishing (NATS) | 55% | Start, update, complete events |

**Capabilities:** cognitive runtime, session-aware execution, prompt pipeline, run lifecycle integration.

---

## Stage 4: Model + Provider Services

**Objective:** Add a provider abstraction that is service-friendly and vendor-neutral.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 4.1 | Provider abstraction (identity, transport, auth, capability metadata) | 8% | Python, inside agent-runtime or split later |
| 4.2 | Direct provider API support (Anthropic, OpenAI) | 0% | SDK-based integrations |
| 4.3 | OpenAI-compatible endpoint support | 0% | Self-hosted models |
| 4.4 | CLI-backed adapter support | 0% | Local model runners |
| 4.5 | Provider auth flows (API key, token, OAuth, env/file secrets) | 0% | Secure credential resolution |
| 4.6 | Provider/model catalog (static + discovered + compatibility) | 5% | Model registry |
| 4.7 | Fallback chains | 5% | Primary → secondary model routing |
| 4.8 | Workflow family: personal assistant | 0% | Conversational workflows |
| 4.9 | Workflow family: coding agent | 0% | Code generation + execution |
| 4.10 | Workflow family: connector-bot | 0% | Automated channel responses |

**Capabilities:** multi-provider model support, local + hosted models, fallback chains, provider discovery.

---

## Stage 5: Memory Service

**Objective:** Build semantic memory as its own service rather than embedding it in the agent process.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 5.1 | `memory-service` gRPC server | 15% | Python + LanceDB |
| 5.2 | Store memory API | 5% | Write memory entries |
| 5.3 | Search memory API | 8% | Semantic vector search |
| 5.4 | Read memory by reference API | 5% | Direct lookup |
| 5.5 | Inject relevant memory context API | 5% | Prompt enrichment |
| 5.6 | Curated memory entries | 0% | Human-authored memories |
| 5.7 | Session-aware recall | 5% | Per-session context |
| 5.8 | Global / per-agent / per-user / per-session scopes | 5% | Memory partitioning |
| 5.9 | Selective retrieval (not full-context injection) | 0% | Efficient recall |
| 5.10 | Memory categorization | 0% | Future hybrid retrieval |
| 5.11 | Memory lifecycle events (NATS) | 5% | Memory captured, updated, deleted |

**Capabilities:** semantic memory, vector-backed recall, memory retrieval service boundary.

---

## Stage 6: Tool Execution + Skills

**Objective:** Separate risky execution from the cognition service and add reusable skill packs.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 6.1 | `tool-execution-service` tool registry | 10% | Go, tool catalog |
| 6.2 | Execution context enforcement | 5% | Sandbox boundaries |
| 6.3 | Allow/deny policy pipeline | 5% | Tool access control |
| 6.4 | Sandbox + elevated execution hooks | 5% | Security isolation |
| 6.5 | Audit and execution reporting | 0% | Tool usage logs |
| 6.6 | `plugin-runner` isolated execution | 8% | Go host + Python plugin paths |
| 6.7 | Plugin process/container lifecycle | 5% | Start, stop, restart |
| 6.8 | Plugin capability registration | 5% | Explicit contracts |
| 6.9 | Skill folder format | 0% | Python, standard layout |
| 6.10 | Bundled / managed / workspace-local skills | 0% | Three skill locations |
| 6.11 | Skill precedence rules | 0% | Override ordering |
| 6.12 | Skill gating (env/bin/config/OS) | 5% | Conditional availability |
| 6.13 | Subagent orchestration contracts | 10% | control-plane ↔ agent-runtime |

**Capabilities:** safe tool execution boundary, isolated plugin execution, skill packs, subagent orchestration.

---

## Stage 7: UI

**Objective:** Build the browser operator surface against the service platform.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 7.1 | Next.js project scaffold | 30% | [specs/ui-hello-world.md](specs/ui-hello-world.md) |
| 7.2 | Gateway connection + auth | 0% | Connects only to api-gateway |
| 7.3 | Chat and session views | 5% | Primary interaction surface |
| 7.4 | Agent and model controls | 0% | Runtime configuration |
| 7.5 | Config editor | 5% | Platform settings |
| 7.6 | Logs/debug views | 5% | Run inspection |
| 7.7 | Health/status dashboard | 0% | Service monitoring |
| 7.8 | Skills and tools visibility | 0% | Available capabilities |
| 7.9 | Live run updates from NATS-fed events | 0% | Real-time via api-gateway |

**Capabilities:** browser control UI, model/config/session operator surfaces, live run visibility.

---

## Stage 8: Connectors, Routing, Delivery

**Objective:** Add real external messaging surfaces as dedicated services.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 8.1 | Connector contract (inbound normalization, identity, capability flags, lifecycle) | 15% | Shared contract for all connectors |
| 8.2 | `connector-slack` | 5% | Go, Slack Bot API |
| 8.3 | `connector-gmail` | 5% | Go, Gmail API |
| 8.4 | `connector-googlechat` | 5% | Go, Google Chat API |
| 8.5 | `connector-notion` | 5% | Go, Notion API |
| 8.6 | Inbound flow: connector → NATS → control-plane → run | 5% | Message ingestion |
| 8.7 | Outbound flow: control-plane → delivery request → connector | 5% | Response delivery |
| 8.8 | Routing rules (connector ↔ session mapping) | 15% | control-plane managed |

**Capabilities:** real inbound/outbound chat surfaces, routing, delivery abstraction.

---

## Stage 9: Plugins + Extension Packaging

**Objective:** Allow new platform capabilities to ship without changing core services.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 9.1 | Go-hosted runtime extension contracts | 0% | Native Go plugins |
| 9.2 | Python-hosted provider/tool/skill extensions | 0% | Python plugin paths |
| 9.3 | Isolated plugin-runner extension services | 5% | Sandboxed execution |
| 9.4 | Plugin-declared tools | 5% | Tool capability registration |
| 9.5 | Plugin-declared providers | 0% | Model provider plugins |
| 9.6 | Plugin-declared connectors | 0% | Channel plugins |
| 9.7 | Plugin-declared control-plane methods | 0% | Platform extension points |
| 9.8 | Plugin-declared services | 0% | New microservice plugins |
| 9.9 | UI metadata/config hints from plugins | 0% | Frontend integration |

**Capabilities:** extension-pack model, plugin-shipped tools/providers/skills/connectors, capability bundles.

---

## Stage 10: Automation, Devices, Media, Hardening

**Objective:** Add advanced platform capabilities after the core services are stable.

| # | Deliverable | Progress | Notes |
|---|-------------|----------|-------|
| 10.1 | `automation-service` cron scheduling | 5% | Go, time-based triggers |
| 10.2 | `automation-service` recurring jobs | 5% | Repeating workflows |
| 10.3 | `automation-service` heartbeats | 0% | Liveness monitoring |
| 10.4 | `automation-service` delayed execution | 5% | Deferred actions |
| 10.5 | `device-node-service` device registration | 5% | Go, paired devices |
| 10.6 | `device-node-service` capability registry | 5% | Node capabilities |
| 10.7 | `device-node-service` approvals | 5% | Device trust |
| 10.8 | `device-node-service` remote execution targets | 0% | Distributed execution |
| 10.9 | `media-service` MinIO-backed attachment storage | 5% | Go, blob management |
| 10.10 | `media-service` media metadata | 0% | File metadata indexing |
| 10.11 | `media-service` transforms and serving | 0% | Image/file processing |
| 10.12 | Operator auth hardening | 15% | Security hardening |
| 10.13 | Browser/device trust model | 0% | Device verification |
| 10.14 | Execution guardrails | 0% | Safety limits |
| 10.15 | Secret handling hardening | 0% | CI/CD secret injection |
| 10.16 | Deployment-mode support | 10% | Dev/staging/production modes |
| 10.17 | OpenTelemetry (traces, metrics, logs) | 25% | Observability stack |
| 10.18 | Idempotent consumers + retry with backoff | 10% | Distributed reliability |
| 10.19 | Graceful degradation | 0% | Partial service availability |

**Capabilities:** scheduled jobs, distributed device model, media pipeline, platform hardening, operational readiness.

---

## Cross-Cutting Concerns

These span multiple stages and are addressed incrementally throughout the build.

| # | Concern | Progress | Notes |
|---|---------|----------|-------|
| X.1 | OpenTelemetry | 25% | Required from day one |
| X.2 | Security + Auth | 15% | Local operator auth first |
| X.3 | CI/CD Pipelines | 80% | Agent workflows operational |
| X.4 | Agent Workforce | 70% | Planning, coding, review, validation, deployment agents active |
| X.5 | Agent Interaction Protocol | 65% | Issue-based coordination active |
| X.6 | CI/CD Agent Integration | 75% | GitHub Actions workflows operational |
| X.7 | Testing Strategy | 55% | Per-language test frameworks defined |
| X.8 | Error Taxonomy | 10% | Structured error classification |
| X.9 | Error Reference Extraction | 0% | Error pattern detection |
| X.10 | Distributed State Transitions | 10% | Saga patterns, idempotency |
| X.11 | Backup + Disaster Recovery | 0% | PostgreSQL + MinIO backup strategy |
| X.12 | Config Schema | 15% | Per-service config format |
| X.13 | Cost Metering | 5% | Token + resource usage tracking |
| X.14 | Kubernetes Deployment | 0% | Future production deployment |
| X.15 | Capability List | 10% | Platform capability inventory |

---

## Infrastructure

| Component | Progress | Port(s) | Notes |
|-----------|----------|---------|-------|
| PostgreSQL 16 | 85% | 5432 | `docker-compose.yml` + `scripts/init-db.sql` |
| NATS 2.10 + JetStream | 0% | 4222, 8222 | `docker-compose.yml` + `scripts/init-nats.sh` |
| MinIO | 75% | 9000, 9001 | `docker-compose.yml` + `scripts/init-minio.sh` |
| LanceDB | 30% | embedded | Part of memory-service (Stage 5) |
| OTel Collector | 70% | 4317, 4318 | Observability pipeline |
| Prometheus | 65% | 9090 | Metrics collection |
| Grafana | 50% | 3001 | Dashboards |

---

## Delivery Strategy

The recommended implementation sequence:

1. **Stages 1–3** — Establish contracts, the control plane, and one usable cognitive run path
2. **Stages 4–7** — Add provider flexibility, memory, safe tool execution, and the first usable UI
3. **Stages 8–9** — Add connectors and extensibility after core contracts stabilize
4. **Stage 10** — Add advanced automation, nodes/devices, media, and hardening once platform shape is proven

---

## Technology Split

| Language | Services | Role |
|----------|----------|------|
| **Go** | api-gateway, control-plane, tool-execution, plugin-runner, automation, media, device-node, all connectors | Control plane, network services, execution enforcement |
| **Python** | agent-runtime, memory-service | Cognition, AI integrations, semantic memory |
| **TypeScript/Next.js** | ui | Browser operator interface |

## Integration Model

| Mechanism | Use | Examples |
|-----------|-----|----------|
| **gRPC** | Synchronous request/response | gateway → control-plane, control-plane → agent-runtime |
| **NATS JetStream** | Async events + lifecycle fanout | Run events, connector messages, memory captures |

---

*Progress scores are updated by the deployment agent after each build.*
*Architecture diagram: [docs/architecture.svg](docs/architecture.svg)*
