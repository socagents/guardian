# R1 — Provider-adapter seam (de-hardcode Gemini) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Guardian's LLM dispatch through a provider registry so any model resolves to an adapter (Gemini today, Cohere in R2) — with **zero behavior change** to the existing Gemini/Vertex path.

**Architecture:** The canonical interchange is the existing Gemini `generateContent` request (`GeminiCallPayload`) / response shape. A tiny `LLMProvider` interface + registry lives in a new `lib/llm/provider.ts`. The existing api-key/vertex dispatch is de-duplicated into one `dispatchGeminiPayload()` and wrapped as the registered `geminiProvider`. The 3 call sites (`callGemini`, `callGeminiRaw`, `summarizeViaGemini`) build the payload exactly as today, then call `getProvider(resolveProviderForModel(model)).invoke(payload, ctx)`. The loop's tool-serialize, response-decode, tool-result-injection, and cost extraction are **untouched**.

**Tech Stack:** Next.js 15 (App Router) route handlers, TypeScript, `google-auth-library`. No TS unit framework — regression is a `node scripts/*.mjs` golden script + `tsc/lint/build` + a live deployed-agent smoke.

## Global Constraints

- **Zero behavior change.** The Gemini + Vertex wire requests, the api-key→vertex fallback, `resolveVertexLocation`, and the `GUARDIAN_VERTEX_CACHE=1` swap must be byte-identical to `main`. Copy the existing bodies verbatim; do not "improve" them.
- **No new provider in R1.** `resolveProviderForModel` returns `'gemini'` for every model that exists today. The `'cohere-north'` branch is present but unreachable until R2.
- Pre-deploy gate (run all four, from `mcp/agent/`): `npx tsc --noEmit && npm run lint && npm run build`, and from `bundles/spark/mcp/`: `PYTHONPATH=$PWD/src python3 -m pytest tests/ -x`.
- Credential guardrail unchanged — this release touches no SecretStore path.
- Reference for the verbatim current code shapes: the seam-extraction notes captured during planning (callGeminiRaw:1234-1271, callGeminiWithApiKey:3042-3073, callGeminiWithVertex:3075-3182, GeminiCallPayload:2766-2803, resolveModelName:3308-3316, callGemini:3379-3465).

---

## File Structure

- **Create** `mcp/agent/lib/llm/provider.ts` — the `LLMProvider` interface, the registry (`registerProvider`/`getProvider`/`hasProvider`), and `resolveProviderForModel` + the provider-id constants. No imports from `route.ts` (avoids a cycle); depends only on the `EffectiveRuntimeConfig` type.
- **Create** `mcp/agent/scripts/test-provider-seam.mjs` — golden/unit script for the registry + model→provider resolution; wired into `npm test`.
- **Modify** `mcp/agent/app/api/chat/route.ts` — add `dispatchGeminiPayload()` (dedup of the api-key/vertex branch), define + register `geminiProvider`, and rewire the 3 call sites to dispatch through the registry.
- **Modify** `mcp/agent/package.json` — add the new script to the `test` chain.
- **Modify** `mcp/agent/app/help/architecture/page.tsx` — add a `#model-providers` section documenting the seam.
- **Modify** `CHANGELOG.md` + `mcp/agent/lib/release-notes.ts` — the R1 entry (prerequisite-role note per the arc).

---

## Task 1: `LLMProvider` interface + registry + model→provider resolution

**Files:**
- Create: `mcp/agent/lib/llm/provider.ts`
- Create: `mcp/agent/scripts/test-provider-seam.mjs`
- Modify: `mcp/agent/package.json`

**Interfaces:**
- Produces: `LLMProvider` (`{ readonly id: string; invoke(payload: unknown, ctx: LLMInvokeContext): Promise<unknown> }`), `LLMInvokeContext` (`{ runtimeConfig: EffectiveRuntimeConfig; modelName: string }`), `registerProvider(p)`, `getProvider(id): LLMProvider`, `hasProvider(id): boolean`, `resolveProviderForModel(modelName): string`, `GEMINI_PROVIDER_ID = 'gemini'`, `COHERE_NORTH_PROVIDER_ID = 'cohere-north'`.

