#!/usr/bin/env bash
# summarize-changes.sh — Generate a structured file-change summary
# Usage: ./coding-agent/scripts/summarize-changes.sh [base-ref]
#
# Compares the current working tree against a base ref (default: main)
# and prints a Markdown summary of changed files with stats.

set -euo pipefail

BASE_REF="${1:-main}"

echo "## Files Modified"
echo ""

# Get diff stats
git diff --stat "${BASE_REF}" -- . | while IFS= read -r line; do
  # Skip the summary line (e.g., "5 files changed, 120 insertions(+), 30 deletions(-)")
  if echo "$line" | grep -qE "files? changed"; then
    echo ""
    echo "---"
    echo "$line"
    continue
  fi
  # Format each file line
  echo "- $line"
done

echo ""
echo "## Changed File List"
echo ""

git diff --name-status "${BASE_REF}" -- . | while IFS=$'\t' read -r status file; do
  case "$status" in
    A) label="added" ;;
    M) label="modified" ;;
    D) label="deleted" ;;
    R*) label="renamed" ;;
    *) label="$status" ;;
  esac
  echo "- \`${file}\` (${label})"
done
