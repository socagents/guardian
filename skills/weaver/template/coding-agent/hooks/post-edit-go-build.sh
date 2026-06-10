#!/usr/bin/env bash
# PostToolUse hook: Run go build after editing Go files.
# Catches compilation errors (undefined refs, import issues) immediately.
set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"

# Only run for Go files
if [ "$EXT" != "go" ]; then
  exit 0
fi

# Find the module root
DIR=$(dirname "$FILE_PATH")
while [ "$DIR" != "/" ] && [ ! -f "$DIR/go.mod" ]; do
  DIR=$(dirname "$DIR")
done

if [ ! -f "$DIR/go.mod" ]; then
  exit 0
fi

# Run go build for the package containing the edited file
PKG_DIR=$(dirname "$FILE_PATH")
REL_PKG=$(realpath --relative-to="$DIR" "$PKG_DIR" 2>/dev/null) || REL_PKG="."
ERRORS=$(cd "$DIR" && go build "./${REL_PKG}/..." 2>&1) || true

# Clean up any binaries produced by go build
BINARY_NAME=$(basename "$DIR")
[ -f "$DIR/$BINARY_NAME" ] && rm -f "$DIR/$BINARY_NAME"

if [ -n "$ERRORS" ]; then
  CLEAN_ERRORS=$(echo "$ERRORS" | grep -v '^$' | head -20)
  if [ -n "$CLEAN_ERRORS" ]; then
    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Go build errors after editing ${FILE_PATH}. Fix these before continuing:\n${CLEAN_ERRORS}"
  }
}
EOF
  fi
fi

exit 0