- [ ] **Step 1: Write the failing golden script**

Create `mcp/agent/scripts/test-provider-seam.mjs`:

```js
// Golden checks for the provider registry + model→provider resolution.
// Pure logic; no network. Run: node scripts/test-provider-seam.mjs
import assert from "node:assert";
import {
  registerProvider, getProvider, hasProvider, resolveProviderForModel,
  GEMINI_PROVIDER_ID, COHERE_NORTH_PROVIDER_ID,
} from "../lib/llm/provider.ts";

// resolveProviderForModel: today's models all route to gemini.
assert.equal(resolveProviderForModel("gemini-3.1-pro-preview"), GEMINI_PROVIDER_ID);
assert.equal(resolveProviderForModel("gemini-2.5-flash"), GEMINI_PROVIDER_ID);
assert.equal(resolveProviderForModel("text-embedding-004"), GEMINI_PROVIDER_ID);
assert.equal(resolveProviderForModel(""), GEMINI_PROVIDER_ID);
// R2 forward-compat: cohere/command names route to cohere-north.
assert.equal(resolveProviderForModel("cohere-north-default"), COHERE_NORTH_PROVIDER_ID);
assert.equal(resolveProviderForModel("command-r-plus"), COHERE_NORTH_PROVIDER_ID);

// registry: register/get/has + clear error on missing id.
assert.equal(hasProvider("test-x"), false);
const fake = { id: "test-x", invoke: async () => ({ ok: true }) };
registerProvider(fake);
assert.equal(hasProvider("test-x"), true);
assert.strictEqual(getProvider("test-x"), fake);
assert.throws(() => getProvider("nope"), /No LLM provider registered/);

console.log("provider-seam: OK");
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd mcp/agent && node scripts/test-provider-seam.mjs`
Expected: FAIL — `Cannot find module '../lib/llm/provider.ts'`.

- [ ] **Step 3: Implement `lib/llm/provider.ts`**

Create `mcp/agent/lib/llm/provider.ts`:

```ts
import type { EffectiveRuntimeConfig } from "@/lib/runtime-config";

/** Context threaded to every provider invocation. */
export type LLMInvokeContext = {
  runtimeConfig: EffectiveRuntimeConfig;
  modelName: string;
};

/**
 * A model backend. The canonical interchange is the Gemini generateContent
 * request (`GeminiCallPayload`, built by the caller) and response object
 * (decoded by the caller). Adapters translate only at the wire, so the
 * agent loop is provider-agnostic without a bespoke neutral IR.
 */
export interface LLMProvider {
  readonly id: string;
  invoke(payload: unknown, ctx: LLMInvokeContext): Promise<unknown>;
}

export const GEMINI_PROVIDER_ID = "gemini";
export const COHERE_NORTH_PROVIDER_ID = "cohere-north";

const registry = new Map<string, LLMProvider>();

export function registerProvider(provider: LLMProvider): void {
  registry.set(provider.id, provider);
}

export function hasProvider(id: string): boolean {
  return registry.has(id);
}

export function getProvider(id: string): LLMProvider {
  const provider = registry.get(id);
  if (!provider) {
    throw new Error(
      `No LLM provider registered for id '${id}'. Configure a model provider at /providers, then retry.`,
    );
  }
  return provider;
}

/**
 * Map a model name to its provider id. R1: every model that exists today is
 * a Google model → 'gemini' (the GeminiProvider handles the Vertex vs
 * API-key choice internally). The cohere/command prefixes are R2 forward-compat.
 */
export function resolveProviderForModel(modelName: string): string {
  const m = (modelName || "").toLowerCase();
  if (m.startsWith("cohere") || m.startsWith("command")) {
    return COHERE_NORTH_PROVIDER_ID;
  }
  return GEMINI_PROVIDER_ID;
}
```

- [ ] **Step 4: Wire the script into `npm test` and run it**

In `mcp/agent/package.json`, change the `test` script to chain both:

```json
"test": "npm run test:json-to-yaml && node scripts/test-provider-seam.mjs",
```

Run: `cd mcp/agent && node scripts/test-provider-seam.mjs`
Expected: `provider-seam: OK`.

