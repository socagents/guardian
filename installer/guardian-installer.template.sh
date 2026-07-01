#!/usr/bin/env bash
# Guardian — single-file installer for clean VMs.
#
# This file is a TEMPLATE. The release workflow generates the real
# `guardian-installer` from this template + installer/docker-compose.yml,
# substituting two placeholder strings (see lines 222-224 below for
# their literal form). One placeholder receives the compose YAML
# verbatim (with VERSION_DEFAULT pinned to the release tag); the other
# receives the literal release version, e.g. "0.1.0".
#
# IMPORTANT for maintainers: do NOT mention either placeholder by its
# literal token anywhere in this file outside the substitution target
# lines themselves. The build script does a global string replace, so
# any second occurrence (even in a comment) will get substituted with
# the entire compose YAML and break the resulting script.
#
# You should NOT run this template directly — it has the placeholders
# unsubstituted. Build the real installer with:
#   bash installer/build-guardian-installer.sh
# (or just push a release tag and let the workflow handle it).
#
# Customer flow on a fresh Linux VM:
#   chmod +x guardian-installer
#   sudo ./guardian-installer
#   (paste GHCR token when prompted)
#
# What the script does, end-to-end:
#   1. Detects OS + verifies sudo
#   2. Installs Docker if missing (via get.docker.com)
#   3. Prompts for the GHCR token (username is hardcoded)
#   4. Auto-generates runtime secrets (MCP_TOKEN, KEK, etc.)
#   5. Writes /opt/guardian/{docker-compose.yml,.env}
#   6. docker login + pull + up + waits for healthy
#   7. Prints the URL the operator can open in a browser

set -euo pipefail

