# Guardian Self-Learning Loop — Phase 1.5: Convergence + Spin-Safety (Design Spec)

- **Date:** 2026-06-12
- **Status:** Approved (design). Next: implementation plan (writing-plans).
- **Builds on:** [`2026-06-11-self-learning-loop-design.md`](2026-06-11-self-learning-loop-design.md) (the Phase-1 harness) + its [Phase-1 plan](plans/2026-06-11-phase1-harness.md).
- **Motivation:** four live attended cycles (2026-06-11/12) proved the Phase-1 loop is *safe* (1 honest no-op, then 3 rigorous checker-rejections — it never shipped a half-fix) but exposed two gaps that block unattended operation.

---

## 1. The problem (proven live)

The Phase-1 loop runs a **fresh-context `claude -p` per cycle**: each cycle re-derives its fix from the `next_focus` text, with no memory of the prior attempt's diff. The adversarial checker rigorously demands a *complete* fix (whole bug-family). For a **wide multi-file bug-family** (the `chat`→`prompt` drift), the maker and checker never converged — 3 consecutive rejections, each catching more missed hits.

Two distinct gaps:

1. **Spin (safety blocker):** an unattended loop would re-pick the same unconvergeable unit **every night** and reject every night — spinning forever, never moving on, accumulating state-only rejection commits.
2. **Non-convergence (capability blocker):** the loop can't *land* a wide fix autonomously, so it defers/rejects work a full-context agent lands easily (as demonstrated when the operator's agent landed the same `chat`→`prompt` fix in one pass).

## 2. Objectives & non-goals

**Objectives**
1. **Never spin** — a unit gets at most K attempts, then becomes a human ticket and the loop moves on.
2. **Ship more, defer less** — let the loop land multi-file fixes by (a) scoping units narrowly so each cycle ships, and (b) carrying context forward for genuinely-wide units.
3. Stay within the existing harness: **no new MCP tools, no XSOAR** — PLAYBOOK prose + the loop's own state + a gitignored carry dir.

**Non-goals**
- Not a redesign of the maker/checker model — the checker's rigor is *correct* and stays.
- Not Phase 2 (XSOAR seeding / `knowledge_upsert` / the judge curriculum) — separate spec.
- No human-in-the-loop per cycle (the loop stays autonomous; deferral is the only handoff).

## 3. Design

The unit of work becomes **explicit and stateful**. Today `next_focus` is free text; Phase 1.5 introduces an `active_unit` the loop tracks across cycles.

### 3.1 The `active_unit` (state)

`state.json` gains:

```json
"active_unit": {
  "id": "<slug>",                    // stable identity across cycles
  "title": "<one line>",
  "scope": "<what + the mapped files/hits>",
  "remaining_scope": ["<slice>", ...],   // unfixed slices of a split-up wide family
  "mode": "narrow" | "wide",
  "rejections": 0,
  "status": "active" | "deferred" | "done"
}
```

…and a `deferred` list:

```json
"deferred": [
  { "id": "<slug>", "title": "...", "scope": "...", "reasons": "<accumulated checker reasons>", "issue": "<url|null>" }
]
```

### 3.2 Narrow-by-default scoping (PLAYBOOK · ORIENT)

When ORIENT finds an issue, it scopes the cycle to the **smallest coherent shippable slice** — one file, or a small group of hits that pass the gate together. If the issue is a wide bug-family, ORIENT **splits** it: open an `active_unit` (`mode: narrow`), fix ONE slice this cycle, record the rest in `remaining_scope`. Subsequent cycles drain `remaining_scope` one slice per cycle. Each cycle ships a complete slice — mirroring how the operator's agent chunked `chat`→`prompt` into renderers / agent-docs / help-prose (3 clean pushes vs 4 rejections).

### 3.3 Carry-forward for inherently-wide units (PLAYBOOK · CHECK/SHIP + state)

Some units are **atomic-but-wide** — they can't be split without breaking the gate (e.g. a symbol rename that's all-or-nothing). ORIENT marks these `mode: wide`. On a checker rejection of a wide unit, the loop:

1. Saves the rejected working diff to **`.guardian-loop/carry/<unit-id>.patch`** (gitignored — survives the per-cycle `git reset --hard` + `git clean -fd`).
2. Records the checker's rejection reasons in the unit.

