# Guardian Self-Learning Loop — Phase 1 (Harness + Self-Healing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a durable, unattended self-improvement loop on the operator's local Mac that, on a nightly schedule, runs one "trainer pass" of Claude Code which finds-and-fixes one coherent maintenance/self-healing unit, verifies it with the full repo gate plus an adversarial checker subagent, and pushes it to `main` — with no human in the loop.

**Architecture:** A **launchd LaunchAgent** on the operator's Mac fires a bash **wrapper** (`guardian_loop.sh`) against a **dedicated repo clone** (`~/guardian-loop`, OUTSIDE `~/Documents` to dodge the macOS TCC revocation failure mode, and separate from the operator's interactive working tree). The wrapper hard-refuses to run in the primary working repo, then resets the clone to clean `origin/main`, opens a best-effort IAP tunnel for live-stack audits, and runs **`claude -p`** (headless Claude Code — full harness: CLAUDE.md, skills, hooks, `.claude/settings.json`) with a thin prompt that points at **`docs/loop/PLAYBOOK.md`**. The playbook is the deterministic pass: ORIENT → FIX → VERIFY (gate) → CHECK (adversarial subagent) → SHIP+STATE. The loop's own memory is two on-disk files (`.guardian-loop/state.json` machine state + `docs/loop/state.md` human mirror), written by a small tested Python module. No new MCP tools, no XSOAR seeding (that is Phase 2).

**Tech Stack:** bash, launchd (LaunchAgent plist), Python 3.12 (stdlib only — `argparse`/`json`/`pathlib`), `claude` CLI (headless `-p`), `gh` + local git auth, `gcloud` IAP tunnel (best-effort, for live-stack audits), the existing Guardian gate (`tsc`/`eslint`/`next build` + `pytest` + `validate_all.py`).

**Source spec:** [`docs/loop/2026-06-11-self-learning-loop-design.md`](../2026-06-11-self-learning-loop-design.md) (§5 mechanics, §5.1 state, §5.2 playbook, §5.3 maker/checker, §7 runtime = local machine, §10 Phase-1 acceptance).

**Security posture (read before Task 5/9):** the loop runs `claude -p --dangerously-skip-permissions`, because the operator's explicit decision is "auto-fix + push everything behind the full gate + adversarial checker; no PR, no path denylist." The gate + checker are the *sole* guardrail and must be uncompromised. Three honest facts the plan accepts:

1. **`--dangerously-skip-permissions` is NOT sandboxed, and cwd-pinning is NOT containment.** The pass can read/write anything the operator's user can — including the real `~/Documents/Kite/guardian` working tree, `~/.ssh`, `~/.aws`, `~/Library`, `.env.vm`. The clone is the *intended* scope, not an enforced one. The operator accepts this; a dedicated minimum-privilege macOS account is the noted follow-up if true isolation is later wanted.
2. **The destructive `git reset --hard`/`git clean -fd` is fenced by a positive-identity guard** (Task 5): the wrapper proceeds only if the target is a git work tree whose `origin` is `kite-production/guardian`, is named `guardian-loop`, carries a `.guardian-loop/IS_LOOP_CLONE` sentinel (written only by `loop_bootstrap.sh`), and is neither the primary repo nor under `~/Documents`. Guard inputs are pinned from the launchd env **before** `loop.env` is sourced, so `loop.env` cannot redirect the reset.
3. **A deterministic secret-scan is a hard gate step** (Task 3), not just the LLM checker — the gate aborts before any push if a credential-like string appears in the diff. Secrets live ONLY in `scripts/loop/loop.env` (gitignored, 0600) and the operator's local git/`gcloud`/keychain auth; the credential guardrail still holds (the loop edits code/docs, never reads/writes SecretStore values).

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
| `scripts/loop/guardian_loop.sh` | The launchd payload: refuse-if-main-repo guard → load env → reset clone to clean `origin/main` → best-effort IAP tunnel → run `claude -p` with the playbook prompt → log → close tunnel. Honors `DRY_RUN=1`. | create |
| `scripts/loop/loop.env.example` | Template for the gitignored local secrets/config file. | create |
| `docs/loop/PLAYBOOK.md` | The deterministic Phase-1 trainer pass (the loop prompt's procedure). | create |
| `deploy/loop/com.guardian.loop.plist` | launchd LaunchAgent that runs the wrapper nightly (`StartCalendarInterval`), redirecting stdout/err to the loop log dir. | create |
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
# state.json + state.md are TRACKED (the loop's versioned memory). Everything
# below is loop-clone-local runtime state that MUST survive `git clean -fd`
# (which never removes ignored files) and must NEVER be committed/pushed.
scripts/loop/loop.env
.guardian-loop/logs/
.guardian-loop/.lock/
.guardian-loop/IS_LOOP_CLONE
.guardian-loop/deps.hash
# Tunnel state dir created in the loop clone by scripts/guardian_tunnels.sh
.guardian-tunnels/
```

(`.guardian-tunnels/` and `*.log` are already ignored repo-wide — harmless duplicates. The sentinel/lock/hash entries are load-bearing: if they were tracked or un-ignored, `git clean -fd` would delete them mid-cycle and the next run's identity guard would fail.)

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
# "Pre-deploy gate" exactly, plus the AI-layer validator, plus a deterministic
# secret-scan (step 0) that is the loop's hard pre-push guardrail. Used by the
# loop's VERIFY step; also runnable by hand: scripts/loop/run_gate.sh [logfile]
set -uo pipefail

REPO="${GUARDIAN_LOOP_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
LOG="${1:-/dev/stdout}"

log()  { echo "[gate] $*" | tee -a "$LOG" >&2; }
fail() { log "FAIL: $1"; exit 1; }

# Step 0 — deterministic secret-scan on the working-tree + staged diff. Runs
# FIRST so a credential-like string aborts the whole pass before any push. Uses
# grep -q (never prints the matched secret). This is the gate, not the LLM checker.
SECRETS_RE='sk-ant-|-----BEGIN [A-Z ]*PRIVATE KEY|ANTHROPIC_API_KEY=[^[:space:]]|GUARDIAN_API_KEY=[^[:space:]]|VM_PASSWORD=[^[:space:]]|XSOAR_KEY=[^[:space:]]|guardian_ak_[A-Za-z0-9]'
log "0/7 secret-scan"
if (cd "$REPO" && { git diff HEAD; git diff --staged; }) | grep -qE "$SECRETS_RE"; then
  fail "secret-scan: a credential-like string appears in the diff — refusing to proceed"
fi

# Single repo-root venv carries pytest + mcp + updater + validator deps (loop_bootstrap.sh)
if [ -f "$REPO/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$REPO/.venv/bin/activate"
fi
PY="$(command -v python3)"

log "1/7 tsc"   ; (cd "$REPO/mcp/agent" && npx tsc --noEmit)            2>&1 | tee -a "$LOG" || fail tsc
log "2/7 lint"  ; (cd "$REPO/mcp/agent" && npm run lint)                2>&1 | tee -a "$LOG" || fail lint
log "3/7 build" ; (cd "$REPO/mcp/agent" && npm run build)               2>&1 | tee -a "$LOG" || fail build
log "4/7 mcp"   ; (cd "$REPO/bundles/spark/mcp" && PYTHONPATH="$PWD/src" "$PY" -m pytest tests/ -x) 2>&1 | tee -a "$LOG" || fail "mcp pytest"
log "5/7 updater"; (cd "$REPO/updater" && "$PY" -m pytest tests/ -x)    2>&1 | tee -a "$LOG" || fail "updater pytest"
log "6/7 validator"; (cd "$REPO" && "$PY" tooling/validate/validate_all.py) 2>&1 | tee -a "$LOG" || fail validator

log "GATE PASS"
```

(`set -uo pipefail` makes `cmd | tee || fail` report `cmd`'s failure, not `tee`'s success.)

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/loop/run_gate.sh && head -1 scripts/loop/run_gate.sh`
Expected: `#!/usr/bin/env bash`

- [ ] **Step 3: Smoke the gate locally (clean tree → PASS)**

Run: `scripts/loop/run_gate.sh /tmp/gate.log; echo "exit=$?"`
Expected: ends with `[gate] GATE PASS` and `exit=0`. (This is the full ~3-5 min gate; it confirms the runner wiring on the dev machine. The loop clone `~/guardian-loop` runs the same script after `loop_bootstrap.sh`.)

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
# One-time (and dep-refresh) provisioning for the loop's clone. Writes the
# loop-clone sentinel + log dir, sets up Node + Python gate deps in a single
# repo-root .venv, and records a deps-hash. Idempotent.
#   Usage: scripts/loop/loop_bootstrap.sh [--deps-only]
#     --deps-only  install deps + refresh the hash but SKIP the final gate-smoke
#                  (guardian_loop.sh calls this when it detects lockfile drift)
set -euo pipefail

DEPS_ONLY=0
[ "${1:-}" = "--deps-only" ] && DEPS_ONLY=1

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

echo "[bootstrap] loop-clone sentinel + log dir (both gitignored)"
mkdir -p "$REPO/.guardian-loop/logs"
: > "$REPO/.guardian-loop/IS_LOOP_CLONE"   # the wrapper's identity guard requires this marker

echo "[bootstrap] node deps (mcp/agent)"
(cd mcp/agent && npm ci)

echo "[bootstrap] python venv at $REPO/.venv"
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python3 -m pip install --upgrade pip

echo "[bootstrap] gate deps: test runner + mcp + updater + validator"
# pytest is in NO requirements.txt — it is the gate's test runner and MUST be
# installed explicitly, or run_gate.sh steps 4/5 die with ModuleNotFoundError.
python3 -m pip install pytest pytest-asyncio
python3 -m pip install -r bundles/spark/mcp/requirements.txt
python3 -m pip install -r updater/requirements.txt
# validate_all.py's only third-party import is `yaml` (PyYAML); jsonschema is a
# defensive extra in case a future validator adds it.
python3 -m pip install pyyaml jsonschema

echo "[bootstrap] recording deps-hash"
cat mcp/agent/package-lock.json bundles/spark/mcp/requirements.txt updater/requirements.txt 2>/dev/null \
  | shasum | awk '{print $1}' > "$REPO/.guardian-loop/deps.hash"

if [ "$DEPS_ONLY" = "1" ]; then
  echo "[bootstrap] --deps-only: deps refreshed, skipping gate-smoke"
  exit 0
fi

echo "[bootstrap] verifying the gate runs"
"$REPO/scripts/loop/run_gate.sh" /tmp/loop-bootstrap-gate.log

echo "[bootstrap] done — clone is ready for the loop"
```

- [ ] **Step 2: Make it executable + shellcheck-clean**

Run: `chmod +x scripts/loop/loop_bootstrap.sh && bash -n scripts/loop/loop_bootstrap.sh && echo "syntax ok"`
Expected: `syntax ok`. (Do NOT run it from your working repo — it is executed in the loop clone `~/guardian-loop` in Task 9. `bash -n` is syntax-only.)

> NOTE for Task 9: if ANY gate step errors on a missing module in the fresh clone's `.venv` (e.g. an mcp test imports `respx`/`anyio`, or the validator imports something beyond `yaml`), add that package to the bootstrap `pip install` block in the same change, commit from the working repo, re-pull in the clone, re-run. `pytest`+`pytest-asyncio` are already covered above; this note is the catch-all for any further test-only import.

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
# Copy to scripts/loop/loop.env on THIS machine (gitignored, mode 0600).
# NEVER commit the real file. NOTE: this file CANNOT change GUARDIAN_LOOP_HOME or
# GUARDIAN_PRIMARY_REPO — the wrapper pins those from the launchd env BEFORE
# sourcing this file, so the destructive reset can never be redirected here.

# Anthropic auth for headless `claude -p`. RECOMMENDED for the unattended loop:
# `claude`'s OAuth creds live in the macOS LOGIN KEYCHAIN, which is only unlocked
# while the Mac is logged in — a reboot/logout before the 02:30 fire LOCKS it and
# the pass fails to authenticate. Set a key here for reliable unattended runs.
# (Leave unset only if you accept the loop skips any night the Mac rebooted.)
ANTHROPIC_API_KEY=

# Model for the loop pass (a strong model — codework + judging).
CLAUDE_LOOP_MODEL=claude-fable-5

# Absolute path to `claude` IF it is not on the launchd plist PATH (Task 9 Step 2).
# Leave unset if `which claude` is under /opt/homebrew/bin or /usr/local/bin.
# CLAUDE_BIN=

# --- Hard ceilings for the unattended pass (no human watching) ---
LOOP_MAX_BUDGET_USD=5     # passed to `claude --print --max-budget-usd`; unset = no budget flag
LOOP_MAX_SECONDS=3600     # wall-clock watchdog kills a hung pass after this many seconds

# Where the dedicated clone lives. (Pinned from the launchd env; kept here for the
# manual `DRY_RUN=1 … guardian_loop.sh` invocation.) Outside ~/Documents, not the
# primary repo.
GUARDIAN_LOOP_HOME=/Users/ayman/guardian-loop

# --- Live-stack audits (best-effort; Phase 1 works repo-only without these) ---
LOOP_USE_TUNNEL=1         # 0 = never tunnel (repo-only audits)
# Guardian agent API key (scope *) to drive /api/agent/* through the tunnel.
# Same value as GUARDIAN_API_KEY in .env.vm.
GUARDIAN_API_KEY=
# Agent base URL via the IAP tunnel. +1 offset (3001 → remote 3000) avoids
# colliding with a local dev server on 3000.
GUARDIAN_BASE=https://localhost:3001
GUARDIAN_AGENT_LOCAL_PORT=3001   # consumed by scripts/guardian_tunnels.sh
```

The tunnel reuses `scripts/guardian_tunnels.sh`, which reads `.env.vm` from the clone root for VM coordinates. Provisioning (Task 9) copies `.env.vm` into the clone if it exists (gitignored — never committed).

- [ ] **Step 2: Write the wrapper**

Create `scripts/loop/guardian_loop.sh`:

```bash
#!/usr/bin/env bash
# launchd payload for the Guardian self-learning loop. One invocation = one
# trainer pass. Positively verifies it is the dedicated loop clone, single-flights
# via a lock, resets to clean origin/main, refreshes deps on lockfile drift, opens
# a best-effort+probed IAP tunnel, then runs headless Claude Code (budget +
# wall-clock bounded) against docs/loop/PLAYBOOK.md. Honors DRY_RUN=1.
# Targets macOS /bin/bash 3.2 — no bash-4 features, no empty-array+nounset traps.
set -uo pipefail

# --- 1. Pin guard inputs from the launchd/CLI env BEFORE sourcing loop.env, so
#        loop.env can never redirect the destructive reset to another repo. ---
LOOP_HOME_PINNED="${GUARDIAN_LOOP_HOME:-$HOME/guardian-loop}"
PRIMARY_REPO="${GUARDIAN_PRIMARY_REPO:-/Users/ayman/Documents/Kite/guardian}"
RESOLVED="$(cd "$LOOP_HOME_PINNED" 2>/dev/null && pwd -P || true)"
[ -n "$RESOLVED" ] || { echo "[loop] REFUSE: no clone at $LOOP_HOME_PINNED" >&2; exit 1; }
fail_guard() { echo "[loop] REFUSE: $1 ($RESOLVED)" >&2; exit 2; }

# --- 2. Destructive-path DENY checks (ALWAYS enforced, even under DRY_RUN) ---
PRIMARY_RESOLVED="$(cd "$PRIMARY_REPO" 2>/dev/null && pwd -P || echo __none__)"
[ "$RESOLVED" != "$PRIMARY_RESOLVED" ] || fail_guard "clone is the primary working repo"
case "$RESOLVED" in "$HOME/Documents"/*|"$HOME/Documents") fail_guard "clone is under ~/Documents (TCC risk)";; esac

# --- 3. Positive-identity ALLOW checks (real runs only; relaxed for DRY_RUN test) ---
if [ "${DRY_RUN:-0}" != "1" ]; then
  [ "$(basename "$RESOLVED")" = "guardian-loop" ] || fail_guard "clone dir is not named guardian-loop"
  git -C "$RESOLVED" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail_guard "not a git work tree"
  git -C "$RESOLVED" remote get-url origin 2>/dev/null | grep -q 'kite-production/guardian' || fail_guard "origin is not kite-production/guardian"
  [ -f "$RESOLVED/.guardian-loop/IS_LOOP_CLONE" ] || fail_guard "missing .guardian-loop/IS_LOOP_CLONE sentinel — run loop_bootstrap.sh"
fi

cd "$RESOLVED" || { echo "[loop] cannot cd $RESOLVED" >&2; exit 1; }

# --- 4. Now safe to load config/secrets (API keys/model/tunnel/budget — NOT the clone home) ---
ENV_FILE="$RESOLVED/scripts/loop/loop.env"
if [ -f "$ENV_FILE" ]; then set -a; # shellcheck disable=SC1090
  . "$ENV_FILE"; set +a; fi

mkdir -p "$RESOLVED/.guardian-loop/logs"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="$RESOLVED/.guardian-loop/logs/cycle-$TS.log"

# --- 5. Single-flight lock (mkdir is atomic; macOS has no util-linux flock) ---
LOCK="$RESOLVED/.guardian-loop/.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +360 2>/dev/null)" ]; then
    echo "[loop] reclaiming stale lock (>6h)" | tee -a "$LOG"; rm -rf "$LOCK"; mkdir "$LOCK"
  else
    echo "[loop] another pass is running; skipping this fire" >&2; exit 0
  fi
fi
TUNNEL_UP=0
cleanup() {
  [ "$TUNNEL_UP" = "1" ] && "$RESOLVED/scripts/guardian_tunnels.sh" stop >>"$LOG" 2>&1
  rm -rf "$LOCK"
  return 0
}
trap cleanup EXIT

# --- 6. Reset to clean origin/main; never reset on a stale ref ---
echo "[loop] $TS starting in $RESOLVED; reset to clean origin/main" | tee -a "$LOG"
if ! git fetch origin main 2>&1 | tee -a "$LOG"; then
  echo "[loop] git fetch failed — aborting (won't run on a stale ref)" | tee -a "$LOG"; exit 1
fi
git checkout -B main origin/main 2>&1 | tee -a "$LOG"   # deterministic clean main even if left detached/dirty
git reset --hard origin/main     2>&1 | tee -a "$LOG"
git clean -fd                    2>&1 | tee -a "$LOG"   # NEVER add -x: would nuke .venv/node_modules/logs (all gitignored)

# --- 7. Refresh deps if lockfiles drifted since last bootstrap ---
HASH_FILE="$RESOLVED/.guardian-loop/deps.hash"
CUR_HASH="$(cat mcp/agent/package-lock.json bundles/spark/mcp/requirements.txt updater/requirements.txt 2>/dev/null | shasum | awk '{print $1}')"
if [ "${DRY_RUN:-0}" != "1" ] && { [ ! -f "$HASH_FILE" ] || [ "$CUR_HASH" != "$(cat "$HASH_FILE" 2>/dev/null)" ]; }; then
  echo "[loop] dependency lockfiles changed; refreshing deps" | tee -a "$LOG"
  "$RESOLVED/scripts/loop/loop_bootstrap.sh" --deps-only >>"$LOG" 2>&1 \
    || echo "[loop] WARN: dep refresh failed; gate may run against stale deps" | tee -a "$LOG"
fi

# --- 8. Best-effort IAP tunnel; trusted ONLY after a reachability probe of the AGENT port ---
if [ "${LOOP_USE_TUNNEL:-1}" = "1" ] && [ -f "$RESOLVED/.env.vm" ]; then
  echo "[loop] opening best-effort IAP tunnel" | tee -a "$LOG"
  if "$RESOLVED/scripts/guardian_tunnels.sh" start >>"$LOG" 2>&1 \
     && curl -sk -m 8 -o /dev/null "${GUARDIAN_BASE:-https://localhost:3001}/" 2>/dev/null; then
    TUNNEL_UP=1
  else
    echo "[loop] tunnel unavailable/unreachable; proceeding repo-only" | tee -a "$LOG"
    "$RESOLVED/scripts/guardian_tunnels.sh" stop >>"$LOG" 2>&1 || true
  fi
fi
if [ "$TUNNEL_UP" = "1" ]; then
  TUNNEL_NOTE="A live-stack IAP tunnel IS reachable this pass at \$GUARDIAN_BASE."
else
  TUNNEL_NOTE="No live-stack tunnel this pass — use repo-only audits."
fi
PROMPT="You are running the Guardian self-learning loop as an UNATTENDED scheduled trainer pass on the operator's local machine. Follow docs/loop/PLAYBOOK.md exactly, top to bottom. Do exactly one coherent unit this pass. Never push on a red gate or a checker rejection. $TUNNEL_NOTE"

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
MODEL="${CLAUDE_LOOP_MODEL:-claude-fable-5}"
BUDGET_NOTE=""; [ -n "${LOOP_MAX_BUDGET_USD:-}" ] && BUDGET_NOTE="--max-budget-usd $LOOP_MAX_BUDGET_USD "

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "[loop] DRY_RUN — tunnel_up=$TUNNEL_UP — would run:" | tee -a "$LOG"
  echo "$CLAUDE_BIN --print --model $MODEL ${BUDGET_NOTE}--dangerously-skip-permissions \"<PLAYBOOK prompt>\"" | tee -a "$LOG"
  exit 0
fi

# --- 9. Run claude with budget flag + a wall-clock watchdog (macOS lacks `timeout`) ---
echo "[loop] launching headless claude -p (model=$MODEL, tunnel_up=$TUNNEL_UP); log: $LOG" | tee -a "$LOG"
if [ -n "${LOOP_MAX_BUDGET_USD:-}" ]; then
  "$CLAUDE_BIN" --print --model "$MODEL" --max-budget-usd "$LOOP_MAX_BUDGET_USD" --dangerously-skip-permissions "$PROMPT" >>"$LOG" 2>&1 &
else
  "$CLAUDE_BIN" --print --model "$MODEL" --dangerously-skip-permissions "$PROMPT" >>"$LOG" 2>&1 &
fi
CLAUDE_PID=$!
( sleep "${LOOP_MAX_SECONDS:-3600}"
  if kill -0 "$CLAUDE_PID" 2>/dev/null; then
    echo "[loop] watchdog: pass exceeded ${LOOP_MAX_SECONDS:-3600}s; terminating" | tee -a "$LOG"
    kill -TERM "$CLAUDE_PID" 2>/dev/null; sleep 10; kill -KILL "$CLAUDE_PID" 2>/dev/null
  fi ) &
WATCHDOG_PID=$!
wait "$CLAUDE_PID"; STATUS=$?
kill "$WATCHDOG_PID" 2>/dev/null || true
echo "[loop] $TS finished; claude exit=$STATUS" | tee -a "$LOG"
exit "$STATUS"
```

- [ ] **Step 3: Make it executable; verify the guard fires; dry-run against a throwaway clone**

Run:
```bash
chmod +x scripts/loop/guardian_loop.sh
# 1. SAFETY GUARD: must refuse to run in the primary working repo (no reset happens)
GUARDIAN_LOOP_HOME="$(git rev-parse --show-toplevel)" scripts/loop/guardian_loop.sh; echo "exit=$? (expect 2)"
# 2. DRY-RUN against a throwaway clone (never touches your working tree, spends no Claude call)
TMP_PARENT=$(mktemp -d); TMP_CLONE="$TMP_PARENT/guardian-loop"
git clone -q "$(git rev-parse --show-toplevel)" "$TMP_CLONE"
GUARDIAN_LOOP_HOME="$TMP_CLONE" DRY_RUN=1 LOOP_USE_TUNNEL=0 scripts/loop/guardian_loop.sh; echo "exit=$? (expect 0)"
rm -rf "$TMP_PARENT"
```
Expected: (1) prints `[loop] REFUSE: clone is the primary working repo …` and `exit=2` — the destructive `git reset --hard` can never hit your working tree (the deny check runs before any git op). (2) the throwaway passes the deny checks (it's under `/var/folders`, not `~/Documents`), identity checks are relaxed under `DRY_RUN`, deps-refresh is skipped under `DRY_RUN`, and it prints `[loop] DRY_RUN — tunnel_up=0 — would run:` + the `claude --print --model … --dangerously-skip-permissions` line, `exit=0`.

- [ ] **Step 4: Commit**

```bash
git add scripts/loop/guardian_loop.sh scripts/loop/loop.env.example
git commit -m "loop: launchd wrapper + secrets template (headless claude -p payload)

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

You are Claude Code running an **unattended scheduled trainer pass** on the
operator's local machine, started by `scripts/loop/guardian_loop.sh`. The clone
is already reset to clean `origin/main`. Do **exactly one coherent unit** this
pass, then verify, check, ship, and record. Then stop.

The wrapper's launch prompt tells you whether a **live-stack IAP tunnel** is up
this pass. If it is NOT, skip every live-stack audit below and use the
repo-only audits — those are always available and are the bulk of Phase 1.

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
c. **A self-heal scan** — run these audits and take the FIRST real issue found.
   **Repo-only audits (ALWAYS available):**
   - **Doc-sync:** sidebar nav vs pages — `find mcp/agent/app -maxdepth 3 -name page.tsx | xargs dirname | sort` vs `href:` entries in `mcp/agent/components/sidebar.tsx`. Architecture-page service list vs the `services:` block in `docker-compose.yml`. CHANGELOG.md newest entry vs `mcp/agent/lib/release-notes.ts` newest entry.
   - **Bug-family audit:** `grep -rn "from usecase\." bundles/spark/connectors */src 2>/dev/null` (import-style regression, see connectors/CLAUDE.md); connector.yaml `spec.tools[].name` bare vs prefixed Python functions; hardcoded-data drift in `mcp/agent/app/api/` (e.g. marketplace `toolCount`).
   - **Spec-drift:** "Implementation gap" bullets in `mcp/agent/app/help/architecture/page.tsx`.
   **Live-stack audits (ONLY if the launch prompt said a tunnel is up):**
   - **Observe:** `curl -sk -H "Authorization: Bearer $GUARDIAN_API_KEY" $GUARDIAN_BASE/api/agent/jobs`; scan the `/observability` surfaces for errors. If no tunnel this pass, SKIP — do not block on stack access.
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
  Step 0 of the gate is a **deterministic secret-scan** of your diff — if it trips,
  you committed/staged a credential-like string; treat as a hard failure.
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
Record the cycle into the loop's memory, then ship the fix **and** the state
update as ONE atomic commit — folding them avoids a second CI/auto-deploy
trigger and the state-loss race if a human pushes between two separate pushes.

1. Record + render (the module is the only writer; note tunnel availability in
   the summary so degraded live-stack access is visible):
   ```bash
   python3 scripts/loop/loop_state.py --repo . record \
     --started-at "<UTC ISO from preflight>" \
     --focus "<the focus>" \
     --outcome "<fixed|no-op|gate-failed|checker-rejected>" \
     --summary "<one line> (tunnel: <up|down>)" \
     --commit "" \
     --gate "<pass|fail|>" --checker "<approved|rejected|n/a>" \
     --next-focus "<what next pass should look at>"
   python3 scripts/loop/loop_state.py --repo . render
   ```
2. **fixed (approved + green)** — one commit (fix + state together), one push,
   with a bounded rebase-retry:
   ```bash
   git add -A
   git commit -m "<conventional message; Refs/Closes #N>

   Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
   for i in 1 2 3; do git pull --rebase origin main && git push origin main && break; sleep 5; done
   ```
   (The shipping commit *is* this one; git history is the source of truth for the
   SHA, so `--commit ""` in the record is fine.)
3. **no-op** — you MAY commit + push the state-only update (same one-commit/
   one-push shape) so the nightly cadence stays visible.
4. **gate-failed / checker-rejected** — first revert the working changes
   (`git reset --hard HEAD && git clean -fd`), then record + render; optionally
   commit + push the state-only record so the failure is visible. NEVER push a
   fix that failed the gate or the checker.
- **Do NOT wait for CI** — the wrapper exits here. The next pass's ORIENT can
  verify the deploy landed (when the tunnel is up, version endpoint vs HEAD).

## Stop
One unit done (or a clean no-op). Exit. The launchd LaunchAgent fires the next pass.
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

## Task 7: launchd LaunchAgent (`com.guardian.loop.plist`)

**Files:**
- Create: `deploy/loop/com.guardian.loop.plist`

- [ ] **Step 1: Write the LaunchAgent plist**

Create `deploy/loop/com.guardian.loop.plist` (a TEMPLATE — `$HOME` is hardcoded to `/Users/ayman` because launchd plists do not expand env vars; provisioning copies it to `~/Library/LaunchAgents/`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.guardian.loop</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/ayman/guardian-loop/scripts/loop/guardian_loop.sh</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>GUARDIAN_LOOP_HOME</key>
    <string>/Users/ayman/guardian-loop</string>
    <!-- launchd gives a minimal PATH and does NOT source ~/.zshrc, so add every
         dir the pass needs: claude/node/npm (Homebrew), git, AND gcloud's SDK bin
         (only added interactively by ~/.zshrc → guardian_tunnels.sh would otherwise
         never find gcloud under launchd). Confirm the real paths in Task 9 Step 2;
         if `which claude` is elsewhere, also set CLAUDE_BIN in loop.env. -->
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/Users/ayman/google-cloud-sdk/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <!-- Nightly at 02:30 local. launchd replays a job missed while the Mac was
       ASLEEP at next wake (coalesced); a run missed because the Mac was powered
       OFF is skipped (next fire is the following night). -->
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>2</integer>
    <key>Minute</key><integer>30</integer>
  </dict>

  <!-- Schedule-only; do not run when (re)loaded. Test runs use `launchctl kickstart`. -->
  <key>RunAtLoad</key>
  <false/>

  <key>StandardOutPath</key>
  <string>/Users/ayman/guardian-loop/.guardian-loop/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/ayman/guardian-loop/.guardian-loop/logs/launchd.err.log</string>
</dict>
</plist>
```

> launchd has no built-in per-run wall-clock limit, so `guardian_loop.sh` wraps the `claude` call in a watchdog (`LOOP_MAX_SECONDS`, default 3600s) that SIGTERMs/SIGKILLs a hung pass, and passes `--max-budget-usd` (`LOOP_MAX_BUDGET_USD`) to cap spend. The operator can also stop a run with `launchctl kill TERM gui/$(id -u)/com.guardian.loop`.

- [ ] **Step 2: Validate the plist syntax**

Run: `plutil -lint deploy/loop/com.guardian.loop.plist`
Expected: `deploy/loop/com.guardian.loop.plist: OK`.

- [ ] **Step 3: Commit**

```bash
git add deploy/loop/com.guardian.loop.plist
git commit -m "loop: launchd LaunchAgent (nightly trainer pass on the local Mac)

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

The loop is a durable, unattended self-improvement cycle that runs on the
**operator's local Mac** (NOT guardian-vm). Design:
[`2026-06-11-self-learning-loop-design.md`](2026-06-11-self-learning-loop-design.md).
Phase-1 procedure: [`PLAYBOOK.md`](PLAYBOOK.md).

## What it does (Phase 1)
A nightly **launchd** LaunchAgent runs one "trainer pass" of headless Claude
Code that finds + fixes one self-healing unit (doc-sync, bug-family, spec-drift,
and — when a best-effort IAP tunnel is up — live-stack observe), runs the full
gate + an adversarial checker, and pushes to `main` (which triggers the normal
CI build + auto-deploy on the VM runner). No XSOAR seeding yet (Phase 2).

## Where things live
| Thing | Path |
|---|---|
| Dedicated clone | `~/guardian-loop` (OUTSIDE `~/Documents`; NOT the working repo) |
| Secrets/config (gitignored, 0600) | `~/guardian-loop/scripts/loop/loop.env` |
| VM coords for the tunnel (gitignored) | `~/guardian-loop/.env.vm` (copied during provisioning) |
| Machine state (tracked) | `.guardian-loop/state.json` |
| Human state mirror | `docs/loop/state.md` |
| Per-cycle transcripts (gitignored) | `.guardian-loop/logs/cycle-*.log` + `launchd.{out,err}.log` |
| LaunchAgent plist | `deploy/loop/com.guardian.loop.plist` → `~/Library/LaunchAgents/` |

## Provisioning (one time — see Task 9 of the plan for the exact commands)
1. `git clone` into `~/guardian-loop` (claude + git are already installed/authed locally).
2. `cp scripts/loop/loop.env.example scripts/loop/loop.env`, fill it, `chmod 600`.
3. Copy `.env.vm` into the clone (for the best-effort tunnel) — gitignored.
4. `scripts/loop/loop_bootstrap.sh` (npm ci + .venv + deps + gate smoke).
5. Install the LaunchAgent: copy the plist to `~/Library/LaunchAgents/` and
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.guardian.loop.plist`.

## Operate it
- **Status:** `launchctl print gui/$(id -u)/com.guardian.loop | grep -E 'state|runs'`
- **Run one pass now:** `launchctl kickstart -k gui/$(id -u)/com.guardian.loop` then
  tail the newest `~/guardian-loop/.guardian-loop/logs/cycle-*.log`.
- **Dry run (no claude):** `DRY_RUN=1 ~/guardian-loop/scripts/loop/guardian_loop.sh`
- **Pause:** `launchctl bootout gui/$(id -u)/com.guardian.loop`
- **Read what it's done:** `~/guardian-loop/docs/loop/state.md`.

## Unattended auth (the two fragile, keychain-backed dependencies)
- **`claude`** OAuth creds live in the macOS **login keychain** — readable only while the Mac is logged in AND the keychain is unlocked. A reboot/logout before the 02:30 fire LOCKS them and the pass fails to authenticate. For reliable nightly runs, set `ANTHROPIC_API_KEY` in `loop.env` (recommended over relying on the keychain).
- **`git push`** uses `gh auth git-credential` reading gh's token from the keyring under the launchd session (no PAT). A future `gh` re-auth, a keychain ACL prompt, or a `gh` path change breaks the unattended push silently. Task 9 Step 7 verifies it under a launchd-like env.
- **`gcloud`** (best-effort tunnel) uses your interactive SSO account, whose token expires on a corporate cadence; when it lapses, the tunnel silently degrades to repo-only audits (visible as `tunnel: down` in `state.md`). A dedicated service account + ADC is the proper unattended fix (Phase 2+).

## Guardrails
The loop auto-pushes to `main` with **no PR**. Its only guardrails are the full
gate (`scripts/loop/run_gate.sh`) and an adversarial checker subagent — both
must pass before any push. The wrapper refuses to run in the primary working
repo or under `~/Documents`. It never touches credentials and never tags a
release (operator-only). To stop it entirely, `launchctl bootout` the agent.
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
| `loop/guardian_loop.sh` | launchd payload: guard → reset clone → best-effort tunnel → run headless `claude -p` against the playbook | Auto, nightly LaunchAgent |
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

## Task 9: Provision the loop on the local Mac + dry-run end-to-end

This task runs **on the operator's Mac**, as shell steps (not TDD). Push the Task-1..8 commits to `main` FIRST so the fresh clone has them. The working repo is `/Users/ayman/Documents/Kite/guardian`; the loop clone is `~/guardian-loop` (deliberately separate, outside `~/Documents`).

- [ ] **Step 1: Push the harness commits**

Run (from the working repo): `git push origin main`
Expected: Tasks 1–8 commits land on `origin/main`. (Triggers a CI build of the agent — harmless; loop files don't change image behavior.)

- [ ] **Step 2: Confirm the toolchain resolves UNDER the launchd PATH (not just interactively)**

Run (this mirrors the plist PATH, so it deterministically surfaces the `gcloud` gap that an interactive check would hide):
```bash
for b in claude node npm git gcloud curl shasum; do
  printf '%-8s ' "$b"
  PATH=/opt/homebrew/bin:/usr/local/bin:/Users/ayman/google-cloud-sdk/bin:/usr/bin:/bin:/usr/sbin:/sbin command -v "$b" || echo "MISSING under launchd PATH"
done
```
Expected: every binary resolves under the plist PATH. If `gcloud` is NOT at `/Users/ayman/google-cloud-sdk/bin`, fix the plist PATH (Task 7) to match `command -v gcloud` from an interactive shell. If `claude` shows MISSING (e.g. a version-manager shim), set `CLAUDE_BIN=<abs path>` in `loop.env` (Step 4).

- [ ] **Step 3: Create the dedicated clone (outside ~/Documents)**

Run:
```bash
git clone https://github.com/kite-production/guardian.git "$HOME/guardian-loop"
cd "$HOME/guardian-loop" && git rev-parse --abbrev-ref HEAD && pwd -P
```
Expected: `main` and path `/Users/ayman/guardian-loop`. Confirm it is NOT under `~/Documents` and NOT the working repo (the wrapper's guard enforces this, but verify here too).

- [ ] **Step 4: Create `loop.env`**

Run:
```bash
cd "$HOME/guardian-loop"
cp scripts/loop/loop.env.example scripts/loop/loop.env
chmod 600 scripts/loop/loop.env
# Edit scripts/loop/loop.env:
#   - GUARDIAN_API_KEY = the value from .env.vm (for live-stack audits)
#   - keep GUARDIAN_LOOP_HOME=/Users/ayman/guardian-loop, GUARDIAN_BASE=https://localhost:3001
#   - if `which claude` (Step 2) wasn't on the plist PATH: add CLAUDE_BIN=<abs path>
#   - set ANTHROPIC_API_KEY ONLY if the unattended claude can't find stored creds
stat -f '%Lp' scripts/loop/loop.env
```
Expected: `600`. (`stat -f` is the BSD/macOS form; the GNU `-c` form does not apply here.)

- [ ] **Step 5: Copy `.env.vm` into the clone IF it exists (for the best-effort tunnel)**

Run:
```bash
SRC="/Users/ayman/Documents/Kite/guardian/.env.vm"
if [ -f "$SRC" ]; then
  cp "$SRC" "$HOME/guardian-loop/.env.vm"
  (cd "$HOME/guardian-loop" && git check-ignore .env.vm) && echo "copied + ignored ✓"
else
  echo "no .env.vm at $SRC — set LOOP_USE_TUNNEL=0 in loop.env; the loop runs repo-only"
fi
```
Expected: either `copied + ignored ✓` (the clone's `.gitignore` ignores it — never committed), or the repo-only message. The tunnel is best-effort: absent `.env.vm` the Phase-1 audits run repo-only and nothing breaks. (`.env.vm` may not exist yet on your machine — that's fine for Phase 1.)

- [ ] **Step 6: Bootstrap the clone deps**

Run: `cd "$HOME/guardian-loop" && scripts/loop/loop_bootstrap.sh`
Expected: ends with `[bootstrap] done — clone is ready for the loop` and the embedded gate prints `[gate] GATE PASS`. (If `validate_all.py` errors on a missing import, add it to the bootstrap `pip install` line, commit from the working repo, re-pull in the clone, re-run — per the Task-4 note.)

- [ ] **Step 7: Verify git push auth UNDER A LAUNCHD-LIKE ENV (read-only)**

Run (mirrors the agent's minimal env so the check exercises what the nightly run actually has — an interactive `git ls-remote` would NOT prove this):
```bash
env -i HOME="$HOME" PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  git -C "$HOME/guardian-loop" ls-remote origin -h refs/heads/main
```
Expected: prints the remote `main` SHA — confirming `gh auth git-credential` can read its token from the keyring under the launchd-like session. The loop pushes with these creds; **no separate PAT** is needed. If this fails, the unattended push won't work until the gh keyring item is reachable under launchd (see the runbook's "Unattended auth" section).

- [ ] **Step 8: Dry-run the wrapper, then probe headless `claude` auth under a launchd-like env**

Run:
```bash
# (a) dry-run the full wrapper logic (no Claude call, no push)
cd "$HOME/guardian-loop" && DRY_RUN=1 scripts/loop/guardian_loop.sh
# (b) prove `claude -p` can actually authenticate in the minimal env launchd gives it
env -i HOME="$HOME" PATH=/opt/homebrew/bin:/usr/local/bin:/Users/ayman/google-cloud-sdk/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  ANTHROPIC_API_KEY="$(grep -E '^ANTHROPIC_API_KEY=' "$HOME/guardian-loop/scripts/loop/loop.env" | cut -d= -f2-)" \
  claude --print --model claude-fable-5 "reply with the single word OK"
```
Expected: (a) resets to clean `origin/main`, attempts the tunnel, prints `[loop] DRY_RUN — tunnel_up=<0|1> — would run:` + the `claude --print …` line, exits 0. (b) prints `OK` — proving auth + PATH + model resolve in the launchd-like environment. **If (b) fails to authenticate, set `ANTHROPIC_API_KEY` in `loop.env`** (the keychain OAuth is not reachable in this stripped env — exactly the reboot/logout failure mode). The `.guardian-loop/logs/` dir already exists (created by `loop_bootstrap.sh` in Step 6), so launchd can open the plist's `StandardOutPath` on the first scheduled fire.

- [ ] **Step 9: Install + load the LaunchAgent**

Run:
```bash
cp "$HOME/guardian-loop/deploy/loop/com.guardian.loop.plist" "$HOME/Library/LaunchAgents/"
plutil -lint "$HOME/Library/LaunchAgents/com.guardian.loop.plist"
launchctl bootout gui/$(id -u)/com.guardian.loop 2>/dev/null || true   # idempotent: clear any prior load
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.guardian.loop.plist"
launchctl print gui/$(id -u)/com.guardian.loop | grep -E 'state =|program ='
```
Expected: `plutil` prints `OK`; `launchctl print` shows the agent registered with `guardian_loop.sh` as its program and a `state = waiting` (scheduled, not yet run).

---

## Task 10: First live cycle — acceptance

This is the §10 Phase-1 acceptance check: the loop fires unattended, runs a pass, gates + checks, pushes (or cleanly no-ops), and updates `state.md` — no human in the loop.

- [ ] **Step 1: Trigger one real pass manually (don't wait for 02:30)**

Run:
```bash
launchctl kickstart -k gui/$(id -u)/com.guardian.loop
# follow it:
tail -f "$(ls -t "$HOME"/guardian-loop/.guardian-loop/logs/cycle-*.log | head -1)"
```
Expected: the log shows ORIENT picking a focus, the gate running, a checker subagent verdict, then either a push (`fixed`) or a clean `no-op`. The pass exits 0.

- [ ] **Step 2: Verify the gate genuinely ran and gated**

Run: `grep -E '\[gate\] (GATE PASS|FAIL)' "$HOME"/guardian-loop/.guardian-loop/logs/gate-*.log | tail -3`
Expected: a `GATE PASS` line for the shipped unit (or, if the pass hit a red gate, a `FAIL:` line AND no push in Step 3 — both are valid loop behavior).

- [ ] **Step 3: Verify state updated + (if fixed) a commit landed on main**

Run:
```bash
cat "$HOME"/guardian-loop/docs/loop/state.md
git -C "$HOME"/guardian-loop log --oneline -3 origin/main
```
Expected: `state.md` shows **1 cycle** with the outcome, gate, checker columns populated, and a `next_focus`. If outcome was `fixed`, `git log origin/main` shows the loop's pushed commit (with the Co-Authored-By trailer) + the `loop: record cycle 1` state commit.

- [ ] **Step 4: Verify no secrets leaked + credential guardrail held**

Run: `git -C "$HOME"/guardian-loop log -p -2 origin/main | grep -iE 'ANTHROPIC_API_KEY=|GUARDIAN_API_KEY=|XSOAR_KEY=|-----BEGIN' || echo "clean: no secrets in the loop's commits"`
Expected: `clean: no secrets in the loop's commits`.

- [ ] **Step 5: Confirm the agent is scheduled to recur**

Run: `launchctl print gui/$(id -u)/com.guardian.loop | grep -E 'state =|runs =|com.guardian.loop'`
Expected: `state = waiting` (loaded, scheduled for the next 02:30 firing). The loop is live.

- [ ] **Step 6: Report Phase-1 completion to the operator**

Summarize: the loop is provisioned + loaded on the local Mac (launchd); first pass outcome (fixed/no-op) + the commit if any; where state + logs live; how to pause (`launchctl bootout gui/$(id -u)/com.guardian.loop`). Note the Mac-must-be-awake tradeoff (launchd runs a missed job at next wake). Note that Phase 2 (XSOAR seeding + `knowledge_upsert` + the judge curriculum) is the next spec→plan.

---

## Self-Review

**1. Spec coverage** (against `docs/loop/2026-06-11-self-learning-loop-design.md`):
- §5 cycle (ORIENT→FIX→VERIFY→CHECK→SHIP+STATE) → Task 6 playbook. ✓ (SEED/INVESTIGATE/JUDGE/DISTILL deliberately deferred to Phase 2 — Phase 1 is harness + self-healing per §6.)
- §5.1 on-disk state (`docs/loop/state.md` + `.guardian-loop/state.json`) → Tasks 1–2. ✓
- §5.2 playbook at `docs/loop/PLAYBOOK.md` → Task 6. ✓
- §5.3 maker/checker (full gate + adversarial subagent, sole guardrail) → Task 3 (gate) + Task 6 step 5 (checker). ✓
- §7 runtime = local Mac, launchd LaunchAgent, headless `claude -p`, dedicated clone (`~/guardian-loop`, outside `~/Documents`, with a main-repo refusal guard), best-effort IAP tunnel for live-stack audits → Tasks 5/7/9. ✓
- §8 decisions (auto-push, no PR, no denylist; Claude-as-judge — N/A in Phase 1 since no judging yet) → wrapper + playbook. ✓
- §10 Phase-1 acceptance → Task 10. ✓
- Phase 2/3 (seeding, `knowledge_upsert`, `run_command`) → out of scope, called out as separate specs. ✓ (no gap — intentional decomposition)

**2. Placeholder scan:** No "TBD/TODO/implement later". The one forward-reference (validate_all.py's exact deps) is flagged as a concrete Task-9 verification with a fallback action, not a placeholder. ✓

**3. Type/name consistency:** `loop_state.py` API — `load_state`/`save_state`/`record_cycle`/`set_next_focus`/`compute_counters`/`render_markdown` + CLI `init`/`record`/`render` — used identically in tests (Task 1), the playbook's record/render calls (Task 6), and the catalogue (Task 8). Counter keys (`cycles_total`/`fixes_shipped`/`noops`/`gate_failures`/`checker_rejections`) match between `compute_counters`, the test, and `render_markdown`. Outcome enum (`fixed`/`no-op`/`gate-failed`/`checker-rejected`) consistent across module, test, playbook, CLI choices. Env var names — `GUARDIAN_LOOP_HOME` (now used by `run_gate.sh` too, renamed from the stray `GUARDIAN_LOOP_REPO`), `GUARDIAN_PRIMARY_REPO`, `CLAUDE_LOOP_MODEL`, `CLAUDE_BIN`, `LOOP_MAX_BUDGET_USD`, `LOOP_MAX_SECONDS`, `GUARDIAN_BASE`, `GUARDIAN_API_KEY`, `GUARDIAN_AGENT_LOCAL_PORT`, `LOOP_USE_TUNNEL`, `DRY_RUN` — consistent across `loop.env.example`, `guardian_loop.sh`, `run_gate.sh`, the plist, and the runbook (the wrapper now reads `loop.env` from a fixed `$RESOLVED/scripts/loop/loop.env` path, so the old `GUARDIAN_LOOP_ENV` override is gone). Paths (`~/guardian-loop` = `/Users/ayman/guardian-loop`, `.guardian-loop/logs/`, `scripts/loop/loop.env`) consistent throughout; no remaining `/home/ayman`, `systemd`, `.timer`, `.service`, or `GUARDIAN_LOOP_REPO` references; the "VM clone"/"on the VM" artifacts in Tasks 3/4 were corrected to "the loop clone". ✓

**4. Adversarial review (4 lenses) folded in.** A maker/checker review (macOS/launchd, security blast-radius, unattended reliability, consistency) ran against this plan + the spec + `guardian_tunnels.sh`, with findings machine-verified on this Mac. Resolved:
- **BLOCKER — pytest missing:** `pytest` is in no `requirements.txt`; bootstrap now installs `pytest pytest-asyncio` (Task 4). Without this the gate's pytest steps failed every cycle on the fresh clone (masked on the dev machine's existing `.venv`).
- **BLOCKER — deny-list-of-one guard:** the wrapper now does a positive-identity check (origin = `kite-production/guardian`, basename `guardian-loop`, `IS_LOOP_CLONE` sentinel) with guard inputs pinned BEFORE sourcing `loop.env` (Task 5).
- **BLOCKER — `claude` keychain auth fragility:** auth flipped to recommend `ANTHROPIC_API_KEY` for unattended runs; Task 9 Step 8 probes headless auth under a launchd-like env (Tasks 5/8/9 + runbook).
- **MAJOR — `gcloud` off launchd PATH** (tunnel silently dead): added `~/google-cloud-sdk/bin` to the plist PATH + a PATH-mirroring check (Tasks 7/9).
- **MAJOR — no deterministic secret-scan** before an auto-push: added as gate step 0/7 (Task 3).
- **MAJOR — `--dangerously-skip-permissions` blast radius understated:** security posture now states cwd-pinning is NOT containment.
- **MAJOR — launchd can't open the log redirect on a fresh clone:** `loop_bootstrap.sh` now creates `.guardian-loop/logs/` before the agent loads (Tasks 4/8/9).
- **MAJOR — no cost/wall-clock ceiling:** added `--max-budget-usd` + a watchdog (Tasks 5/7).
- **MAJOR — stale-deps drift / `.env.vm` cp failure / fetch-on-stale-ref:** dep-freshness hash-check + tolerant `.env.vm` copy + `git fetch`-guarded reset (Tasks 5/9).
- **MINOR — folded the two-push-per-cycle into one atomic commit** (Task 6); added a single-flight lock + tunnel reachability probe (Task 5); corrected the missed-run-only-on-sleep wording (Task 7) and the `jsonschema`-vs-`yaml` bootstrap comment (Task 4).
- **CONFIRMED SAFE (no change needed):** `git clean -fd` (no `-x`) preserves `.venv`/`node_modules`/logs (all gitignored); macOS bash 3.2 + the launchctl `bootstrap`/`bootout`/`kickstart`/`print` forms are correct.
