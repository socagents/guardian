#!/usr/bin/env bash
# =============================================================================
# Dream Maker — Self-Hosted Runner Bootstrap
# =============================================================================
#
# Installs all required tools on a fresh Ubuntu/Debian machine to run the
# Dream Maker agent pipeline as a GitHub Actions self-hosted runner.
#
# Usage:
#   bash setup-runner.sh                    # interactive (prompts for config)
#   bash setup-runner.sh --non-interactive  # uses env vars or defaults
#
# Environment variables (for non-interactive mode):
#   GITHUB_RUNNER_URL    — repo URL (e.g. https://github.com/org/repo)
#   GITHUB_RUNNER_TOKEN  — registration token from GitHub Settings → Actions
#   GITHUB_RUNNER_LABEL  — custom label (default: dream-maker)
#   RUNNER_USER          — user to run as (default: current user)
#   TOKEN_LOG_DIR        — token log base dir (default: ~/dream-maker-logs)
#   DEPLOY_STATE_DIR     — deploy state dir (default: ~/dream-maker-deploy)
#
# =============================================================================
set -euo pipefail

# --- Colors and helpers ------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

check_cmd() {
  if command -v "$1" &>/dev/null; then
    ok "$1 found: $(command -v "$1")"
    return 0
  else
    return 1
  fi
}

# --- Parse arguments ---------------------------------------------------------

NON_INTERACTIVE=false
for arg in "$@"; do
  case "$arg" in
    --non-interactive) NON_INTERACTIVE=true ;;
    --help|-h)
      echo "Usage: bash setup-runner.sh [--non-interactive]"
      echo ""
      echo "Installs all tools needed for the Dream Maker agent pipeline."
      echo "See script header for environment variable documentation."
      exit 0
      ;;
  esac
done

# --- OS check ----------------------------------------------------------------

if [[ ! -f /etc/os-release ]]; then
  fail "This script supports Ubuntu/Debian only. /etc/os-release not found."
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
  warn "Detected OS: $ID. This script is tested on Ubuntu/Debian."
  warn "Proceeding anyway — some commands may fail."
fi

info "OS: $PRETTY_NAME"
info "User: $(whoami)"

# --- Configuration -----------------------------------------------------------

RUNNER_USER="${RUNNER_USER:-$(whoami)}"
RUNNER_HOME="$(eval echo ~"$RUNNER_USER")"
RUNNER_LABEL="${GITHUB_RUNNER_LABEL:-dream-maker}"
TOKEN_LOG_DIR="${TOKEN_LOG_DIR:-$RUNNER_HOME/dream-maker-logs}"
DEPLOY_STATE_DIR="${DEPLOY_STATE_DIR:-$RUNNER_HOME/dream-maker-deploy}"

echo ""
echo "============================================"
echo "  Dream Maker — Runner Bootstrap"
echo "============================================"
echo "  Runner user:    $RUNNER_USER"
echo "  Runner home:    $RUNNER_HOME"
echo "  Runner label:   $RUNNER_LABEL"
echo "  Token logs:     $TOKEN_LOG_DIR"
echo "  Deploy state:   $DEPLOY_STATE_DIR"
echo "============================================"
echo ""

# =============================================================================
# Phase 1: System packages
# =============================================================================

info "Phase 1: Installing system packages..."

sudo apt-get update -qq
sudo apt-get install -y -qq \
  build-essential \
  curl \
  git \
  jq \
  unzip \
  wget \
  ca-certificates \
  gnupg \
  lsb-release \
  software-properties-common \
  python3 \
  python3-pip \
  python3-venv \
  sshpass \
  > /dev/null 2>&1

ok "System packages installed"

# =============================================================================
# Phase 2: Docker
# =============================================================================

info "Phase 2: Installing Docker..."

if check_cmd docker; then
  info "Docker already installed, skipping"
else
  # Add Docker's official GPG key and repository
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin > /dev/null 2>&1

  # Add user to docker group
  sudo usermod -aG docker "$RUNNER_USER"
  ok "Docker installed (log out and back in for group membership)"
fi

# Verify
docker --version
docker compose version

# =============================================================================
# Phase 3: Node.js (v22 LTS)
# =============================================================================

info "Phase 3: Installing Node.js v22..."

