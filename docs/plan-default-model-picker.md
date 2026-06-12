# Default-Model Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator set a default model on Settings → Models (a "Set as default" control on the model detail page), persist it in `operator_state.db`, and have the chat window use it automatically — replacing the opaque "auto" with a "Default — `<model>`" entry, while still allowing a per-chat override.

**Architecture:** The persistence layer **already exists and is reused as-is** — the `operator_state` key-value store, its MCP REST routes (`GET/PUT/DELETE /api/v1/operator-state/{key}`), and the agent proxy (`/api/agent/operator-state/[key]`). The default lives at key `default_model = {provider, model}`. The work is: (1) the chat route reads that key server-side (mirroring the existing `readSubagentsEnabled` pattern) and feeds it into `resolveModelName`; (2) the chat dropdown shows a dynamic "Default — `<model>`" entry instead of "auto"; (3) the model detail page gets a "Set as default" radio that `PUT`s the key; (4) the models-page "default" badge goes live. No new MCP endpoint, no Python.

**Tech Stack:** Next.js 15 / React 19 / TypeScript (the `guardian-agent` UI + chat route). Verified by `tsc --noEmit` + `eslint` + `next build` (the agent has no JS unit-test runner) plus a deployed smoke. No Python changes.

**Source spec:** [`docs/spec-default-model-picker.md`](spec-default-model-picker.md). **Resolves the spec's §10 open items:** use the existing generic operator-state surface (no new `/api/v1/config/default-model` endpoint).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `mcp/agent/lib/runtime-config.ts` | `EffectiveRuntimeConfig` — add a `defaultModel?: string \| null` field the chat route populates. | modify |
| `mcp/agent/app/api/chat/route.ts` | `readDefaultModel()` (mirror `readSubagentsEnabled`) reads operator-state `default_model`; the POST handler sets `runtimeConfig.defaultModel`; `resolveModelName` reads it before `GEMINI_MODEL`. | modify |
| `mcp/agent/app/models/[model]/page.tsx` | "Set as default" control → `PUT /api/agent/operator-state/default_model`; the page's default badge reads the live value. | modify |
| `mcp/agent/app/models/page.tsx` | The stubbed `defaultModel` state goes live (reads `/api/agent/operator-state/default_model`) so the list "default" badge renders on the right card. | modify |
| `mcp/agent/components/chat/chat-header.tsx` + `use-chat.ts` + the chat page that wires them | Replace the dropdown's "auto" with a "Default — `<model>`" entry (pre-selected, sends no override); fetch the operator default to populate `defaultModel`. | modify |
| Docs: `app/help/architecture/page.tsx`, `app/help/user/page.tsx`, `lib/journeys.ts`, `CHANGELOG.md`, `lib/release-notes.ts` | Document the resolution chain + the operator flow. | modify |

**Verification reality:** the agent side has **no JS unit-test framework** — correctness is `tsc`/`lint`/`build` + a deployed smoke (set default → `GET` shows it → chat uses it). Each task ends by building; the final task does the live smoke. (The MCP operator-state store is already pytest-covered; this feature adds no Python.)

**Read before starting:** `mcp/agent/CLAUDE.md` (the agent conventions, the pre-deploy gate, the proxy pattern) and the spec.

---

## Task 1: chat route reads the operator default + `resolveModelName` uses it

**Files:** Modify `mcp/agent/lib/runtime-config.ts`, `mcp/agent/app/api/chat/route.ts`.

- [ ] **Step 1: Add `defaultModel` to the runtime-config type**

In `mcp/agent/lib/runtime-config.ts`, find the `EffectiveRuntimeConfig` interface/type and add a field (place it near `GEMINI_MODEL`):
```ts
  /** Operator-chosen default model (operator_state.db key `default_model`),
   *  populated per chat request by route.ts. Null = no default set → fall
   *  back to GEMINI_MODEL. */
  defaultModel?: string | null;
```
(Do NOT make `getEffectiveRuntimeConfig` fetch it — runtime-config derives from the filesystem, not network/operator-state, per root CLAUDE.md § Canonical-state Rule 3. The chat route populates this field after building the config.)

