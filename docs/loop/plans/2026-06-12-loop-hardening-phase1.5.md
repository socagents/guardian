# Loop Phase 1.5 (Convergence + Spin-Safety) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the self-learning loop so it never spins on an unconvergeable unit and can actually land multi-file fixes — by making the unit of work an explicit, stateful `active_unit` with narrow-by-default scoping, carry-forward context for atomic-wide units, and defer-after-K.

**Architecture:** All within the existing Phase-1 harness — no new MCP tools, no XSOAR. The testable core is the loop's on-disk state machine (`scripts/loop/loop_state.py`): it gains an `active_unit` (tracked across cycles) and a `deferred[]` list, plus functions to open/reject/defer/complete units and render them. The *behavior* (narrow scoping, carry-forward via `git apply`, defer-after-K) lives in `docs/loop/PLAYBOOK.md` as prose the `claude -p` pass follows, driven by a `loop_state.py` CLI. Carry-forward diffs live in a gitignored `.guardian-loop/carry/`.

**Tech Stack:** Python 3.12 stdlib (`argparse`/`json`/`pathlib`), pytest, bash, the existing loop harness.

**Source spec:** [`docs/loop/2026-06-12-loop-hardening-phase1.5-design.md`](../2026-06-12-loop-hardening-phase1.5-design.md). **Builds on:** the Phase-1 [`loop_state.py`](../../../scripts/loop/loop_state.py) + [`PLAYBOOK.md`](../PLAYBOOK.md).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `scripts/loop/loop_state.py` | The loop's state machine — now also the `active_unit` lifecycle (`open_unit`/`set_remaining`/`record_rejection`/`should_defer`/`defer_unit`/`complete_unit`/`is_deferred`) + `deferred[]`, rendered into `state.md`, plus CLI subcommands so the PLAYBOOK pass can drive them. | modify |
| `scripts/loop/test_loop_state.py` | Unit tests for the new state functions + backward-compat load. | modify |
| `docs/loop/PLAYBOOK.md` | The behavior: ORIENT narrow-scoping + narrow/wide judgment, carry-forward apply/extend, defer-after-K, the revised cycle. | modify |
| `.gitignore` | Ignore `.guardian-loop/carry/` (carry-forward patches; survive the per-cycle reset). | modify |
| `docs/loop/README.md` | Operator-facing description of the active-unit / deferred / carry model. | modify |

**Note on the existing file:** `loop_state.py` was hardened during the Phase-1 build (a `load_state` that `setdefault`s the top-level keys, a `_cell` markdown-escaper, `pytest.raises` tests). Read it before editing — the new code must follow those patterns (e.g. `load_state` must `setdefault` the two new keys for backward compat with the *deployed* old-schema `state.json`).

---

## Task 1: `active_unit` schema + open/complete + accessor (TDD)

**Files:**
- Modify: `scripts/loop/loop_state.py`
- Test: `scripts/loop/test_loop_state.py`

- [ ] **Step 1: Read the current file**

Run: `sed -n '1,60p' scripts/loop/loop_state.py` (note `SCHEMA_VERSION`, `default_state`, `load_state`).

- [ ] **Step 2: Write the failing tests** — append to `scripts/loop/test_loop_state.py`:

```python
def test_default_state_has_active_unit_and_deferred():
    s = ls.default_state()
    assert s["active_unit"] is None
    assert s["deferred"] == []
    assert s["schema_version"] == ls.SCHEMA_VERSION


def test_load_state_backfills_new_keys_for_old_schema(tmp_path):
    # An old (Phase-1) state.json with no active_unit/deferred must load cleanly.
    p = tmp_path / "state.json"
    p.write_text('{"schema_version": 1, "cycles": [], "next_focus": "x", "open_findings": []}')
    s = ls.load_state(p)
    assert s["active_unit"] is None
    assert s["deferred"] == []


def test_open_unit_sets_active():
    s = ls.default_state()
    ls.open_unit(s, id="jobs-chat-prompt", title="chat→prompt", scope="renderers + docs", mode="narrow")
    u = ls.active_unit(s)
    assert u["id"] == "jobs-chat-prompt"
    assert u["mode"] == "narrow"
    assert u["rejections"] == 0
    assert u["status"] == "active"
    assert u["remaining_scope"] == []


def test_open_unit_rejects_bad_mode():
    s = ls.default_state()
    import pytest
    with pytest.raises(ValueError, match="mode"):
        ls.open_unit(s, id="x", title="t", scope="s", mode="banana")


def test_complete_unit_clears_active():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.complete_unit(s)
    assert ls.active_unit(s) is None
```