> Note: `node` runs `.ts` imports directly under the repo's Node version (the existing `test-json-to-yaml.mjs` imports `.mjs`; if `node` cannot resolve the `.ts` import in this environment, change the import to a compiled path or run via `npx tsx scripts/test-provider-seam.mjs` and use that in the `test` script instead). Verify which works before committing.

- [ ] **Step 5: Commit**

```bash
git add mcp/agent/lib/llm/provider.ts mcp/agent/scripts/test-provider-seam.mjs mcp/agent/package.json
git commit -m "feat(llm): provider registry + model→provider resolution seam (R1, Refs #98)"
```

---

## Task 2: Extract the shared Gemini dispatch + register `geminiProvider`

**Files:**
- Modify: `mcp/agent/app/api/chat/route.ts`

**Interfaces:**
- Consumes: `LLMProvider`, `registerProvider`, `GEMINI_PROVIDER_ID`, `LLMInvokeContext` from Task 1; existing `callGeminiWithApiKey`, `callGeminiWithVertex`, `isInvalidGeminiApiKeyError`, `GeminiCallPayload`, `EffectiveRuntimeConfig`.
- Produces: `dispatchGeminiPayload(payload: GeminiCallPayload, runtimeConfig: EffectiveRuntimeConfig, modelName: string): Promise<unknown>` and a module-level registered `geminiProvider`.

This task is a **pure refactor**: the api-key→vertex branch currently appears identically inside both `callGeminiRaw` (route.ts:1252-1269) and `callGemini` (route.ts:3437-3462). Extract it once, verbatim.

- [ ] **Step 1: Add the import**

Near the other `@/lib` imports at the top of `route.ts`:

```ts
import {
  LLMProvider,
  LLMInvokeContext,
  registerProvider,
  getProvider,
  resolveProviderForModel,
  GEMINI_PROVIDER_ID,
} from "@/lib/llm/provider";
```

- [ ] **Step 2: Add `dispatchGeminiPayload` + register the provider**

Immediately AFTER the `callGeminiWithVertex` definition (route.ts:~3182), add — this is the exact branch copied from the current call sites, no logic change:

```ts
/**
 * The Gemini/Vertex dispatch, extracted once from callGemini/callGeminiRaw.
 * Chooses the API-key path first (with vertex fallback on an invalid key),
 * else the Vertex SA path. Behavior-identical to the pre-seam call sites.
 */
async function dispatchGeminiPayload(
  payload: GeminiCallPayload,
  runtimeConfig: EffectiveRuntimeConfig,
  modelName: string,
): Promise<unknown> {
  if (runtimeConfig.GEMINI_API_KEY) {
    try {
      return await callGeminiWithApiKey(payload, runtimeConfig, modelName);
    } catch (error) {
      if (
        runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS &&
        isInvalidGeminiApiKeyError(error)
      ) {
        return callGeminiWithVertex(payload, runtimeConfig, modelName);
      }
      throw error;
    }
  }
  if (runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS) {
    return callGeminiWithVertex(payload, runtimeConfig, modelName);
  }
  throw new Error(
    "No model provider is configured. Add a Vertex AI or Gemini API provider at /providers, then try again.",
  );
}

/** The Gemini adapter — canonical interchange in, Gemini response out. */
const geminiProvider: LLMProvider = {
  id: GEMINI_PROVIDER_ID,
  invoke: (payload, ctx: LLMInvokeContext) =>
    dispatchGeminiPayload(
      payload as GeminiCallPayload,
      ctx.runtimeConfig,
      ctx.modelName,
    ),
};
registerProvider(geminiProvider);
```

- [ ] **Step 3: Type-check**

Run: `cd mcp/agent && npx tsc --noEmit`
Expected: PASS (no errors; the new function + object are consistent with existing types).

- [ ] **Step 4: Commit**

```bash
git add mcp/agent/app/api/chat/route.ts
git commit -m "refactor(chat): extract dispatchGeminiPayload + register geminiProvider (R1, Refs #98)"
```

---

## Task 3: Rewire the 3 call sites to dispatch via the registry

**Files:**
- Modify: `mcp/agent/app/api/chat/route.ts`