- [ ] **Step 2: Add `readDefaultModel()` to the chat route (mirror `readSubagentsEnabled`)**

In `mcp/agent/app/api/chat/route.ts`, near the existing `readSubagentsEnabled()` (search for it — ~line 1810), add:
```ts
/**
 * Read the operator's default model from operator-state (`default_model`).
 * Mirrors readSubagentsEnabled. The model detail page sets this via
 * PUT /api/v1/operator-state/default_model {value: {provider, model}}.
 * Returns the model id string, or null if unset/unreadable (→ caller falls
 * back to GEMINI_MODEL). Never throws.
 */
async function readDefaultModel(): Promise<string | null> {
  try {
    const result = await callMcpServer<{ value?: unknown }>(
      `/api/v1/operator-state/${encodeURIComponent('default_model')}`,
    );
    const raw = result?.value;
    if (raw && typeof raw === 'object' && 'model' in (raw as Record<string, unknown>)) {
      const m = (raw as Record<string, unknown>).model;
      return typeof m === 'string' && m.length > 0 ? m : null;
    }
    return null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 3: `resolveModelName` reads the default before the env var**

In `route.ts`, change `resolveModelName` (search `function resolveModelName`) from:
```ts
  return modelOverride || runtimeConfig.GEMINI_MODEL || 'gemini-3.1-pro-preview';
```
to:
```ts
  return modelOverride
    || runtimeConfig.defaultModel
    || runtimeConfig.GEMINI_MODEL
    || 'gemini-3.1-pro-preview';