# Resolve $0 to an absolute path RIGHT NOW, before any cd changes the
# cwd (step 7 cd's into $INSTALL_DIR, after which a relative $0 like
# `./dist/installer-dev/guardian-installer-dev` won't resolve). The
# post-install self-persist step (end of file) uses this to copy the
# binary into $INSTALL_DIR/.
#
# readlink -f requires every component of the path to exist; if it
# fails (rare — the binary IS running so it must exist), fall through
# to constructing the absolute path from $PWD + dirname($0) + basename
# ($0). Either way, INSTALLER_BINARY_PATH is absolute by the time any
# subsequent cd runs.
case "$0" in
  /*) INSTALLER_BINARY_PATH="$0" ;;
  *)  INSTALLER_BINARY_PATH="$(readlink -f "$0" 2>/dev/null \
        || echo "$(cd "$(dirname "$0")" 2>/dev/null && pwd)/$(basename "$0")")" ;;
esac

# ─── Constants ────────────────────────────────────────────────────────
GUARDIAN_VERSION="__INSTALLER_VERSION__"
# Container runtime this installer targets: "docker" (default) or "podman"
# (RHEL/Podman-native build). Substituted at build time by
# build-guardian-installer.sh. Drives Step 2 (runtime install/validation).
GUARDIAN_RUNTIME="__INSTALLER_RUNTIME__"
GHCR_REGISTRY="ghcr.io"
GHCR_USER="thekite-dev"
GHCR_OWNER="kite-production"
INSTALL_DIR="${GUARDIAN_INSTALL_DIR:-/opt/guardian}"
# How long to wait for guardian-agent's first-boot healthcheck. The very first
# boot does TLS cert generation + Next.js warm-up + embedded MCP subprocess
# init, which on a fresh/slower box can take several minutes — longer than the
# old 300s, which produced a false "did not become healthy" failure even though
# the stack came up fine moments later (seen on RHEL 8 + Podman). Default 600s;
# override with GUARDIAN_HEALTH_TIMEOUT_SECS. Subsequent boots are fast.
HEALTH_TIMEOUT_SECS="${GUARDIAN_HEALTH_TIMEOUT_SECS:-600}"

# ─── Embedded digest manifest (v0.3.0+) ──────────────────────────────
# release.yml builds this installer with the per-image content digests
# of every guardian-* image at this exact version. The manifest is
# embedded verbatim below; the install/upgrade flow appends it to
# /opt/guardian/.env so docker compose resolves each service's
# `image: ...@${DIGEST_<SVC>}` reference to the matching content blob.
#
# Customer impact: containers are recreated by docker compose iff the
# image content actually changed between versions. Services whose
# image bytes are unchanged typically retain in-memory state across
# upgrades that don't touch their source.
#
# If this heredoc is empty or contains DIGEST_MANIFEST_MISSING=1,
# the installer was built without MANIFEST_PATH (a dev-build
# scenario) — the install/upgrade flow will exit with a clear error
# rather than producing a broken stack.
DIGEST_MANIFEST=$(cat <<'_GUARDIAN_DIGEST_MANIFEST_HEREDOC_END_'
__INSTALLER_DIGEST_MANIFEST__
_GUARDIAN_DIGEST_MANIFEST_HEREDOC_END_
)

# ─── Argument parsing ─────────────────────────────────────────────────
# --upgrade-to N.N.N  → on an existing install, rewrite GUARDIAN_VERSION
#                       in .env to the given version (default behavior
#                       is to preserve the existing pin). On a fresh
#                       install, install at the given version instead
#                       of the installer's bundled default.
# --help / -h         → print usage and exit.

# v0.1.21: capture the original argv BEFORE the parser consumes it.
# The arg-parsing loop below uses `shift` after each option, so by the
# time we hit the sudo re-exec further down, `$@` is empty and any
# args the user passed are lost on the second invocation. Pre-v0.1.21
# this silently turned `./guardian-installer --upgrade-to 0.1.20` into
# `./guardian-installer` after sudo, falling back to the binary's
# stamped version. Customers saw "Already at v<old> — no version
# change needed" instead of an upgrade.
ORIGINAL_ARGS=("$@")

UPGRADE_TO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --upgrade-to)
      [[ -n "${2:-}" ]] || { echo "ERROR: --upgrade-to requires a version (e.g. --upgrade-to 0.1.6)" >&2; exit 1; }
      UPGRADE_TO="$2"
      shift 2
      ;;
    --upgrade-to=*)
      UPGRADE_TO="${1#*=}"
      shift
      ;;
    --help|-h)
      cat <<USAGE
Usage: guardian-installer [--upgrade-to N.N.N]

  No flags                Install Guardian (or upgrade an existing
                          install) at v$GUARDIAN_VERSION. This binary is
                          sealed to v$GUARDIAN_VERSION — it embeds the
                          digest manifest for that exact version's
                          images. To install a different version,
                          download the corresponding installer binary
                          from the GitHub Release for that version.

  --upgrade-to N.N.N      Backward-compat flag. Must equal v$GUARDIAN_VERSION
                          (the binary's sealed version) or the install
                          errors out. Kept for operator scripts that
                          pass the flag explicitly during upgrades; in
                          v0.3.0+ it's redundant — the binary's stamp
                          IS the target version.

  Pre-v0.3.0 NOTE         Pre-v0.3.0 installers used tag-based image
                          refs and could install ANY version with the
                          same binary. v0.3.0+ installers use digest
                          pinning and embed the per-version manifest;
                          one binary = one installable version.

Examples:
  sudo ./guardian-installer                          # → installs v$GUARDIAN_VERSION
  sudo GUARDIAN_REGISTRY_TOKEN=ghp_... ./guardian-installer

Release notes + assets:
  https://github.com/kite-production/guardian/releases/tag/v$GUARDIAN_VERSION
USAGE
      exit 0
      ;;
    *)
      echo "ERROR: unknown option '$1' (try --help)" >&2
      exit 1
      ;;
  esac
done

if [[ -n "$UPGRADE_TO" ]]; then
  if ! printf '%s' "$UPGRADE_TO" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: --upgrade-to must be N.N.N semver (got: '$UPGRADE_TO')" >&2
    exit 1
  fi
  # v0.3.0+ — installer binaries are SEALED to a single version because
  # the digest manifest is embedded at build time. The pre-v0.3.0
  # `--upgrade-to N.N.N` semantics ("install a different version with
  # the same binary") no longer hold: this binary's manifest only
  # describes v$GUARDIAN_VERSION's images. We accept the flag for
  # backward compatibility with operator scripts but error out if it
  # mismatches the binary version, with a clear pointer to the right
  # download.
  if [[ "$UPGRADE_TO" != "$GUARDIAN_VERSION" ]]; then
    cat >&2 <<USAGE_ERR
ERROR: --upgrade-to v$UPGRADE_TO doesn't match this binary's version (v$GUARDIAN_VERSION).

In v0.3.0+ each guardian-installer binary is sealed to a single version
because it embeds the digest manifest for that version's images. To
install v$UPGRADE_TO, download the v$UPGRADE_TO installer binary:

  gh release download v$UPGRADE_TO --repo kite-production/guardian \\
    --pattern guardian-installer
  chmod +x guardian-installer
  sudo ./guardian-installer

(Pre-v0.3.0 installers used tag-based image refs and could install any
version with the same binary; v0.3.0+ installers cannot.)
USAGE_ERR
    exit 1
  fi
fi

# TARGET_VERSION is the version this binary installs. Pre-v0.3.0 it
# could differ from GUARDIAN_VERSION via --upgrade-to; v0.3.0+ they
# are always equal (see the check above). Kept as a separate variable
# for backward-readable code.
TARGET_VERSION="$GUARDIAN_VERSION"

# ─── Cosmetics ────────────────────────────────────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_BOLD=$'\033[1m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m';  C_DIM=$'\033[2m';   C_RESET=$'\033[0m'
else
  C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_RESET=""
fi

say()  { printf "%s%s%s\n" "$C_BOLD" "$*" "$C_RESET"; }
info() { printf "%s→%s %s\n" "$C_DIM" "$C_RESET" "$*"; }
ok()   { printf "%s✓%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s!%s %s\n" "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf "%s✗%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

# ─── Banner ───────────────────────────────────────────────────────────
say ""
say "  Guardian — installer (v$GUARDIAN_VERSION)"
say "  ───────────────────────────────────────"
if [[ -n "$UPGRADE_TO" ]]; then
  say "  Upgrade mode → target version v$UPGRADE_TO"
  say "  ───────────────────────────────────────"
fi
say ""

# ─── Step 1: Pre-flight (OS, sudo, etc.) ──────────────────────────────
info "Step 1/7 — pre-flight checks"

# Sudo / root check. We need write access to INSTALL_DIR (default
# /opt/guardian — root-owned by convention) AND access to docker.sock
# (root or docker group). If the caller already has both, we skip
# self-elevation entirely — that lets rootless-docker users and
# pre-created-INSTALL_DIR setups run the installer as their own user.
# This branch fires identically for:
#   - GitHub Actions self-hosted runner (runner user owns INSTALL_DIR,
#     in docker group)
#   - Customers with rootless docker who chown their install dir
#   - Customers with podman-docker shim + non-root install dir
# Otherwise re-exec under sudo, preserving env vars callers may set.
if [[ "$(id -u)" -ne 0 ]]; then
  # Test write access without actually writing. `mkdir -p` is
  # idempotent + side-effect-free for an existing writable dir.
  CAN_WRITE_INSTALL_DIR=0
  if mkdir -p "$INSTALL_DIR" 2>/dev/null && [[ -w "$INSTALL_DIR" ]]; then
    CAN_WRITE_INSTALL_DIR=1
  fi
  CAN_ACCESS_DOCKER=0
  if [[ -w /var/run/docker.sock ]] || docker info >/dev/null 2>&1; then
    CAN_ACCESS_DOCKER=1
  fi

  if (( CAN_WRITE_INSTALL_DIR == 1 && CAN_ACCESS_DOCKER == 1 )); then
    info "Running as $(whoami) without elevation (write access to $INSTALL_DIR + docker available)."
  elif command -v sudo >/dev/null 2>&1; then
    info "Re-running under sudo (need root for $INSTALL_DIR + docker)…"
    # Pass ORIGINAL_ARGS (captured before the parser shifted them off)
    # so flags like --upgrade-to actually survive the re-exec. The
    # `${ARRAY[@]+"${ARRAY[@]}"}` idiom is safe under set -u when the
    # array is empty (bash 4.x+).
    exec sudo -E -- "$0" "${ORIGINAL_ARGS[@]+"${ORIGINAL_ARGS[@]}"}"
  else
    die "Not running as root and sudo not available, and current user
       lacks write access to $INSTALL_DIR or cannot reach docker.
       Either (a) re-run as root:  su - root -c '$0'
       or (b) pre-create $INSTALL_DIR and add your user to the
              docker group, then re-run."
  fi
fi

# OS detection. /etc/os-release is the modern standard (systemd
# distros). The Docker convenience script supports a fixed allowlist;
# we mirror it here so we can fail fast on unsupported distros.
if [[ ! -f /etc/os-release ]]; then
  die "Cannot detect OS (no /etc/os-release). This script supports
       Ubuntu, Debian, RHEL, Fedora, Rocky, AlmaLinux, openSUSE."
fi
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}:${ID_LIKE:-}" in
  ubuntu*|debian*|*ubuntu*|*debian*|rhel*|*rhel*|fedora*|*fedora*|\
  centos*|*centos*|rocky*|*rocky*|almalinux*|*almalinux*|\
  opensuse*|*opensuse*|sles*|*sles*)
    ok "OS detected: ${PRETTY_NAME:-${ID}}"
    ;;
  *)
    die "Unsupported OS: ${PRETTY_NAME:-${ID}}.
       Guardian auto-install supports Ubuntu/Debian/RHEL/Fedora/Rocky/
       AlmaLinux/openSUSE. For other distros, install Docker manually
       and run installer/install.sh from the multi-file kit instead."
    ;;
esac

# Architecture check. We publish multi-arch images for amd64/arm64.
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64|aarch64|arm64) ok "Architecture: $ARCH" ;;
  *) die "Unsupported architecture: $ARCH (need amd64 or arm64)." ;;
esac

# ─── Step 2: container runtime (Docker, or Podman on RHEL/Podman builds) ──
if [ "$GUARDIAN_RUNTIME" = "podman" ]; then
  # ── Podman / RHEL path (no Docker Engine) ──────────────────────────
  # Strategy ("Podman-as-Docker"): install podman + the podman-docker
  # compat shim (provides a `docker` CLI alias + the /var/run/docker.sock
  # symlink the stack mounts), enable the rootful API socket, and ensure a
  # `docker compose` provider resolves. After this, the rest of the
  # installer's docker/`docker compose` calls route to Podman unchanged.
  info "Step 2/7 — Podman runtime (RHEL/Podman build)"

  if ! command -v podman >/dev/null 2>&1; then
    warn "Podman not found — installing via the system package manager…"
    if command -v dnf >/dev/null 2>&1; then
      dnf install -y -q podman podman-docker || die "Failed to install podman + podman-docker via dnf."
    elif command -v yum >/dev/null 2>&1; then
      yum install -y -q podman podman-docker || die "Failed to install podman + podman-docker via yum."
    else
      die "No dnf/yum found. Install 'podman' and 'podman-docker' manually, then re-run."
    fi
  else
    # Podman present — make sure the docker-compat shim is installed too
    # (it provides the `docker` command + /var/run/docker.sock symlink).
    if ! command -v docker >/dev/null 2>&1; then
      if command -v dnf >/dev/null 2>&1; then dnf install -y -q podman-docker || true
      elif command -v yum >/dev/null 2>&1; then yum install -y -q podman-docker || true; fi
    fi
  fi
  ok "Podman present: $(podman --version)"

  # Rootful Docker-compatible API socket — the updater drives it to manage
  # connector containers. systemd socket-activates podman on first connect.
  # Capture systemd's output so a failure is diagnosable on a box we can't
  # reach (no test VM) instead of being swallowed by 2>/dev/null.
  if ! _sockout="$(systemctl enable --now podman.socket 2>&1)"; then
    die "Could not enable the rootful Podman API socket: ${_sockout}
       Try: sudo systemctl enable --now podman.socket ; systemctl status podman.socket"
  fi
  # podman-docker normally symlinks /run/podman/podman.sock → /var/run/docker.sock;
  # create it explicitly if the package didn't.
  if [ ! -S /var/run/docker.sock ] && [ -S /run/podman/podman.sock ]; then
    ln -sf /run/podman/podman.sock /var/run/docker.sock
  fi
  [ -S /var/run/docker.sock ] \
    || die "Podman API socket missing at /var/run/docker.sock after enabling podman.socket.
       Check: systemctl status podman.socket ; ls -l /run/podman/podman.sock"
  ok "Podman API socket active at /var/run/docker.sock"

  # Reboot persistence. Rootful Podman does NOT auto-restart containers after a
  # host reboot the way dockerd does; podman-restart.service (shipped with
  # podman) does it at boot — but on RHEL 8's podman 4.9 it revives ONLY
  # `restart=always` containers (not `unless-stopped`; that landed in podman 5).
  # podman-compose.yml therefore pins every service to `restart: always` (see
  # its header note B). The stack is brought up in Step 7, so enabling the unit
  # now means the next boot revives Guardian.
  if ! _prout="$(systemctl enable podman-restart.service 2>&1)"; then
    warn "Could not enable podman-restart.service (${_prout}). The stack may not"
    warn "auto-start after a reboot — run 'sudo systemctl enable --now podman-restart.service'"
    warn "or re-run this installer after rebooting."
  else
    ok "podman-restart.service enabled — stack will revive after a host reboot"
  fi

  # Ensure a real Docker Compose v2 provider resolves. The podman-docker shim
  # routes `docker compose` → `podman compose`, which delegates to an external
  # provider. podman-compose (Python) is NOT in RHEL 8 base/AppStream — it
  # lives only in EPEL/pip, which a restricted-egress box can't reach, and it
  # isn't Compose v2. Instead install the official Docker Compose v2 *plugin*
  # (a single standalone CLI binary — NOT the Docker engine/daemon; the runtime
  # stays Podman) from the Docker repo (download.docker.com, the channel these
  # customers already allow-list), then point Podman's compose provider at it.
  # Using real Compose v2 also makes containers carry the standard
  # com.docker.compose.* labels, so guardian-updater's project detection works
  # identically to Docker.
  if ! docker compose version >/dev/null 2>&1; then
    warn "Installing Docker Compose v2 (compose CLI only — the Docker engine is NOT installed; runtime stays Podman)…"
    if command -v dnf >/dev/null 2>&1; then
      dnf install -y -q dnf-plugins-core 2>/dev/null || true
      dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null || true
      dnf install -y -q docker-compose-plugin 2>/dev/null || true
    elif command -v yum >/dev/null 2>&1; then
      yum install -y -q yum-utils 2>/dev/null || true
      yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null || true
      yum install -y -q docker-compose-plugin 2>/dev/null || true
    fi
    # The plugin lands as a cli-plugin binary; podman's `compose` won't find it
    # on PATH automatically, so register it explicitly as the compose provider.
    _compose_bin=""
    for _p in /usr/libexec/docker/cli-plugins/docker-compose \
              /usr/lib/docker/cli-plugins/docker-compose \
              /usr/local/lib/docker/cli-plugins/docker-compose; do
      [ -x "$_p" ] && _compose_bin="$_p" && break
    done
    if [ -n "$_compose_bin" ]; then
      mkdir -p /etc/containers/containers.conf.d
      printf '[engine]\ncompose_providers=["%s"]\ncompose_warning_logs=false\n' "$_compose_bin" \
        > /etc/containers/containers.conf.d/guardian-compose.conf
      ok "Docker Compose v2 plugin registered as Podman's compose provider: $_compose_bin"
    fi
  fi
else
  # ── Docker path (default; unchanged) ───────────────────────────────
  info "Step 2/7 — Docker"

  if ! command -v docker >/dev/null 2>&1; then
    warn "Docker not found — installing via get.docker.com…"
    warn "(This pulls and runs Docker's official convenience script.)"

    # The convenience script is the canonical way to install Docker
    # Engine + compose plugin on the supported distros. We need curl
    # to fetch it; install curl first if missing.
    if ! command -v curl >/dev/null 2>&1; then
      info "Installing curl first…"
      if command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq && apt-get install -y -qq curl
      elif command -v dnf >/dev/null 2>&1; then
        dnf install -y -q curl
      elif command -v yum >/dev/null 2>&1; then
        yum install -y -q curl
      elif command -v zypper >/dev/null 2>&1; then
        zypper -n install -y curl
      else
        die "Cannot install curl on this distro. Install it manually."
      fi
    fi

    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh

    systemctl enable --now docker || true
    ok "Docker installed: $(docker --version)"
  else
    ok "Docker already present: $(docker --version)"
  fi
fi

# Verify compose plugin (v2) is available. The convenience script
# installs it; older boxes that pre-date the plugin-era of compose
# may need a manual nudge.
if ! docker compose version >/dev/null 2>&1; then
  if [ "$GUARDIAN_RUNTIME" = "podman" ]; then
    die "Docker Compose v2 is not resolvable through Podman's compose shim.
       The installer tried to install the Compose v2 plugin (CLI only — not the
       Docker engine) from download.docker.com and register it as Podman's
       compose provider, but it's still not working. Install it manually:
         sudo dnf install -y dnf-plugins-core
         sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
         sudo dnf install -y docker-compose-plugin
         sudo mkdir -p /etc/containers/containers.conf.d
         printf '[engine]\\ncompose_providers=[\"/usr/libexec/docker/cli-plugins/docker-compose\"]\\n' | \\
           sudo tee /etc/containers/containers.conf.d/guardian-compose.conf
       then re-run this installer. (Verify with: docker compose version)"
  else
    die "'docker compose' v2 plugin not available even after install.
       Install manually:
       https://docs.docker.com/compose/install/linux/"
  fi
fi
ok "Compose plugin present: $(docker compose version --short 2>/dev/null || docker compose version | head -1)"

# Verify daemon is actually reachable. systemctl enable should have
# started it, but on some hosts (containers, exotic init systems) it
# may not have.
if ! docker info >/dev/null 2>&1; then
  die "docker daemon not reachable.
       Start it manually:  systemctl start docker"
fi
ok "Docker daemon reachable"

# ─── Step 3: Detect existing install (resumable) ──────────────────────
info "Step 3/7 — checking for existing install"

# Reads a value from $INSTALL_DIR/.env. Echoes the value to stdout if
# present and non-empty; returns 1 otherwise. Used to decide which
# steps to skip when re-running on an existing install.
read_env_value() {
  local var="$1"
  local file="$INSTALL_DIR/.env"
  [[ -f "$file" ]] || return 1
  local value
  value=$(grep -E "^${var}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true)
  [[ -n "$value" ]] || return 1
  printf '%s' "$value"
}

# v0.5.50 — write_env_value VAR VALUE
# Updates an existing `VAR=...` line in-place, or appends `VAR=VALUE`
# if the key isn't present. Preserves all other lines (including
# comments + ordering) and re-applies mode 600 after the rewrite.
#
# Idempotent — calling with the same value is a no-op (same content
# written via temp-file swap; permissions are re-applied either way).
#
# Why this exists: pre-v0.5.50 the installer captured a fresh token
# from env var or interactive prompt into $GHCR_TOKEN (used by docker
# login + image pulls) but never wrote it back to .env. On the next
# re-run, read_env_value would surface the stale token, validation
# would fail, the operator would be re-prompted. With this helper +
# the call-site at the end of step 4, fresh tokens persist across
# re-runs.
write_env_value() {
  local var="$1"
  local value="$2"
  local file="$INSTALL_DIR/.env"
  [[ -f "$file" ]] || return 1
  if grep -qE "^${var}=" "$file"; then
    # Update in-place via awk. Match by `VAR=` prefix (with anchor)
    # so VAR2 doesn't accidentally match VAR. Values with '=' inside
    # them survive correctly because we don't FS-split — we just
    # rewrite the line wholesale.
    awk -v k="$var" -v v="$value" '
      index($0, k "=") == 1 { print k "=" v; next }
      { print }
    ' "$file" > "$file.new"
    mv "$file.new" "$file"
  else
    # Key absent — append at end. Note: this writes the new key
    # without a preceding section header / comment, which is fine
    # for the registry-token case (any caller would have an existing
    # GUARDIAN_REGISTRY_TOKEN line on any post-fresh-install .env).
    printf '%s=%s\n' "$var" "$value" >> "$file"
  fi
  chmod 600 "$file"
}

EXISTING_INSTALL=0
if [[ -f "$INSTALL_DIR/.env" ]]; then
  EXISTING_INSTALL=1
  ok "Existing install detected at $INSTALL_DIR — resuming"
  ok "  (secrets in your .env will be preserved untouched)"
else
  info "Fresh install (no $INSTALL_DIR/.env found)"
fi

# ─── Step 4: Registry token (reuse, validate, or prompt) ──────────────
info "Step 4/7 — registry credentials"

# Validates a GHCR token by exchanging it for a bearer at the GHCR
# token endpoint, then attempting to fetch a manifest for one of the
# images this installer will pull. Returns 0 if the token can actually
# pull from ghcr.io/$GHCR_OWNER/* (i.e. valid + has read:packages),
# non-zero otherwise.
#
# Why probe instead of trust: tokens stored in .env may be:
#   * Expired (ghs_ ephemeral tokens last ~1 hour)
#   * Missing read:packages scope (e.g. a `repo`-only PAT)
#   * Revoked since last use
# Pre-v0.5.8 the installer blindly reused whatever was in .env; the
# failure surfaced at step 7's docker compose pull with a confusing
# 'denied: denied' message. v0.5.8 catches it at step 4 so the
# operator can paste a fresh token before any irreversible state
# changes (digest manifest rewrite, etc.) happen.
validate_ghcr_token() {
  local token="$1"
  local bearer http_code
  # GHCR token-exchange: trade PAT for a per-image pull bearer
  bearer=$(curl -fsS \
    -u "$GHCR_USER:$token" \
    "https://${GHCR_REGISTRY}/token?service=${GHCR_REGISTRY}&scope=repository:${GHCR_OWNER}/guardian-agent:pull" \
    2>/dev/null | python3 -c 'import sys, json; print(json.load(sys.stdin).get("token", ""))' 2>/dev/null || true)
  [[ -n "$bearer" ]] || return 1
  # Probe: HEAD the manifest. 200 = good, 403 = scope missing,
  # 401 = bearer didn't accept (shouldn't happen if exchange succeeded),
  # 404 with body MANIFEST_UNKNOWN ("OCI index found...") = our Accept
  # header was too narrow for what GHCR actually has stored.
  #
  # The Accept header MUST include all four manifest media types
  # because the install pulls a mix of formats:
  #   * customer release tags (built by `docker build` in release.yml)
  #     → application/vnd.docker.distribution.manifest.v2+json
  #     (legacy single-arch Docker v2)
  #   * dev `:dev` tags (built by build-<svc>.yml's composite action,
  #     which uses buildx/OCI conventions)
  #     → application/vnd.oci.image.index.v1+json
  #     (multi-arch OCI image index)
  # docker compose pull handles both natively, so omitting either
  # from this Accept header blocks installs that would otherwise
  # succeed at step 7. v0.5.10 fix: previous header listed only
  # the legacy Docker single-arch type, which made GHCR refuse to
  # serve the `:dev` manifest (OCI index) and v0.5.8's validation
  # appeared to reject valid tokens.
  # Probe a tag GUARANTEED to exist for this installer's distribution so
  # 200=authorized vs 404=unauthorized stays unambiguous: the release
  # version for customer installers, or the rolling `dev` tag for
  # dev-<sha> installers (whose images carry the `dev` tag, not the full
  # dev-<sha> version string). A hardcoded `dev` probe broke installs off
  # a mirror that has only version + `latest` tags (e.g. ghcr.io/kite-production),
  # where guardian-agent:dev does not exist.
  local probe_tag="$GUARDIAN_VERSION"
  [[ "$probe_tag" == dev-* ]] && probe_tag="dev"
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $bearer" \
    -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json" \
    "https://${GHCR_REGISTRY}/v2/${GHCR_OWNER}/guardian-agent/manifests/${probe_tag}" 2>/dev/null || echo "000")
  [[ "$http_code" == "200" ]]
}

# Priority order:
#   1. GUARDIAN_REGISTRY_TOKEN env var (caller passed it explicitly)
#   2. Existing .env (re-run case — try to reuse, but VALIDATE first)
#   3. Interactive prompt
#
# Each token source is validated against GHCR before acceptance. On
# validation failure, we fall through to the interactive prompt
# (rather than silently using a token that's going to fail at pull
# time and waste the operator's debugging cycle).
GHCR_TOKEN="${GUARDIAN_REGISTRY_TOKEN:-}"
TOKEN_SOURCE="env var"

if [[ -z "$GHCR_TOKEN" && "$EXISTING_INSTALL" == "1" ]]; then
  if GHCR_TOKEN=$(read_env_value GUARDIAN_REGISTRY_TOKEN); then
    TOKEN_SOURCE="$INSTALL_DIR/.env"
  fi
fi

# Attempt validation loop. If the captured token is invalid AND we
# can prompt interactively, ask for a new one. Cap at 3 attempts.
ATTEMPT=0
MAX_ATTEMPTS=3
while (( ATTEMPT < MAX_ATTEMPTS )); do
  ATTEMPT=$(( ATTEMPT + 1 ))

  # If we still have no token after the priority chain, prompt now.
  if [[ -z "${GHCR_TOKEN:-}" ]]; then
    if [[ ! -t 0 && ! -r /dev/tty ]]; then
      die "No registry token available and no TTY for interactive
            prompt. Provide GUARDIAN_REGISTRY_TOKEN env var or edit
            $INSTALL_DIR/.env."
    fi
    echo ""
    echo "  A registry token is needed to pull Guardian images."
    echo "  (You should have received this from Kite during onboarding."
    echo "  Generate a fine-grained PAT at github.com/settings/tokens"
    echo "  with read:packages scope for the ${GHCR_OWNER} org.)"
    echo ""
    read -r -s -p "  Token (input hidden): " GHCR_TOKEN </dev/tty
    echo ""
    TOKEN_SOURCE="interactive prompt"
  fi

  # Basic shape check
  if [[ -z "$GHCR_TOKEN" ]]; then
    warn "Token cannot be empty. Please try again."
    continue
  fi
  if [[ ${#GHCR_TOKEN} -lt 30 ]]; then
    warn "That doesn't look like a valid GitHub PAT (too short — they're 40+ chars).
       Please try again."
    GHCR_TOKEN=""
    continue
  fi

  # Validate against GHCR
  info "Validating token against ${GHCR_REGISTRY}/${GHCR_OWNER}/guardian-agent ..."
  if validate_ghcr_token "$GHCR_TOKEN"; then
    ok "Token valid (source: $TOKEN_SOURCE)"
    break
  fi

  # Validation failed. Report + re-prompt (if interactive) or die.
  warn "Token from $TOKEN_SOURCE failed validation against ${GHCR_REGISTRY}."
  warn "Likely causes: expired (ghs_ tokens last ~1 hour), missing"
  warn "read:packages scope, or revoked. Need a fine-grained PAT for"
  warn "${GHCR_OWNER} with Packages: Read-only permission."
  if [[ ! -t 0 && ! -r /dev/tty ]]; then
    die "Cannot prompt for a fresh token (no TTY).
       Re-run with GUARDIAN_REGISTRY_TOKEN=<fresh PAT> or update
       $INSTALL_DIR/.env's GUARDIAN_REGISTRY_TOKEN line."
  fi
  GHCR_TOKEN=""
  TOKEN_SOURCE=""  # will be set to "interactive prompt" on next loop
done

if [[ -z "${GHCR_TOKEN:-}" ]]; then
  die "Exhausted $MAX_ATTEMPTS attempts to obtain a valid registry token.
       Generate a PAT at github.com/settings/tokens (Packages: Read-only
       for ${GHCR_OWNER}) and re-run the installer."
fi
ok "Token captured"

# v0.5.50 — Persist freshly-obtained tokens back to .env so subsequent
# re-runs don't re-prompt. Fires when the captured token came from
# either the env var path (operator passed GUARDIAN_REGISTRY_TOKEN=...)
# or the interactive-prompt path (.env had an expired one, operator
# typed a new one). The .env-source path is skipped because the
# value already matches what's on disk.
#
# Why this is important: ghs_ tokens last ~1 hour, so on existing
# installs the .env-stored token regularly fails validation; without
# write-back, every re-run forces the operator to find + paste a new
# PAT (pre-v0.5.50 behavior).
if [[ "$EXISTING_INSTALL" == "1" && "$TOKEN_SOURCE" != "$INSTALL_DIR/.env" ]]; then
  if write_env_value GUARDIAN_REGISTRY_TOKEN "$GHCR_TOKEN"; then
    ok "Persisted fresh token to $INSTALL_DIR/.env (next re-run won't re-prompt unless this token also expires)"
  else
    warn "Failed to persist token to $INSTALL_DIR/.env; current install proceeds OK but next re-run will re-prompt"
  fi
fi

# ─── Step 5: Runtime secrets (reuse or generate) ──────────────────────
info "Step 5/7 — runtime secrets"

if [[ "$EXISTING_INSTALL" == "1" ]]; then
  # Verify all required secrets are still present in .env. We don't
  # need to load their values into bash variables (we won't rewrite
  # .env), just confirm they exist and are non-empty.
  missing_secrets=()
  for var in MCP_TOKEN GUARDIAN_SECRET_KEK; do
    if ! read_env_value "$var" >/dev/null; then
      missing_secrets+=("$var")
    fi
  done
  if [[ ${#missing_secrets[@]} -gt 0 ]]; then
    die "Existing $INSTALL_DIR/.env is missing required values: ${missing_secrets[*]}
       Either restore them manually or delete the .env to reset.
       NOTE: deleting .env destroys GUARDIAN_SECRET_KEK, which means any
       operator secrets you've stored via the UI become unreadable."
  fi
  ok "Reusing existing secrets from $INSTALL_DIR/.env"

  # v0.5.5+ — back-fill GUARDIAN_DEFAULT_ADMIN_PASSWORD on pre-v0.5.5
  # installs that don't carry it yet. This value is consumed by the
  # agent's entrypoint seed step on first boot of a fresh SecretStore;
  # on upgrades with an existing SecretStore it's never consulted. So
  # back-fill on upgrade is harmless + future-proofs against a later
  # factory-reset on this host (which would wipe SecretStore but keep
  # .env, then need the seed value).
  #
  # Both branches (back-fill OR already-present) ALSO assign the
  # value to the bash variable space, so the installer's epilogue
  # banner ("First-time login: …") can substitute it without
  # tripping `set -u`. v0.5.5 hotfix — original v0.5.5 set the bash
  # var only in the fresh-install branch + missed it in the
  # existing-install paths, so the epilogue crashed with an unbound
  # variable on every upgrade. Bytes-on-disk vs. shell-var-space are
  # separate namespaces; both have to be set.
  if GUARDIAN_DEFAULT_ADMIN_PASSWORD=$(read_env_value GUARDIAN_DEFAULT_ADMIN_PASSWORD); then
    : # already present in .env (and now in the bash var)
  else
    GUARDIAN_DEFAULT_ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
    {
      echo ""
      echo "# ─── Bootstrap admin password (v0.5.5+) ──────────────────────────────"
      echo "# Auto-generated by guardian-installer on v0.5.5 upgrade back-fill."
      echo "# Consumed only when SecretStore is empty (fresh install OR after"
      echo "# guardian-factory-reset). Forced password change at /profile makes"
      echo "# this irrelevant after first login."
      echo "GUARDIAN_DEFAULT_ADMIN_PASSWORD=$GUARDIAN_DEFAULT_ADMIN_PASSWORD"
    } >> "$INSTALL_DIR/.env"
    ok "Back-filled GUARDIAN_DEFAULT_ADMIN_PASSWORD (pre-v0.5.5 install)"
  fi
else
  # Fresh install — generate everything. GUARDIAN_SECRET_KEK is the only
  # load-bearing one for stored operator data; the others are bundle-
  # internal coordination or first-boot seeds.
  MCP_TOKEN="$(openssl rand -hex 32)"
  GUARDIAN_SECRET_KEK="$(openssl rand -base64 32)"
  # v0.5.5+ — admin bootstrap password. Random per install (pre-v0.5.5
  # this was a hardcoded literal in the guardian-agent image; v0.5.5
  # moves it out so no credential is baked anywhere in any image).
  GUARDIAN_DEFAULT_ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
  ok "3 runtime secrets generated"
fi

# ─── Step 6: Refresh files ────────────────────────────────────────────
info "Step 6/7 — refreshing $INSTALL_DIR/{docker-compose.yml,.env}"

mkdir -p "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# docker-compose.yml — ALWAYS write fresh. The embedded YAML below is
# sealed at the installer's version (deterministic from VERSION), so
# overwriting on every run is safe and ensures the operator gets
# whatever compose-level fixes the installer version brings. Customers
# are not expected to hand-edit this file; if you do, it'll be replaced
# next time you run the installer.
cat > "$INSTALL_DIR/docker-compose.yml" <<'_GUARDIAN_COMPOSE_HEREDOC_END_'
__INSTALLER_COMPOSE_YAML__
_GUARDIAN_COMPOSE_HEREDOC_END_
chmod 644 "$INSTALL_DIR/docker-compose.yml"
ok "docker-compose.yml refreshed"

# v0.5.3 — host-side recovery utilities, embedded in the installer
# binary the same way the compose YAML is embedded (heredoc with a
# unique terminator). Two scripts ship:
#
#   1. guardian-factory-reset            — wipes guardian_* volumes +
#      re-runs this installer. MUST be host-side because a container
#      can't delete the volume it's mounting.
#
#   2. guardian-reset-admin-password     — thin host wrapper around
#      the in-container `/app/cli/reset-admin.mjs` CLI. Host-side for
#      operator-UX consistency with factory-reset (same invocation
#      shape: sudo /opt/guardian/guardian-<utility>) while the credential
#      write itself stays inside the agent boundary that already owns
#      the SecretStore + audit machinery.
#
# Why embedded here vs. shipped as separate files in the multi-file
# install kit only: the single-file `guardian-installer` is the customer-
# primary distribution path (one binary, gh release download + run).
# Embedding the recovery utilities means operators ALWAYS have them on
# disk at /opt/guardian/ after install — no second download, no
# "wait, where's the script?" support ticket. The multi-file kit
# (installer/install.sh path) also ships them via direct file copy in
# release.yml.
#
# Pre-v0.5.3 (v0.4.0–v0.5.2) the only operator-facing recovery path
# was `docker exec -it guardian_agent node /app/cli/reset-admin.mjs`.
# That works, but it's awkward to type from memory under stress, and
# it gave customers a wildly different ergonomics from the (then-
# nonexistent) factory-reset path. v0.5.3 brings both to the same
# shape.
cat > "$INSTALL_DIR/guardian-factory-reset" <<'_GUARDIAN_FACTORY_RESET_HEREDOC_END_'
__INSTALLER_FACTORY_RESET_SH__
_GUARDIAN_FACTORY_RESET_HEREDOC_END_
chmod 755 "$INSTALL_DIR/guardian-factory-reset"
ok "guardian-factory-reset refreshed"

cat > "$INSTALL_DIR/guardian-reset-admin-password" <<'_GUARDIAN_RESET_PASSWORD_HEREDOC_END_'
__INSTALLER_RESET_PASSWORD_SH__
_GUARDIAN_RESET_PASSWORD_HEREDOC_END_
chmod 755 "$INSTALL_DIR/guardian-reset-admin-password"
ok "guardian-reset-admin-password refreshed"

# .env — preserve existing on resume; write fresh on first install.
# The .env is the source of truth for the customer's runtime state
# (secrets, KEK, image-digest pins). Re-runs must NEVER clobber it —
# that would rotate GUARDIAN_SECRET_KEK and lock out operator secrets
# stored via the UI.
#
# v0.3.0+ — version pinning happens via the digest manifest, not via a
# bare GUARDIAN_VERSION=tag line. The block below ALWAYS strips any
# existing DIGEST_GUARDIAN_* lines + the GUARDIAN_VERSION line from the
# .env (regardless of fresh/existing) and re-appends the manifest from
# the embedded heredoc. This means:
#   - Fresh install: heredoc writes secrets, then manifest section
#     appends version + digests in one consistent block.
#   - Upgrade: existing secrets + KEK preserved, stale digest pins
#     stripped, new digests appended.
#   - v0.2.x → v0.3.x migration: the .env has no DIGEST_* lines AND
#     a stale GUARDIAN_VERSION=tag line; both get cleaned up and the
#     manifest takes over.
#
# Detection of v0.2.x → v0.3.x migration (for the operator notice
# below) happens BEFORE the strip — once we strip we lose the signal.
V02X_MIGRATION=0
if [[ "$EXISTING_INSTALL" == "1" ]]; then
  if ! grep -q '^DIGEST_GUARDIAN_AGENT=' "$INSTALL_DIR/.env" 2>/dev/null; then
    V02X_MIGRATION=1
  fi
fi

if [[ "$EXISTING_INSTALL" == "1" ]]; then
  CURRENT_VERSION=$(read_env_value GUARDIAN_VERSION || echo "unknown")
  if [[ "$CURRENT_VERSION" == "$GUARDIAN_VERSION" ]] && [[ "$V02X_MIGRATION" -eq 0 ]]; then
    ok "Already at v$GUARDIAN_VERSION — refreshing digest manifest only"
  elif [[ "$V02X_MIGRATION" -eq 1 ]]; then
    say ""
    warn "v0.2.x → v$GUARDIAN_VERSION migration detected"
    warn "  Pre-v0.3.0 installs used tag-based image refs. v0.3.0+ uses digest"
    warn "  pinning, which means this upgrade is a one-time recreation of ALL"
    warn "  containers as the compose file's image-ref shape changes. After"
    warn "  this hop, subsequent v0.3.x → v0.3.x+1 upgrades selectively"
    warn "  recreate only the services whose image content actually changed."
    warn ""
    warn "  Preserved across this upgrade:"
    warn "    - All named volumes (operator data, secrets store, skills"
    warn "      volume)"
    warn "    - Your GUARDIAN_SECRET_KEK + GHCR token + UI password"
    warn ""
    warn "  Lost across this upgrade (one-time):"
    warn "    - guardian-agent in-flight jobs / chat sessions"
    say ""
  else
    info "Upgrading $CURRENT_VERSION → $GUARDIAN_VERSION (digest manifest will replace)"
  fi
  ok "Existing secrets + KEK in $INSTALL_DIR/.env preserved"
else
  # Heredoc with shell interpolation enabled (no quotes around the
  # delimiter) so the secrets generated above expand. mode 600 because
  # GUARDIAN_REGISTRY_TOKEN + KEK are sensitive.
  #
  # Note: GUARDIAN_VERSION is NOT written here. It lives in the digest
  # manifest section appended below, which is the single source of
  # truth for both the version label AND the per-image digests.
  cat > "$INSTALL_DIR/.env" <<EOF
# Generated by guardian-installer (v$GUARDIAN_VERSION) on $(date -u +%Y-%m-%dT%H:%M:%SZ).
# Edit by hand if needed; both install.sh + the in-app updater read from here.
#
# v0.3.0+ — the GUARDIAN_VERSION line + DIGEST_GUARDIAN_* lines at the
# bottom of this file are MANIFEST-MANAGED. Re-running guardian-installer
# (or the in-app updater) strips and re-appends them as a unit. Editing
# them by hand is supported but next install/upgrade will overwrite.

# ─── GHCR registry credentials ────────────────────────────────────────
GUARDIAN_REGISTRY_USER=$GHCR_USER
GUARDIAN_REGISTRY_TOKEN=$GHCR_TOKEN

# ─── Internal MCP coordination token ──────────────────────────────────
MCP_TOKEN=$MCP_TOKEN

# ─── Encryption-at-rest KEK for SecretStore ───────────────────────────
# WARNING: losing this makes existing stored operator secrets
# unrecoverable. Back this up alongside your other deployment creds.
GUARDIAN_SECRET_KEK=$GUARDIAN_SECRET_KEK

# ─── Bootstrap admin password (v0.5.5+) ──────────────────────────────
# Seeded into SecretStore on first boot. The agent forces you to change
# it at /profile on first login, after which this value is never
# consulted. If you lose it before changing the password, run
# sudo /opt/guardian/guardian-reset-admin-password from the host.
# Pre-v0.5.5 this was the literal "guardian-admin-CHANGE-ME" baked
# into the agent image; v0.5.5 moves it here so no credential is
# baked anywhere in any image.
GUARDIAN_DEFAULT_ADMIN_PASSWORD=$GUARDIAN_DEFAULT_ADMIN_PASSWORD

# ─── Operator config (filled in via /providers + /instances after login) ─
# Leaving these blank is fine. v0.4.0+ — the agent boots with default
# admin credentials (admin / value of GUARDIAN_DEFAULT_ADMIN_PASSWORD
# above) and the operator configures providers + connector instances
# via the UI after signing in and rotating the default password at
# /profile.
EOF
  chmod 600 "$INSTALL_DIR/.env"
  ok "Wrote $INSTALL_DIR/.env"
fi

# ─── Step 6.5: Apply the digest manifest to .env ──────────────────────
# v0.3.0+ — the customer compose references each image by digest
# (`@${DIGEST_<SVC>}`). Without DIGEST_* values in .env, docker compose
# resolves them to the explicit-invalid fallback and fails loudly. So
# this step is load-bearing: if it doesn't run, the whole stack fails
# to come up.
#
# Pattern: strip any pre-existing GUARDIAN_VERSION + DIGEST_GUARDIAN_*
# lines (left over from a prior version's manifest, or absent in
# v0.2.x → v0.3.x migration), then append the embedded manifest as a
# clean block. Idempotent on repeat runs.
info "Applying digest manifest for v$GUARDIAN_VERSION"

# Sanity: refuse to proceed if the embedded manifest is the build-time
# placeholder (i.e. this binary was built without MANIFEST_PATH). That
# would be a dev-build mistake; production release.yml always passes
# the manifest. Failing here protects the operator from a half-broken
# stack with invalid digests.
if printf '%s' "$DIGEST_MANIFEST" | grep -q '^DIGEST_MANIFEST_MISSING=1'; then
  die "This guardian-installer was built without an embedded digest
       manifest (DIGEST_MANIFEST_MISSING=1). It cannot install a v0.3.0+
       stack because the customer compose requires per-image digests
       in .env.

       This is a build-time failure, not an operator-fixable runtime
       issue. Download a customer release binary from:
         https://github.com/kite-production/guardian/releases/tag/v$GUARDIAN_VERSION"
fi

# Validate the manifest has the expected keys before we touch .env.
# Minimum bar: GUARDIAN_VERSION matches this binary, plus all 3
# stack-service digests are present. Per-instance connector digests
# are validated by guardian-updater at runtime (less load-bearing here
# because they're only needed when the operator creates a connector
# instance).
_required_keys=(
  "GUARDIAN_VERSION=$GUARDIAN_VERSION"
  "DIGEST_GUARDIAN_AGENT="
  "DIGEST_GUARDIAN_UPDATER="
  "DIGEST_GUARDIAN_BROWSER="
)
for key in "${_required_keys[@]}"; do
  if ! printf '%s' "$DIGEST_MANIFEST" | grep -q "^${key}"; then
    die "Embedded digest manifest is missing required key matching '${key}'.
         This binary appears corrupted; re-download from:
           https://github.com/kite-production/guardian/releases/tag/v$GUARDIAN_VERSION"
  fi
done

# Ensure the .env ends with a newline before we strip + append (some
# editors leave files without one, which makes the appended block run
# onto the last existing line).
if [[ -s "$INSTALL_DIR/.env" ]] && [[ "$(tail -c 1 "$INSTALL_DIR/.env" | xxd -p 2>/dev/null)" != "0a" ]]; then
  printf '\n' >> "$INSTALL_DIR/.env"
fi

# Strip stale manifest-managed lines AND the comment header block we
# emit alongside them (v0.5.4 — pre-v0.5.4 only the value lines were
# stripped, so every re-run accumulated a fresh comment block while
# the value lines correctly rotated. Operators ran `cat .env` after a
# dozen dev-installer runs and saw ~25 orphan headers).
#
# Patterns:
#   * VALUE lines: GUARDIAN_VERSION= + DIGEST_GUARDIAN_*= (pinned at line
#     start so we never false-positive on DIGEST_GUARDIAN_AGENT_DEPRECATED
#     etc. that some future operator script might add).
#   * HEADER comment block: 4 lines emitted by this installer below.
#     Also matches install.sh's 3-line variant ("managed by install.sh")
#     so a .env that's bounced between both installer flavors gets
#     cleaned the same way.
sed -i.bak \
  -e '/^# ─── Digest manifest (managed by /d' \
  -e '/^# DO NOT EDIT BY HAND\./d' \
  -e '/^# strips and rewrites these lines/d' \
  -e "/^# version, download that version's guardian-installer/d" \
  -e '/^# these lines as a unit from the bundled/d' \
  -e '/^GUARDIAN_VERSION=/d' \
  -e '/^DIGEST_GUARDIAN_/d' \
  "$INSTALL_DIR/.env"
rm -f "$INSTALL_DIR/.env.bak"

# v0.6.7 — operator config-file separation principle. Per-instance
# connector image digests (DIGEST_GUARDIAN_CONNECTOR_*) DO NOT belong
# in .env. .env is for service credentials + the 3 core compose-
# substitution digests that docker-compose interpolates. Connector
# image refs are runtime data guardian-updater uses to spawn dynamic
# instance containers — they live in a dedicated file at
# /opt/guardian/connector-digests.env (mounted into guardian_updater
# as /host/connector-digests.env). The strip above already removed
# DIGEST_GUARDIAN_CONNECTOR_* lines from .env via the catch-all
# `DIGEST_GUARDIAN_` pattern, so legacy .env files inherit the cleanup
# on the first v0.6.7 install/upgrade. The connector-digests.env
# file is fully rewritten below from the embedded manifest.

# Collapse consecutive blank lines that the strip above may leave
# behind (one per stripped block). awk is portable across BSD/GNU
# sed differences in '-s' / squeeze-blanks support.
awk 'NF || prev_nf { print } { prev_nf = NF }' \
  "$INSTALL_DIR/.env" > "$INSTALL_DIR/.env.tmp" \
  && mv "$INSTALL_DIR/.env.tmp" "$INSTALL_DIR/.env"

# v0.6.7 — split the embedded manifest into two destinations:
#   * Core (GUARDIAN_VERSION + 3 stack-service digests + anything that
#     isn't a per-connector digest) → /opt/guardian/.env. Required by
#     docker-compose's image-ref substitution at stack-up time.
#   * Per-connector digests (DIGEST_GUARDIAN_CONNECTOR_*) → /opt/guardian/
#     connector-digests.env. Read by guardian-updater at runtime to
#     spawn dynamic instance containers. NOT a compose substitution.
#
# This satisfies the operator config-file separation principle
# (see CLAUDE.md § Operator config-file separation): .env holds
# credentials + compose substitutions; connector-digests.env holds
# per-instance image pins.
CORE_MANIFEST=$(printf '%s\n' "$DIGEST_MANIFEST" | grep -v '^DIGEST_GUARDIAN_CONNECTOR_' || true)
CONNECTOR_MANIFEST=$(printf '%s\n' "$DIGEST_MANIFEST" | grep '^DIGEST_GUARDIAN_CONNECTOR_' || true)

# Append the core manifest to .env (compose substitutions + version).
{
  echo ""
  echo "# ─── Digest manifest (managed by guardian-installer v$GUARDIAN_VERSION) ──"
  echo "# DO NOT EDIT BY HAND. Re-running the installer (or the in-app updater)"
  echo "# strips and rewrites these lines as a unit. To install a different"
  echo "# version, download that version's guardian-installer binary."
  echo "# Note (v0.6.7+): per-connector image pins moved to"
  echo "# $INSTALL_DIR/connector-digests.env. .env is now for credentials"
  echo "# + the 3 core compose-substitution digests only."
  printf '%s\n' "$CORE_MANIFEST"
} >> "$INSTALL_DIR/.env"

chmod 600 "$INSTALL_DIR/.env"

# Write the connector-digests.env file from scratch. Idempotent on
# repeat runs (full rewrite, not append). chmod 644 — the file is
# not sensitive (image digests are public refs), and guardian_updater
# reads it via a read-only bind-mount as a non-root user inside the
# container.
if [[ -n "$CONNECTOR_MANIFEST" ]]; then
  {
    echo "# Per-instance connector image pins (managed by"
    echo "# guardian-installer v$GUARDIAN_VERSION). Read by guardian-updater"
    echo "# at runtime to spawn dynamic connector instance containers."
    echo "#"
    echo "# v0.6.7+ — this file is the canonical home for"
    echo "# DIGEST_GUARDIAN_CONNECTOR_* values. Per the operator config-"
    echo "# file separation principle (CLAUDE.md), connector image refs"
    echo "# do NOT belong in .env: they aren't docker-compose"
    echo "# substitutions, they're runtime data for guardian-updater."
    echo "#"
    echo "# DO NOT EDIT BY HAND. Re-running the installer rewrites this"
    echo "# file from the version-pinned manifest."
    printf '%s\n' "$CONNECTOR_MANIFEST"
  } > "$INSTALL_DIR/connector-digests.env"
  chmod 644 "$INSTALL_DIR/connector-digests.env"
  _connector_count=$(printf '%s\n' "$CONNECTOR_MANIFEST" | grep -c '^DIGEST_' || true)
else
  # No connector digests in the manifest — older customer release, or
  # dev installer that didn't bundle them yet. Create an empty
  # placeholder so the volume mount in docker-compose doesn't fail.
  {
    echo "# Per-instance connector image pins (v0.6.7+). This file is"
    echo "# empty because the installer binary's embedded manifest did"
    echo "# not include DIGEST_GUARDIAN_CONNECTOR_* entries. guardian-"
    echo "# updater will fall back to /host/.env (legacy path) or"
    echo "# tag-pinning. Re-run a newer installer to populate."
  } > "$INSTALL_DIR/connector-digests.env"
  chmod 644 "$INSTALL_DIR/connector-digests.env"
  _connector_count=0
fi

_core_count=$(printf '%s\n' "$CORE_MANIFEST" | grep -c '^DIGEST_' || true)
ok "Digest manifest applied: GUARDIAN_VERSION=$GUARDIAN_VERSION + $_core_count core + $_connector_count connector digests"

# ─── v0.2.x → v0.3.x migration: stop the stack BEFORE compose up ──────
# When a v0.2.x install is upgrading, the existing containers are
# still running with tag-based image refs. The new compose has
# digest-based image refs. `docker compose up -d --remove-orphans`
# WILL recreate them — but we want a clean stop first to:
#   (a) avoid the racy window where the old and new copies of a
#       service both try to bind the same host ports during the swap
#   (b) give the operator a clear "stack stopped → starting fresh"
#       narrative in the install log instead of a confusing mix of
#       old-container exit messages and new-container start messages
if [[ "$V02X_MIGRATION" == "1" ]]; then
  info "v0.2.x → v$GUARDIAN_VERSION migration — stopping the existing stack first"
  ( cd "$INSTALL_DIR" && docker compose down --remove-orphans 2>&1 | tail -20 )
  ok "Existing stack stopped; preparing to start v$GUARDIAN_VERSION"
fi

# ─── Step 7: docker login + pull + up + wait healthy ──────────────────
info "Step 7/7 — pulling images and starting the stack"

cd "$INSTALL_DIR"

# docker login. --password-stdin keeps the token out of process listings
# and shell history.
echo "$GHCR_TOKEN" \
  | docker login "$GHCR_REGISTRY" -u "$GHCR_USER" --password-stdin
ok "Logged into $GHCR_REGISTRY"

if [ "$GUARDIAN_RUNTIME" = "podman" ]; then
  # PODMAN auth divergence: `docker login` here is `podman login` (via the
  # podman-docker shim), which writes credentials to Podman's auth file
  # (/run/containers/<uid>/auth.json). But our compose provider is the Docker
  # Compose v2 plugin binary, which authenticates from $DOCKER_CONFIG/config.json
  # (default /root/.docker/config.json) — a DIFFERENT file podman login does not
  # populate. Without this, `docker compose pull` fails with
  # "unable to retrieve auth token: invalid username/password: unauthorized"
  # on every install. Write the same creds in Docker config.json format where
  # the plugin reads them. (Verified live on RHEL 8.10 + podman 4.9.4.)
  mkdir -p /root/.docker
  _ghcr_auth="$(printf '%s:%s' "$GHCR_USER" "$GHCR_TOKEN" | base64 | tr -d '\n')"
  printf '{"auths":{"%s":{"auth":"%s"}}}\n' "$GHCR_REGISTRY" "$_ghcr_auth" \
    > /root/.docker/config.json
  chmod 600 /root/.docker/config.json
  unset _ghcr_auth
  ok "Registry creds mirrored to /root/.docker/config.json for the compose provider"
fi

# Pull all images. First pull on a fresh box can take several minutes
# (~1 GB total across the stack images on amd64).
info "Pulling images (this may take a few minutes on first install)…"
docker compose pull
ok "Images pulled"

# Bring the stack up.
info "Starting Guardian…"
docker compose up -d --remove-orphans
ok "Stack started"

# Wait for guardian-agent's healthcheck. The healthcheck verifies BOTH
# the Next.js UI and the embedded MCP, so green here means everything's
# actually serving traffic.
info "Waiting for guardian-agent to become healthy (up to ${HEALTH_TIMEOUT_SECS}s)…"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT_SECS ))
status="starting"
while [[ "$(date +%s)" -lt "$deadline" ]]; do
  status=$(docker inspect -f '{{.State.Health.Status}}' guardian_agent 2>/dev/null || echo missing)
  case "$status" in
    healthy)
      break
      ;;
    unhealthy)
      warn "guardian-agent reports unhealthy — recent logs:"
      docker compose logs --tail 20 guardian-agent >&2 || true
      ;;
  esac
  sleep 5
done

if [[ "$status" != "healthy" ]]; then
  echo ""
  warn "guardian-agent did not report healthy within ${HEALTH_TIMEOUT_SECS}s."
  warn "The stack is still running (restart policy keeps it up) and a slow first"
  warn "boot can finish shortly after this wait — check again in a minute with:"
  warn "    docker compose -f $INSTALL_DIR/docker-compose.yml ps"
  warn "If it stays unhealthy, inspect the logs:"
  warn "    docker compose -f $INSTALL_DIR/docker-compose.yml logs guardian-agent"
  warn "    docker compose -f $INSTALL_DIR/docker-compose.yml logs guardian-updater"
  warn "You can raise the wait with GUARDIAN_HEALTH_TIMEOUT_SECS=900 and re-run."
  exit 1
fi

ok "guardian-agent healthy"

# ─── Self-install: persist this binary to $INSTALL_DIR ───────────────
#
# After the stack is up, copy this installer binary itself to
# $INSTALL_DIR/ under the standard name (guardian-installer for release
# builds, guardian-installer-dev for dev builds — derived from this
# script's basename). This is what makes guardian-factory-reset's
# auto-recovery step work: post-wipe, factory-reset re-runs whichever
# binary it finds at $INSTALL_DIR/guardian-installer{,-dev}.
#
# Why post-install rather than pre: we only persist the binary if the
# install itself succeeded. A broken binary that managed to crash mid-
# install shouldn't get cached for future factory-resets to pick up.
#
# Pre-v0.5.6 the installer never self-copied; the binary lived
# wherever the operator ran it from (~/, /tmp/, a release-downloads
# folder). After the install completed, factory-reset couldn't find
# it and asked the operator to confirm "proceed without auto-recovery"
# — workable but a confusing UX surprise.
# Use INSTALLER_BINARY_PATH captured at the very top of this script
# (before the step-7 cd to $INSTALL_DIR). $0 here would be unreliable
# — by this point cwd has changed and a relative $0 won't resolve.
SELF_NAME="$(basename "$INSTALLER_BINARY_PATH")"
if [[ -f "$INSTALLER_BINARY_PATH" ]]; then
  # Only persist if the source path is OUTSIDE $INSTALL_DIR (avoid the
  # cp-self-onto-self error when re-running an already-persisted copy).
  case "$INSTALLER_BINARY_PATH" in
    "$INSTALL_DIR"/*) : ;;  # already there; no-op
    *)
      DEST="$INSTALL_DIR/$SELF_NAME"
      if cp "$INSTALLER_BINARY_PATH" "$DEST" 2>/dev/null && chmod +x "$DEST"; then
        ok "Persisted $SELF_NAME → $DEST (guardian-factory-reset will use this)"
      else
        warn "Could not persist $SELF_NAME to $DEST (continuing — factory-reset will warn but works)"
      fi
      ;;
  esac
else
  warn "Cannot self-persist installer: INSTALLER_BINARY_PATH=$INSTALLER_BINARY_PATH not found"
  warn "(factory-reset will hard-fail until you run a fresh installer)"
fi

# ─── Final message: tell the operator how to open it ─────────────────
# Try to find a non-loopback IPv4 the operator can hit from outside.
# Falls back to "localhost" if we can't determine one (e.g. inside a
# container with no network introspection).
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -z "$HOST_IP" ]] && HOST_IP="localhost"

cat <<EOF

${C_GREEN}  ✓ Guardian v$GUARDIAN_VERSION is running.${C_RESET}

  ${C_BOLD}Open in a browser:${C_RESET}    https://$HOST_IP:3000

  ${C_BOLD}Note:${C_RESET}                 The agent uses a self-signed cert. Your
                        browser will warn the first time; accept it
                        to proceed.

  ${C_BOLD}First-time login:${C_RESET}     Sign in with the default credentials:

                            username:  admin
                            password:  $GUARDIAN_DEFAULT_ADMIN_PASSWORD

                        v0.5.5+ — the password above is randomly
                        generated per install (no credential is baked
                        into any image). It also lives at
                        $INSTALL_DIR/.env under
                        GUARDIAN_DEFAULT_ADMIN_PASSWORD if you need
                        to retrieve it after closing this terminal.

                        The UI will then show a non-dismissible banner
                        and redirect you to /profile. Change the
                        password there — the server revokes your
                        session and you'll be asked to sign in again
                        with the new credentials. After that, the
                        GUARDIAN_DEFAULT_ADMIN_PASSWORD value above is
                        never consulted again (your operator-set
                        password lives encrypted in SecretStore).

  ${C_BOLD}Forgot password?${C_RESET}      Run from this host:
                            sudo $INSTALL_DIR/guardian-reset-admin-password

                        Interactive prompts ask for the new password
                        (no current-password required — the trust
                        boundary is your shell access to the host).
                        The script is a thin wrapper around the in-
                        container reset CLI; it handles the docker exec
                        and TTY plumbing for you.

  ${C_BOLD}Factory reset?${C_RESET}        Return to fresh-shipped state (wipes ALL
                        operator state — memories, instances, API keys,
                        audit log, sessions, jobs, notifications;
                        preserves .env so registry creds + KEK survive):
                            sudo $INSTALL_DIR/guardian-factory-reset

                        The script lists what it'll delete and asks you
                        to type 'FACTORY RESET' before doing anything.
                        --yes skips the prompt, --dry-run shows the plan
                        without wiping. Re-runs the installer at the end
                        so the stack is back up by the time the script
                        returns.

  ${C_BOLD}Configure providers:${C_RESET}  After first login + password change, set
                        up your model provider at /providers (Vertex
                        AI service-account JSON or Gemini API key).
                        Connector instances live at /instances.

  ${C_BOLD}Files on disk:${C_RESET}        $INSTALL_DIR/
                          ├── docker-compose.yml    (don't hand-edit)
                          └── .env                  (your secrets — chmod 600)

  ${C_BOLD}Useful commands:${C_RESET}
    docker compose -f $INSTALL_DIR/docker-compose.yml ps
    docker compose -f $INSTALL_DIR/docker-compose.yml logs -f guardian-agent
    docker compose -f $INSTALL_DIR/docker-compose.yml down

  ${C_BOLD}Future updates:${C_RESET}       download the new guardian-installer binary
                        from the GitHub Releases page and run it with
                        sudo on this host. The installer detects the
                        existing install at $INSTALL_DIR and preserves
                        your secrets, KEK material, and operator state
                        across upgrades — only image digests + the
                        docker-compose.yml are refreshed.

                            https://github.com/kite-production/guardian/releases

                        Guardian has no in-UI Update button by design;
                        upgrades happen via the installer only so the
                        operator stays in control of each upgrade point.

EOF
