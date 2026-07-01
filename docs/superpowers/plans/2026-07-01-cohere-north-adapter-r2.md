# R2 — Cohere North adapter Implementation Plan

> Executes on top of R1's provider registry (`mcp/agent/lib/llm/provider.ts`). Spec: `docs/superpowers/specs/2026-07-01-provider-adapter-seam-and-cohere.md` §5. Translation core drafted at scratch `cohere-provider-design.ts`.

**Goal:** Add "Cohere North" as a configurable provider whose `CohereProvider` runs Guardian's full tool-using investigation loop on a customer's private Cohere deployment. No Cohere key yet → tested against a byte-faithful STC-contract mock; real-Cohere validation deferred.

**Global constraints:** Bearer token REST-only (guardrail). TLS verify ON default. Single static model, no discovery. Embeddings stay on Vertex. Zero change to Gemini/Vertex paths. Pre-deploy gate (tsc/lint/build + golden + pytest). Fetch+rebase before building (clone drifts behind origin).

**Conversation model (R2):** fresh `conversation.id` UUID per `invoke()`, send full translated history. `conversation_mode` config field (default `stateless`) reserved for the per-session-delta variant if lab testing shows North needs it.

---

### Task 1 — cohere-north bundle + manifest
- Create `bundles/spark/providers/cohere-north/provider.yaml` (per explorer item 7: `configSchema` endpoint_url/agent_id/tls_verify/ca_pem/conversation_mode; `secretSlots: bearer_token`; single static model `cohere-north-default` supports streaming+tool_use).
- Create `bundles/spark/providers/cohere-north/src/provider.py` (`list_models()`→[]; `chat()`/`embed()`→NotImplementedError; `__init__` reads config+secrets).
- Register in `bundles/spark/manifest.yaml providers[]` after vertex: `{id: cohere-north, path: ./providers/cohere-north/, version: 0.1.0, required: false}`.
- Test: pytest still green (bundle loads). Commit.

### Task 2 — credential resolver + runtime-config
- Create `mcp/agent/lib/cohere-credentials.ts` mirroring `anthropic-credentials.ts` (two-value cache): `resolveMcpDirect()` reads `process.env.MCP_TOKEN/MCP_URL` directly (circular-import guard); `fetchUncached` GETs `/api/v1/providers?provider_id=cohere-north` then `/api/v1/providers/{id}?include_secrets=true`, returns `{endpoint: config.endpoint_url, bearerToken: secrets.bearer_token, agentId: config.agent_id, tlsVerify, caPem}`. Export `resolveCohereNorthCredentials()` + `bustCohereCredsCache()`.
- `mcp/agent/lib/runtime-config.ts`: add `COHERE_NORTH_ENDPOINT/COHERE_NORTH_BEARER_TOKEN/COHERE_NORTH_AGENT_ID/COHERE_NORTH_TLS_VERIFY/COHERE_NORTH_CA_PEM` to the type; in `getEffectiveRuntimeConfig()` add `const cohere = await resolveCohereNorthCredentials()` (dynamic import) and populate the fields (`cohere.endpoint || get("COHERE_NORTH_ENDPOINT")`, etc.).
- tsc. Commit.

### Task 3 — CohereProvider adapter + golden test
- Create `mcp/agent/lib/llm/cohere-provider.ts` from scratch design: pure `geminiToCohereBody(payload, agentId, conversationId)` + `cohereConversationToGemini(convo)` (+ `jsonSchemaToParamDefs`, `mapType`, `extractText`), then `cohereProvider: LLMProvider` whose `invoke` reads endpoint/bearer/agentId from `ctx.runtimeConfig`, builds body, POSTs `{base}/api/v1/chat`, polls `{base}/api/v1/conversations/{id}` (bounded backoff ≤200s, TLS per config), returns `cohereConversationToGemini(convo)`. Self-registers via `registerProvider(cohereProvider)`.
- Import `cohere-provider` in `route.ts` (triggers registration) — one import line next to the R1 provider import.
- Create `mcp/agent/scripts/test-cohere-translate.mjs`: golden asserts on the pure functions (text turn, tool-call turn, tool-result turn, tools→parameter_definitions, response→functionCall parts + usageMetadata). Wire into `npm test`.
- Run golden; tsc. Commit.