- [ ] **Step 3: Run — verify FAIL**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -k "active_unit or open_unit or complete_unit or backfills" -v`
Expected: FAIL — `AttributeError`/`KeyError` (functions + keys not defined). (If `python3` lacks pytest, use `../../.venv/bin/python3`.)

- [ ] **Step 4: Implement** — in `scripts/loop/loop_state.py`:

(a) Bump the schema + add constants near the top (after `VALID_OUTCOMES`):
```python
SCHEMA_VERSION = 2  # v2 adds active_unit + deferred (Phase 1.5)
VALID_MODES = ("narrow", "wide")
K_NARROW = 2  # defer a narrow unit after this many checker rejections
K_WIDE = 3    # wide (atomic) units get one more attempt
```
(Replace the existing `SCHEMA_VERSION = 1` line.)

(b) Add the two keys to `default_state()`'s returned dict (after `"open_findings": [],`):
```python
        "active_unit": None,
        "deferred": [],
```

(c) In `load_state`, after the existing `setdefault` block, add:
```python
    data.setdefault("active_unit", None)
    data.setdefault("deferred", [])
```

(d) Add the functions (after `set_next_focus`):
```python
def active_unit(state: dict) -> dict | None:
    return state.get("active_unit")


def open_unit(state: dict, *, id: str, title: str, scope: str, mode: str = "narrow") -> dict:
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {VALID_MODES}")
    state["active_unit"] = {
        "id": id,
        "title": title,
        "scope": scope,
        "mode": mode,
        "remaining_scope": [],
        "rejections": 0,
        "reasons": "",
        "status": "active",
    }
    return state


def complete_unit(state: dict) -> dict:
    state["active_unit"] = None
    return state
```

- [ ] **Step 5: Run — verify PASS**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -v`
Expected: PASS (all prior tests + the 5 new ones).

- [ ] **Step 6: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add scripts/loop/loop_state.py scripts/loop/test_loop_state.py
git commit -m "loop: active_unit schema + open/complete (Phase 1.5, schema v2)

Refs the loop-hardening spec (Phase 1.5).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: rejection tracking + defer threshold + defer (TDD)

**Files:**
- Modify: `scripts/loop/loop_state.py`, `scripts/loop/test_loop_state.py`

- [ ] **Step 1: Write the failing tests** — append to `test_loop_state.py`:

```python
def test_set_remaining():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.set_remaining(s, ["slice-b", "slice-c"])
    assert ls.active_unit(s)["remaining_scope"] == ["slice-b", "slice-c"]


def test_record_rejection_increments_and_stores_reasons():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.record_rejection(s, "missed file A")
    ls.record_rejection(s, "missed file A and B")
    u = ls.active_unit(s)
    assert u["rejections"] == 2
    assert u["reasons"] == "missed file A and B"


def test_should_defer_narrow_after_2():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.record_rejection(s, "r1")
    assert ls.should_defer(s) is False
    ls.record_rejection(s, "r2")
    assert ls.should_defer(s) is True


def test_should_defer_wide_after_3():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="wide")
    ls.record_rejection(s, "r1")
    ls.record_rejection(s, "r2")
    assert ls.should_defer(s) is False
    ls.record_rejection(s, "r3")
    assert ls.should_defer(s) is True


def test_should_defer_no_active_unit_is_false():
    s = ls.default_state()
    assert ls.should_defer(s) is False


def test_defer_unit_moves_to_deferred_and_clears_active():
    s = ls.default_state()
    ls.open_unit(s, id="hard", title="t", scope="files X,Y,Z", mode="wide")
    ls.record_rejection(s, "still missing Z")
    ls.defer_unit(s, issue="https://example/issues/9")
    assert ls.active_unit(s) is None
    assert len(s["deferred"]) == 1
    d = s["deferred"][0]
    assert d["id"] == "hard"
    assert d["reasons"] == "still missing Z"
    assert d["issue"] == "https://example/issues/9"
    assert ls.is_deferred(s, "hard") is True
    assert ls.is_deferred(s, "other") is False
```

