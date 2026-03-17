#!/usr/bin/env bash
# generate-pr-summary.sh — Generate a PR description from issue + changes
# Usage: ./coding-agent/scripts/generate-pr-summary.sh <issue-number> [base-ref]
#
# Reads the GitHub Issue body and combines it with the file change summary
# to produce a structured PR description. Outputs to stdout.

set -euo pipefail

ISSUE_NUMBER="${1:?Usage: generate-pr-summary.sh <issue-number> [base-ref]}"
BASE_REF="${2:-main}"
REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo 'unknown/repo')}"

# Fetch issue metadata
ISSUE_TITLE=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json title -q .title 2>/dev/null || echo "Issue #${ISSUE_NUMBER}")
ISSUE_BODY=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json body -q .body 2>/dev/null || echo "_Could not fetch issue body_")

# Get file change summary
CHANGED_FILES=$(git diff --name-status "${BASE_REF}" -- . 2>/dev/null || echo "Unable to compute diff")
DIFF_STAT=$(git diff --stat "${BASE_REF}" -- . 2>/dev/null || echo "Unable to compute stats")

cat <<EOF
## Summary

Implements #${ISSUE_NUMBER}: ${ISSUE_TITLE}

## Changes

${DIFF_STAT}

### Files

$(echo "$CHANGED_FILES" | while IFS=$'\t' read -r status file; do
  case "$status" in
    A) echo "- **Added** \`${file}\`" ;;
    M) echo "- **Modified** \`${file}\`" ;;
    D) echo "- **Deleted** \`${file}\`" ;;
    R*) echo "- **Renamed** \`${file}\`" ;;
    *) echo "- \`${file}\` (${status})" ;;
  esac
done)

## Issue Reference

Closes #${ISSUE_NUMBER}

## Checklist

- [ ] All acceptance criteria from the issue are satisfied
- [ ] Tests added/updated and passing
- [ ] Build and lint checks pass
- [ ] No temporary or debug files included
EOF
