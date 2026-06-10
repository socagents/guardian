#!/usr/bin/env bash
# collect-test-results.sh — Run project checks and capture results
# Usage: ./coding-agent/scripts/collect-test-results.sh
#
# Detects the project's test/build/lint tools and runs them,
# capturing pass/fail status for each. Outputs a Markdown summary.

set -uo pipefail

RESULTS_FILE="${1:-/tmp/test-results.md}"

echo "## Tests and Checks" > "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

run_check() {
  local name="$1"
  shift
  local cmd="$*"

  echo "Running: ${name}..."
  if eval "$cmd" > /tmp/check-output.txt 2>&1; then
    echo "- [x] **${name}**: passed" >> "$RESULTS_FILE"
  else
    echo "- [ ] **${name}**: FAILED" >> "$RESULTS_FILE"
    echo '  ```' >> "$RESULTS_FILE"
    tail -20 /tmp/check-output.txt >> "$RESULTS_FILE"
    echo '  ```' >> "$RESULTS_FILE"
  fi
}

# Detect and run build
if [ -f "Makefile" ] && grep -q "^build:" Makefile; then
  run_check "Build" "make build"
elif [ -f "package.json" ] && grep -q '"build"' package.json; then
  run_check "Build" "npm run build"
elif [ -f "Cargo.toml" ]; then
  run_check "Build" "cargo build"
elif ls *.go > /dev/null 2>&1 || [ -f "go.mod" ]; then
  run_check "Build" "go build ./..."
fi

# Detect and run lint
if [ -f "package.json" ] && grep -q '"lint"' package.json; then
  run_check "Lint" "npm run lint"
elif [ -f "Makefile" ] && grep -q "^lint:" Makefile; then
  run_check "Lint" "make lint"
elif command -v golangci-lint > /dev/null 2>&1; then
  run_check "Lint" "golangci-lint run ./..."
elif [ -f "pyproject.toml" ] || [ -f "setup.cfg" ]; then
  if command -v ruff > /dev/null 2>&1; then
    run_check "Lint" "ruff check ."
  fi
fi

# Detect and run type checks
if [ -f "tsconfig.json" ]; then
  run_check "Type Check" "npx tsc --noEmit"
elif [ -f "pyproject.toml" ] && command -v mypy > /dev/null 2>&1; then
  run_check "Type Check" "mypy ."
fi

# Detect and run tests
if [ -f "package.json" ] && grep -q '"test"' package.json; then
  run_check "Tests" "npm test"
elif [ -f "Makefile" ] && grep -q "^test:" Makefile; then
  run_check "Tests" "make test"
elif [ -f "Cargo.toml" ]; then
  run_check "Tests" "cargo test"
elif ls *.go > /dev/null 2>&1 || [ -f "go.mod" ]; then
  run_check "Tests" "go test ./..."
elif [ -f "pyproject.toml" ] || [ -f "pytest.ini" ]; then
  run_check "Tests" "pytest"
fi

echo "" >> "$RESULTS_FILE"
echo "---" >> "$RESULTS_FILE"
echo "_Collected at $(date -u '+%Y-%m-%dT%H:%M:%SZ')_" >> "$RESULTS_FILE"

cat "$RESULTS_FILE"