- [ ] **Step 2: Run — verify FAIL**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -k "remaining or rejection or defer" -v`
Expected: FAIL (functions undefined).

- [ ] **Step 3: Implement** — add to `loop_state.py` (after `complete_unit`):

```python
def set_remaining(state: dict, slices: list) -> dict:
    u = state.get("active_unit")
    if not u:
        raise ValueError("no active unit")
    u["remaining_scope"] = list(slices)
    return state


def record_rejection(state: dict, reasons: str) -> dict:
    u = state.get("active_unit")
    if not u:
        raise ValueError("no active unit")
    u["rejections"] += 1
    u["reasons"] = reasons  # latest accumulated checker reasons
    return state


def _defer_threshold(mode: str) -> int:
    return K_WIDE if mode == "wide" else K_NARROW


def should_defer(state: dict) -> bool:
    u = state.get("active_unit")
    return bool(u) and u["rejections"] >= _defer_threshold(u.get("mode", "narrow"))


def defer_unit(state: dict, *, issue: str | None = None) -> dict:
    u = state.get("active_unit")
    if not u:
        raise ValueError("no active unit")
    state["deferred"].append({
        "id": u["id"],
        "title": u["title"],
        "scope": u["scope"],
        "reasons": u.get("reasons", ""),
        "issue": issue,
    })
    state["active_unit"] = None
    return state


def is_deferred(state: dict, unit_id: str) -> bool:
    return any(d.get("id") == unit_id for d in state.get("deferred", []))
```

- [ ] **Step 4: Run — verify PASS**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/loop_state.py scripts/loop/test_loop_state.py
git commit -m "loop: rejection tracking + defer-after-K + defer_unit (Phase 1.5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: render the Active-unit + Deferred sections (TDD)

**Files:**
- Modify: `scripts/loop/loop_state.py`, `scripts/loop/test_loop_state.py`

- [ ] **Step 1: Write the failing tests** — append:

```python
def test_render_shows_active_unit():
    s = ls.default_state()
    ls.open_unit(s, id="UNIT-MARK", title="TITLE-MARK", scope="s", mode="wide")
    ls.record_rejection(s, "r1")
    md = ls.render_markdown(s)
    assert "Active unit" in md
    assert "UNIT-MARK" in md
    assert "TITLE-MARK" in md
    assert "wide" in md


def test_render_shows_deferred_with_issue_link():
    s = ls.default_state()
    ls.open_unit(s, id="HARD-MARK", title="hard", scope="s", mode="narrow")
    ls.record_rejection(s, "r1")
    ls.record_rejection(s, "r2")
    ls.defer_unit(s, issue="https://example/issues/42")
    md = ls.render_markdown(s)
    assert "Deferred — needs human" in md
    assert "HARD-MARK" in md
    assert "https://example/issues/42" in md


def test_render_no_active_unit_says_none():
    md = ls.render_markdown(ls.default_state())
    assert "Active unit" in md  # heading present
    assert "_none active_" in md
```

- [ ] **Step 2: Run — verify FAIL**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -k render -v`
Expected: FAIL (new headings/markers absent).

- [ ] **Step 3: Implement** — in `render_markdown`, insert these sections BEFORE the existing `## Next focus` section (use the existing `_cell`/plain string style; the function builds a `lines` list):

```python
    # --- Active unit (Phase 1.5) ---
    lines += ["## Active unit", ""]
    u = state.get("active_unit")
    if u:
        lines += [
            f"- **{u.get('id', '')}** — {u.get('title', '')}",
            f"  - mode: `{u.get('mode', '')}` · rejections: {u.get('rejections', 0)}"
            f" · remaining slices: {len(u.get('remaining_scope', []))}",
            f"  - scope: {u.get('scope', '')}",
            "",
        ]
    else:
        lines += ["_none active_", ""]

    # --- Deferred — needs human (Phase 1.5) ---
    lines += ["## Deferred — needs human", ""]
    deferred = state.get("deferred", [])
    if deferred:
        for d in deferred:
            issue = d.get("issue") or "(no issue)"
            lines.append(f"- **{d.get('id', '')}** — {d.get('title', '')} → {issue}")
            if d.get("reasons"):
                lines.append(f"  - blocked on: {d['reasons']}")
    else:
        lines.append("_none_")
    lines.append("")
```

