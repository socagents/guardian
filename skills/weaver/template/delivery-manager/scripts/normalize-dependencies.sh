#!/usr/bin/env bash
# normalize-dependencies.sh — Auto-fix non-canonical dependency formats in issue bodies
#
# Usage: normalize-dependencies.sh <issue-number> [<issue-number> ...]
# Or:    echo "42 43 44" | xargs bash normalize-dependencies.sh
#
# Scans each issue body for non-canonical dependency phrases and replaces
# them with the canonical "Depends on: #N" format that the dispatch workflow
# recognizes.

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q '.nameWithOwner')}"
NORMALIZED_COUNT=0

if [ $# -eq 0 ]; then
  echo "Usage: normalize-dependencies.sh <issue-number> [<issue-number> ...]"
  exit 0
fi

echo "Normalizing dependencies for $# issue(s)..."

for ISSUE_NUM in "$@"; do
  # Strip any leading # character
  ISSUE_NUM="${ISSUE_NUM#\#}"

  BODY=$(gh issue view "$ISSUE_NUM" --repo "$REPO" --json body -q '.body' 2>/dev/null || true)
  if [ -z "$BODY" ]; then
    echo "  ⚠️  Could not read issue #${ISSUE_NUM} — skipping"
    continue
  fi

  ORIGINAL_BODY="$BODY"

  # Replace non-canonical dependency phrases with "Depends on: #N"
  # Canonical format: "Depends on: #N" (capital D, with colon)
  # Non-canonical formats to fix:
  #   - "requires #N"          → "Depends on: #N"
  #   - "after #N"             → "Depends on: #N"
  #   - "blocked by #N"        → "Depends on: #N"
  #   - "needs #N"             → "Depends on: #N"
  #   - "waiting on #N"        → "Depends on: #N"
  #   - "depends on #N"        → "Depends on: #N" (lowercase, missing colon)
  #   - "Depends on #N"        → "Depends on: #N" (missing colon)
  BODY=$(echo "$BODY" | sed -E '
    s/[Rr]equires (#[0-9])/Depends on: \1/g
    s/[Aa]fter (#[0-9])/Depends on: \1/g
    s/[Bb]locked by (#[0-9])/Depends on: \1/g
    s/[Nn]eeds (#[0-9])/Depends on: \1/g
    s/[Ww]aiting on (#[0-9])/Depends on: \1/g
    s/[Dd]epends on (#[0-9])/Depends on: \1/g
  ')

  if [ "$BODY" = "$ORIGINAL_BODY" ]; then
    echo "  ✅ #${ISSUE_NUM} — no normalization needed"
    continue
  fi

  gh issue edit "$ISSUE_NUM" --repo "$REPO" --body "$BODY"
  NORMALIZED_COUNT=$((NORMALIZED_COUNT + 1))
  echo "  🔧 #${ISSUE_NUM} — dependency format normalized"
done

echo ""
echo "Done. Normalized ${NORMALIZED_COUNT} issue(s)."