**Interfaces:**
- Consumes: `dispatchGeminiPayload`/`geminiProvider` (Task 2), `getProvider`, `resolveProviderForModel` (Task 1).

Each site keeps building the payload exactly as today; only the final dispatch changes from the inline branch to `getProvider(resolveProviderForModel(modelName)).invoke(...)`. Net behavior is identical because `resolveProviderForModel` returns `'gemini'` for all current models.

- [ ] **Step 1: Rewire `callGeminiRaw` (route.ts:1252-1269)**

Replace the body after `const modelName = resolveModelName(modelOverride, runtimeConfig);` — i.e. replace the whole `if (runtimeConfig.GEMINI_API_KEY) { ... } ... throw new Error(...)` block — with:

```ts
  const modelName = resolveModelName(modelOverride, runtimeConfig);
  return getProvider(resolveProviderForModel(modelName)).invoke(payload, {
    runtimeConfig,
    modelName,
  });
```

- [ ] **Step 2: Rewire `callGemini` (route.ts:3437-3462)**

Same replacement: after `const modelName = resolveModelName(modelOverride, runtimeConfig);`, replace the api-key/vertex branch + trailing throw with:

```ts
  const modelName = resolveModelName(modelOverride, runtimeConfig);
  return getProvider(resolveProviderForModel(modelName)).invoke(payload, {
    runtimeConfig,
    modelName,
  });
```

- [ ] **Step 3: Rewire `summarizeViaGemini` (route.ts:~3352)**

Locate `summarizeViaGemini` (the /compress compaction caller). It builds a `GeminiCallPayload` and dispatches via the same branch. Apply the identical replacement: after it resolves the model name, dispatch via `getProvider(resolveProviderForModel(modelName)).invoke(payload, { runtimeConfig, modelName })`. (Read the current body first — if it calls `callGeminiWithVertex`/`callGeminiWithApiKey` directly with a hardcoded model, thread its model name through `resolveProviderForModel` the same way.)

- [ ] **Step 4: Verify no direct dispatch call sites remain outside the provider**

Run: `cd mcp/agent && grep -n "callGeminiWithApiKey\|callGeminiWithVertex" app/api/chat/route.ts`
Expected: the ONLY references are inside `dispatchGeminiPayload` (and the two function definitions themselves). If any other call site references them directly, rewire it the same way.

- [ ] **Step 5: Type-check + build**

Run: `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp/agent/app/api/chat/route.ts
git commit -m "refactor(chat): route all LLM dispatch through the provider registry (R1, Refs #98)"
```

---

## Task 4: Regression gate — golden + live Gemini smoke

**Files:**
- Modify: `mcp/agent/scripts/test-provider-seam.mjs` (add a dispatch-routing assertion)

- [ ] **Step 1: Add a routing-invariant assertion to the golden script**

Append to `test-provider-seam.mjs` (proves that for every model the models catalog can emit today, the resolved provider is `gemini`):

```js
// R1 invariant: every current model routes to gemini (no cohere yet configured).
for (const m of [
  "gemini-3.1-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash",
  "gemini-2.0-flash", "text-embedding-004", "text-embedding-005",
]) {
  assert.equal(resolveProviderForModel(m), GEMINI_PROVIDER_ID, `model ${m} must route to gemini in R1`);
}
console.log("provider-seam routing invariant: OK");
```

Run: `cd mcp/agent && node scripts/test-provider-seam.mjs`
Expected: both `OK` lines.

- [ ] **Step 2: Full pre-deploy gate**

Run from `mcp/agent`: `npx tsc --noEmit && npm run lint && npm run build`
Run from `bundles/spark/mcp`: `PYTHONPATH=$PWD/src python3 -m pytest tests/ -x`
Expected: all green.

- [ ] **Step 3: Push + let CI auto-deploy**

```bash
git push origin main
```
Watch `build-dev-installer.yml` to completion; confirm `GUARDIAN_VERSION` on guardian-vm matches `git rev-parse --short HEAD` (own the wait — do not punt to the operator).

- [ ] **Step 4: Live Gemini investigation smoke (the real regression proof)**