```

- [ ] **Step 4: Populate `runtimeConfig.defaultModel` once per request**

In the chat `POST` handler, where `runtimeConfig` is obtained (search `getEffectiveRuntimeConfig(`), set the default right after — alongside how `readSubagentsEnabled()` is already awaited per request. Add (adapt the exact variable name to the handler):
```ts
  // Operator's default model (operator_state.db). Populated here so every
  // resolveModelName() call in this request honors it. null → GEMINI_MODEL.
  runtimeConfig.defaultModel = await readDefaultModel();
```
If `runtimeConfig` is a `const` from `getEffectiveRuntimeConfig`, mutating one field is fine (it's a per-request object); if TS complains about mutating a readonly, instead build a shallow copy: `const rc = { ...await getEffectiveRuntimeConfig(), defaultModel: await readDefaultModel() }` and use `rc` thereafter. Pick whichever matches the handler's existing shape; the goal is `resolveModelName` sees `defaultModel`.

- [ ] **Step 5: Build (the gate for this TS change)**

Run: `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build`
Expected: all pass. (If `resolveModelName` is called from a path that doesn't populate `defaultModel`, the `|| runtimeConfig.GEMINI_MODEL` fallback keeps behavior unchanged — confirm no call site breaks.)

- [ ] **Step 6: Commit**
```bash
cd "$(git rev-parse --show-toplevel)"
git add mcp/agent/lib/runtime-config.ts mcp/agent/app/api/chat/route.ts
git commit -m "chat: resolve the operator default model (operator_state) before the GEMINI_MODEL env

Refs the default-model picker.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: "Set as default" control on the model detail page

**Files:** Modify `mcp/agent/app/models/[model]/page.tsx`.

- [ ] **Step 1: Read the detail page to find the model + the header area**

Read `mcp/agent/app/models/[model]/page.tsx`. Note: how it gets the current model (`model`/`provider` from the route + the fetched `ModelInfo`), the glass `header` block (~line 144), and the existing default-badge comment (~line 11). Identify a spot in the header (near the model name `<h1>`) for the control.

- [ ] **Step 2: Add state + the setter + the control**

Add React state for the current default + a busy flag, fetch the current default on mount, and render a "Set as default" control. Concretely, inside `ModelDetailPage`:
```tsx
  const [defaultModel, setDefaultModel] = useState<{ provider?: string; model?: string } | null>(null);
  const [savingDefault, setSavingDefault] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/agent/operator-state/default_model")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setDefaultModel((d?.value as { provider?: string; model?: string }) ?? null); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const isDefault = defaultModel?.model === model?.model;

  async function makeDefault() {
    if (!model) return;
    setSavingDefault(true);
    try {
      const res = await fetch("/api/agent/operator-state/default_model", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: { provider: model.provider, model: model.model } }),
      });
      if (res.ok) setDefaultModel({ provider: model.provider, model: model.model });
    } finally {
      setSavingDefault(false);
    }
  }
```
Then render a control in the header (place near the `<h1>` model name). Use Material-3 semantic tokens (no hex), matching the page's style:
```tsx
  <button
    type="button"
    onClick={makeDefault}
    disabled={savingDefault || isDefault || model?.wip}
    aria-pressed={isDefault}
    className="mt-2 inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-label border border-outline-variant text-on-surface disabled:opacity-60"
  >
    <span className="material-symbols-rounded text-base">
      {isDefault ? "radio_button_checked" : "radio_button_unchecked"}
    </span>
    {isDefault ? "Default model" : savingDefault ? "Saving…" : "Set as default"}
  </button>
```
(If the page already imports `useState`/`useEffect`, reuse; otherwise add them to the existing `react` import.)

- [ ] **Step 3: Build**

Run: `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build`
Expected: pass.

- [ ] **Step 4: Commit**
```bash
git add "mcp/agent/app/models/[model]/page.tsx"
git commit -m "models: Set-as-default control on the model detail page (writes operator_state default_model)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: live "default" badge on the models list

**Files:** Modify `mcp/agent/app/models/page.tsx`.

- [ ] **Step 1: Make the stubbed `defaultModel` live**

Read `mcp/agent/app/models/page.tsx`. Find the stub (`const [defaultModel] = useState<{ model: string; provider: string } | null>(null);`, ~line 180) and the comment above it ("Guardian doesn't yet expose a 'default model' config"). Replace the stub so it fetches the live value:
```tsx
  const [defaultModel, setDefaultModel] = useState<{ model: string; provider: string } | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/agent/operator-state/default_model")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const v = d?.value as { provider?: string; model?: string } | undefined;
        if (!cancelled && v?.model) setDefaultModel({ model: v.model, provider: v.provider ?? "" });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
```
Update the stale comment to: `// Default model = operator_state.db key 'default_model' (set on a model's detail page). The badge highlights the matching card.` Leave the existing badge-render branch (the `defaultModel !== null && defaultModel.model === model.model …` comparison ~line 361) unchanged — it now receives a real value.

- [ ] **Step 2: Build + commit**
```bash
cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build
cd "$(git rev-parse --show-toplevel)"
git add mcp/agent/app/models/page.tsx
git commit -m "models: live default badge on the list (reads operator_state default_model)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: chat dropdown — "Default — `<model>`" instead of "auto"

**Files:** Modify the chat page (the one that calls `useChat`), `mcp/agent/components/chat/chat-header.tsx`, `mcp/agent/components/chat/use-chat.ts` as needed.

- [ ] **Step 1: Trace how the dropdown gets `defaultModel` + where "auto" renders**

Read `mcp/agent/components/chat/chat-header.tsx` (the `ModelOption` interface + the model-picker render — search for where `models` is mapped to options and where the current/"auto" label is shown) and `use-chat.ts` (`defaultModel`, `overrideModel`, `currentModel: overrideModel || options?.defaultModel`, line ~1604; `effectiveModel` line ~710). Find the chat **page** that constructs `useChat({ ... })` and passes `defaultModel` — identify where that `defaultModel` value comes from today (this is the source of "auto").

- [ ] **Step 2: Feed the operator default into the chat page**

In the chat page, fetch the operator default once and pass it as `useChat`'s `defaultModel`:
```tsx
  const [opDefaultModel, setOpDefaultModel] = useState<string | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/agent/operator-state/default_model")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const m = (d?.value as { model?: string } | undefined)?.model;
        if (!cancelled && typeof m === "string" && m) setOpDefaultModel(m);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
```
Pass `defaultModel: opDefaultModel ?? <existing fallback>` into `useChat(...)` (keep the existing fallback for when no default is set, so behavior is unchanged on a fresh install).

- [ ] **Step 3: Relabel the dropdown's "auto" entry → "Default — `<model>`"**

In `chat-header.tsx`'s model picker, the entry that represents "use the default / no override" (currently shown as "auto") must instead read **`Default — ${defaultModel}`** (the resolved default model name), and selecting it must continue to send **no override** (so `resolveModelName` resolves server-side to the operator's default). Concretely: where the option list is built, the first/sentinel entry's label becomes `` `Default — ${defaultModel ?? "model"}` `` and its selection clears `overrideModel` (the existing "use default" path). Remove the literal "auto" label. The specific models stay as override options. Match the component's existing option-rendering shape (don't restructure the picker).

- [ ] **Step 4: Build**

Run: `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build`
Expected: pass. Eyeball that no "auto" string literal remains in the model picker: `grep -nE '"auto"|>auto<|Auto' mcp/agent/components/chat/chat-header.tsx` should show none in the model-picker block (other unrelated "auto" — e.g. approval/compaction — are fine).

- [ ] **Step 5: Commit**
```bash
git add mcp/agent/components/chat/chat-header.tsx mcp/agent/components/chat/use-chat.ts mcp/agent/app/chat
git commit -m "chat: dropdown shows 'Default — <model>' (operator default) instead of 'auto'

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: docs — architecture, user guide, journeys, release notes

**Files:** Modify `mcp/agent/app/help/architecture/page.tsx`, `mcp/agent/app/help/user/page.tsx`, `mcp/agent/lib/journeys.ts`, `CHANGELOG.md`, `mcp/agent/lib/release-notes.ts`.

- [ ] **Step 1: Architecture page — the resolution chain**

In `app/help/architecture/page.tsx`, add to the models/chat section a short note (match the page's `Section`/`Code` component conventions — read the help-page-update conventions first):
> **Default model.** The chat model resolves as `per-chat override → operator default → `GEMINI_MODEL` env → hardcoded`. The operator default is `operator_state.db` key `default_model = {provider, model}`, set on Settings → Models → [model] → "Set as default", read by the chat route via `GET /api/v1/operator-state/default_model`.

- [ ] **Step 2: User guide — the operator flow**

In `app/help/user/page.tsx`, add a paragraph (tagged with the introducing version): "Pick your default chat model on **Settings → Models**, open a model, and click **Set as default**. New chats use it automatically (shown as 'Default — <model>' in the model dropdown); you can still switch models per chat."

- [ ] **Step 3: Journey**

In `lib/journeys.ts`, add a journey: Models → open a model → Set as default → open Chat → confirm the dropdown shows "Default — <model>" pre-selected.

- [ ] **Step 4: CHANGELOG + release-notes**

Add a `CHANGELOG.md` entry (operator language) and a matching newest-first `mcp/agent/lib/release-notes.ts` highlight (~12 words): "Set a default chat model on Settings → Models; the chat window uses it (no more 'auto')."

- [ ] **Step 5: Build + commit**
```bash
cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build
cd "$(git rev-parse --show-toplevel)"
git add mcp/agent/app/help/architecture/page.tsx mcp/agent/app/help/user/page.tsx mcp/agent/lib/journeys.ts CHANGELOG.md mcp/agent/lib/release-notes.ts
git commit -m "docs: default-model picker — architecture chain, user guide, journey, release notes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: verify end-to-end on the deployed install (acceptance)

**Files:** none (verification). Runs against guardian-vm via the IAP tunnel.

- [ ] **Step 1: Land + deploy**

Merge the branch to `main` (finishing-a-development-branch) and push; the build chain rebuilds the agent + auto-deploys. Wait for `Build agent` → `Build dev installer` → "Auto-deploy on guardian-vm" to go green (own the wait).

- [ ] **Step 2: Set a default via the API path the UI uses, then confirm persistence**

Via the IAP tunnel + the bearer (`GUARDIAN_API_KEY`), exercise the operator-state surface the UI writes:
```bash
# (in the standard tunnel session, agent on local 3001)
curl -sk -X PUT -H "Authorization: Bearer $GUARDIAN_API_KEY" -H "Content-Type: application/json" \
  https://localhost:3001/api/agent/operator-state/default_model \
  -d '{"value":{"provider":"gemini","model":"gemini-3.5-flash"}}'
curl -sk -H "Authorization: Bearer $GUARDIAN_API_KEY" \
  https://localhost:3001/api/agent/operator-state/default_model
```
Expected: the GET returns `{"value":{"provider":"gemini","model":"gemini-3.5-flash"}}` (the persisted default). Use a model id that actually appears in `GET /api/agent/models`.

- [ ] **Step 3: Confirm the chat uses it**

Start a chat turn with NO model override (a job-style `prompt` or a `/api/chat` POST without a model field) and verify the recorded run used the operator default (check the run's `model` in the audit / job run, or the chat response metadata). Then POST again with an explicit different model → confirm the override wins.

- [ ] **Step 4: Operator hands-on (UI — needs the operator session)**

Operator: Settings → Models → open a model → "Set as default" lights up; open Chat → the dropdown reads "Default — <model>" pre-selected; switch to another model → it sticks for that chat. (This is the one step requiring the operator's logged-in session; the API smoke above pre-verifies the wiring.)

---

## Self-Review

**1. Spec coverage** (against `docs/spec-default-model-picker.md`):
- §4.1 persistence in operator_state.db → reused existing store; key `default_model`. ✓
- §4.2 backend surface → **resolved to the existing generic operator-state REST + proxy** (no new endpoint — this is the spec's §10 open item resolved). ✓
- §4.3 radio on detail page + live list badge → Tasks 2, 3. ✓
- §4.4 resolveModelName chain + dropdown "Default — <model>" replacing "auto" → Tasks 1, 4. ✓
- §6 error handling (unset → GEMINI_MODEL fallback; unreadable → null) → Task 1 `readDefaultModel` returns null on any non-conforming/missing value. ✓ (Strict model-exists validation from spec §6 is dropped — the radio only ever sets a real `{provider, model}` from a real model's page, so validation is implicit; noted here as a deliberate simplification.)
- §7 testing → tsc/lint/build per task + the deployed smoke (Task 6); no JS unit framework exists, stated up front. ✓
- §8 docs → Task 5 (architecture/user/journeys/CHANGELOG/release-notes). ✓
- §9 decisions (operator_state storage; dynamic "Default" entry; REST/operator-only; detail-page radio) → all reflected. ✓

**2. Placeholder scan:** No TBD/TODO. The UI tasks say "read the current file, add this control at <location>" with the actual control code provided — concrete, not a placeholder. The one spec requirement intentionally dropped (strict model-exists validation) is called out with the reason. ✓

**3. Type/name consistency:** operator-state key `default_model` and value shape `{provider, model}` are identical across the chat read (Task 1 `readDefaultModel`), the detail-page write (Task 2 PUT body `{value:{provider,model}}`), the list badge read (Task 3), the chat-page read (Task 4), and the smoke (Task 6). `runtimeConfig.defaultModel` (string|null) is defined in Task 1 Step 1 and used in Step 3's `resolveModelName`. The agent proxy path `/api/agent/operator-state/default_model` is consistent across Tasks 2–4 + 6. ✓
