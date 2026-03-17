#!/usr/bin/env bash
# =============================================================================
# Dream Maker — Repository Initialization
# =============================================================================
#
# Called by the Dream Maker skill to initialize a new project repository
# with all template files, placeholders replaced.
#
# Usage:
#   bash init-repo.sh \
#     --project-name "My Project" \
#     --github-org "my-org" \
#     --github-repo "my-project" \
#     --runner-label "my-runner" \
#     --runner-user "ubuntu" \
#     --target-dir "/path/to/repo" \
#     [--slack-workspace "my-workspace"] \
#     [--slack-build-channel "C0XXX"] \
#     [--slack-issues-channel "C0YYY"] \
#     [--slack-tokens-channel "C0ZZZ"] \
#     [--tech-stack "go,python,typescript"]
#     [--limit-coding 100]
#     [--limit-review 100]
#     [--limit-planning 20]
#     [--limit-validation 50]
#     [--limit-deploy 100]
#
# =============================================================================
set -euo pipefail

# --- Parse arguments ---------------------------------------------------------

PROJECT_NAME=""
GITHUB_ORG=""
GITHUB_REPO=""
RUNNER_LABEL="dream-maker"
RUNNER_USER="ubuntu"
TARGET_DIR=""
SLACK_WORKSPACE="your-workspace"
SLACK_BUILD_CHANNEL="CHANGEME"
SLACK_ISSUES_CHANNEL="CHANGEME"
SLACK_TOKENS_CHANNEL="CHANGEME"
TECH_STACK="go,python,typescript"
LIMIT_CODING="100"
LIMIT_REVIEW="100"
LIMIT_PLANNING="20"
LIMIT_VALIDATION="50"
LIMIT_DEPLOY="100"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-name) PROJECT_NAME="$2"; shift 2 ;;
    --github-org) GITHUB_ORG="$2"; shift 2 ;;
    --github-repo) GITHUB_REPO="$2"; shift 2 ;;
    --runner-label) RUNNER_LABEL="$2"; shift 2 ;;
    --runner-user) RUNNER_USER="$2"; shift 2 ;;
    --target-dir) TARGET_DIR="$2"; shift 2 ;;
    --slack-workspace) SLACK_WORKSPACE="$2"; shift 2 ;;
    --slack-build-channel) SLACK_BUILD_CHANNEL="$2"; shift 2 ;;
    --slack-issues-channel) SLACK_ISSUES_CHANNEL="$2"; shift 2 ;;
    --slack-tokens-channel) SLACK_TOKENS_CHANNEL="$2"; shift 2 ;;
    --tech-stack) TECH_STACK="$2"; shift 2 ;;
    --limit-coding) LIMIT_CODING="$2"; shift 2 ;;
    --limit-review) LIMIT_REVIEW="$2"; shift 2 ;;
    --limit-planning) LIMIT_PLANNING="$2"; shift 2 ;;
    --limit-validation) LIMIT_VALIDATION="$2"; shift 2 ;;
    --limit-deploy) LIMIT_DEPLOY="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# --- Validate ----------------------------------------------------------------

if [[ -z "$PROJECT_NAME" || -z "$GITHUB_ORG" || -z "$GITHUB_REPO" || -z "$TARGET_DIR" ]]; then
  echo "ERROR: --project-name, --github-org, --github-repo, and --target-dir are required"
  exit 1
fi

# --- Locate template ---------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(realpath "$SCRIPT_DIR/../template")"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "ERROR: Template directory not found at $TEMPLATE_DIR"
  exit 1
fi

echo "Template source: $TEMPLATE_DIR"
echo "Target: $TARGET_DIR"

# --- Copy template files -----------------------------------------------------

mkdir -p "$TARGET_DIR"

# Copy visible files and directories
cp -r "$TEMPLATE_DIR"/* "$TARGET_DIR/" 2>/dev/null || true

# Copy hidden files/dirs explicitly
for hidden in .github .claude .gitignore; do
  if [[ -e "$TEMPLATE_DIR/$hidden" ]]; then
    cp -r "$TEMPLATE_DIR/$hidden" "$TARGET_DIR/"
  fi
done

echo "Template files copied"

# --- Replace placeholders ----------------------------------------------------

cd "$TARGET_DIR"

find . -type f \( -name "*.yml" -o -name "*.md" -o -name "*.sh" \
  -o -name "*.json" -o -name "*.toml" -o -name "*.py" \) \
  -not -path './.git/*' \
  -exec sed -i '' \
    -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
    -e "s|{{GITHUB_ORG}}|${GITHUB_ORG}|g" \
    -e "s|{{GITHUB_REPO}}|${GITHUB_REPO}|g" \
    -e "s|{{RUNNER_LABEL}}|${RUNNER_LABEL}|g" \
    -e "s|{{RUNNER_USER}}|${RUNNER_USER}|g" \
    -e "s|{{SLACK_WORKSPACE}}|${SLACK_WORKSPACE}|g" \
    -e "s|{{SLACK_BUILD_CHANNEL_ID}}|${SLACK_BUILD_CHANNEL}|g" \
    -e "s|{{SLACK_ISSUES_CHANNEL_ID}}|${SLACK_ISSUES_CHANNEL}|g" \
    -e "s|{{SLACK_TOKENS_CHANNEL_ID}}|${SLACK_TOKENS_CHANNEL}|g" \
    -e "s|{{LIMIT_CODING}}|${LIMIT_CODING}|g" \
    -e "s|{{LIMIT_REVIEW}}|${LIMIT_REVIEW}|g" \
    -e "s|{{LIMIT_PLANNING}}|${LIMIT_PLANNING}|g" \
    -e "s|{{LIMIT_VALIDATION}}|${LIMIT_VALIDATION}|g" \
    -e "s|{{LIMIT_DEPLOY}}|${LIMIT_DEPLOY}|g" \
    {} +

echo "Placeholders replaced"

# --- Remove unused tech stack rules -----------------------------------------

IFS=',' read -ra STACKS <<< "$TECH_STACK"

has_stack() {
  local needle="$1"
  for s in "${STACKS[@]}"; do
    [[ "$(echo "$s" | xargs)" == "$needle" ]] && return 0
  done
  return 1
}

if ! has_stack "go"; then
  rm -f .claude/rules/go-services.md
  rm -f coding-agent/hooks/post-edit-go-build.sh
  echo "Removed Go rules (not in tech stack)"
fi

if ! has_stack "python"; then
  rm -f .claude/rules/python-services.md
  echo "Removed Python rules (not in tech stack)"
fi

if ! has_stack "typescript"; then
  rm -f .claude/rules/nextjs-ui.md
  rm -f coding-agent/hooks/post-edit-typecheck.sh
  echo "Removed TypeScript rules (not in tech stack)"
fi

if ! has_stack "proto"; then
  rm -f .claude/rules/proto-contracts.md
  echo "Removed Proto rules (not in tech stack)"
fi

# --- Summary -----------------------------------------------------------------

FILE_COUNT=$(find . -type f -not -path './.git/*' | wc -l | tr -d ' ')
echo ""
echo "============================================"
echo "  Repository initialized: $PROJECT_NAME"
echo "  Files: $FILE_COUNT"
echo "  Tech stack: $TECH_STACK"
echo "============================================"
