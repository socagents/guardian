# Guardian Self-Learning Loop — Phase 1 (Harness + Self-Healing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a durable, unattended self-improvement loop on `guardian-vm` that, on a nightly schedule, runs one "trainer pass" of Claude Code which finds-and-fixes one coherent maintenance/self-healing unit, verifies it with the full repo gate plus an adversarial checker subagent, and pushes it to `main` — with no human in the loop.

**Architecture:** A **systemd timer** on `guardian-vm` fires a bash **wrapper** (`guardian_loop.sh`) against a **dedicated repo clone** (`/home/ayman/guardian-loop`, isolated from the CI runner workspace). The wrapper resets the clone to clean `origin/main`, then runs **`claude -p`** (headless Claude Code — full harness: CLAUDE.md, skills, hooks, `.claude/settings.json`) with a thin prompt that points at **`docs/loop/PLAYBOOK.md`**. The playbook is the deterministic pass: ORIENT → FIX → VERIFY (gate) → CHECK (adversarial subagent) → SHIP+STATE. The loop's own memory is two on-disk files (`.guardian-loop/state.json` machine state + `docs/loop/state.md` human mirror), written by a small tested Python module. No new MCP tools, no XSOAR seeding (that is Phase 2).

**Tech Stack:** bash, systemd (timer + oneshot service), Python 3.12 (stdlib only — `argparse`/`json`/`pathlib`), `claude` CLI (headless `-p`), `gh`, the existing Guardian gate (`tsc`/`eslint`/`next build` + `pytest` + `validate_all.py`).

**Source spec:** [`docs/loop/2026-06-11-self-learning-loop-design.md`](../2026-06-11-self-learning-loop-design.md) (§5 mechanics, §5.1 state, §5.2 playbook, §5.3 maker/checker, §7 runtime = guardian-vm, §10 Phase-1 acceptance).

**Security posture (read before Task 5/9):** the loop runs `claude -p --dangerously-skip-permissions` in an **isolated VM clone with no inbound network**, because the operator's explicit decision is "auto-fix + push everything behind the full gate + adversarial checker; no PR, no path denylist." The gate + checker are the *sole* guardrail and must therefore be uncompromised. Credentials never enter the repo: the loop's secrets (Anthropic key, gh push token, Guardian API key) live ONLY in `scripts/loop/loop.env`, which is gitignored and created by hand on the VM. The credential guardrail still holds — the loop edits code/docs but must never read/write SecretStore values or commit secrets.

---

## File Structure

