# Provider-adapter seam + Cohere North provider — design spec

**Date:** 2026-07-01
**Status:** Draft for operator review
**Scope:** Two contained releases. R1 introduces a provider-adapter seam (de-hardcode Gemini). R2 adds Cohere North as the first non-Google adapter.

---

## 1. Goal & motivation

Make Guardian **model-agnostic**: any provider's model (Gemini, Cohere, future Ollama/OpenAI) is configured on the Providers page, appears on the Models page after a successful connection test, and is selectable everywhere a model is chosen — chat dropdown, jobs, subagents, default-model picker — with the LLM call routed to the correct provider adapter.

Motivating customer requirement (STC): run Guardian's **full investigation loop** on a private, on-prem **Cohere North** deployment (`core.stc.com.sa`) instead of Google, for data sovereignty. This requires tool-calling to work on Cohere, which Cohere supports.

**Non-goal:** changing what the agent *does*. This is plumbing — the investigation behavior, skills, and tools are unchanged.

---

## 2. Current state (the constraint we're removing)

Guardian's LLM call path is a hand-rolled, **Gemini/Vertex-shaped** loop (~6,300 lines in `mcp/agent/app/api/chat/route.ts`), with **no provider abstraction**. Model selection is already uniform (a model-name string flows through chat, jobs, subagents), but the *call* is hardwired to Google's shape at every seam:

| Seam | Location | Google-native shape |
|---|---|---|
| Dispatch | `callGeminiRaw` (route.ts:1238) | `GEMINI_API_KEY` → `callGeminiWithApiKey`, else SA-JSON → `callGeminiWithVertex` |
| Model routing | `resolveModelName` (route.ts:3308) | falls back to `gemini-3.1-pro-preview` |
| Tool serialize | `getGeminiTools` (route.ts:2711) | `{ functionDeclarations: [...] }` |
| Request build | `callGemini` / `GeminiCallPayload` (route.ts:3379 / 2766) | `{ contents, tools, systemInstruction, generationConfig }` |
| Response decode | main loop (route.ts:5235) | `part.functionCall = { name, args }`, `usageMetadata.*` |
| Tool-result inject | route.ts:6061 | `{ role:'user', parts:[{ functionResponse:{ name, response } }] }` |
| Vertex-only extras | `lib/vertex-cache.ts`, `resolveVertexLocation`, `thinkingConfig` | context-cache + region routing |

Provider **storage** is already generic: `ProviderStore` (SQLite + SecretStore, `bundles/spark/mcp/src/usecase/provider_store.py`) stores any `provider_id`; REST CRUD (`bundles/spark/mcp/src/api/providers.py`) is provider-neutral; `manifest.yaml` `providers[]` (line ~256) lists bundle providers. **No storage change is needed for a new provider** — the work is entirely the TypeScript call path + the new bundle + UI.

---

## 3. Target architecture

### 3.1 `LLMProvider` interface (the seam)

**Canonical interchange = the Gemini `generateContent` request/response shape** the mature agent loop already speaks. Each provider is an adapter that translates *to/from* that canonical shape. This is a deliberate risk-reduction over a brand-new neutral IR: the loop's tool-serialize, response-decode, and tool-result-injection stay byte-identical; only the **dispatch** (the HTTP call) is abstracted.

```ts
type LLMInvokeContext = { runtimeConfig: EffectiveRuntimeConfig; modelName: string };

interface LLMProvider {
  readonly id: string;                                       // 'gemini' | 'cohere-north'
  invoke(payload: GeminiCallPayload, ctx: LLMInvokeContext): Promise<unknown>; // returns a Gemini-generateContent-shaped response object
}
```

- `GeminiCallPayload` (existing type, exported) is the canonical **request**; the returned object is the canonical **response** the loop already decodes (`response.candidates[0].content.parts[]`, `usageMetadata`).
- `GeminiProvider.invoke` = today's `callGeminiWithApiKey` / `callGeminiWithVertex` logic verbatim (credential-based sub-dispatch + Vertex cache + region routing stay inside it).
- `CohereProvider.invoke` (R2) receives the canonical Gemini-shaped payload, translates to Cohere's request (`functionDeclarations`→`parameter_definitions`, `contents`+`functionResponse`→`messages`+`tool_results`, `systemInstruction`→`system`), POSTs `/api/v1/chat`, **polls** `/api/v1/conversations/{id}`, then translates the Cohere reply back into a Gemini-generateContent-shaped object (`tool_calls`→`functionCall` parts, text→`text` parts, `meta.tokens`→`usageMetadata`). The loop never knows which provider answered.

