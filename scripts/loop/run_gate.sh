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

# Step 0 — deterministic secret-scan of ADDED diff lines (the real leak vector;
# removed lines are cleanups). This is the loop's hard pre-push guardrail, not the
# LLM checker. grep -q never echoes a match. THIS script is excluded from the scan
# so its own pattern literals can't self-trip when the loop edits the gate.
SECRETS_RE='sk-ant-[A-Za-z0-9_-]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY|ANTHROPIC_API_KEY=[^[:space:]]|GUARDIAN_API_KEY=[^[:space:]]|VM_PASSWORD=[^[:space:]]|XSOAR_KEY=[^[:space:]]|guardian_ak_[A-Za-z0-9]'
log "0/7 secret-scan"
if (cd "$REPO" && { git diff HEAD -- . ':(exclude)scripts/loop/run_gate.sh'; git diff --staged -- . ':(exclude)scripts/loop/run_gate.sh'; }) \
     | grep '^+' | grep -vE '^\+\+\+' \
     | grep -qE "$SECRETS_RE"; then
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