| File | Responsibility | New? |
|---|---|---|
| `scripts/loop/loop_state.py` | The ONLY writer of the loop's on-disk memory. Pure functions (`load_state`, `record_cycle`, `compute_counters`, `render_markdown`) + a CLI (`init`/`record`/`render`). Counters derived from `cycles[]` (single source of truth). | create |
| `scripts/loop/test_loop_state.py` | Unit tests for `loop_state.py`. | create |
| `.guardian-loop/state.json` | Machine state — source of truth (committed, versioned loop memory). | create |
| `.guardian-loop/logs/` | Per-cycle `claude -p` transcripts (gitignored). | create (dir) |
| `docs/loop/state.md` | Human-readable mirror of `state.json`, rendered by the module. | create |
| `scripts/loop/run_gate.sh` | Runs the FULL repo gate (tsc/lint/build · mcp pytest · updater pytest · validator). Exit 0 = all green. | create |
| `scripts/loop/loop_bootstrap.sh` | One-time clone provisioning: `npm ci` + a single repo-root `.venv` with mcp/updater/validator deps. | create |
| `scripts/loop/guardian_loop.sh` | The systemd payload: load env → reset clone to clean `origin/main` → run `claude -p` with the playbook prompt → log. Honors `DRY_RUN=1`. | create |
| `scripts/loop/loop.env.example` | Template for the gitignored VM secrets file. | create |
| `docs/loop/PLAYBOOK.md` | The deterministic Phase-1 trainer pass (the loop prompt's procedure). | create |
| `deploy/loop/guardian-loop.service` | systemd oneshot unit that runs the wrapper. | create |
| `deploy/loop/guardian-loop.timer` | systemd timer (nightly, persistent, jittered). | create |
| `docs/loop/README.md` | Operator runbook: provision, enable/disable, dry-run, where state/logs live. | create |
| `.claude/loop.md` | Update so the interactive `/loop` and the scheduled pass converge on `docs/loop/PLAYBOOK.md`. | modify |
| `scripts/CLAUDE.md` | Add catalogue rows for the new `scripts/loop/*` scripts. | modify |
| `.gitignore` | Ignore `scripts/loop/loop.env` and `.guardian-loop/logs/`; keep `.guardian-loop/state.json` tracked. | modify |

---

## Task 1: Loop state module (`loop_state.py`) — TDD

**Files:**
- Create: `scripts/loop/loop_state.py`
- Test: `scripts/loop/test_loop_state.py`

- [ ] **Step 1: Write the failing tests**

Create `scripts/loop/test_loop_state.py`:

```python
"""Tests for the Guardian loop state module. Run from scripts/loop/:
    python3 -m pytest test_loop_state.py -v
"""
import loop_state as ls


def test_load_missing_returns_default(tmp_path):
    state = ls.load_state(tmp_path / "nope.json")
    assert state["schema_version"] == ls.SCHEMA_VERSION
    assert state["cycles"] == []
    assert "next_focus" in state
    assert state["open_findings"] == []


def test_record_cycle_appends_and_numbers():
    state = ls.default_state()
    ls.record_cycle(state, {"outcome": "fixed", "focus": "x"})
    ls.record_cycle(state, {"outcome": "no-op", "focus": "y"})
    assert [c["n"] for c in state["cycles"]] == [1, 2]
    assert state["cycles"][0]["outcome"] == "fixed"


def test_compute_counters():
    state = ls.default_state()
    for o in ["fixed", "fixed", "no-op", "gate-failed", "checker-rejected"]:
        ls.record_cycle(state, {"outcome": o, "focus": "f"})
    c = ls.compute_counters(state)
    assert c == {
        "cycles_total": 5,
        "fixes_shipped": 2,
        "noops": 1,
        "gate_failures": 1,
        "checker_rejections": 1,
    }


def test_render_contains_next_focus_and_latest_cycle():
    state = ls.default_state()
    ls.set_next_focus(state, "FOCUS-MARKER")
    ls.record_cycle(state, {
        "outcome": "fixed", "focus": "CYCLE-MARKER",
        "started_at": "2026-06-11T02:30:00Z", "commit": "abc1234",
        "gate": "pass", "checker": "approved",
    })
    md = ls.render_markdown(state)
    assert "FOCUS-MARKER" in md
    assert "CYCLE-MARKER" in md
    assert "abc1234" in md


def test_roundtrip_save_load(tmp_path):
    p = tmp_path / "state.json"
    state = ls.default_state()
    ls.record_cycle(state, {"outcome": "fixed", "focus": "f"})
    ls.save_state(p, state)
    again = ls.load_state(p)
    assert again["cycles"][0]["outcome"] == "fixed"


def test_record_cycle_rejects_unknown_outcome():
    state = ls.default_state()
    try:
        ls.record_cycle(state, {"outcome": "banana", "focus": "f"})
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown outcome")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loop_state'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/loop/loop_state.py`:

```python
#!/usr/bin/env python3
"""Guardian self-learning loop — on-disk state (the loop's own memory).

Two files (the loop's persistent "sixth element"):
  - .guardian-loop/state.json  — machine state (SOURCE OF TRUTH)
  - docs/loop/state.md         — human-readable mirror, rendered from the JSON

This module is the ONLY writer of both. The trainer pass calls the CLI at the
end of each cycle: `record` then `render`. Counters are DERIVED from cycles[]
at render time, so there is a single source of truth and nothing to keep in sync.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_VERSION = 1
VALID_OUTCOMES = ("fixed", "no-op", "gate-failed", "checker-rejected")


def default_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "cycles": [],
        "next_focus": (
            "self-heal: doc-sync audit "
            "(sidebar nav vs pages; architecture page service list vs docker compose)"
        ),
        "open_findings": [],
    }


def load_state(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return default_state()
    return json.loads(path.read_text())


def save_state(path: Path, state: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def record_cycle(state: dict, cycle: dict) -> dict:
    outcome = cycle.get("outcome")
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}; expected one of {VALID_OUTCOMES}")
    numbered = {"n": len(state["cycles"]) + 1}
    numbered.update(cycle)
    state["cycles"].append(numbered)
    return state


def set_next_focus(state: dict, focus: str) -> dict:
    state["next_focus"] = focus
    return state


def compute_counters(state: dict) -> dict:
    cycles = state["cycles"]
    return {
        "cycles_total": len(cycles),
        "fixes_shipped": sum(1 for c in cycles if c.get("outcome") == "fixed"),
        "noops": sum(1 for c in cycles if c.get("outcome") == "no-op"),
        "gate_failures": sum(1 for c in cycles if c.get("outcome") == "gate-failed"),
        "checker_rejections": sum(1 for c in cycles if c.get("outcome") == "checker-rejected"),
    }


def render_markdown(state: dict) -> str:
    c = compute_counters(state)
    lines = [
        "# Guardian self-learning loop — state",
        "",
        "> Rendered from `.guardian-loop/state.json` by `scripts/loop/loop_state.py`.",
        "> Do not hand-edit; change the JSON (or use the CLI) and re-render.",
        "",
        "## Counters",
        "",
        f"- Cycles total: **{c['cycles_total']}**",
        f"- Fixes shipped: **{c['fixes_shipped']}**",
        f"- No-ops: **{c['noops']}**",
        f"- Gate failures: **{c['gate_failures']}**",
        f"- Checker rejections: **{c['checker_rejections']}**",
        "",
        "## Next focus",
        "",
        state["next_focus"],
        "",
        "## Open findings",
        "",
    ]
    if state["open_findings"]:
        for f in state["open_findings"]:
            lines.append(f"- [{f.get('status', 'open')}] {f.get('id', '')}: {f.get('desc', '')}")
    else:
        lines.append("_none_")
    lines += ["", "## Recent cycles (last 10)", ""]
    if state["cycles"]:
        lines.append("| # | started | focus | outcome | commit | gate | checker |")
        lines.append("|---|---|---|---|---|---|---|")
        for cyc in state["cycles"][-10:]:
            lines.append(
                f"| {cyc.get('n')} | {cyc.get('started_at', '')} | {cyc.get('focus', '')} | "
                f"{cyc.get('outcome', '')} | {cyc.get('commit', '') or '—'} | "
                f"{cyc.get('gate', '')} | {cyc.get('checker', '')} |"
            )
    else:
        lines.append("_no cycles yet_")
    lines.append("")
    return "\n".join(lines)


# --------------------------- CLI ---------------------------

def _paths(repo: str):
    root = Path(repo)
    return root / ".guardian-loop" / "state.json", root / "docs" / "loop" / "state.md"


def cmd_init(args):
    json_path, md_path = _paths(args.repo)
    state = load_state(json_path)  # preserve existing state if present
    save_state(json_path, state)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state))
    print(f"init: wrote {json_path} and {md_path}")


def cmd_record(args):
    json_path, _ = _paths(args.repo)
    state = load_state(json_path)
    record_cycle(state, {
        "started_at": args.started_at,
        "focus": args.focus,
        "outcome": args.outcome,
        "summary": args.summary,
        "commit": args.commit,
        "gate": args.gate,
        "checker": args.checker,
    })
    if args.next_focus:
        set_next_focus(state, args.next_focus)
    save_state(json_path, state)
    print(f"recorded cycle #{len(state['cycles'])} outcome={args.outcome}")


def cmd_render(args):
    json_path, md_path = _paths(args.repo)
    state = load_state(json_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state))
    print(f"rendered {md_path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Guardian self-learning loop state")
    p.add_argument("--repo", default=".", help="repo root (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    r = sub.add_parser("record")
    r.set_defaults(func=cmd_record)
    r.add_argument("--started-at", required=True, dest="started_at")
    r.add_argument("--focus", required=True)
    r.add_argument("--outcome", required=True, choices=VALID_OUTCOMES)
    r.add_argument("--summary", default="")
    r.add_argument("--commit", default="")
    r.add_argument("--gate", default="", choices=["", "pass", "fail"])
    r.add_argument("--checker", default="", choices=["", "approved", "rejected", "n/a"])
    r.add_argument("--next-focus", default="", dest="next_focus")
    sub.add_parser("render").set_defaults(func=cmd_render)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd scripts/loop && python3 -m pytest test_loop_state.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 5: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add scripts/loop/loop_state.py scripts/loop/test_loop_state.py
git commit -m "loop: state module (machine state + rendered state.md), TDD

Refs the Phase-1 self-learning loop harness.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: Seed the initial loop memory + gitignore

**Files:**
- Create: `.guardian-loop/state.json`, `docs/loop/state.md` (both via the module)
- Modify: `.gitignore`

- [ ] **Step 1: Generate the initial state files**

Run: `python3 scripts/loop/loop_state.py --repo . init`
Expected output: `init: wrote .guardian-loop/state.json and docs/loop/state.md`

- [ ] **Step 2: Verify the rendered files**

Run: `cat .guardian-loop/state.json && echo '---' && cat docs/loop/state.md`
Expected: `state.json` has `"cycles": []`, `"schema_version": 1`, a `next_focus` string, `"open_findings": []`. `state.md` shows all-zero counters, the next-focus line, "_none_" findings, "_no cycles yet_".

- [ ] **Step 3: Ignore logs + the secrets file (keep state.json tracked)**

Append to `.gitignore`:

```gitignore

# Guardian self-learning loop (scripts/loop/, docs/loop/, .guardian-loop/)
# state.json is TRACKED (the loop's versioned memory); only logs + secrets are ignored.
scripts/loop/loop.env
.guardian-loop/logs/
```

- [ ] **Step 4: Verify git sees state.json but not logs/secrets**

Run: `mkdir -p .guardian-loop/logs && touch .guardian-loop/logs/x.log scripts/loop/loop.env && git status --porcelain .guardian-loop scripts/loop docs/loop`
Expected: `.guardian-loop/state.json`, `docs/loop/state.md`, the `scripts/loop/*.py` (already committed in Task 1) appear; `.guardian-loop/logs/x.log` and `scripts/loop/loop.env` do NOT appear. Then `rm .guardian-loop/logs/x.log scripts/loop/loop.env`.

- [ ] **Step 5: Commit**

```bash
git add .guardian-loop/state.json docs/loop/state.md .gitignore
git commit -m "loop: seed initial state.json + state.md; gitignore logs+secrets

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: Full-gate runner (`run_gate.sh`)

**Files:**
- Create: `scripts/loop/run_gate.sh`

- [ ] **Step 1: Write the gate runner**

Create `scripts/loop/run_gate.sh`:

```bash
#!/usr/bin/env bash
# Guardian full pre-deploy gate. Exit 0 = ALL green. Mirrors root CLAUDE.md
# "Pre-deploy gate" exactly, plus the AI-layer validator. Used by the loop's
# VERIFY step; also runnable by hand: scripts/loop/run_gate.sh [logfile]
set -uo pipefail

REPO="${GUARDIAN_LOOP_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
LOG="${1:-/dev/stdout}"

log()  { echo "[gate] $*" | tee -a "$LOG" >&2; }
fail() { log "FAIL: $1"; exit 1; }

# Single repo-root venv carries mcp + updater + validator deps (see loop_bootstrap.sh)
if [ -f "$REPO/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$REPO/.venv/bin/activate"
fi
PY="$(command -v python3)"

log "1/6 tsc"   ; (cd "$REPO/mcp/agent" && npx tsc --noEmit)            2>&1 | tee -a "$LOG" || fail tsc
log "2/6 lint"  ; (cd "$REPO/mcp/agent" && npm run lint)                2>&1 | tee -a "$LOG" || fail lint
log "3/6 build" ; (cd "$REPO/mcp/agent" && npm run build)               2>&1 | tee -a "$LOG" || fail build
log "4/6 mcp"   ; (cd "$REPO/bundles/spark/mcp" && PYTHONPATH="$PWD/src" "$PY" -m pytest tests/ -x) 2>&1 | tee -a "$LOG" || fail "mcp pytest"
log "5/6 updater"; (cd "$REPO/updater" && "$PY" -m pytest tests/ -x)    2>&1 | tee -a "$LOG" || fail "updater pytest"
log "6/6 validator"; (cd "$REPO" && "$PY" tooling/validate/validate_all.py) 2>&1 | tee -a "$LOG" || fail validator

log "GATE PASS"
```

(`set -o pipefail` makes `cmd | tee || fail` report `cmd`'s failure, not `tee`'s success.)

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/loop/run_gate.sh && head -1 scripts/loop/run_gate.sh`
Expected: `#!/usr/bin/env bash`

- [ ] **Step 3: Smoke the gate locally (clean tree → PASS)**

Run: `scripts/loop/run_gate.sh /tmp/gate.log; echo "exit=$?"`
Expected: ends with `[gate] GATE PASS` and `exit=0`. (This is the full ~3-5 min gate; it confirms the runner wiring on the dev machine. The VM clone runs the same script after `loop_bootstrap.sh`.)

- [ ] **Step 4: Commit**

```bash
git add scripts/loop/run_gate.sh
git commit -m "loop: full-gate runner (tsc/lint/build · mcp+updater pytest · validator)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: Clone provisioning script (`loop_bootstrap.sh`)

**Files:**
- Create: `scripts/loop/loop_bootstrap.sh`

- [ ] **Step 1: Write the bootstrap script**

Create `scripts/loop/loop_bootstrap.sh`:

```bash
#!/usr/bin/env bash
# One-time (and dep-refresh) provisioning for the loop's clone. Sets up the
# Node + Python deps the gate needs, in a single repo-root .venv. Idempotent.
#   Usage: scripts/loop/loop_bootstrap.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

echo "[bootstrap] node deps (mcp/agent)"
(cd mcp/agent && npm ci)

echo "[bootstrap] python venv at $REPO/.venv"
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python3 -m pip install --upgrade pip

echo "[bootstrap] mcp + updater + validator deps"
python3 -m pip install -r bundles/spark/mcp/requirements.txt
python3 -m pip install -r updater/requirements.txt
# tooling/validate deps (PyYAML + jsonschema are what validate_all.py imports)
python3 -m pip install pyyaml jsonschema

echo "[bootstrap] verifying the gate runs"
"$REPO/scripts/loop/run_gate.sh" /tmp/loop-bootstrap-gate.log

echo "[bootstrap] done — clone is ready for the loop"
```

- [ ] **Step 2: Make it executable + shellcheck-clean**

Run: `chmod +x scripts/loop/loop_bootstrap.sh && bash -n scripts/loop/loop_bootstrap.sh && echo "syntax ok"`
Expected: `syntax ok`. (Do NOT run it on the dev machine — it is executed on the VM clone in Task 9. `bash -n` is syntax-only.)

> NOTE for Task 9: confirm the exact import list `tooling/validate/validate_all.py` needs by reading its imports on the VM; if it imports a package beyond `pyyaml`/`jsonschema`, add it to the bootstrap `pip install` line in the same change.

- [ ] **Step 3: Commit**

```bash
git add scripts/loop/loop_bootstrap.sh
git commit -m "loop: one-time clone provisioning (npm ci + repo-root .venv + deps)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: Loop wrapper + secrets template (`guardian_loop.sh`, `loop.env.example`)

**Files:**
- Create: `scripts/loop/guardian_loop.sh`, `scripts/loop/loop.env.example`

- [ ] **Step 1: Write the secrets template**

Create `scripts/loop/loop.env.example`:

```bash
# Copy to scripts/loop/loop.env on guardian-vm (gitignored, mode 0600).
# NEVER commit the real file. These are the only secrets the loop needs.

# Anthropic API key for the headless `claude -p` run.
ANTHROPIC_API_KEY=

# Model for the loop pass (a strong model — this does codework + judging).
CLAUDE_LOOP_MODEL=claude-fable-5

# Guardian agent API key (scope *) so the pass can drive /api/agent/* if needed.
# Same value as GUARDIAN_API_KEY in .env.vm. Used over localhost on the VM.
GUARDIAN_API_KEY=

# Guardian agent base URL as seen from the VM (loop runs ON the VM → localhost).
GUARDIAN_BASE=https://localhost:3000

# Where the dedicated clone lives (must differ from the CI runner workspace).
GUARDIAN_LOOP_HOME=/home/ayman/guardian-loop

# git push credential: a fine-grained PAT with contents:write on
# kite-production/guardian. Configured into git via `gh auth` during
# provisioning (Task 9) — NOT used directly here. Listed for documentation.
# GH_LOOP_TOKEN=
```

- [ ] **Step 2: Write the wrapper**

Create `scripts/loop/guardian_loop.sh`:

```bash
#!/usr/bin/env bash
# systemd payload for the Guardian self-learning loop. One invocation = one
# trainer pass. Resets the clone to clean origin/main, then runs headless
# Claude Code against docs/loop/PLAYBOOK.md. Honors DRY_RUN=1 (prints the
# claude command, runs nothing).
set -uo pipefail

LOOP_HOME="${GUARDIAN_LOOP_HOME:-/home/ayman/guardian-loop}"
ENV_FILE="${GUARDIAN_LOOP_ENV:-$LOOP_HOME/scripts/loop/loop.env}"

if [ -f "$ENV_FILE" ]; then
  set -a; # shellcheck disable=SC1090
  . "$ENV_FILE"; set +a
fi

cd "$LOOP_HOME" || { echo "[loop] no clone at $LOOP_HOME" >&2; exit 1; }

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$LOOP_HOME/.guardian-loop/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/cycle-$TS.log"

echo "[loop] $TS starting; resetting clone to clean origin/main" | tee -a "$LOG"
git fetch origin main                              2>&1 | tee -a "$LOG"
git checkout main                                  2>&1 | tee -a "$LOG"
git reset --hard origin/main                       2>&1 | tee -a "$LOG"
git clean -fd                                      2>&1 | tee -a "$LOG"   # untracked only; gitignored logs survive

PROMPT="You are running the Guardian self-learning loop as an UNATTENDED scheduled trainer pass on guardian-vm. Follow docs/loop/PLAYBOOK.md exactly, top to bottom. Do exactly one coherent unit this pass. Never push on a red gate or a checker rejection."

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
MODEL="${CLAUDE_LOOP_MODEL:-claude-fable-5}"

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "[loop] DRY_RUN — would run:" | tee -a "$LOG"
  echo "$CLAUDE_BIN --print --model $MODEL --dangerously-skip-permissions \"<PLAYBOOK prompt>\"" | tee -a "$LOG"
  exit 0
fi

echo "[loop] launching headless claude -p (model=$MODEL); log: $LOG" | tee -a "$LOG"
"$CLAUDE_BIN" --print --model "$MODEL" --dangerously-skip-permissions "$PROMPT" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
echo "[loop] $TS finished; claude exit=$STATUS" | tee -a "$LOG"
exit "$STATUS"
```

- [ ] **Step 3: Make it executable + dry-run it**

Run:
```bash
chmod +x scripts/loop/guardian_loop.sh
GUARDIAN_LOOP_HOME="$(git rev-parse --show-toplevel)" DRY_RUN=1 scripts/loop/guardian_loop.sh
```
Expected: prints the reset steps, then `[loop] DRY_RUN — would run:` and a `claude --print --model … --dangerously-skip-permissions` line; exits 0 without invoking `claude`. (On the dev machine the `git reset --hard origin/main` runs against your real clone — acceptable since the tree is clean and you are on `main`; if uneasy, run with `GUARDIAN_LOOP_HOME=/tmp/throwaway-empty` to see only the "no clone" guard.)

- [ ] **Step 4: Commit**

```bash
git add scripts/loop/guardian_loop.sh scripts/loop/loop.env.example
git commit -m "loop: systemd wrapper + secrets template (headless claude -p payload)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: The trainer playbook (`docs/loop/PLAYBOOK.md`)

**Files:**
- Create: `docs/loop/PLAYBOOK.md`

- [ ] **Step 1: Write the Phase-1 playbook**

Create `docs/loop/PLAYBOOK.md`:

````markdown
# Guardian Self-Learning Loop — PLAYBOOK (Phase 1: harness + self-healing)

You are Claude Code running an **unattended scheduled trainer pass** on
guardian-vm, started by `scripts/loop/guardian_loop.sh`. The clone is already
reset to clean `origin/main`. Do **exactly one coherent unit** this pass, then
verify, check, ship, and record. Then stop.

Phase 1 has **no incident seeding and no new tools** — the job is to *harden
Guardian and keep it consistent*. (Seeding + judging investigations is Phase 2.)

## Ground rules (non-negotiable, every pass)
- **Never push on a red gate or a checker rejection.** Revert and record instead.
- **One unit per pass.** A focused, coherent change — not a grab-bag.
- **Honor every contract in CLAUDE.md.** Spec-driven workflow, contained-release
  discipline, documentation discipline, the credential guardrail.
- **Credential guardrail:** never read/write SecretStore values; never commit
  secrets. You edit code/docs only.
- This pass **auto-pushes to `main`**, which triggers CI build + auto-deploy.
  That is the intended delivery path. Do not tag a release (that is operator-only).

## 0. Preflight
1. `git rev-parse --short HEAD` — note the starting commit.
2. Read the loop's memory: `docs/loop/state.md` and `.guardian-loop/state.json`.
   Note `next_focus` and any `open_findings`.
3. Record the start time (UTC ISO-8601) for the state entry at the end.

## 1. ORIENT — pick ONE focus (first match wins)
a. **An open finding** in `state.json.open_findings` not yet resolved.
b. **`next_focus`** from state, if still valid.
c. **A self-heal scan** — run these audits and take the FIRST real issue found:
   - **Doc-sync:** sidebar nav vs pages — `find mcp/agent/app -maxdepth 3 -name page.tsx | xargs dirname | sort` vs `href:` entries in `mcp/agent/components/sidebar.tsx`. Architecture page service list vs `docker compose ps` (over localhost on the VM). CHANGELOG.md newest entry vs `mcp/agent/lib/release-notes.ts` newest entry.
   - **Bug-family audit:** `grep -rn "from usecase\." bundles/spark/connectors */src 2>/dev/null` (import-style regression, see connectors/CLAUDE.md); connector.yaml `spec.tools[].name` bare vs prefixed Python functions; hardcoded-data drift in `mcp/agent/app/api/` (e.g. marketplace `toolCount`).
   - **Spec-drift:** "Implementation gap" bullets in `mcp/agent/app/help/architecture/page.tsx`.
   - **Observe:** hit the local stack — `curl -sk -H "Authorization: Bearer $GUARDIAN_API_KEY" $GUARDIAN_BASE/api/agent/jobs` and the updater on `:8090`; scan `/observability` surfaces for errors.
d. **Nothing to do** → skip to step 6 and record a clean `no-op` cycle, set a
   sensible `next_focus`, do NOT push, exit.

## 2. SCOPE the unit
- If the fix is **non-trivial** (new behavior / operator-visible / API change),
  open or find a GitHub issue first (`gh issue create --template release.md`),
  apply the mechanical labels, and reference it (`Refs #N`/`Closes #N`) — per
  CLAUDE.md spec-driven workflow. **Trivial** self-heal (doc-sync, bug-family,
  prose) is `scenario:trivial` / auto-closable.

## 3. FIX — implement the one unit
- Standard architecture first; clean cohesive change; minimal-but-complete.
- If operator-visible, do the **full doc cycle** in the same change (architecture
  page, user guide, journeys, CHANGELOG.md, release-notes.ts) per CLAUDE.md.

## 4. VERIFY — the full gate
- Run `scripts/loop/run_gate.sh "$PWD/.guardian-loop/logs/gate-$(date +%H%M%S).log"`.
- **Red** → revert your working changes (`git reset --hard HEAD && git clean -fd`),
  record the cycle as `gate-failed` with a summary of what broke, set `next_focus`
  to the failure, do NOT push, exit.

## 5. CHECK — adversarial checker subagent (maker ≠ checker)
- Spawn a **fresh subagent** (the Agent tool) with the diff (`git diff` / `git
  diff --staged`) and instructions to **REFUTE** the change:
  - Does the gate genuinely pass (not papered over)? Is the fix correct, complete,
    and spec-consistent? Does it honor CLAUDE.md (credential guardrail, contained
    release, docs discipline)? Any regression risk? **Default to REJECT on doubt.**
  - The subagent returns a verdict: `approved` or `rejected` + reasons.
- **Rejected** → revert, record `checker-rejected` with the reasons, set
  `next_focus`, do NOT push, exit.

## 6. SHIP + STATE
- **Approved + green:**
  1. Commit with a CLAUDE.md-conformant message (`Refs`/`Closes #N`, the
     Co-Authored-By trailer).
  2. `git push origin main`.
  3. Capture the pushed short SHA: `SHA=$(git rev-parse --short HEAD)`.
- **No-op:** no commit, `SHA=""`.
- Update the loop memory (the module is the only writer):
  ```bash
  python3 scripts/loop/loop_state.py --repo . record \
    --started-at "<UTC ISO from preflight>" \
    --focus "<the focus>" \
    --outcome "<fixed|no-op|gate-failed|checker-rejected>" \
    --summary "<one line>" \
    --commit "$SHA" \
    --gate "<pass|fail|>" \
    --checker "<approved|rejected|n/a>" \
    --next-focus "<what next pass should look at>"
  python3 scripts/loop/loop_state.py --repo . render
  ```
- If you pushed code, also commit the state update and push it (state is the
  loop's versioned memory):
  ```bash
  git add .guardian-loop/state.json docs/loop/state.md
  git commit -m "loop: record cycle <n> (<outcome>)

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  git push origin main
  ```
- **Do NOT wait for CI** — the wrapper exits here. The next pass's ORIENT can
  verify the deploy landed (version on the VM vs HEAD).

## Stop
One unit done (or a clean no-op). Exit. The systemd timer fires the next pass.
````

- [ ] **Step 2: Structure sanity check**

Run: `grep -nE '^## (0|1|2|3|4|5|6)\.|Ground rules|Stop' docs/loop/PLAYBOOK.md`
Expected: lists the ground-rules heading, steps 0–6, and Stop — confirming the full ORIENT→…→SHIP+STATE skeleton is present and ordered.

- [ ] **Step 3: Commit**

```bash
git add docs/loop/PLAYBOOK.md
git commit -m "loop: Phase-1 trainer playbook (orient/fix/verify/check/ship+state)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: systemd units (`guardian-loop.service` + `.timer`)

**Files:**
- Create: `deploy/loop/guardian-loop.service`, `deploy/loop/guardian-loop.timer`

- [ ] **Step 1: Write the service unit**

Create `deploy/loop/guardian-loop.service`:

```ini
[Unit]
Description=Guardian self-learning loop — one trainer pass
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=ayman
WorkingDirectory=/home/ayman/guardian-loop
# Single env knob; secrets are loaded by the wrapper from scripts/loop/loop.env
Environment=GUARDIAN_LOOP_HOME=/home/ayman/guardian-loop
ExecStart=/home/ayman/guardian-loop/scripts/loop/guardian_loop.sh
# A pass should never run longer than an hour; kill it if it hangs.
TimeoutStartSec=3600
```

- [ ] **Step 2: Write the timer unit**

Create `deploy/loop/guardian-loop.timer`:

```ini
[Unit]
Description=Run the Guardian self-learning loop nightly

[Timer]
# 02:30 VM-local, with up to 10 min jitter; catch up if the VM was down.
OnCalendar=*-*-* 02:30:00
RandomizedDelaySec=600
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Syntax-validate (if systemd is present locally; else defer to Task 9)**

Run: `command -v systemd-analyze >/dev/null && systemd-analyze verify deploy/loop/guardian-loop.service deploy/loop/guardian-loop.timer && echo "units ok" || echo "no systemd here — verify on VM in Task 9"`
Expected (macOS dev machine): `no systemd here — verify on VM in Task 9`. (On Linux: `units ok`.)

- [ ] **Step 4: Commit**

```bash
git add deploy/loop/guardian-loop.service deploy/loop/guardian-loop.timer
git commit -m "loop: systemd timer + oneshot service (nightly trainer pass)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 8: Operator runbook + converge `.claude/loop.md` + scripts catalogue

**Files:**
- Create: `docs/loop/README.md`
- Modify: `.claude/loop.md`, `scripts/CLAUDE.md`

- [ ] **Step 1: Write the operator runbook**

Create `docs/loop/README.md`:

````markdown
# Guardian self-learning loop — operator runbook

The loop is a durable, unattended self-improvement cycle that runs on
**guardian-vm**. Design: [`2026-06-11-self-learning-loop-design.md`](2026-06-11-self-learning-loop-design.md).
Phase-1 procedure: [`PLAYBOOK.md`](PLAYBOOK.md).

## What it does (Phase 1)
A nightly systemd timer runs one "trainer pass" of headless Claude Code that
finds + fixes one self-healing unit (doc-sync, bug-family, spec-drift, observe),
runs the full gate + an adversarial checker, and pushes to `main` (which
triggers the normal CI build + auto-deploy). No XSOAR seeding yet (Phase 2).

## Where things live
| Thing | Path |
|---|---|
| Dedicated clone | `/home/ayman/guardian-loop` (separate from the CI runner workspace) |
| Secrets (gitignored, 0600) | `/home/ayman/guardian-loop/scripts/loop/loop.env` |
| Machine state (tracked) | `.guardian-loop/state.json` |
| Human state mirror | `docs/loop/state.md` |
| Per-cycle transcripts (gitignored) | `.guardian-loop/logs/cycle-*.log` |
| Timer + service units | `deploy/loop/guardian-loop.{timer,service}` |

## Provisioning (one time — see Task 9 of the plan for the exact commands)
1. Install + authenticate the `claude` CLI on the VM.
2. `git clone` into `/home/ayman/guardian-loop`.
3. `cp scripts/loop/loop.env.example scripts/loop/loop.env`, fill it, `chmod 600`.
4. Configure a git push credential (fine-grained PAT, contents:write).
5. `scripts/loop/loop_bootstrap.sh` (npm ci + .venv + deps + gate smoke).
6. Install the units + enable the timer (`sudo` cp to `/etc/systemd/system/`,
   `systemctl daemon-reload`, `systemctl enable --now guardian-loop.timer`).

## Operate it
- **Status:** `systemctl status guardian-loop.timer` · `systemctl list-timers guardian-loop*`
- **Run one pass now:** `sudo systemctl start guardian-loop.service` then tail
  `~/guardian-loop/.guardian-loop/logs/cycle-*.log`.
- **Dry run (no claude):** `DRY_RUN=1 ~/guardian-loop/scripts/loop/guardian_loop.sh`
- **Pause:** `sudo systemctl disable --now guardian-loop.timer`
- **Read what it's done:** `docs/loop/state.md`.

## Guardrails
The loop auto-pushes to `main` with **no PR**. Its only guardrails are the full
gate (`scripts/loop/run_gate.sh`) and an adversarial checker subagent — both
must pass before any push. It never touches credentials and never tags a
release (operator-only). To stop it entirely, disable the timer.
````

- [ ] **Step 2: Converge `.claude/loop.md` onto the playbook**

In `.claude/loop.md`, replace the file's body so the interactive `/loop` defers to the same playbook (single source of truth). Read the current file first, then replace its content with:

```markdown
# Guardian project loop

<!-- Lands at .claude/loop.md — customizes the bare `/loop` prompt for this repo.
     The unattended scheduled loop and the interactive `/loop` share ONE
     procedure: docs/loop/PLAYBOOK.md. Keep them convergent. -->

Run the Guardian self-learning loop trainer pass. Follow
**`docs/loop/PLAYBOOK.md`** exactly — ORIENT → SCOPE → FIX → VERIFY (full gate)
→ CHECK (adversarial subagent) → SHIP + STATE. One coherent unit per iteration.

Rules that survive every iteration (also enforced by the playbook):
- Read the repo CLAUDE.md contracts before editing; never commit credentials
  (`.env`, `.env.vm`, `scripts/loop/loop.env` stay local).
- Never push on a red gate or a checker rejection.
- The loop's memory is `.guardian-loop/state.json` + `docs/loop/state.md` — read
  it at the start (ORIENT) and write it at the end (SHIP + STATE).
- End the iteration after one unit (or a clean no-op).
```

- [ ] **Step 3: Add catalogue rows to `scripts/CLAUDE.md`**

In `scripts/CLAUDE.md`, add these rows to the "Script catalogue" table (after the existing rows):

```markdown
| `loop/loop_state.py` | The loop's on-disk memory writer (`.guardian-loop/state.json` + `docs/loop/state.md`); `init`/`record`/`render` | Auto, every loop cycle |
| `loop/run_gate.sh` | Runs the full Guardian gate (tsc/lint/build · mcp+updater pytest · validator) | Auto, loop VERIFY step + manual |
| `loop/loop_bootstrap.sh` | One-time clone provisioning (npm ci + repo-root .venv + deps) | Manual, VM provisioning |
| `loop/guardian_loop.sh` | systemd payload: reset clone → run headless `claude -p` against the playbook | Auto, nightly timer |
```

- [ ] **Step 4: Verify the docs are coherent**

Run: `grep -c "PLAYBOOK.md" .claude/loop.md docs/loop/README.md && grep -c "loop/" scripts/CLAUDE.md`
Expected: `.claude/loop.md` and `docs/loop/README.md` each reference `PLAYBOOK.md` ≥1; `scripts/CLAUDE.md` has ≥4 `loop/` rows.

- [ ] **Step 5: Commit**

```bash
git add docs/loop/README.md .claude/loop.md scripts/CLAUDE.md
git commit -m "loop: operator runbook; converge .claude/loop.md on PLAYBOOK; catalogue rows

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 9: Provision the loop on guardian-vm + dry-run end-to-end

This task runs **on guardian-vm**, mostly as operator/agent shell steps (not TDD). Access via IAP per root CLAUDE.md (`set -a && source .env.vm && set +a`, then the IAP tunnel + `sshpass -e ssh`). Push the Task-1..8 commits to `main` FIRST so the clone has them.

- [ ] **Step 1: Push the harness commits**

Run (from the dev machine): `git push origin main`
Expected: Tasks 1–8 commits land on `origin/main`. (This triggers a CI build of the agent — expected and harmless; the loop files don't change any image behavior.)

- [ ] **Step 2: Install + authenticate the `claude` CLI on the VM**

On the VM: install the Claude Code CLI (per the official install for Linux x64) and confirm `claude --version`. Authentication is via `ANTHROPIC_API_KEY` in `loop.env` (Step 5) — no interactive login needed for `claude -p`.
Expected: `claude --version` prints a version.

- [ ] **Step 3: Create the dedicated clone**

On the VM:
```bash
git clone https://github.com/kite-production/guardian.git /home/ayman/guardian-loop
cd /home/ayman/guardian-loop && git rev-parse --abbrev-ref HEAD
```
Expected: `main`. Confirm the path differs from the runner workspace (`/home/ayman/actions-runner/_work/guardian/guardian`).

- [ ] **Step 4: Configure the git push credential**

On the VM, configure a fine-grained PAT (contents:write on `kite-production/guardian`) as the git credential for the loop clone — e.g. `gh auth login` with the token, then `gh auth setup-git`, or a `git credential-store` entry. (This is the manual step the `.claude/settings.json` `git config` deny intends to keep out of the loop itself.)
Verify (read-only): `cd /home/ayman/guardian-loop && git ls-remote origin -h refs/heads/main`
Expected: prints the remote `main` SHA (push auth resolves).

- [ ] **Step 5: Create `loop.env`**

On the VM:
```bash
cd /home/ayman/guardian-loop
cp scripts/loop/loop.env.example scripts/loop/loop.env
chmod 600 scripts/loop/loop.env
# edit scripts/loop/loop.env: set ANTHROPIC_API_KEY, GUARDIAN_API_KEY (= the
# value from .env.vm), leave GUARDIAN_BASE=https://localhost:3000.
```
Verify (without printing secrets): `test -f scripts/loop/loop.env && stat -c '%a' scripts/loop/loop.env`
Expected: `600`.

- [ ] **Step 6: Bootstrap the clone deps**

On the VM:
```bash
cd /home/ayman/guardian-loop && scripts/loop/loop_bootstrap.sh
```
Expected: ends with `[bootstrap] done — clone is ready for the loop` and the embedded gate run prints `[gate] GATE PASS`. (If `validate_all.py` errors on a missing import, add it to the bootstrap `pip install` line, commit, re-pull, re-run — per the Task-4 note.)

- [ ] **Step 7: Dry-run the wrapper end-to-end**

On the VM:
```bash
cd /home/ayman/guardian-loop && DRY_RUN=1 scripts/loop/guardian_loop.sh
```
Expected: resets to clean `origin/main`, prints `[loop] DRY_RUN — would run:` + the `claude --print …` line, exits 0. Confirms env-load + clone-reset + log dir all work without spending a Claude call.

- [ ] **Step 8: Install + enable the systemd units**

On the VM:
```bash
sudo cp /home/ayman/guardian-loop/deploy/loop/guardian-loop.service /etc/systemd/system/
sudo cp /home/ayman/guardian-loop/deploy/loop/guardian-loop.timer   /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/guardian-loop.service /etc/systemd/system/guardian-loop.timer
sudo systemctl daemon-reload
sudo systemctl enable --now guardian-loop.timer
systemctl list-timers 'guardian-loop*' --all
```
Expected: `systemd-analyze verify` prints nothing (valid); `list-timers` shows `guardian-loop.timer` with a NEXT firing time.

---

## Task 10: First live cycle — acceptance

This is the §10 Phase-1 acceptance check: the loop fires unattended, runs a pass, gates + checks, pushes (or cleanly no-ops), and updates `state.md` — no human in the loop.

- [ ] **Step 1: Trigger one real pass manually (don't wait for 02:30)**

On the VM:
```bash
sudo systemctl start guardian-loop.service
# follow it:
tail -f "$(ls -t /home/ayman/guardian-loop/.guardian-loop/logs/cycle-*.log | head -1)"
```
Expected: the log shows ORIENT picking a focus, the gate running, a checker subagent verdict, then either a push (`fixed`) or a clean `no-op`. The pass exits 0.

- [ ] **Step 2: Verify the gate genuinely ran and gated**

Run: `grep -E '\[gate\] (GATE PASS|FAIL)' /home/ayman/guardian-loop/.guardian-loop/logs/gate-*.log | tail -3`
Expected: a `GATE PASS` line for the shipped unit (or, if the pass hit a red gate, a `FAIL:` line AND no push in Step 3 — both are valid loop behavior).

- [ ] **Step 3: Verify state updated + (if fixed) a commit landed on main**

Run:
```bash
cat /home/ayman/guardian-loop/docs/loop/state.md
git -C /home/ayman/guardian-loop log --oneline -3 origin/main
```
Expected: `state.md` shows **1 cycle** with the outcome, gate, checker columns populated, and a `next_focus`. If outcome was `fixed`, `git log origin/main` shows the loop's pushed commit (with the Co-Authored-By trailer) + the `loop: record cycle 1` state commit.

- [ ] **Step 4: Verify no secrets leaked + credential guardrail held**

Run: `git -C /home/ayman/guardian-loop log -p -2 origin/main | grep -iE 'ANTHROPIC_API_KEY=|GUARDIAN_API_KEY=|XSOAR_KEY=|-----BEGIN' || echo "clean: no secrets in the loop's commits"`
Expected: `clean: no secrets in the loop's commits`.

- [ ] **Step 5: Confirm the timer will recur**

Run: `systemctl list-timers 'guardian-loop*' --all`
Expected: `guardian-loop.timer` shows the next nightly firing. The loop is live.

- [ ] **Step 6: Report Phase-1 completion to the operator**

Summarize: the loop is provisioned + enabled on guardian-vm; first pass outcome (fixed/no-op) + the commit if any; where state + logs live; how to pause (`systemctl disable --now guardian-loop.timer`). Note that Phase 2 (XSOAR seeding + `knowledge_upsert` + the judge curriculum) is the next spec→plan.

---

## Self-Review

**1. Spec coverage** (against `docs/loop/2026-06-11-self-learning-loop-design.md`):
- §5 cycle (ORIENT→FIX→VERIFY→CHECK→SHIP+STATE) → Task 6 playbook. ✓ (SEED/INVESTIGATE/JUDGE/DISTILL deliberately deferred to Phase 2 — Phase 1 is harness + self-healing per §6.)
- §5.1 on-disk state (`docs/loop/state.md` + `.guardian-loop/state.json`) → Tasks 1–2. ✓
- §5.2 playbook at `docs/loop/PLAYBOOK.md` → Task 6. ✓
- §5.3 maker/checker (full gate + adversarial subagent, sole guardrail) → Task 3 (gate) + Task 6 step 5 (checker). ✓
- §7 runtime = guardian-vm, systemd timer, headless `claude -p`, dedicated clone, localhost stack → Tasks 5/7/9. ✓
- §8 decisions (auto-push, no PR, no denylist; Claude-as-judge — N/A in Phase 1 since no judging yet) → wrapper + playbook. ✓
- §10 Phase-1 acceptance → Task 10. ✓
- Phase 2/3 (seeding, `knowledge_upsert`, `run_command`) → out of scope, called out as separate specs. ✓ (no gap — intentional decomposition)

**2. Placeholder scan:** No "TBD/TODO/implement later". The one forward-reference (validate_all.py's exact deps) is flagged as a concrete Task-9 verification with a fallback action, not a placeholder. ✓

**3. Type/name consistency:** `loop_state.py` API — `load_state`/`save_state`/`record_cycle`/`set_next_focus`/`compute_counters`/`render_markdown` + CLI `init`/`record`/`render` — used identically in tests (Task 1), the playbook's record/render calls (Task 6), and the catalogue (Task 8). Counter keys (`cycles_total`/`fixes_shipped`/`noops`/`gate_failures`/`checker_rejections`) match between `compute_counters`, the test, and `render_markdown`. Outcome enum (`fixed`/`no-op`/`gate-failed`/`checker-rejected`) consistent across module, test, playbook, CLI choices. Env var names (`GUARDIAN_LOOP_HOME`/`GUARDIAN_LOOP_ENV`/`CLAUDE_LOOP_MODEL`/`GUARDIAN_BASE`/`GUARDIAN_API_KEY`) consistent across `loop.env.example`, `guardian_loop.sh`, the service unit, and the runbook. Paths (`/home/ayman/guardian-loop`, `.guardian-loop/logs/`, `scripts/loop/loop.env`) consistent throughout. ✓
