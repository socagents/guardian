#!/usr/bin/env bash
#
# sync-labels.sh — idempotently sync GitHub repo labels from
# .github/labels.json. Run this whenever .github/labels.json changes,
# or when bootstrapping a fresh clone of the repo into a new org/repo.
#
# v0.5.17+ — the spec-driven workflow defines the label taxonomy in
# .github/labels.json (committed; the canonical source). This script
# applies that taxonomy to the GitHub repo via `gh label create` /
# `gh label edit`. Existing labels not in the config are left alone
# (no delete) — operators can prune obsolete labels by hand.
#
# Usage:
#   .github/scripts/sync-labels.sh                # sync to current repo
#   .github/scripts/sync-labels.sh kite-prod/guardian   # sync to specific repo
#
# Requirements: gh CLI authenticated with `gh auth login`. Operator
# PAT with `repo` scope works; customer PAT with only `read:packages`
# does NOT (this script writes labels — write access required).

set -euo pipefail

REPO="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABELS_JSON="${SCRIPT_DIR}/../labels.json"

if [[ ! -f "$LABELS_JSON" ]]; then
  echo "ERROR: $LABELS_JSON not found" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI not installed. https://cli.github.com/" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not installed (used for JSON parsing)" >&2
  exit 1
fi

REPO_FLAG=()
if [[ -n "$REPO" ]]; then
  REPO_FLAG=(--repo "$REPO")
fi

echo "Syncing labels to ${REPO:-current repo}…"

# Parse labels.json — entries that are pure _comment objects (no
# "name" key) are documentation-only and skipped. Each real entry
# has name + color + description.
python3 -c '
import json, sys
data = json.load(open(sys.argv[1]))
for entry in data:
    if "name" not in entry:
        continue
    name = entry["name"]
    color = entry["color"]
    desc = entry["description"]
    print(name + "\t" + color + "\t" + desc)
' "$LABELS_JSON" | while IFS=$'\t' read -r name color desc; do
  # `gh label create --force` updates if it exists, creates if it doesn't.
  # Use ${REPO_FLAG[@]+"${REPO_FLAG[@]}"} to handle the empty-array case
  # safely under `set -u` — bare ${REPO_FLAG[@]} on an empty declared
  # array still triggers "unbound variable" on macOS bash 3.x.
  if gh label create "$name" \
       --color "$color" \
       --description "$desc" \
       --force \
       ${REPO_FLAG[@]+"${REPO_FLAG[@]}"} >/dev/null 2>&1; then
    printf "  ✓ %-30s #%s\n" "$name" "$color"
  else
    printf "  ✗ %-30s FAILED\n" "$name" >&2
  fi
done

echo ""
echo "Done. Run \`gh label list\` to verify."