(Place this block right after the counters section and before `"## Next focus"`. Read the current `render_markdown` to find the exact insertion point — it appends to a `lines` list in order.)

- [ ] **Step 4: Run — verify PASS**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/loop_state.py scripts/loop/test_loop_state.py
git commit -m "loop: render Active-unit + Deferred-needs-human sections (Phase 1.5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: CLI subcommands so the PLAYBOOK can drive the state machine

**Files:**
- Modify: `scripts/loop/loop_state.py`, `scripts/loop/test_loop_state.py`

- [ ] **Step 1: Write the failing test** — append (drives the module as a CLI end-to-end against a temp repo):

```python
import subprocess, sys, json
from pathlib import Path

def test_cli_unit_lifecycle(tmp_path):
    mod = str(Path(__file__).with_name("loop_state.py"))
    def run(*args):
        subprocess.run([sys.executable, mod, "--repo", str(tmp_path), *args], check=True)
    run("init")
    run("open-unit", "--id", "u1", "--title", "t", "--scope", "s", "--mode", "narrow")
    run("record-rejection", "--reasons", "missed A")
    run("record-rejection", "--reasons", "missed A,B")
    run("defer-unit", "--issue", "https://x/1")
    state = json.loads((tmp_path / ".guardian-loop" / "state.json").read_text())
    assert state["active_unit"] is None
    assert state["deferred"][0]["id"] == "u1"
    assert state["deferred"][0]["issue"] == "https://x/1"
    md = (tmp_path / "docs" / "loop" / "state.md").read_text()
    assert "Deferred — needs human" in md and "u1" in md
```

- [ ] **Step 2: Run — verify FAIL**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -k cli_unit -v`
Expected: FAIL — argparse errors on the unknown subcommands.

- [ ] **Step 3: Implement** — add CLI handlers + subparsers in `loop_state.py`.

Add these command functions (after `cmd_render`); each loads, mutates, saves, and re-renders `state.md` so it stays current:
```python
def _save_and_render(args, mutate):
    json_path, md_path = _paths(args.repo)
    state = load_state(json_path)
    mutate(state)
    save_state(json_path, state)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state))


def cmd_open_unit(args):
    _save_and_render(args, lambda s: open_unit(
        s, id=args.id, title=args.title, scope=args.scope, mode=args.mode))
    print(f"opened unit {args.id} ({args.mode})")


def cmd_set_remaining(args):
    _save_and_render(args, lambda s: set_remaining(s, args.slices or []))
    print(f"remaining slices: {len(args.slices or [])}")


def cmd_record_rejection(args):
    _save_and_render(args, lambda s: record_rejection(s, args.reasons))
    print("recorded rejection")


def cmd_defer_unit(args):
    _save_and_render(args, lambda s: defer_unit(s, issue=args.issue or None))
    print("deferred active unit")


def cmd_complete_unit(args):
    _save_and_render(args, lambda s: complete_unit(s))
    print("completed active unit")
```

In `build_parser`, register the subparsers (after the existing `render` parser):
```python
    o = sub.add_parser("open-unit"); o.set_defaults(func=cmd_open_unit)
    o.add_argument("--id", required=True)
    o.add_argument("--title", required=True)
    o.add_argument("--scope", required=True)
    o.add_argument("--mode", default="narrow", choices=list(VALID_MODES))

    sr = sub.add_parser("set-remaining"); sr.set_defaults(func=cmd_set_remaining)
    sr.add_argument("--slices", nargs="*", default=[])

    rr = sub.add_parser("record-rejection"); rr.set_defaults(func=cmd_record_rejection)
    rr.add_argument("--reasons", required=True)

    du = sub.add_parser("defer-unit"); du.set_defaults(func=cmd_defer_unit)
    du.add_argument("--issue", default="")

    sub.add_parser("complete-unit").set_defaults(func=cmd_complete_unit)