if check_cmd node; then
  NODE_VER=$(node --version)
  if [[ "$NODE_VER" == v22* ]]; then
    info "Node.js v22 already installed, skipping"
  else
    warn "Node.js $NODE_VER found, but v22 recommended. Installing v22..."
  fi
else
  # Install via NodeSource
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - > /dev/null 2>&1
  sudo apt-get install -y -qq nodejs > /dev/null 2>&1
  ok "Node.js installed: $(node --version)"
fi

# Install pnpm globally
if ! check_cmd pnpm; then
  sudo npm install -g pnpm > /dev/null 2>&1
  ok "pnpm installed"
fi

# =============================================================================
# Phase 4: Go 1.22+
# =============================================================================

info "Phase 4: Installing Go..."

if check_cmd go; then
  GO_VER=$(go version)
  info "Go already installed: $GO_VER"
else
  GO_VERSION="1.22.5"
  wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -O /tmp/go.tar.gz
  sudo rm -rf /usr/local/go
  sudo tar -C /usr/local -xzf /tmp/go.tar.gz
  rm /tmp/go.tar.gz

  # Add to PATH for current session and persistent
  export PATH=$PATH:/usr/local/go/bin
  echo 'export PATH=$PATH:/usr/local/go/bin' >> "$RUNNER_HOME/.profile"
  ok "Go installed: $(go version)"
fi

# Install golangci-lint
if ! check_cmd golangci-lint; then
  curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | \
    sh -s -- -b /usr/local/bin > /dev/null 2>&1
  ok "golangci-lint installed"
fi

# =============================================================================
# Phase 5: Python tooling
# =============================================================================

info "Phase 5: Installing Python tooling..."

python3 --version

# Install uv (fast Python package manager)
if ! check_cmd uv; then
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
  export PATH="$RUNNER_HOME/.local/bin:$PATH"
  ok "uv installed"
fi

# Install ruff (linter/formatter)
if ! check_cmd ruff; then
  pip3 install --user ruff > /dev/null 2>&1
  ok "ruff installed"
fi

# Install mypy
if ! check_cmd mypy; then
  pip3 install --user mypy > /dev/null 2>&1
  ok "mypy installed"
fi

# =============================================================================
# Phase 6: GitHub CLI
# =============================================================================

info "Phase 6: Installing GitHub CLI..."

if check_cmd gh; then
  info "gh CLI already installed: $(gh --version | head -1)"
else
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
    https://cli.github.com/packages stable main" | \
    sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq gh > /dev/null 2>&1
  ok "gh CLI installed: $(gh --version | head -1)"
fi

# =============================================================================
# Phase 7: Agent CLIs
# =============================================================================

info "Phase 7: Installing agent CLIs..."

# Claude Code CLI
if check_cmd claude; then
  info "Claude Code CLI already installed"
else
  info "Installing Claude Code CLI..."
  sudo npm install -g @anthropic-ai/claude-code > /dev/null 2>&1
  ok "Claude Code CLI installed"
fi

# Codex CLI
if check_cmd codex; then
  info "Codex CLI already installed"
else
  info "Installing Codex CLI..."
  sudo npm install -g @openai/codex > /dev/null 2>&1
  ok "Codex CLI installed"
fi

# =============================================================================
# Phase 8: Directory structure
# =============================================================================

info "Phase 8: Creating directory structure..."

# Token log directories (one per agent type)
TOKEN_LOG_DIRS=(
  "claude-code"
  "codex-cli"
  "planning-agent"
  "review-agent"
  "validation-agent"
  "deployment-agent"
  "roadmap-progress"
  "summaries"
)

for dir in "${TOKEN_LOG_DIRS[@]}"; do
  mkdir -p "$TOKEN_LOG_DIR/$dir"
done
ok "Token log directories created at $TOKEN_LOG_DIR"

# Deploy state directory
mkdir -p "$DEPLOY_STATE_DIR"
ok "Deploy state directory created at $DEPLOY_STATE_DIR"

# =============================================================================
# Phase 9: Agent configuration
# =============================================================================

info "Phase 9: Configuring agent CLIs..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_CONFIG_DIR="$SCRIPT_DIR/../runner-config"

# Claude Code settings
CLAUDE_DIR="$RUNNER_HOME/.claude"
mkdir -p "$CLAUDE_DIR"

