# Guardian Self-Learning Loop — Design Spec

- **Date:** 2026-06-11
- **Status:** Approved (design). Next: implementation plan (writing-plans).
- **Author:** Guardian agent loop (brainstormed with operator)
- **Grounded in:** [Claude Agent SDK — agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop), [Addy Osmani — Loop Engineering](https://addyosmani.com/blog/loop-engineering/), [CoALA — Cognitive Architectures for Language Agents (arXiv 2309.02427)](https://ar5iv.labs.arxiv.org/html/2309.02427)

---

## 1. Purpose & context

Guardian is deployed and working: a Cortex XSOAR incident-investigation agent on `guardian-vm`, with a live `primary-xsoar` connector instance, validated end-to-end against the operator's Cortex XSOAR 8 tenant.

This spec designs a **self-learning loop** that continuously makes Guardian *better at investigating incidents* and *fixes issues along the way*. The loop is **operated by Claude** (the coding agent) on a schedule; the **investigating is done by the Guardian product agent**. The two are deliberately separate.

The loop is a closed self-improvement cycle:

> **seed** synthetic incidents → **drive** Guardian's investigation → **judge** the result → **distill + improve** (skills / knowledge / memory / code) → **gate** (green checks + adversarial checker) → **push** → **update state** → repeat.

### 1.1 The two-actor separation (load-bearing)

- **Claude (the meta-loop)** seeds incidents, observes, **judges** investigation quality, and **improves** Guardian. Claude never investigates.
- **The Guardian agent (the product)** does the actual investigating — fetch case, read war room, research, run commands, document, update/close — driven by a Guardian *job*.

### 1.2 Phasing of the judge (operator decision)

- **Phase 1 (this spec): Claude is the judge.** Claude grades each investigation directly. Because Claude *seeds* the incident, it knows the expected answer.
- **Phase 2 (future, out of scope):** a *judging skill* + a second Guardian *job* move the judge-and-improve loop **inside** Guardian, so it self-improves without Claude. This spec is designed so Phase 2 is a drop-in replacement — Claude stands in today for what that job will do.

## 2. Objectives & non-goals

**Objectives**
1. Make Guardian measurably better at investigating each XSOAR incident *type* over time.
2. Fix Guardian bugs and harden the codebase as a side effect of running the loop.
3. Build out a proper **layered memory architecture (CoALA)** for the Guardian agent: skills (procedural), knowledge (semantic), memory (episodic).
4. Run unattended on a schedule, surviving session close.
5. Auto-fix and push to `main` with no PR step — gated solely by a thorough verification suite + an adversarial checker.

**Non-goals (for this loop)**
- No human PR-review gate (operator chose maximum autonomy).
- No formal scoring engine or rubric system. Claude judges with its own intelligence, informally noting in the loop's state what it seeded so it knows the expected outcome — but there is no built scoring infrastructure. The formal judging skill is Phase 2.
- No path denylist / "no-auto-push zone" (operator chose to auto-push everything that passes gate + checker).
- Not the Guardian *product's* runtime monitoring loop in production — this is a *training* loop that exercises and improves it.

## 3. The CoALA memory architecture, mapped to Guardian

The loop *is* CoALA's "learning operations" (write episodic → reflect into semantic → update procedural), performed by Claude now and by a Guardian job in Phase 2.

| CoALA layer | Stores | Guardian substrate | Build? |
|---|---|---|---|
| **Working** | the live decision cycle — current incident, retrieved knowledge, goals | the agent's chat/investigation **context window** (one run) | inherent |
| **Procedural** | *how* to investigate + which actions, in what order (stable, reusable — Voyager-style skill library) | **Skills** (`xsoar_case_investigation` + one per incident type), progressive disclosure via `skills_read` | exists (runtime-mutable) |
| **Semantic** | generalizable *facts/rules* the procedure cites — IOC patterns, MITRE technique→action maps, vendor/product reference, tenant conventions | **Knowledge base** (`knowledge_search`) | **build:** runtime KB-write (`POST /api/v1/kbs/{name}/docs` + `knowledge_upsert` tool) |
| **Episodic** | raw past-investigation **trajectories** + outcomes, and **distilled lessons** | raw → **run transcripts** (`job_runs` + sessions); distilled → **memory store** (`memory_store`/`memory_search`) | exists |

**Learning operations the loop performs** (CoALA §Learning):
1. **Write episodic** — every investigation already lands a transcript (raw episodic).
2. **Reflect: episodic → semantic** — read past trajectories + outcomes, distill generalizable facts/rules, write to the **KB** (and tenant-specific evolving lessons to the **memory store**). (Reflexion / Generative-Agents pattern.)
3. **Update procedural** — refine/create the per-incident-type **skill** when a better procedure is found; fix connector tools/code.
4. **Retrieve** — at investigation time the agent pulls semantic (`knowledge_search`) + procedural (`skills_read`) + distilled-episodic (`memory_search`) into working memory.

## 4. The three-substrate split (memory vs knowledge vs skills)

Each answers a different question. That is the entire contract.

| | **SKILLS** (procedural) | **KNOWLEDGE** (semantic) | **MEMORY** (episodic) |
|---|---|---|---|
| **Answers** | *How do I investigate this?* | *What is this thing?* | *What happened last time?* |
| **Holds** | ordered steps + tools/actions, per incident type | standalone reusable facts the steps cite | distilled lessons + evolving tenant specifics |
| **Read via** | `skills_read` (auto-selected by description) | `knowledge_search(query)` | `memory_search(query)` |
| **Loop writes via** | `skills_create` / `skills_update` | `knowledge_upsert` *(the one new write surface)* | `memory_store` |
| **Volatility** | stable | slow-growing reference | continuously appended + distilled |

**Routing rule** (decide in order, for any new learning):
1. A step or action sequence? → **Skill** (the recipe).
2. A reusable fact the steps refer to? → **Knowledge** (the ingredient reference).
3. "What worked / what we missed," or a tenant-specific evolving truth? → **Memory** (the cook's notes).

**Why the split earns its keep:** no duplication/rot (facts live once in knowledge, many skills cite them); progressive disclosure stays cheap (skill bodies hold steps only, facts pulled on demand); distillation has a home (raw transcripts compress → a rule that either generalizes → knowledge, or is a lesson → memory) so episodic never bloats.

## 5. The loop mechanics (one cycle)

A **scheduled task** fires on a cron and runs one "trainer pass." Each firing is a fresh Claude invocation, so the loop's own memory is on disk.

```
   read STATE ↓                                                       ↑ write STATE
   1. ORIENT       read state → pick focus (an incident type + any open bug)
   2. SEED         xsoar_create_incident × N (chosen type) + record answer-key in state   ◄ Claude
   3. INVESTIGATE  trigger the standing "investigate open incidents" job (run-now) → poll  ◄ Guardian agent
   4. OBSERVE      pull job-run transcript + xsoar_get_war_room + /api/v1/audit tool-trail
   5. JUDGE        Claude grades each investigation vs the seeded answer-key                ◄ Claude
   6. DISTILL→     route each learning to ONE substrate (the §4 rule):
      IMPROVE         • better step/action → skills_create/update   (procedural)
                      • reusable fact      → knowledge_upsert         (semantic)
                      • mistake / tenant   → memory_store             (episodic-distilled)
                      • Guardian bug       → edit code + fix
   7. VERIFY       full gate (tsc/lint/build · MCP+updater pytest · validator)
                   + a CHECKER subagent (fresh context, adversarial) re-judges the diff
   8. SHIP/STATE   green + checker-approved → commit + push to main; clean up synthetic
                   incidents; write results + next focus to state. Red gate → revert, never push.
```

Step 3's agent investigates using exactly the three substrates from §4 (`skills_read` + `knowledge_search` + `memory_search`), so the loop's step-6 improvements directly change step-3 behavior next cycle — the closed self-improvement.

### 5.1 The loop's own state (Osmani's "sixth element")

Distinct from the *agent's* memory. Lives in the repo, versioned:
- `docs/loop/state.md` — human-readable curriculum: incident types covered, score trend, open bugs, pending improvements, "next focus."
- `.guardian-loop/state.json` — machine state (counters, last-run ids, budgets).

Read first, written last, every cycle.

### 5.2 The loop playbook

The scheduled task fires a thin prompt: *"run the Guardian trainer pass per `docs/loop/PLAYBOOK.md`."* The playbook is the deterministic, reproducible pass — and is itself improvable (the loop may refine it). Lives at `docs/loop/PLAYBOOK.md`.

### 5.3 Maker/checker (the sole guardrail besides the gate)

Step 7's checker is a **separate subagent**, fresh context, instructed to *refute* the change: does the gate genuinely pass? Is the skill/fact/fix correct and safe? Maker ≠ checker (the article's core safeguard). Because there is **no PR and no path denylist**, the gate + adversarial checker are the *only* things between the loop and `main` — so the spec requires:
- The gate is the FULL repo gate (`cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build`; MCP pytest; updater pytest; `validate_all.py`), never a subset.
- The checker is adversarial by construction (default-to-reject; must independently re-derive that the change is correct).
- A red gate at any point → the loop reverts its working changes for that item and does **not** push; it records the failure in state.

### 5.4 Synthetic-incident hygiene

Every seeded incident is tagged (label `guardian-loop-synthetic`) and **closed/cleaned after judging**, so the loop does not pollute the real XSOAR tenant. The cleanup is part of step 8 and is itself verified (the next cycle's orient step confirms no stale synthetic incidents remain open).

### 5.5 Budget & stopping

Each cycle is bounded: N incidents, M improvements, a turn/$ cap (per the Agent SDK loop's `max_turns` / budget controls). A cycle ends on scope-done / budget-hit / red-gate. The *loop* only stops when the operator disables the schedule.

## 6. Components & build phases

| Component | State | Note |
|---|---|---|
| Investigate engine (job → agent) | exists | prompt-job + `xsoar_case_investigation` + `bypass_approvals`; `run-now` + poll `…/runs` |
| Skills write (procedural) | exists | `skills_create`/`skills_update` |
| Memory write (episodic-distilled) | exists | `memory_store`/`memory_search` |
| Eval signals | exists | run transcripts + `xsoar_get_war_room` + `/api/v1/audit` |
| `xsoar_create_incident` (seed) | build | `POST /incident`, tag `guardian-loop-synthetic` |
| Knowledge write (semantic) | build | `POST /api/v1/kbs/{name}/docs` + `knowledge_upsert` tool (`kb_store.upsert()` already exists; only API + tool registration needed) |
| `xsoar_run_command` (act) | build, **blocked** | needs operator's workaround spec |
| Scheduled trainer + state + playbook + checker | build | the loop itself |

**Phases (never blocked on the missing tool):**
- **Phase 1 — Harness + self-healing** (zero new tools): scheduled trainer pass, `docs/loop/{PLAYBOOK.md,state.md}`, gate + adversarial checker, the bug-family-audit / doc-sync / observe-and-fix half. Investigates real cases if any exist; auto-fixes + pushes. Proves the loop end-to-end.
- **Phase 2 — Curriculum + memory layers**: build `xsoar_create_incident` + the KB-write surface; add seed → investigate → judge → distill-into-skills/knowledge/memory. Self-learning turns on.
- **Phase 3 — Acting investigations**: add `xsoar_run_command` when the operator's workaround lands.

## 7. Where the loop runs (RESOLVED — local machine)

The loop must reach **repo + GitHub + the Guardian stack + the XSOAR tenant**. **Decision (2026-06-11, revised): it runs on the operator's local machine (macOS), NOT on guardian-vm** — the operator does not want `claude` running on the VM.

- **Scheduler:** a **launchd LaunchAgent** on the Mac (durable, survives session close, OS-owned; launchd coalesces a missed run when the Mac was asleep at the fire time). A cloud routine is ruled out — it can't reach the VM/stack; an in-session `/loop` is ruled out — it dies on session close.
- **Payload:** the LaunchAgent fires a wrapper that runs **`claude -p`** (headless Claude Code) — the *full* harness (CLAUDE.md, skills, hooks, `.claude/settings.json`), just unattended. "Headless" ≠ lesser; same agent, no human watching, which is exactly what "unattended" requires.
- **Isolation:** a **dedicated clone at `~/guardian-loop`** — deliberately OUTSIDE `~/Documents` to avoid the macOS TCC Files-&-Folders revocation failure mode ([[documents-tcc-revocation-failure-mode]]), and separate from the operator's interactive working tree. The wrapper **hard-refuses** to run in the primary working repo, because its `git reset --hard origin/main` would destroy uncommitted work.
- **Git push auth:** the loop pushes via `gh`'s **active account, which must stay `thekite-dev`** — the only account with access to `kite-production/guardian` (the personal `ayman-m` account 404s). No separate PAT; the active-account credential is the auth ([[gh-account-drift-push-auth]]).
- **`claude` auth:** the loop uses this laptop's **logged-in Claude Code session** (the operator's subscription) — **no Anthropic API key** (the loop runs locally, so it's the same `claude` the operator uses interactively). Consequence: the login creds are in the macOS login keychain, unlocked only while logged in — a reboot/logout before the fire locks them and that night skips (accepted). No `--max-budget-usd` (subscription isn't $-billed); the wall-clock watchdog bounds each run.
- **Stack access:** the loop is NOT on the VM, so live-stack audits go through a **best-effort IAP tunnel** (reusing `scripts/guardian_tunnels.sh`, which reads `.env.vm`). Phase 1's work is overwhelmingly repo self-healing; if the tunnel can't open, the pass proceeds with repo-only audits.
- **Delivery path:** `git push origin main` triggers the normal CI build + auto-deploy on the VM runner — the loop's fixes ship through the existing pipeline regardless of where the loop itself runs.
- **Tradeoff accepted:** the Mac must be awake (or wake) around the fire time; launchd runs a missed job at next wake.

## 8. Decisions captured

- **Job of the loop:** maintain/harden + self-learn (fix issues + grow Guardian's investigation ability).
- **Autonomy:** auto-fix + push to `main`, **no PR**, **no path denylist** — gated solely by full gate + adversarial checker.
- **Mechanism:** in-Claude-Code scheduled task, survives session close, unattended.
- **Judge:** Claude (Phase 1); a judging skill + job move it inside Guardian (Phase 2).
- **Substrates:** procedural=skills, semantic=knowledge, episodic=memory — per the §4 routing rule.

## 9. Open items / dependencies

- **`run_xsoar_command` workaround spec** (operator to provide) — gates Phase 3 only.
- **Incident-type curriculum** — which XSOAR incident types to seed/train first (e.g. phishing, malware, C2/data-exfil, URL-filtering). Default: start with a small set the loop expands as scores stabilize.
- **Where it runs** (§7) — local vs VM clone.
- **Cadence** — exact cron (e.g. nightly vs every few hours). Default: start conservative (nightly) and tighten.

## 10. Acceptance (how we'll know the loop works)

- **Phase 1:** the scheduled task fires unattended, runs a pass that finds + fixes at least one real issue (or cleanly reports "nothing to do"), passes the full gate + checker, pushes, and updates `state.md` — with no human in the loop.
- **Phase 2:** seeding a phishing incident → the Guardian agent investigates it → Claude judges a gap → authors/updates the phishing skill (or a knowledge fact, or a memory lesson) → re-seeding the same type shows the agent now does the previously-missed step. Demonstrable closed-loop improvement on one incident type.
- **Phase 3:** an investigation that *acts* via `xsoar_run_command` and documents the result.
