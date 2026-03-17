#!/usr/bin/env bash
# =============================================================================
# sync-project-status.sh — Keep GitHub Project board in sync with issue labels
# =============================================================================
# Usage:  sync-project-status.sh <issue_number> <target_status>
#
# Maps issue label transitions to project kanban columns:
#   status:ready       → Ready
#   status:in-progress → In progress
#   status:in-review   → In review
#   (issue closed)     → Done
#
# Requires:
#   GH_TOKEN with project write access (PROJECT_PAT)
#   PROJECT_OWNER and PROJECT_NUMBER env vars
# =============================================================================
set -uo pipefail

ISSUE_NUMBER="${1:?Usage: sync-project-status.sh <issue_number> <target_status>}"
TARGET_STATUS="${2:?Usage: sync-project-status.sh <issue_number> <target_status>}"

PROJECT_OWNER="${PROJECT_OWNER:-{{GITHUB_ORG}}}"
PROJECT_NUMBER="${PROJECT_NUMBER:-1}"

# Validate target status
case "$TARGET_STATUS" in
  "Backlog"|"Ready"|"In progress"|"In review"|"Done") ;;
  *) echo "::warning::Unknown project status: $TARGET_STATUS"; exit 0 ;;
esac

echo "Syncing issue #${ISSUE_NUMBER} → project status '${TARGET_STATUS}'"

# Step 1: Find the project item ID for this issue
ITEM_ID=$(gh project item-list "$PROJECT_NUMBER" \
  --owner "$PROJECT_OWNER" \
  --format json \
  --limit 200 \
  2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('items', []):
    content = item.get('content', {})
    if content.get('type') == 'Issue' and content.get('number') == ${ISSUE_NUMBER}:
        print(item['id'])
        break
" 2>/dev/null)

if [ -z "$ITEM_ID" ]; then
  echo "::warning::Issue #${ISSUE_NUMBER} not found in project ${PROJECT_NUMBER}"
  exit 0
fi

echo "Found project item: $ITEM_ID"

# Step 2: Get the Status field ID and option ID
FIELD_INFO=$(gh project field-list "$PROJECT_NUMBER" \
  --owner "$PROJECT_OWNER" \
  --format json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
target = '${TARGET_STATUS}'
for field in data.get('fields', []):
    if field.get('name') == 'Status':
        field_id = field['id']
        for opt in field.get('options', []):
            if opt['name'] == target:
                print(f\"{field_id} {opt['id']}\")
                break
        break
" 2>/dev/null)

FIELD_ID=$(echo "$FIELD_INFO" | awk '{print $1}')
OPTION_ID=$(echo "$FIELD_INFO" | awk '{print $2}')

if [ -z "$FIELD_ID" ] || [ -z "$OPTION_ID" ]; then
  echo "::warning::Could not find Status field or option '${TARGET_STATUS}'"
  exit 0
fi

echo "Status field: $FIELD_ID, option: $OPTION_ID"

# Step 3: Update the project item
gh project item-edit \
  --project-id "$(gh project view "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")" \
  --id "$ITEM_ID" \
  --field-id "$FIELD_ID" \
  --single-select-option-id "$OPTION_ID" \
  2>/dev/null

if [ $? -eq 0 ]; then
  echo "✓ Issue #${ISSUE_NUMBER} moved to '${TARGET_STATUS}'"
else
  echo "::warning::Failed to update project status for #${ISSUE_NUMBER}"
fi
