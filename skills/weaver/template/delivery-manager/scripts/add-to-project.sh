#!/usr/bin/env bash
# add-to-project.sh — Add an issue to a GitHub Project and populate fields
#
# Usage:
#   ./delivery-manager/scripts/add-to-project.sh <issue-number> [options]
#
# Options:
#   --project <number>     Project number (default: 1)
#   --owner <login>        Project owner (default: from GITHUB_REPOSITORY_OWNER or gh)
#   --status <value>       Status field value (default: Todo)
#   --priority <value>     Priority field value (e.g., P0, P1, P2)
#   --area <value>         Layer/Area field value
#   --complexity <value>   Complexity field value (S, M, L, XL)
#   --stage <value>        Build Stage field value
#   --spec <path>          Spec file path (text field)
#   --spec-commit <sha>    Spec commit SHA (text field)
#
# Requires: gh CLI with project permissions

set -euo pipefail

ISSUE_NUMBER=""
PROJECT_NUMBER="1"
OWNER=""
STATUS="Todo"
PRIORITY=""
AREA=""
COMPLEXITY=""
STAGE=""
SPEC=""
SPEC_COMMIT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT_NUMBER="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --status) STATUS="$2"; shift 2 ;;
    --priority) PRIORITY="$2"; shift 2 ;;
    --area) AREA="$2"; shift 2 ;;
    --complexity) COMPLEXITY="$2"; shift 2 ;;
    --stage) STAGE="$2"; shift 2 ;;
    --spec) SPEC="$2"; shift 2 ;;
    --spec-commit) SPEC_COMMIT="$2"; shift 2 ;;
    *)
      if [ -z "$ISSUE_NUMBER" ]; then
        ISSUE_NUMBER="$1"
      else
        echo "Unknown argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$ISSUE_NUMBER" ]; then
  echo "Usage: add-to-project.sh <issue-number> [options]" >&2
  exit 1
fi

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)}"
if [ -z "$OWNER" ]; then
  OWNER="${GITHUB_REPOSITORY_OWNER:-$(echo "$REPO" | cut -d/ -f1)}"
fi

echo "Adding issue #$ISSUE_NUMBER to project $PROJECT_NUMBER (owner: $OWNER)..."

# Get issue node ID
ISSUE_NODE_ID=$(gh api "repos/${REPO}/issues/${ISSUE_NUMBER}" --jq .node_id)

if [ -z "$ISSUE_NODE_ID" ]; then
  echo "Error: Could not find issue #$ISSUE_NUMBER" >&2
  exit 1
fi

# Add to project
ITEM_ID=$(gh project item-add "$PROJECT_NUMBER" \
  --owner "$OWNER" \
  --url "https://github.com/${REPO}/issues/${ISSUE_NUMBER}" \
  --format json 2>&1 | jq -r '.id')

if [ -z "$ITEM_ID" ] || [ "$ITEM_ID" = "null" ]; then
  echo "Error: Failed to add issue to project" >&2
  exit 1
fi

echo "Added as project item: $ITEM_ID"

# Helper function to set a single-select field
set_select_field() {
  local field_name="$1"
  local value="$2"

  if [ -z "$value" ]; then return; fi

  # Get field ID and option ID
  local field_data
  field_data=$(gh project field-list "$PROJECT_NUMBER" \
    --owner "$OWNER" \
    --format json | jq -r --arg name "$field_name" '
    .fields[] | select(.name == $name)
  ')

  local field_id
  field_id=$(echo "$field_data" | jq -r '.id')

  local option_id
  option_id=$(echo "$field_data" | jq -r --arg val "$value" '
    .options[]? | select(.name == $val) | .id
  ')

  if [ -n "$field_id" ] && [ -n "$option_id" ] && [ "$option_id" != "null" ]; then
    gh project item-edit \
      --project-id "$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json | jq -r '.id')" \
      --id "$ITEM_ID" \
      --field-id "$field_id" \
      --single-select-option-id "$option_id" 2>/dev/null && \
      echo "  Set $field_name = $value" || \
      echo "  Warning: Could not set $field_name = $value"
  else
    echo "  Warning: Field '$field_name' or value '$value' not found"
  fi
}

# Helper function to set a text field
set_text_field() {
  local field_name="$1"
  local value="$2"

  if [ -z "$value" ]; then return; fi

  local field_id
  field_id=$(gh project field-list "$PROJECT_NUMBER" \
    --owner "$OWNER" \
    --format json | jq -r --arg name "$field_name" '
    .fields[] | select(.name == $name) | .id
  ')

  if [ -n "$field_id" ] && [ "$field_id" != "null" ]; then
    gh project item-edit \
      --project-id "$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json | jq -r '.id')" \
      --id "$ITEM_ID" \
      --field-id "$field_id" \
      --text "$value" 2>/dev/null && \
      echo "  Set $field_name = $value" || \
      echo "  Warning: Could not set $field_name = $value"
  else
    echo "  Warning: Text field '$field_name' not found"
  fi
}

# Populate fields
set_select_field "Status" "$STATUS"
[ -n "$PRIORITY" ] && set_select_field "Priority" "$PRIORITY"
[ -n "$AREA" ] && set_select_field "Layer" "$AREA"
[ -n "$COMPLEXITY" ] && set_select_field "Complexity" "$COMPLEXITY"
[ -n "$STAGE" ] && set_select_field "Build Stage" "$STAGE"
[ -n "$SPEC" ] && set_text_field "Spec" "$SPEC"
[ -n "$SPEC_COMMIT" ] && set_text_field "Spec Commit" "$SPEC_COMMIT"

echo ""
echo "Done: Issue #$ISSUE_NUMBER added to project with fields populated."
