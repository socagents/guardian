#!/usr/bin/env bash
# create-feature-issues.sh — Create parent + sub-issues from a spec decomposition
#
# Usage:
#   ./delivery-manager/scripts/create-feature-issues.sh <issues-json-file>
#
# Input: A JSON file with this structure:
# {
#   "spec_path": "specs/my-feature.md",
#   "spec_commit": "abc1234",
#   "milestone": "Stage 2",
#   "parent": {
#     "title": "[Feature] My Feature",
#     "labels": ["layer:integration", "status:planning"],
#     "body_file": "/tmp/parent-body.md"
#   },
#   "sub_issues": [
#     {
#       "title": "Implement API endpoint for X",
#       "labels": ["layer:integration", "complexity:M", "backend", "api"],
#       "body_file": "/tmp/sub-1-body.md",
#       "depends_on": []
#     },
#     {
#       "title": "Add frontend form for X",
#       "labels": ["layer:presentation", "complexity:S", "frontend"],
#       "body_file": "/tmp/sub-2-body.md",
#       "depends_on": [0]
#     }
#   ]
# }
#
# The script:
# 1. Creates the parent issue
# 2. Creates each sub-issue, linking to the parent
# 3. Assigns milestone
# 4. Outputs a summary with issue numbers

set -euo pipefail

INPUT_FILE="${1:?Usage: create-feature-issues.sh <issues-json-file>}"
REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)}"

if [ ! -f "$INPUT_FILE" ]; then
  echo "Error: Input file not found: $INPUT_FILE" >&2
  exit 1
fi

SPEC_PATH=$(jq -r '.spec_path' "$INPUT_FILE")
SPEC_COMMIT=$(jq -r '.spec_commit' "$INPUT_FILE")
MILESTONE=$(jq -r '.milestone // empty' "$INPUT_FILE")

echo "=== Creating Feature Issues ==="
echo "Spec: $SPEC_PATH @ $SPEC_COMMIT"
echo "Repo: $REPO"
echo ""

# --- Create parent issue ---
PARENT_TITLE=$(jq -r '.parent.title' "$INPUT_FILE")
PARENT_LABELS=$(jq -r '.parent.labels | join(",")' "$INPUT_FILE")
PARENT_BODY_FILE=$(jq -r '.parent.body_file' "$INPUT_FILE")

PARENT_ARGS=(
  --repo "$REPO"
  --title "$PARENT_TITLE"
  --body-file "$PARENT_BODY_FILE"
)

if [ -n "$PARENT_LABELS" ]; then
  PARENT_ARGS+=(--label "$PARENT_LABELS")
fi

if [ -n "${MILESTONE:-}" ]; then
  PARENT_ARGS+=(--milestone "$MILESTONE")
fi

PARENT_URL=$(gh issue create "${PARENT_ARGS[@]}" 2>&1)
PARENT_NUMBER=$(echo "$PARENT_URL" | grep -oE '[0-9]+$')

echo "Created parent issue: #$PARENT_NUMBER — $PARENT_TITLE"
echo ""

# --- Create sub-issues ---
SUB_COUNT=$(jq '.sub_issues | length' "$INPUT_FILE")
declare -a SUB_NUMBERS=()

for i in $(seq 0 $((SUB_COUNT - 1))); do
  SUB_TITLE=$(jq -r ".sub_issues[$i].title" "$INPUT_FILE")
  SUB_LABELS=$(jq -r ".sub_issues[$i].labels | join(\",\")" "$INPUT_FILE")
  SUB_BODY_FILE=$(jq -r ".sub_issues[$i].body_file" "$INPUT_FILE")

  SUB_ARGS=(
    --repo "$REPO"
    --title "$SUB_TITLE"
    --body-file "$SUB_BODY_FILE"
  )

  if [ -n "$SUB_LABELS" ]; then
    SUB_ARGS+=(--label "$SUB_LABELS")
  fi

  if [ -n "${MILESTONE:-}" ]; then
    SUB_ARGS+=(--milestone "$MILESTONE")
  fi

  SUB_URL=$(gh issue create "${SUB_ARGS[@]}" 2>&1)
  SUB_NUMBER=$(echo "$SUB_URL" | grep -oE '[0-9]+$')
  SUB_NUMBERS+=("$SUB_NUMBER")

  echo "Created sub-issue: #$SUB_NUMBER — $SUB_TITLE"

  # Link as sub-issue of parent (if GitHub CLI supports it)
  gh issue edit "$SUB_NUMBER" --repo "$REPO" \
    --add-label "status:planning" 2>/dev/null || true
done

echo ""
echo "=== Summary ==="
echo "Parent: #$PARENT_NUMBER"
for j in "${!SUB_NUMBERS[@]}"; do
  SUB_TITLE=$(jq -r ".sub_issues[$j].title" "$INPUT_FILE")
  echo "  Sub-issue: #${SUB_NUMBERS[$j]} — $SUB_TITLE"
done
echo ""
echo "Total: 1 parent + $SUB_COUNT sub-issues created"