**Two-level dispatch:** the *outer* level (this interface) routes by **model → provider** (Gemini vs Cohere). The *inner* Google credential choice (`GEMINI_API_KEY` vs `GOOGLE_APPLICATION_CREDENTIALS`) stays inside `GeminiProvider`, unchanged.

### 3.2 Provider-tagged model registry

Today model entries are name-strings assumed to be Gemini. Introduce a registry where each entry carries its provider:

```ts
type ModelEntry = { id: string; provider: 'gemini'|'vertex'|'cohere-north'; displayName: string;
                    contextCap: number; pricing?: {...}; supports: {tools:boolean, thinking:boolean} };
```

- `models/route.ts` composes the registry from: built-in Google models (as today) **+** any configured provider's static models.
- `resolveModelName` → returns `{modelId, provider}`; dispatch selects the adapter by `provider`. The hardcoded `gemini-3.1-pro-preview` fallback becomes "the configured default model's provider."
- `lib/model-pricing.ts` and `lib/model-context-caps.ts` gain provider-aware lookups (Cohere entries added in R2).

This is what makes chat/jobs/subagents "just work" across providers — they already pass a model id; the registry tells the dispatch which adapter to use.

---

## 4. R1 — Provider-adapter seam (de-hardcode Gemini)

**Deliverable:** the seam + registry, with today's Gemini/Vertex **dispatch** extracted into a `GeminiProvider`, **byte-for-byte unchanged**. No new provider, no user-visible change.

- Define `LLMProvider` + `LLMInvokeContext` (canonical shape = `GeminiCallPayload` in / Gemini-response out) + a provider registry.
- Implement `GeminiProvider.invoke` by moving `callGeminiWithApiKey` + `callGeminiWithVertex` (incl. the api-key→vertex fallback, `resolveVertexLocation`, and the `GUARDIAN_VERTEX_CACHE` swap) behind the interface — **pure extraction, no logic change**.
- Add `resolveProviderForModel(modelName)` (model→provider id; for R1 every model → `'gemini'`).
- Rewire the 3 dispatch call sites (`callGemini`, `callGeminiRaw`, `summarizeViaGemini`) to build the `GeminiCallPayload` exactly as today, then call `getProvider(resolveProviderForModel(modelName)).invoke(payload, ctx)`.
- The loop's `getGeminiTools`, response-decode (`part.functionCall`), tool-result injection (`functionResponse`), and `extractAndRecordCost` are **untouched** — they remain the canonical shape.

R1 does NOT touch pricing/context-cap tables or the model registry's UI (Cohere entries land in R2).