```

- [ ] **Step 4: Run — verify PASS**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -v`
Expected: PASS (all tests, including `test_cli_unit_lifecycle`).

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/loop_state.py scripts/loop/test_loop_state.py
git commit -m "loop: CLI subcommands for the active_unit state machine (Phase 1.5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: PLAYBOOK — narrow scoping, carry-forward, defer-after-K

**Files:**
- Modify: `docs/loop/PLAYBOOK.md`

- [ ] **Step 1: Read the current playbook**

Run: `cat docs/loop/PLAYBOOK.md` (note the ORIENT, VERIFY, CHECK, SHIP+STATE sections + the ground rules).

- [ ] **Step 2: Rewrite ORIENT to be unit-aware + narrow-scoping**

Replace the ORIENT section (`## 1. ORIENT — pick ONE focus`) with:

````markdown
## 1. ORIENT — continue or open ONE unit (narrow by default)
First check the loop's memory: `python3 scripts/loop/loop_state.py --repo . render` already
refreshed `state.md` from `state.json`. Read `.guardian-loop/state.json`.

a. **If an `active_unit` exists** (status `active`): CONTINUE it.
   - `mode: narrow` → take the NEXT slice from its `remaining_scope` (one file / small group).
   - `mode: wide` → if a carry patch exists at `.guardian-loop/carry/<active_unit.id>.patch`,
     `git apply` it first, then extend it (see step 3 / §5 carry-forward).
b. **Else open a NEW unit** from the first real issue an audit finds (the §1c audits below).
   - Give it a stable `id` (kebab slug), a `title`, and a `scope` (the mapped files/hits).
   - **Scope it NARROW:** the smallest coherent slice that passes the gate on its own. If the
     issue is a WIDE bug-family across many files, decide:
       - **Splittable** (slices ship independently) → `mode: narrow`; fix ONE slice this cycle;
         record the rest as `remaining_scope`.
       - **Atomic-but-wide** (all-or-nothing for the gate, e.g. a rename) → `mode: wide`.
     Open it: `python3 scripts/loop/loop_state.py --repo . open-unit --id <slug> --title "..." --scope "..." --mode <narrow|wide>`
     and, when splitting, `... set-remaining --slices "<slice2>" "<slice3>" ...`.
   - **NEVER open a unit whose id is already in `state.json.deferred[]`** — those are human-owned.
c. **Self-heal audits** (run to FIND a new unit only when there is no active unit) — unchanged
   from Phase 1: doc-sync, bug-family, spec-drift; live-stack audits if the tunnel is up. When an
   audit re-surfaces an already-`deferred` issue, SKIP it.
d. **Nothing to do** → record a clean `no-op` cycle and exit (no active unit to continue, no new
   issue found).
````

- [ ] **Step 3: Add carry-forward to the CHECK step + defer to SHIP/STATE**

