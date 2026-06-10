#!/usr/bin/env bash
# link-dependencies.sh — Set up issue dependency relationships
#
# Usage:
#   ./delivery-manager/scripts/link-dependencies.sh <deps-json-file>
#
# Input: A JSON file with this structure:
# [
#   { "issue": 20, "depends_on": [18, 19] },
#   { "issue": 22, "depends_on": [20] }
# ]
#
# This script:
# 1. For each issue, adds a comment listing its dependencies
# 2. Adds the "blocked" label if an issue has unresolved dependencies
# 3. Outputs a dependency graph summary
#
# Note: GitHub does not have native issue dependencies (outside Projects).
# This script uses conventions (comments + labels) to express dependencies.

set -euo pipefail

INPUT_FILE="${1:?Usage: link-dependencies.sh <deps-json-file>}"
REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)}"

if [ ! -f "$INPUT_FILE" ]; then
  echo "Error: Input file not found: $INPUT_FILE" >&2
  exit 1
fi

echo "=== Linking Issue Dependencies ==="
echo "Repo: $REPO"
echo ""

DEP_COUNT=$(jq 'length' "$INPUT_FILE")

for i in $(seq 0 $((DEP_COUNT - 1))); do
  ISSUE=$(jq -r ".[$i].issue" "$INPUT_FILE")
  DEPS=$(jq -r ".[$i].depends_on | map(\"#\" + tostring) | join(\", \")" "$INPUT_FILE")
  DEP_COUNT_FOR_ISSUE=$(jq ".[$i].depends_on | length" "$INPUT_FILE")

  if [ "$DEP_COUNT_FOR_ISSUE" -eq 0 ]; then
    echo "Issue #$ISSUE: no dependencies"
    continue
  fi

  # Check which dependencies are still open
  OPEN_DEPS=""
  for dep_num in $(jq -r ".[$i].depends_on[]" "$INPUT_FILE"); do
    DEP_STATE=$(gh issue view "$dep_num" --repo "$REPO" --json state -q .state 2>/dev/null || echo "UNKNOWN")
    if [ "$DEP_STATE" = "OPEN" ]; then
      OPEN_DEPS="${OPEN_DEPS} #${dep_num}"
    fi
  done

  # Add dependency comment
  COMMENT_BODY="**Dependencies:** This issue depends on ${DEPS}.

_Added by Delivery Manager._"

  gh issue comment "$ISSUE" --repo "$REPO" -F - <<EOF
$COMMENT_BODY
EOF

  echo "Issue #$ISSUE: depends on $DEPS"

  # Add blocked label if there are open dependencies
  if [ -n "${OPEN_DEPS}" ]; then
    gh issue edit "$ISSUE" --repo "$REPO" --add-label "blocked" 2>/dev/null || true
    echo "  → Marked as blocked (open deps:${OPEN_DEPS})"
  fi
done

echo ""
echo "=== Dependency Graph ==="
jq -r '.[] | "  #\(.issue) → depends on \(.depends_on | map("#" + tostring) | join(", "))"' "$INPUT_FILE"
echo ""
echo "Done: $DEP_COUNT dependency relationships processed."
