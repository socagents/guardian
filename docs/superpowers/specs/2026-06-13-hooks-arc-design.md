# Guardian hooks arc — design (recommendation)

> 4-agent research+design workflow, 2026-06-13. NOT operator-approved; recommendation to review.

I have full grounding. The command transport spawns with `{ ...process.env, ...resolveSecretEnv(...) }` — important for the security section (a command hook inherits the agent's full env including `MCP_TOKEN`/`GUARDIAN_API_KEY`, which is exactly why the credential-guardrail discussion matters). I now have everything needed to write the design.

---

# Guardian Hooks Arc — Design & Recommendation

Grounded in the real files: `mcp/agent/app/settings/hooks/page.tsx`, `mcp/agent/lib/hooks.ts`, `mcp/agent/lib/hook-runner.ts`, `mcp/agent/components/investigation/ui.tsx`, `mcp/agent/lib/api/investigation.ts`, and the connector tool catalog (`xsoar_*`, `xsiam_*`, `xql_lookup`).

This is a recommendation for operator review. It is actionable enough to execute, but per the contained-release discipline it splits into **two separate releases** (UI modernization, then the two hooks) — each with its own issue, scope, and one-journey smoke.

---

## 1. Hooks-page modernization plan

**One file to edit:** `mcp/agent/app/settings/hooks/page.tsx`. The data contract is stable — no changes to `/api/agent/hooks*` routes, no MCP-side changes, no type changes in `lib/hooks.ts`. Pure UI.

### 1a. The one-liner — exact placement

Replace the 5-line `<p>` at **lines 182–188** (the `text-sm text-on-surface-variant ml-9 max-w-2xl` block) with EXACTLY the operator's text. Keep the existing `ml-9` (aligns under the title past the icon) but widen to `max-w-3xl` so the single longer sentence doesn't wrap awkwardly:

```tsx
<p className="text-sm text-on-surface-variant ml-9 max-w-3xl leading-relaxed">
  Policy contributors that fire at chat-lifecycle events (tool calls, prompts,
  compaction, run start/end). Each hook runs through a transport (command, HTTP
  webhook) and may deny/ask/inject context. Configured here, executed
  transparently by every chat turn.
</p>
```

Note: this is the operator's verbatim one-liner — it is not shorter than the current blurb, it is the *canonical replacement*. Do not substitute the "Chat-lifecycle policy enforcement" string the UI report suggested; the operator dictated the exact text.

### 1b. Adopt the investigation `ui.tsx` primitives

Import from `@/components/investigation/ui` and delete the locally-defined `glassCard` (line 103–107) in favor of the shared `glassStyle`:

```tsx
import { glassStyle, Badge, StatCard, EmptyState, InvestigationTabBar } from "@/components/investigation/ui";
```

Confirmed signatures (read from source):
- `StatCard({ icon, label, value, tone? })` — glass card, big number + uppercase label.
- `Badge({ tone?, children })` — uppercase pill, `border`-based tone classes.
- `EmptyState({ icon, title, hint?, children? })` — centered glass card; `children` slot takes the CTA button.
- `InvestigationTabBar<T>({ tabs, active, onChange })` — underline tab bar; `tabs: {key,label,icon}[]`.

### 1c. Redesigned views (concrete "ugly" fixes)

**List view (the page body).** Add a **StatCard row** above the list, derived client-side from the already-fetched `hooks` array (no new fetch):

```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
  <StatCard icon="webhook"     label="Total hooks"  value={hooks.length} />
  <StatCard icon="toggle_on"   label="Enabled"      value={hooks.filter(h => h.enabled !== false).length} tone="bg-primary/15 text-primary" />
  <StatCard icon="toggle_off"  label="Disabled"     value={hooks.filter(h => h.enabled === false).length} tone="bg-surface-container-high text-on-surface-variant" />
  <StatCard icon="lock"        label="Fail-closed"  value={hooks.filter(h => h.failurePolicy === "block").length} tone="bg-error/15 text-error" />
</div>
```

**Filter bar** (fixes "no search/filter"): a thin row of event-group + transport chips above the list, plus a name filter input. Pure client-side `.filter()` over the in-memory `hooks` — no API change.

**Row cards** (`HookRowCard`, lines 285–403) — fixes "dense rows":
- Swap the 6–8 inline `<span>` micro-badges for `Badge` with tone. Keep only **three** primary badges on the row: `event`, transport kind, and (when set) `fail-closed`. Demote `tool:<glob>` and `priority` into a muted second line, not first-line chips.
- Keep the existing toggle switch + edit/delete buttons (they work). Increase row padding `p-4 → p-5` and gap for breathing room.

**Empty state** (lines 227–244) — replace the hand-rolled block with the shared `EmptyState`, moving the "Add hook" CTA into its `children`:

```tsx
<EmptyState icon="webhook" title="No hooks registered"
  hint="A common starter is the slack-approval built-in on PreToolUse — routes destructive-tool approvals through your #soc-ops channel with just a webhook URL.">
  <button onClick={openNewHook} className="...primary CTA...">Add your first hook</button>
</EmptyState>
```

**Editor drawer** (`HookEditor`, line 407+) — fixes "flat drawer" + "no field grouping":
- Apply `glassStyle` + `backdropFilter: blur(16px)` to the drawer panel (replaces the flat `surface-container` + border-left).
- Group fields into sections using `InvestigationTabBar` *inside the drawer* with tabs: **Metadata** (name, description, priority) · **Matching** (event, toolGlob, triggerPrefix) · **Transport** (the existing transport picker + builtin/plugin config sections) · **Execution** (timeoutMs, failurePolicy). This directly reuses the investigation detail-page pattern and replaces the current single-column field dump.
- Header: show "Creating new hook…" vs "Editing <name>" (the `isNew` prop already exists at line 409).

**Delete flow** (fixes "crude `confirm()`", line 154): keep the native `confirm()` for the modernization release (it's safe and works) OR replace with a glass confirmation card. **Recommend deferring** the glass modal to a follow-up — swapping `confirm()` is the one change that risks scope creep on a "make it pretty" release. Note it inline as `// TODO(hooks-ui-2): glass delete modal`.

### 1d. Files touched (modernization release)

| File | Change |
|---|---|
| `mcp/agent/app/settings/hooks/page.tsx` | One-liner swap, import `ui.tsx` primitives, StatCard row, filter bar, slimmer `HookRowCard`, `EmptyState`, glass+tabbed `HookEditor`. |
| `mcp/agent/app/help/user/page.tsx` | Update/add `#hooks` user-guide section to reflect the modernized page (per documentation discipline). |
| `mcp/agent/lib/release-notes.ts` + `CHANGELOG.md` | One entry, newest-first. |
| `mcp/agent/lib/journeys.ts` | "Manage a chat-lifecycle hook" journey if not already present. |

Sidebar already has the `/settings/hooks` entry — no `sidebar.tsx` change.

---

## 2. Clever Guardian hook use-cases (ranked)

All are **safe under the credential guardrail**: none read/write SecretStore. They read investigation/incident *metadata* over REST (the catalog/workflow side) and emit decisions/context. Each is grounded in a real event (`lib/hooks.ts` `HOOK_EVENTS`) and real tools (`xsoar_*` / `xsiam_*`).

> Security note that shapes every command-transport idea below: `runCommandHook` spawns with `{ ...process.env, ...resolveSecretEnv(transport.env) }` (hook-runner.ts:317) — a command hook inherits the agent's full environment, **including `MCP_TOKEN` and `GUARDIAN_API_KEY`**. So a hook script *can* call back into the agent/MCP REST surface to read investigation state. It must be written to read-and-decide only, never to read a secret value and emit it. See Risks.

| # | Use-case | Event | Transport | Decision / inject | Why it's valuable for Guardian |
|---|---|---|---|---|---|
| **1** | **No-verdict close guard** — block `xsoar_close_incident` when the linked Guardian Issue's `summary` has no `VERDICT:` line. | `PreToolUse`, matcher `toolGlob: xsoar_close_incident` | command | `deny` + reason "Issue <id> has no recorded VERDICT — record a disposition before closing." | The single most damaging analyst mistake is closing an incident with no recorded disposition. `splitVerdict()` already parses the `VERDICT:` line from `Issue.summary`; this enforces it deterministically instead of hoping the LLM remembers. **(BUILD #1 — see §3.)** |
| **2** | **Bad-indicator auto-note** — when `xsoar_enrich_indicator` returns a DBotScore of 3 (malicious), auto-write an `xsoar_add_note` and inject a flag for the model. | `PostToolUse`, matcher `toolGlob: xsoar_enrich_indicator` | command | `injectContext`: "Indicator <ioc> scored DBotScore 3 (malicious). Treat as confirmed-bad; recommend containment." | DBotScore 3 is the bright-line "this is real." Surfacing it the instant enrichment returns means the analyst never misses a confirmed-bad IOC buried in a long result. DBotScore semantics are already encoded in `investigation.ts:332` (3 = bad). **(BUILD #2 — see §3.)** |
| **3** | **Open-incident context injector** — prepend the count of open Guardian Issues to every prompt. | `UserPromptSubmit` | command | `injectContext`: "Guardian queue: 7 open Issues, 2 critical. Most recent: INC-1242 (phishing)." | Gives the agent standing awareness of the live queue without the analyst pasting it. Reads `GET /api/agent/issues?status=open` (workflow-state side, no secrets). |
| **4** | **Verdict-preservation on compaction** — before context compaction, snapshot the active investigation's `VERDICT:` + scope so they survive the summarize. | `PreCompact` | command | `injectContext` carrying the verdict/scope text (does **not** deny — compaction proceeds). | Compaction is where investigations lose their thread. Re-anchoring the disposition post-summary keeps a long hunt coherent. Mirrors the canonical "re-inject conventions after compaction" pattern. |
| **5** | **Production-tenant change freeze** — block `xsiam_*` and `xsoar_run_playbook` writes during a declared change-freeze window. | `PreToolUse`, matcher `toolGlob: xsiam_*,xsoar_run_playbook` | command | `deny` (during window) + reason "Change freeze active until <time>; <tool> blocked." | A SOC-standard guardrail. Window read from a plain file the operator drops on the host — no secret involved. `failurePolicy: block` (fail-closed). |
| **6** | **Destructive-tool Slack approval** — route destructive XSOAR/XSIAM calls to Slack and await Approve/Deny. | `PreToolUse`, matcher `toolGlob: xsoar_close_incident,xsiam_*delete*` | **builtin** `slack-approval` (already shipped) | `ask` → approval card; Slack round-trip decides. | Zero new code — the `slack-approval` builtin exists. Best "configure via UI, no engineering" story. Webhook URL is config, not a secret read. |
| **7** | **Turn-cost budget warning** — warn when a chat turn exceeds a cost budget. | `RunEnd` | **builtin** `cost-warn-over-budget` (already shipped) | `injectContext` / notification only (RunEnd is non-decisional). | Cost governance for long autonomous hunts. Also zero new code. |

**Why these are safe:** #1–#5 read only Issue/incident *metadata* and emit decisions or context. #6/#7 are existing builtins. None call `providers_*`, `instances_*`, `api_keys_*`, or read SecretStore — consistent with the agent-credential guardrail.

---

## 3. The two to build first

Pick **#1 (PRE)** and **#2 (POST)** — highest IR value, both end-to-end smoke-testable on the VM, both `command` transport with a small read-only script. Each hook is created **via the UI / REST** (not shipped as an image default — see §4).

### Build hook A — `block-close-without-verdict` (PreToolUse)

- **Event:** `PreToolUse`
- **Matcher:** `{ "toolGlob": "xsoar_close_incident" }`
- **Transport:** `command` → `python3 /opt/guardian/hooks/block_close_without_verdict.py`
- **failurePolicy:** `block` (fail-closed — if the check can't run, don't allow the close)
- **timeoutMs:** `3000`

**Script contract** (stdin = `HookPayload` for `PreToolUse`: `{event, sessionId, toolName, args, trigger?}`; stdout = `HookResult` JSON):

1. Read JSON from stdin; pull the incident ref from `args` (e.g. `args.incident_id`).
2. `GET http://localhost:8080/api/v1/issues?source_ref=<ref>` using the inherited `MCP_TOKEN` bearer (read-only; no secret emitted).
3. Apply `splitVerdict()`-equivalent logic: does the matched Issue's `summary` start with `VERDICT:`?
   - **No** → emit `{"decision":"deny","reason":"Issue <id> has no recorded VERDICT — record a disposition before closing.","metadata":{"check":"verdict-gate"}}`
   - **Yes** → emit `{}` (no-op; close proceeds).
4. Quote every shell/JSON value; reject `..` in any path; never echo the token. Diagnostics → stderr only (stdout is reserved for the `HookResult` JSON — a stray `print` corrupts parsing, per the engine's stdout contract).

**Smoke test (observable end-to-end on the VM):**
- Trigger: in chat, ask the agent to close an incident whose Issue has **no** verdict.
- Observable: the tool call is blocked; the synthesized error carries the deny reason; the chat shows the agent reporting it can't close. Verify the `hook_dispatched` audit row at `/observability/events` (action `agent.hook.dispatched`) shows the deny.
- Negative case: record a `VERDICT:` line on the Issue, retry the same close → tool proceeds. Confirms no false-positive lockout.

### Build hook B — `flag-malicious-indicator` (PostToolUse)

- **Event:** `PostToolUse`
- **Matcher:** `{ "toolGlob": "xsoar_enrich_indicator" }`
- **Transport:** `command` → `python3 /opt/guardian/hooks/flag_malicious_indicator.py`
- **failurePolicy:** `warn` (POST is informational; a failed flag must never break the turn)
- **timeoutMs:** `3000`

**Script contract** (stdin = `PostToolUse` payload: `{event, sessionId, toolName, args, result, durationMs, trigger?}`; stdout = `HookResult`):

1. Parse `result`; find any indicator with DBotScore `== 3` (the `dbotMeta`/`investigation.ts:332` "bad" bucket).
2. If found → emit `{"injectContext":"Indicator <ioc> scored DBotScore 3 (malicious). Treat as confirmed-bad; recommend containment.","metadata":{"dbot":3,"ioc":"<ioc>"}}`. PostToolUse honors `injectContext` only — no `decision`.
3. If none → emit `{}`.
4. Same hardening: structured JSON parse, stderr-only diagnostics, no secret in output.

**Smoke test:**
- Trigger: in chat, ask the agent to enrich a known-bad indicator (e.g. a test IOC your XSOAR returns DBotScore 3 for).
- Observable: the agent's *next* turn references the injected "confirmed-bad / recommend containment" line that it was never told — proving the inject landed. Verify the `hook_dispatched` audit row shows the inject + the `metadata.dbot:3`.
- Negative: enrich a clean indicator (DBotScore 0/1) → no injection, agent behaves normally.

Both scripts are **read-only against MCP REST + decision/inject out** — they satisfy the guardrail and are independently smoke-testable with one chat action each.

---

## 4. Build sequence (contained releases)

Two releases, per one-concept-per-release discipline.

### Release A — Hooks-page modernization (UI-only)
- **Scenario 1** (code-only, installer unchanged, minor bump).
- One issue: "Modernize /settings/hooks UI + canonical one-liner." Operator-testable (UI surface change).
- Files: §1d. Ships its own `#hooks` user-guide anchor + one journey + release note.
- Smoke: the single journey — open `/settings/hooks`, see StatCards + slimmed rows + glass tabbed editor + the exact one-liner under the title; create/toggle/delete a throwaway hook.
- Tell the operator exactly: *review `/help/user#hooks`*.

### Release B — The two IR hooks
**Recommendation: create them via the UI/REST as operator-managed hooks, NOT as image-shipped defaults.** Rationale grounded in storage:

- Hooks persist in the **MCP-side SQLite `hooks.db`** (`hook_store.py`), created through `POST /api/v1/hooks`. There is **no image-baked default-hooks seed path** (unlike the skills volume auto-merge in `entrypoint.sh`). Shipping a hook "as a default" would require inventing a new seeding mechanism — scope creep, and it would re-create the v0.x "two storage homes / sync between them" trap that canonical-state discipline forbids.
- `command` hooks reference an **absolute host script path** (`/opt/guardian/hooks/*.py`). Those scripts must land on the customer host. The clean delivery is: ship the two scripts in the **installer kit** under `/opt/guardian/hooks/`, and document the exact `POST /api/v1/hooks` body (or UI steps) so the operator registers them. That keeps the *script* as shipped code and the *hook registration* as operator config — the right boundary.

So Release B is:
1. Add `block_close_without_verdict.py` + `flag_malicious_indicator.py` to the installer kit, deployed to `/opt/guardian/hooks/`.
2. Document registration in the user guide (`#hooks` extended) + provide copy-paste `POST /api/agent/hooks` bodies.
3. If the change touches the installer (it adds files to the install kit) → this is **Scenario 2** (code + installer change, MAJOR bump, `WIPE_VOLUMES=false`). Classify carefully before tagging.
4. Operator-testable; smoke per the two flows in §3, run by the agent via IAP tunnel, then operator hands-on.

> If the operator would rather these be true "defaults that appear on every install," that's a *third* release: build a `hooks.db` seed path in `entrypoint.sh` mirroring the skills auto-merge marker. That's a real feature, not a freebie — flag it as such, don't smuggle it in.

---

## 5. Risks

**Arbitrary command execution (the headline risk).** `command` hooks run via `spawn(transport.command, { shell: true })` with the agent's full environment. Per Anthropic's posture, hooks "execute arbitrary shell commands automatically without confirmation." Mitigations: ship the two scripts as **reviewed, absolute-path, repo-tracked files** (no operator-typed inline shell); quote every variable; reject `..` in paths; use structured JSON parsing not text scraping. Prefer the **builtin** transport (#6/#7) where possible — in-process, no subprocess.

**Credential guardrail.** A command hook inherits `MCP_TOKEN` + `GUARDIAN_API_KEY` (hook-runner.ts:317). The two build scripts use that ONLY to read investigation/incident metadata over REST and must **never** read a SecretStore value or emit any token to stdout/stderr/audit (hook output is captured into the transcript + the `hook_dispatched` audit row). Code review gate before shipping: grep each script for any provider/secret/api-key call; confirm it touches only `/api/v1/issues` (read). This keeps hooks on the catalog/workflow side of the boundary, consistent with root CLAUDE.md.

**False-positive denies blocking legit work.** Hook A is `failurePolicy: block` — if the Issue lookup fails (incident not yet linked to an Issue, transient MCP error, `source_ref` mismatch), it could block a legitimate close. Mitigations: (a) tight `timeoutMs` (3s) so a hung script doesn't stall the turn; (b) a clear deny `reason` so the analyst knows *why* and how to proceed (record a verdict) rather than hitting an opaque wall; (c) the negative smoke case (verdict present → proceeds) is mandatory before `ready-for-testing`; (d) ship it **disabled by default**, operator flips it on after watching it run in `warn` mode first. Hook B is `warn` so it can never block a turn.

**Per-event semantics traps.** `PostToolUse` honors `injectContext` only — a hook there returning `decision:"deny"` silently does nothing (it cannot undo an already-run tool). The build correctly puts the *blocking* logic in the `PreToolUse` hook and the *informational* logic in `PostToolUse`. Don't invert them.

---

**Key files for the operator to review when executing:** `mcp/agent/app/settings/hooks/page.tsx` (Release A), `mcp/agent/components/investigation/ui.tsx` (the reused primitives), `mcp/agent/lib/hooks.ts` (`HookPayload`/`HookResult`/matcher contract the scripts must honor), `mcp/agent/lib/hook-runner.ts` (command-transport env inheritance — the security-relevant line 317), and the installer kit for Release B's `/opt/guardian/hooks/*.py`.