The **next** cycle, seeing an active wide unit with a carry patch: `git apply .guardian-loop/carry/<id>.patch`, then **extends** it to address the recorded reasons — building on prior work instead of re-deriving from scratch.

### 3.4 Defer-after-K (PLAYBOOK · SHIP/STATE + state)

After each checker rejection of the active unit, `rejections` increments. When `rejections >= K`:

- **K = 2 for `narrow`, K = 3 for `wide`** (wide gets one more attempt since it's harder).
- The loop **defers**: moves the unit into `deferred[]` with its mapped scope + accumulated reasons; renders it into a **"Deferred — needs human"** section of `state.md`; and **files a GitHub issue** (title + the scope + the checker reasons) as the human handoff.
- ORIENT **never re-picks** a `deferred` unit (it checks `deferred[]` ids + ORIENT's audits skip them).
- The next cycle picks a **fresh** focus.

This is the spin-safety guarantee: at most K attempts per unit, then a ticket + move on.

### 3.5 The revised cycle

```
ORIENT      continue active_unit (apply carry patch if wide) OR open a new unit
            (narrow-scope it; split wide families into remaining_scope)
FIX         implement THIS slice (or extend the carried diff)
VERIFY      full gate (unchanged)
CHECK       adversarial checker (unchanged)
  rejected  → wide: save carry patch + reasons; narrow: discard
            → rejections++ ; if rejections>=K → DEFER (issue + deferred[] + fresh focus)
SHIP+STATE  approved+green → commit+push the slice; update active_unit
            (drain remaining_scope, or mark done); record cycle
```

## 4. Where the code lands

| File | Change |
|---|---|
| `scripts/loop/loop_state.py` (+ `test_loop_state.py`) | The `active_unit` + `deferred[]` schema and functions (`open_unit`, `set_remaining`, `record_rejection`, `defer_unit`, `complete_unit`); render an "Active unit" + "Deferred — needs human" section of `state.md`. TDD. |
| `docs/loop/PLAYBOOK.md` | ORIENT narrow-scoping + narrow/wide judgment; the carry-forward apply/extend step; the defer-after-K rule; the revised cycle (§3.5). |
| `.gitignore` | add `.guardian-loop/carry/`. |
| `docs/loop/README.md` | document the active-unit / deferred / carry model (operator runbook). |

**No wrapper change** — the pass reads/writes everything via `loop_state.py` + the carry dir. **No new tools, no XSOAR.**

## 5. Decisions captured

- **Convergence strategy:** *Both* — narrow-scope by default; carry-forward for inherently-wide (atomic) units. (Operator choice.)
- **Defer thresholds:** K = 2 (narrow), K = 3 (wide).
- **Defer handoff:** record in `state.md` "Deferred — needs human" **and** file a GitHub issue with the mapped scope + checker reasons.
- **Carry storage:** `.guardian-loop/carry/<unit-id>.patch` (gitignored; survives the per-cycle reset).
- **Stays in Phase-1 harness:** PLAYBOOK + state + carry dir; no new MCP tools, no XSOAR.

## 6. Acceptance

- **Spin-safety:** drive a unit to K rejections (e.g. point ORIENT at a deliberately-hard unit) → the loop files an issue, moves the unit to `deferred[]` / `state.md`, and the *next* cycle picks a different focus (does NOT re-pick the deferred unit).
- **Narrow convergence:** seed a 3-file drift → the loop ships it as 3 consecutive single-slice pushes (each gate+checker-green), draining `remaining_scope` to empty, then marks the unit `done`.
- **Wide carry-forward:** an atomic-but-wide unit that rejects once → the next cycle applies the carry patch + extends it + ships (demonstrably building on the prior attempt, not re-deriving).

## 7. Open items

- **"Same unit" identity across cycles** — the `active_unit.id` slug is set at open time and persists in state; ORIENT matches on it. (Implementation detail for the plan: how ORIENT decides "this is the same unit I was working" — answer: the active_unit in state IS the in-flight unit; ORIENT continues it unless it's `done`/`deferred`.)
- **Issue-spam guard** — defer files one issue per unit; the loop must not re-file for an already-deferred unit (the `deferred[].issue` url guards this).
