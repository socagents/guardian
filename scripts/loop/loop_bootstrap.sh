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
