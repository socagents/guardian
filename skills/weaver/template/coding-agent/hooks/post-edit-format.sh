#!/usr/bin/env bash
# PostToolUse hook: Auto-format files after Edit/Write operations.
# Runs the appropriate formatter based on file extension.
# Exit 0 always — formatting is silent, no feedback to Claude needed.
set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if no file path (shouldn't happen for Edit/Write)
if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"

case "$EXT" in
  go)
    gofmt -w "$FILE_PATH" 2>/dev/null
    ;;
  py)
    if command -v ruff &>/dev/null; then
      ruff format "$FILE_PATH" 2>/dev/null
    elif [ -f "$HOME/.local/bin/ruff" ]; then
      "$HOME/.local/bin/ruff" format "$FILE_PATH" 2>/dev/null
    fi
    ;;
  ts|tsx|js|jsx|json)
    if command -v npx &>/dev/null; then
      npx --yes prettier --write "$FILE_PATH" 2>/dev/null
    fi
    ;;
  proto)
    if command -v buf &>/dev/null; then
      buf format -w "$FILE_PATH" 2>/dev/null
    fi
    ;;
esac

exit 0
