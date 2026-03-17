#!/usr/bin/env bash
# PostToolUse hook: Run type checker after Edit/Write on typed files.
# Feeds errors back to Claude as additionalContext so it can fix call sites.
set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"
ERRORS=""

case "$EXT" in
  go)
    # Find the module root (directory with go.mod)
    DIR=$(dirname "$FILE_PATH")
    while [ "$DIR" != "/" ] && [ ! -f "$DIR/go.mod" ]; do
      DIR=$(dirname "$DIR")
    done
    if [ -f "$DIR/go.mod" ]; then
      PKG_DIR=$(dirname "$FILE_PATH")
      ERRORS=$(cd "$DIR" && go vet "./$(realpath --relative-to="$DIR" "$PKG_DIR")/..." 2>&1) || true
    fi
    ;;
  py)
    MYPY=""
    if command -v mypy &>/dev/null; then
      MYPY="mypy"
    elif [ -f "$HOME/.local/bin/mypy" ]; then
      MYPY="$HOME/.local/bin/mypy"
    fi
    if [ -n "$MYPY" ]; then
      ERRORS=$($MYPY "$FILE_PATH" --no-error-summary --no-color 2>&1) || true
    fi
    ;;
  ts|tsx)
    # Find the tsconfig root
    DIR=$(dirname "$FILE_PATH")
    while [ "$DIR" != "/" ] && [ ! -f "$DIR/tsconfig.json" ]; do
      DIR=$(dirname "$DIR")
    done
    if [ -f "$DIR/tsconfig.json" ]; then
      ERRORS=$(cd "$DIR" && npx tsc --noEmit 2>&1) || true
    fi
    ;;
esac

# If errors found, provide feedback to Claude
if [ -n "$ERRORS" ] && [ "$ERRORS" != "" ]; then
  # Filter out empty lines and noise
  CLEAN_ERRORS=$(echo "$ERRORS" | grep -v '^$' | head -30)
  if [ -n "$CLEAN_ERRORS" ]; then
    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Type/compilation errors detected after editing ${FILE_PATH}. Please fix these:\n${CLEAN_ERRORS}"
  }
}
EOF
  fi
fi

exit 0
