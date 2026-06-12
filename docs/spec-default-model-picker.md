# Default-Model Picker — Design Spec

- **Date:** 2026-06-12
- **Status:** Approved (design). Next: implementation plan (writing-plans).
- **Author:** brainstormed with operator.

---

## 1. Problem

The chat model dropdown offers **"auto"**, which is opaque. `resolveModelName` (in
`mcp/agent/app/api/chat/route.ts`) resolves it as:

```ts
return modelOverride || runtimeConfig.GEMINI_MODEL || 'gemini-3.1-pro-preview';
```

So "auto" = the install-time `GEMINI_MODEL` env var (currently a Flash variant) — a global the
operator can't see or change from the UI. The operator wants to **choose the default model from the
Settings → Models page** and have the chat window use it (while still being able to override per
chat).

The scaffold already exists and is mostly unwired:
- The model **list** page (`app/models/page.tsx`) has clickable cards (→ detail page) and a
  **stubbed "default" badge** ("never rendered until the concept lands").
- The model **detail** page (`app/models/[model]/page.tsx`) renders full details (context window,
  thinking, tool-calling) and its comment says it reads `/api/v1/config` "for the default-model badge".
- `default_model?: { provider?: string; model?: string }` already exists in `lib/api/types.ts`.

What's missing: **persistence + a setter + the radio UI + wiring `resolveModelName` to read it.**

## 2. Gemini context (operator asked)

There is **no "Gemini 3.5 Pro"** as of June 2026. The Pro tier is **Gemini 3.1 Pro**
(`gemini-3.1-pro-preview`; the retired `gemini-3-pro-preview` now points here). The newest model is
**Gemini 3.5 Flash** (GA), which **beats 3.1 Pro on coding + agentic benchmarks** at lower cost — so
Flash is a defensible default for Guardian's agentic workload. The picker lets the operator choose
whichever models their provider exposes; **no model is hardcoded as "the" default** beyond the
existing fallback chain. (Informational — not a code change in this spec.)

## 3. Objectives & non-goals

**Objectives**
1. Operator sets a **default model** (a `{provider, model}` pair) from Settings → Models, via a
   radio/"Set as default" control on the **model detail page**.
2. The default is **persisted** server-side and surfaced via `/api/v1/config`.
3. The **chat window uses it automatically** — "auto" is replaced by a dynamic **"Default — `<model>`"**
   entry that is pre-selected, shows the current default's name, and tracks Settings changes.
4. The operator can still **override** the model per chat (pick any available model in the dropdown).

**Non-goals**
- No per-conversation persistence of overrides beyond the existing chat behavior.
- No new model-detail fields (context window / thinking / tool-calling already render).
- Not exposing default-model setting to the **agent** (it's operator config → REST/operator-only,
  per the credential/catalog boundary; the agent gets no MCP tool for it).

## 4. Design

### 4.1 Persistence — `operator_state.db`
Per Guardian's state taxonomy (root CLAUDE.md § Operator workflow state), the default model is
**operator workflow state**: not a secret (no SecretStore), not platform catalog — an operator
preference that should follow them server-side. It lands in **`operator_state.db`** under a narrow
key, e.g. `default_model` → `{"provider": "...", "model": "..."}`. This is exactly the "per-key narrow
surface when a use case emerges" the taxonomy anticipates.

### 4.2 Backend surface (MCP, REST-only)
- **Read:** `default_model` is added to the existing `GET /api/v1/config` payload (the field already
  exists in the type; wire it to read from `operator_state.db`).
- **Write:** `PUT /api/v1/config/default-model` (MCP REST, MCP_TOKEN-gated) with body
  `{"provider": "...", "model": "..."}` → validates the model exists in the live `/api/v1/models`
  list, writes it to `operator_state.db`. Clearing (revert to env default) = `PUT` with an empty body
  or `DELETE`.
- **Agent proxy:** `mcp/agent/app/api/agent/config/default-model/route.ts` forwards the `PUT` to the
  MCP via `resolveMcp()` (UI can't reach the MCP directly). Operator-session-gated (middleware),
  same as other `/api/agent/*` config routes.
- **Credential guardrail:** `default_model` is NOT a SecretStore value and NOT catalog metadata —
  it's operator config, so REST + operator-session-only; **no `mcp.tool()` registration** (the agent
  never sets it).

### 4.3 UI — the "Set as default" radio
- On the **model detail page** (`app/models/[model]/page.tsx`): a "Set as default" control (radio or
  button) near the details. Clicking it `PUT`s `{provider, model}` and updates the badge to "Default".
  If this model already IS the default, the control shows the selected/checked state.