Against the deployed agent (IAP tunnel + `GUARDIAN_API_KEY` bearer), run one full tool-using turn on a Gemini model and confirm it behaves exactly as before:

```bash
# POST /api/chat with a simple tool-using prompt (e.g. "list the connected XSOAR instances")
# on the default Gemini model; assert: SSE streams text, a tool call fires and returns,
# the turn completes, and a chat_turn_cost audit row is written (usageMetadata intact).
```
Expected: identical behavior to pre-R1 — streaming, tool dispatch, thinking events, and cost accounting all unchanged. Apply `status:ready-for-testing` on #98 after this passes.

---

## Task 5: Docs — architecture section + release notes

**Files:**
- Modify: `mcp/agent/app/help/architecture/page.tsx` (add `#model-providers`)
- Modify: `CHANGELOG.md`
- Modify: `mcp/agent/lib/release-notes.ts`

- [ ] **Step 1: Add the `#model-providers` architecture section**

Add a `Section` (per the help-page-update skill's `Section`/`SubSection` shape) with `id="model-providers"` describing: the `LLMProvider` interface + registry, that the canonical interchange is the Gemini `generateContent` shape, the two-level dispatch (model→provider outer; Google api-key-vs-vertex inner), and that adapters translate only at the wire. State the R1 gap explicitly: "Cohere North adapter lands in R2 (guardian#98)." Add `<ModelProviders />` to the render list next to its sibling sections.

- [ ] **Step 2: CHANGELOG + release-notes entry**

`CHANGELOG.md` — a top entry describing R1 as an internal refactor with no operator-visible change, and the arc note: *"Prerequisite for the Cohere North provider (guardian#98) — the provider-adapter seam; Cohere ships in R2."* `release-notes.ts` — one newest-first highlight (~12 words): *"Model backends now run through a provider adapter — Cohere support coming."*

- [ ] **Step 3: Gate + commit**

Run the full pre-deploy gate again (docs touch `page.tsx` → `npm run build` validates it). Then:

```bash
git add mcp/agent/app/help/architecture/page.tsx CHANGELOG.md mcp/agent/lib/release-notes.ts
git commit -m "docs(llm): document the provider-adapter seam (#model-providers) (R1, Refs #98)"
```

---

## Self-Review

**1. Spec coverage** (against §3.1 + §4 of the spec):
- `LLMProvider` interface + registry → Task 1. ✓
- Canonical interchange = Gemini shape → Tasks 2-3 (payload passed through, response decoded by loop unchanged). ✓
- `GeminiProvider` = verbatim dispatch → Task 2. ✓
- `resolveProviderForModel` (all → gemini in R1) → Task 1. ✓
- 3 call sites rewired → Task 3. ✓
- Loop decode/serialize/tool-inject/cost untouched → guaranteed (no task edits them). ✓
- Hard regression gate (golden + live Gemini) → Task 4. ✓
- Pricing/context-cap tables NOT touched in R1 → confirmed (no task touches them; matches revised §4). ✓

**2. Placeholder scan:** Task 3 Step 3 (`summarizeViaGemini`) says "read the current body first" because its exact model-name handling wasn't captured verbatim — this is a genuine read-then-apply, not a hand-wave; the transformation is fully specified. The `node` vs `npx tsx` note in Task 1 Step 4 is a real environment check, resolved before commit. No TBD/TODO left.

**3. Type consistency:** `LLMProvider.invoke(payload: unknown, ctx: LLMInvokeContext)` (Task 1) matches the `geminiProvider.invoke` definition + the call-site `.invoke(payload, { runtimeConfig, modelName })` (Tasks 2-3). `resolveProviderForModel`/`getProvider` names identical across tasks. `dispatchGeminiPayload` signature stable between definition (Task 2) and the grep check (Task 3 Step 4).

**Regression risk note:** the only way R1 changes behavior is if `resolveProviderForModel` ever returns non-`'gemini'` for a current model (it can't — all current names are `gemini-*`/`text-embedding-*`) or if the extracted `dispatchGeminiPayload` diverges from the originals (it's a verbatim copy; Task 4's live smoke catches any drift). Everything else is pass-through.