**Hard regression gate (this release's whole risk surface):** the existing Gemini + Vertex paths must be provably identical — same requests on the wire, same tool loop, same cost accounting, same streaming, same context-cache behavior. Verified by: the full pre-deploy gate; a captured-request golden test (serialize a fixed turn+tools, assert the Gemini payload is unchanged); and a live investigation smoke on the deployed agent (an end-to-end case on Gemini behaves exactly as before). **R1 does not tag until the Gemini path is confirmed unchanged on the deployed install.**

---

## 5. R2 — Cohere North adapter

**Deliverable:** Cohere as a configurable provider, end-to-end, running the full investigation loop.

### 5.1 Bundle + registry
- `bundles/spark/providers/cohere-north/provider.yaml` mirroring `vertex/provider.yaml`: `configSchema` (`endpoint_url`, `agent_id`, `tls_verify` bool + optional `ca_pem`, `conversation_mode` enum), `secretSlots: [{ name: bearer_token, required: true }]`, `spec.models[]` = **single static entry** (`cohere-north-default`). Register in `manifest.yaml` `providers[]`.
- `Provider.list_models()` → the static entry (no discovery); `embed()` → `NotImplementedError` (embeddings stay on Vertex `text-embedding-004`).

### 5.2 Credential (REST-only, guardrail-compliant)
- Bearer token is a SecretStore value → written only via `POST/PUT /api/v1/providers`; **never** an `mcp.tool()`.
- New `mcp/agent/lib/cohere-credentials.ts` (mirrors `vertex-credentials.ts`): reads `MCP_TOKEN`/`MCP_URL` from env, GETs the provider instance with `include_secrets=true`, ~30s TTL cache, bust-on-update. Keeps the token off the agent's tool catalog.

### 5.3 `CohereAdapter` — the translation table
| Normalized concept | Gemini (R1) | Cohere North |
|---|---|---|
| Tools | `functionDeclarations[]` | flat list w/ `parameter_definitions: {name:{description,type,required}}` |
| Model tool-call | `part.functionCall {name, args}` | `tool_calls[] {name, parameters}` |
| Tool result turn | `role:'user' + functionResponse` | `role:'tool' + tool_results[]` |
| System prompt | `systemInstruction` | top-level `system` |
| Usage | `usageMetadata.*` | `meta.tokens.{input,output}` |
| Transport | stream `generateContent` | `POST {endpoint}/api/v1/chat` `{messages, agent:{id}, conversation:{id}, tools, stream:true}` → **poll** `GET {endpoint}/api/v1/conversations/{id}`, extract `messages[-1].content[?].text`; synthesize normalized stream |

- **Conversation lifecycle:** fresh client-supplied `conversation.id` (UUID) **per Guardian session** for investigation isolation; reuse is an explicit opt-in only. (Validate on lab Toolkit that a client-supplied UUID is accepted.)
- **TLS:** verify **on** by default; optional custom `ca_pem`. We do not replicate the STC client's `verify=False`.
- **Timeouts/poll:** bounded poll with backoff to a ~200s ceiling; clean error surfaced to the loop if the conversation never completes.

### 5.4 UI + wiring
- `providers/page.tsx`: "Cohere North" card (endpoint, agent id, bearer token, TLS options) + **Test Connection** → new `app/api/agent/providers/cohere/test/route.ts` (a real `POST /api/v1/chat` + poll ping with the bearer).
- `providers/config/route.ts`: 4th patch object (cohere config + secret), fix the no-op short-circuit gate (~line 361) to include it.
- `models/route.ts`: spread the static Cohere model entry when `endpoint && bearer_token` configured.
- On success the Cohere model appears in the chat dropdown, jobs, and subagent model pickers automatically (they read the registry).

---

## 6. Testing strategy

1. **R1 Gemini regression** — golden captured-request test + live investigation on the deployed agent; Gemini path unchanged.
2. **STC contract mock** — a tiny `kind:service` mock (reuse the Splunk-mimic pattern) implementing the exact observed contract: `POST /api/v1/chat` → 200 + stash; `GET /api/v1/conversations/{id}` → `{messages:[{content:[{},{text}]}]}`. Authoritative test for the poll+extract adapter and the `/api/v1` prefix.
3. **Lab Cohere Toolkit** — self-hosted `docker compose` Toolkit (`/v1/chat`, `/v1/tools`, conversations, Cohere tool format) validates real tool-calling semantics: a Guardian investigation runs a tool round-trip on Cohere.
4. **End-to-end** — configure the provider in the UI → Test Connection green → switch a chat + a job to the Cohere model → confirm a tool-using investigation completes.

---

## 7. Security & guardrail compliance

- Bearer token: SecretStore, REST-only, never on the agent tool catalog (root CLAUDE.md § Agent credential guardrail). No new credential-reading MCP tool.
- Catalog boundary: the provider is credential-side; `providers_create/update/delete` stay REST-only.
- TLS verify default-on; `verify=False` explicitly rejected as a default.
- Conversation isolation prevents cross-investigation history bleed.

---

## 8. Open questions / lab-validation items

1. Does STC's specific North build accept **tool definitions** on `/api/v1/chat` (product supports it; their agent config may or may not enable it)? Validated on the lab Toolkit; confirmed against STC only with a sandbox token/spec.
2. Does the endpoint accept a **client-supplied conversation UUID** (isolation) or require a create-conversation call first? Validated on lab.
3. Exact **North response envelope** vs. Toolkit (`content[1].text` fallback logic) — pin against the mock; confirm against a real North sample if available.
4. Streaming: do we ever need the POST stream body, or is poll-the-conversation always sufficient (as STC's own client assumes)? Default: poll.

---

## 9. Out of scope / future

- Ollama / OpenAI adapters — cheap once the seam exists (each is one `LLMProvider`), tracked separately.
- Cohere embeddings — not offered by North; embeddings remain on Vertex.
- Multi-agent-per-provider selection — `agent_id` is a fixed config field for now.