In the `## 5. CHECK` section, after the "Rejected → revert/record" bullet, add:
````markdown
- **On a rejection, branch by mode (the convergence machinery):**
  - `record-rejection`: `python3 scripts/loop/loop_state.py --repo . record-rejection --reasons "<the checker's specific reasons>"`.
  - **`mode: wide`** → save the rejected diff for the next cycle to build on:
    `mkdir -p .guardian-loop/carry && git diff > ".guardian-loop/carry/$(python3 -c 'import json;print(json.load(open(".guardian-loop/state.json"))["active_unit"]["id"])').patch"`
    then revert the working tree (`git reset --hard HEAD && git clean -fd -e .guardian-loop`).
  - **`mode: narrow`** → just revert (no carry); the slice will be re-derived (it's small).
  - **DEFER check:** if `python3 scripts/loop/loop_state.py --repo . show-defer` prints `DEFER`
    (rejections ≥ K: 2 narrow / 3 wide), then HAND OFF instead of retrying:
      1. File a GitHub issue: `gh issue create --title "loop deferred: <title>" --body "<scope + accumulated checker reasons>"` → capture the URL.
      2. `python3 scripts/loop/loop_state.py --repo . defer-unit --issue "<url>"` (moves it to `deferred[]`, clears the active unit).
      3. Record the cycle `--outcome checker-rejected`, set a fresh `--next-focus`, do NOT push the fix. Exit.
````

> Implementation note for Task 5: add a tiny `show-defer` CLI command in `loop_state.py` that prints `DEFER` when `should_defer(state)` else `OK` — so the playbook can branch in bash. Add it in this task (it's playbook-support):
> ```python
> def cmd_show_defer(args):
>     _, _ = _paths(args.repo)
>     state = load_state(_paths(args.repo)[0])
>     print("DEFER" if should_defer(state) else "OK")
> # in build_parser: sub.add_parser("show-defer").set_defaults(func=cmd_show_defer)
> ```
> (No new test needed beyond Task 2's `should_defer` coverage; smoke it once by hand.)

In `## 6. SHIP + STATE`, add to the **fixed** path: after pushing the slice,
````markdown
  - **Drain the unit:** if the active unit still has `remaining_scope`, pop the shipped slice
    (`... set-remaining --slices "<the rest>"`) so the next cycle continues it; if it's now empty,
    `python3 scripts/loop/loop_state.py --repo . complete-unit`. A `wide` unit that finally ships:
    delete its carry patch (`rm -f .guardian-loop/carry/<id>.patch`) and `complete-unit`.
````

- [ ] **Step 4: Sanity-check the structure**

Run: `grep -nE 'active_unit|remaining_scope|carry|show-defer|defer-unit|complete-unit|never open a unit whose id' docs/loop/PLAYBOOK.md`
Expected: the new ORIENT/carry/defer/drain mechanics are all present.

- [ ] **Step 5: Add the `show-defer` CLI + commit**

Add the `cmd_show_defer` + its subparser (per the note above) to `loop_state.py`, then:
```bash
git add docs/loop/PLAYBOOK.md scripts/loop/loop_state.py
git commit -m "loop: PLAYBOOK — narrow scoping + carry-forward + defer-after-K (Phase 1.5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: gitignore the carry dir + README the model

**Files:**
- Modify: `.gitignore`, `docs/loop/README.md`

- [ ] **Step 1: Ignore the carry dir**

Add to the loop block in `.gitignore` (next to `.guardian-loop/logs/`):
```gitignore
.guardian-loop/carry/
```

- [ ] **Step 2: Verify it's ignored**

Run: `mkdir -p .guardian-loop/carry && touch .guardian-loop/carry/x.patch && git check-ignore .guardian-loop/carry/x.patch && rm .guardian-loop/carry/x.patch`
Expected: prints `.guardian-loop/carry/x.patch` (ignored).

- [ ] **Step 3: Document the model in the runbook**

In `docs/loop/README.md`, add a section after "## What it does (Phase 1)":
````markdown
## Convergence + spin-safety (Phase 1.5)
The loop tracks an **active unit** (`state.json.active_unit`) — what it's working on across
cycles, shown in `state.md`:
- **Narrow by default:** each cycle ships the smallest coherent slice; a wide bug-family is
  split and cleared over several cycles (each a clean push).
- **Carry-forward (wide units):** an atomic-but-wide unit that the checker rejects saves its diff
  to `.guardian-loop/carry/<id>.patch` (gitignored); the next cycle `git apply`s it and extends it.
- **Defer-after-K:** after K rejections (2 narrow / 3 wide) the loop files a GitHub issue, lists
  the unit under **"Deferred — needs human"** in `state.md`, and moves on — it never spins.
````

- [ ] **Step 4: Commit**

```bash
git add .gitignore docs/loop/README.md
git commit -m "loop: gitignore carry dir + document Phase 1.5 convergence model

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: Verify on the loop clone + the gate (acceptance)

**Files:** none (verification). Runs against the loop clone `~/guardian-loop`.

- [ ] **Step 1: Push the harness commits + sync the clone**

```bash
git push origin main
cd "$HOME/guardian-loop" && git fetch origin main && git checkout -B main origin/main
```

- [ ] **Step 2: The new state module passes the gate (its tests run inside it)**

Run: `cd "$HOME/guardian-loop" && scripts/loop/run_gate.sh /tmp/p15-gate.log`
Expected: `GATE PASS` (the new `test_loop_state.py` cases are part of the mcp/agent-independent pytest? — they live in `scripts/loop/`, run them explicitly): also run `cd "$HOME/guardian-loop/scripts/loop" && ../../.venv/bin/python3 -m pytest test_loop_state.py -v` → all PASS.

- [ ] **Step 3: Exercise the state machine end-to-end (no Claude spend)**

```bash
cd "$HOME/guardian-loop"
python3 scripts/loop/loop_state.py --repo . open-unit --id demo --title "demo" --scope "fileA,fileB" --mode narrow
python3 scripts/loop/loop_state.py --repo . set-remaining --slices "fileB"
python3 scripts/loop/loop_state.py --repo . record-rejection --reasons "missed fileB"
python3 scripts/loop/loop_state.py --repo . record-rejection --reasons "still missed fileB"
python3 scripts/loop/loop_state.py --repo . show-defer        # expect DEFER
python3 scripts/loop/loop_state.py --repo . defer-unit --issue "https://example/issues/test"
grep -A3 "Deferred — needs human" docs/loop/state.md          # expect the demo unit listed
# clean up the demo state so it doesn't pollute the loop's real memory:
git checkout -- .guardian-loop/state.json docs/loop/state.md
```
Expected: `show-defer` prints `DEFER` after the 2nd narrow rejection; `state.md` lists `demo` under "Deferred — needs human" with the issue link; the cleanup reverts the demo.

- [ ] **Step 4: One live cycle exercises the real path (optional, operator-gated)**

Trigger one attended cycle (`GUARDIAN_LOOP_HOME=~/guardian-loop ~/guardian-loop/scripts/loop/guardian_loop.sh`) and confirm in the cycle log + `state.md` that ORIENT either continued/opened an `active_unit` and shipped a narrow slice, OR cleanly no-op'd — i.e. the new mechanics drive a real pass without error. (This spends a Claude call; run it when ready to go live.)

---

## Self-Review

**1. Spec coverage** (against `docs/loop/2026-06-12-loop-hardening-phase1.5-design.md`):
- §3.1 `active_unit` + `deferred[]` schema → Tasks 1–2. ✓
- §3.2 narrow-by-default scoping → Task 5 (ORIENT) + `set_remaining`/`remaining_scope` (Tasks 2/4). ✓
- §3.3 carry-forward (`.guardian-loop/carry/<id>.patch`, apply+extend) → Task 5 (CHECK/ORIENT) + Task 6 (gitignore). ✓
- §3.4 defer-after-K (K=2/3, issue + state.md + fresh focus, never re-pick) → `should_defer`/`defer_unit`/`is_deferred` (Task 2) + `show-defer` + ORIENT skip + SHIP defer (Task 5) + render (Task 3). ✓
- §3.5 revised cycle → Task 5. ✓
- §4 files (loop_state.py + tests, PLAYBOOK, .gitignore, README) → Tasks 1–6. ✓
- §6 acceptance (spin-safety, narrow convergence, wide carry-forward) → Task 7 step 3 (spin-safety end-to-end) + step 4 (live). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step has full content. The `show-defer` CLI is fully specified in Task 5's note. ✓

**3. Type/name consistency:** function names — `open_unit`/`active_unit`/`complete_unit`/`set_remaining`/`record_rejection`/`should_defer`/`defer_unit`/`is_deferred`/`_defer_threshold` — used identically across Tasks 1–4 tests, impl, and the CLI handlers. Constants `K_NARROW=2`/`K_WIDE=3`/`VALID_MODES`/`SCHEMA_VERSION=2` consistent. CLI subcommands (`open-unit`/`set-remaining`/`record-rejection`/`defer-unit`/`complete-unit`/`show-defer`) match between the parser registration (Task 4/5), the playbook invocations (Task 5), and the acceptance commands (Task 7). State keys (`active_unit`, `deferred`, `remaining_scope`, `rejections`, `reasons`, `mode`, `status`, `issue`) consistent across schema, functions, render, and CLI. ✓