- The **list** page (`app/models/page.tsx`): the existing stubbed `defaultModel` state becomes live
  (read from `/api/v1/config`), so the "default" badge renders on the correct card. (Optionally a
  quick "set default" affordance on the card — but the detail-page control is the primary path.)

### 4.4 Chat wiring — replace "auto"
- **`resolveModelName`** (`app/api/chat/route.ts`) gains the persisted default in its chain, BEFORE
  the env fallback:
  ```ts
  return modelOverride
    || runtimeConfig.defaultModel?.model   // operator-set default (operator_state.db, via config)
    || runtimeConfig.GEMINI_MODEL
    || 'gemini-3.1-pro-preview';
  ```
  (`EffectiveRuntimeConfig` is extended to carry `defaultModel` read from `/api/v1/config`.)
- **The chat model dropdown** drops the literal **"auto"** entry and adds a dynamic top entry:
  **"Default — `<default model name>`"**. It is pre-selected for a new chat, displays the current
  default's name, and **selecting it sends NO `modelOverride`** (so `resolveModelName` resolves to
  the operator's default — which auto-tracks Settings changes). Every available model is listed below
  as a selectable per-chat override.

## 5. Data flow
```
Settings → Models → [model detail] → "Set as default"
   → PUT /api/agent/config/default-model {provider, model}
   → (agent proxy) → PUT /api/v1/config/default-model (MCP, MCP_TOKEN)
   → operator_state.db: default_model = {provider, model}

Chat new conversation
   → GET /api/v1/config → default_model
   → dropdown pre-selects "Default — <model>"
   → user sends a message with NO modelOverride
   → resolveModelName → runtimeConfig.defaultModel.model  ✅ (the operator's choice)
   → user can pick another model → modelOverride → that model for this chat
```

## 6. Error handling
- Setter validates the `{provider, model}` is in the live `/api/v1/models` list → 400 on unknown.
- If no default is set (fresh install): `default_model` is null → `resolveModelName` falls through to
  `GEMINI_MODEL` (unchanged behavior); the dropdown's "Default" entry shows the resolved env model.
- If the set default later disappears from the provider's model list (model retired): the chat
  resolution still sends that model name to the provider; a provider 4xx surfaces as the existing
  chat error. The Models page badge simply won't match any card. (Acceptable; operator re-picks.)

## 7. Testing
- **MCP (pytest):** the `default_model` read/write on operator_state (set → get round-trip; validation
  rejects an unknown model; clearing reverts to null).
- **Agent (tsc/lint/build):** the new proxy route + the extended `resolveModelName` chain + the
  dropdown change compile under strict route validation.
- **Smoke (deployed):** set a default on the detail page → `GET /api/v1/config` shows it → open a new
  chat → the dropdown pre-selects "Default — <model>" → a chat turn uses that model (verify via the
  run's recorded model / audit).

## 8. Docs (ship with the code)
- **Architecture page** (`app/help/architecture/page.tsx`): a `#models` / `#chat` note documenting the
  default-model resolution chain (`override → operator default → env → hardcoded`) and operator_state
  storage. (Architecture page is the spec.)
- **User guide** (`app/help/user/page.tsx`): a paragraph — "set your default model on Settings →
  Models → [model] → Set as default; the chat window uses it, and you can change it per chat."
- **Journeys** (`lib/journeys.ts`): a click-path — Models → pick model → Set as default → open chat →
  confirm pre-selected.
- **CHANGELOG.md + release-notes.ts:** the operator-visible delta.

## 9. Decisions captured
- **Storage:** `operator_state.db` (operator workflow state). (Operator-approved.)
- **Chat dropdown:** a dynamic **"Default — `<model>`"** entry — pre-selected, shows the name, tracks
  Settings, sends no override; specific models selectable as per-chat overrides. (Operator-approved.)
- **Surface:** REST/operator-only (no agent MCP tool — it's config, per the guardrail).
- **Radio home:** the model **detail page** (primary); list-page badge goes live.

## 10. Open items
- Exact `operator_state.db` access path on the MCP side (a generic key-value helper vs a narrow
  `default_model` accessor) — resolve in the plan; the taxonomy prefers a **narrow** per-key surface.
- Whether `EffectiveRuntimeConfig` fetches `default_model` per chat request or caches it — resolve in
  the plan (a per-request `/api/v1/config` read is acceptable; the route already loads runtime config).