if [[ -f "$RUNNER_CONFIG_DIR/claude-settings.json" ]]; then
  if [[ ! -f "$CLAUDE_DIR/settings.json" ]]; then
    cp "$RUNNER_CONFIG_DIR/claude-settings.json" "$CLAUDE_DIR/settings.json"
    ok "Claude Code settings installed"
  else
    info "Claude Code settings already exist, skipping"
  fi
fi

# Codex config
CODEX_DIR="$RUNNER_HOME/.codex"
mkdir -p "$CODEX_DIR"

if [[ -f "$RUNNER_CONFIG_DIR/codex-config.toml" ]]; then
  if [[ ! -f "$CODEX_DIR/config.toml" ]]; then
    cp "$RUNNER_CONFIG_DIR/codex-config.toml" "$CODEX_DIR/config.toml"
    ok "Codex CLI config installed"
  else
    info "Codex CLI config already exists, skipping"
  fi
fi

# =============================================================================
# Phase 10: GitHub Actions Runner (optional)
# =============================================================================

info "Phase 10: GitHub Actions Runner..."

RUNNER_DIR="$RUNNER_HOME/actions-runner"

if [[ -f "$RUNNER_DIR/.runner" ]]; then
  info "GitHub Actions runner already configured, skipping"
else
  if [[ -z "${GITHUB_RUNNER_URL:-}" ]]; then
    if $NON_INTERACTIVE; then
      warn "GITHUB_RUNNER_URL not set, skipping runner registration"
    else
      echo ""
      echo "To register a self-hosted runner, you need:"
      echo "  1. Repository URL (e.g. https://github.com/org/repo)"
      echo "  2. Registration token (Settings → Actions → Runners → New)"
      echo ""
      read -rp "Repository URL (or press Enter to skip): " GITHUB_RUNNER_URL
    fi
  fi

  if [[ -n "${GITHUB_RUNNER_URL:-}" ]]; then
    if [[ -z "${GITHUB_RUNNER_TOKEN:-}" ]]; then
      read -rp "Runner registration token: " GITHUB_RUNNER_TOKEN
    fi

    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"

    # Download latest runner
    RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/^v//')
    RUNNER_ARCH="x64"
    curl -o actions-runner.tar.gz -L \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
    tar xzf actions-runner.tar.gz
    rm actions-runner.tar.gz

    # Configure
    ./config.sh \
      --url "$GITHUB_RUNNER_URL" \
      --token "$GITHUB_RUNNER_TOKEN" \
      --name "$(hostname)" \
      --labels "self-hosted,$RUNNER_LABEL" \
      --work "_work" \
      --unattended

    # Install as service
    sudo ./svc.sh install "$RUNNER_USER"
    sudo ./svc.sh start

    ok "GitHub Actions runner registered and started"
  fi
fi

# =============================================================================
# Verification
# =============================================================================

echo ""
echo "============================================"
echo "  Verification"
echo "============================================"

PASS=0
TOTAL=0

verify() {
  TOTAL=$((TOTAL + 1))
  if check_cmd "$1"; then
    PASS=$((PASS + 1))
  else
    warn "MISSING: $1"
  fi
}

verify docker
verify node
verify pnpm
verify go
verify python3
verify gh
verify jq
verify claude
verify codex
verify golangci-lint
verify ruff
verify mypy
verify uv

echo ""

# Check directories
for dir in "${TOKEN_LOG_DIRS[@]}"; do
  TOTAL=$((TOTAL + 1))
  if [[ -d "$TOKEN_LOG_DIR/$dir" ]]; then
    PASS=$((PASS + 1))
  else
    warn "MISSING DIR: $TOKEN_LOG_DIR/$dir"
  fi
done

echo ""
echo "============================================"
echo "  Result: $PASS / $TOTAL checks passed"
echo "============================================"

if [[ $PASS -eq $TOTAL ]]; then
  ok "Runner setup complete! All tools installed."
else
  warn "Some checks failed. Review warnings above."
fi

echo ""
echo "Next steps:"
echo "  1. Authenticate gh CLI:    gh auth login"
echo "  2. Authenticate Claude:    claude auth"
echo "  3. Set Codex API key:      export OPENAI_API_KEY=..."
echo "  4. Log out and back in (for Docker group membership)"
echo ""