### Task 4 — config route (CRUD wiring)
- `mcp/agent/app/api/agent/providers/config/route.ts`: add cohere keys to `PROVIDER_KEYS` (cohereNorthEndpoint/AgentId/TlsVerify/CaPem/BearerToken) + `SENSITIVE_KEYS` (BearerToken); add `COHERE_NORTH_PROVIDER_ID`/instance-name consts; build `cohereConfigPatch` (endpoint_url/agent_id/tls_verify/ca_pem/conversation_mode) + `cohereSecretsPatch` (bearer_token); **extend the no-op gate** to include the cohere patches; add the upsert call (`mode:"all"`) to the Promise.all; add `bustCohereCredsCache()` on success; GET exposes `cohereNorthEndpoint`(plain)/`cohereNorthBearerToken`(REDACTED). tsc. Commit.

### Task 5 — models catalog
- `mcp/agent/app/api/agent/models/route.ts`: add `COHERE_NORTH_MODELS: ModelInfo[]` (single `cohere-north-default`, provider `cohere-north`, chat, supportsTools:true, contextWindow 128000); in GET resolve cohere creds in the Promise.all + spread when `Boolean(endpoint && bearer)`. tsc. Commit.

### Task 6 — providers UI (card + counter)
- `mcp/agent/app/providers/page.tsx`: add cohere fields to `ProviderConfig`; add a "Cohere North" card (endpoint + agent_id text inputs, masked bearer, optional TLS-verify toggle) mirroring the Vertex card; Test button → `/api/agent/providers/cohere-north/test` (soft-404 tolerant); include cohere in the save payload + the "Active Backends" counter. build. Commit.

### Task 7 — test-connection route
- Create `mcp/agent/app/api/agent/providers/cohere-north/test/route.ts` mirroring vertex/test: resolve REDACTED bearer from store, POST a minimal `{messages:[{role:USER,message:ping}], agent:{id}, stream:false}` + poll, return `{status, message}` (always 200), audit `provider_probed`. build. Commit.

### Task 8 — STC-contract mock (kind:service)
- Create `bundles/spark/connectors/cohere-mimic/` (or a standalone test service): implements `POST /api/v1/chat` (accept messages/agent/conversation/tools, script a 2-turn tool flow: first call → tool_call, second call w/ tool_results → final text) + `GET /api/v1/conversations/{id}` (return North-shaped messages). Reuse the splunk-mimic `kind:service` pattern. connector.yaml + Dockerfile + server. (Deployed later for integration; the golden test already covers translation.)

### Task 9 — docs
- Architecture: extend `#model-resolution` § Provider-adapter dispatch (remove the "not yet wired" gap line) + a Cohere North subsection (endpoint, poll model, conversation isolation, tool translation). User guide: "Cohere North provider" under providers. CHANGELOG + release-notes v0.2.110. journeys: add "configure a Cohere North provider" click-path. build. Commit.

### Task 10 — gate + push + deploy + verify + arc completion
- Full gate; push; watch CI → auto-deploy; verify version. Golden translation test in CI. Deploy the mock (Task 8) on guardian-vm, create a cohere-north provider pointing at it, switch a chat to `cohere-north-default`, confirm a tool-using turn completes (integration proof of POST/poll/translate). If mock deploy is deferred, the golden test + a Test-Connection green is the R2 acceptance floor.
- **Arc complete** → ask operator for the customer tag (v0.2.110) per approval phrasing.

## Acceptance
- Operator configures Cohere on `/providers` → model appears on `/models` → selectable in chat/jobs. Golden translation test passes. (Full tool-using investigation on real Cohere = deferred to key/sandbox.)
