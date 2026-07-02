#!/usr/bin/env bash
# Builds the ONE-FILE self-extracting installer: guardian-installer.sh
#
# Layout of the produced file:
#   [ header ]  ← build-guardian-installer.sh output, RUNTIME=auto (runtime is
#                 detected at install time; both compose variants embedded)
#   exit 0      ← stops bash before it reaches the binary payload
#   __GUARDIAN_PAYLOAD_BELOW__
#   [ payload ] ← gzipped tar of:
#                   images.tar.gz          (docker/podman save of every image)
#                   compose/docker-compose-x86_64
#                   compose/docker-compose-aarch64   (Compose v2 provider)
#
# The installer template locates the marker with awk, streams the payload out
# with `tail -n +N` (byte-safe), unpacks it, and drives its existing offline
# install path from images.tar.gz — no registry, no token, no download.docker.com.
#
# Inputs (env):
#   VERSION            required — e.g. 0.4.0
#   MANIFEST_PATH      required — release digest manifest (as build-guardian-installer.sh)
#   INSTALLER_OWNER    default socagents — GHCR org baked into the header/compose
#   IMAGES             space-separated image refs to save into the payload
#                      (ignored if IMAGES_TAR is set)
#   IMAGES_TAR         optional — pre-made images.tar.gz (test/CI convenience;
#                      bypasses `save`)
#   CONTAINER_CLI      docker|podman — used for `save` (default docker)
#   COMPOSE_VERSION    Docker Compose v2 provider version (default v2.29.7)
#   COMPOSE_SKIP_DOWNLOAD=1  stage tiny stub compose binaries (local tests only)
#   OUTPUT_DIR         default $REPO_ROOT/dist/installer
#   OUTPUT_NAME        default guardian-installer.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION="${VERSION:?VERSION required (e.g. 0.4.0)}"
MANIFEST_PATH="${MANIFEST_PATH:?MANIFEST_PATH required}"
INSTALLER_OWNER="${INSTALLER_OWNER:-socagents}"
CONTAINER_CLI="${CONTAINER_CLI:-docker}"
COMPOSE_VERSION="${COMPOSE_VERSION:-v2.29.7}"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/dist/installer}"
OUTPUT_NAME="${OUTPUT_NAME:-guardian-installer.sh}"
PAYLOAD_MARKER="__GUARDIAN_PAYLOAD_BELOW__"

if [[ -z "${IMAGES_TAR:-}" && -z "${IMAGES:-}" ]]; then
  echo "ERROR: set IMAGES (refs to save) or IMAGES_TAR (pre-made images.tar.gz)" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/payload/compose"

echo "==> 1/4 render header (RUNTIME=auto, owner=$INSTALLER_OWNER, v$VERSION)"
OUTPUT_DIR="$WORK" OUTPUT_NAME="header.sh" \
  VERSION="$VERSION" RUNTIME="auto" INSTALLER_OWNER="$INSTALLER_OWNER" \
  MANIFEST_PATH="$MANIFEST_PATH" \
  "$SCRIPT_DIR/build-guardian-installer.sh" >/dev/null
[[ -f "$WORK/header.sh" ]] || { echo "ERROR: header build produced no output" >&2; exit 1; }

echo "==> 2/4 stage Docker Compose v2 provider (amd64 + arm64)"
if [[ "${COMPOSE_SKIP_DOWNLOAD:-0}" == "1" ]]; then
  for a in x86_64 aarch64; do
    printf '#!/bin/sh\necho "docker-compose stub"\n' > "$WORK/payload/compose/docker-compose-$a"
    chmod +x "$WORK/payload/compose/docker-compose-$a"
  done
else
  for pair in "x86_64:linux-x86_64" "aarch64:linux-aarch64"; do
    a="${pair%%:*}"; asset="${pair##*:}"
    curl -fSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-${asset}" \
      -o "$WORK/payload/compose/docker-compose-$a"
    chmod +x "$WORK/payload/compose/docker-compose-$a"
  done
fi

echo "==> 3/4 assemble image payload"
if [[ -n "${IMAGES_TAR:-}" ]]; then
  cp "$IMAGES_TAR" "$WORK/payload/images.tar.gz"
else
  echo "    $CONTAINER_CLI save → gzip: $IMAGES"
  # shellcheck disable=SC2086
  $CONTAINER_CLI save $IMAGES | gzip > "$WORK/payload/images.tar.gz"
fi
[[ -s "$WORK/payload/images.tar.gz" ]] || { echo "ERROR: images.tar.gz empty" >&2; exit 1; }
( cd "$WORK/payload" && tar -cz images.tar.gz compose ) > "$WORK/payload.tgz"

echo "==> 4/4 concatenate header + marker + payload"
OUT="$OUTPUT_DIR/$OUTPUT_NAME"
{
  cat "$WORK/header.sh"
  printf '\nexit 0\n%s\n' "$PAYLOAD_MARKER"
  cat "$WORK/payload.tgz"
} > "$OUT"
chmod +x "$OUT"
( cd "$OUTPUT_DIR" && sha256sum "$OUTPUT_NAME" > "${OUTPUT_NAME}.sha256" )

# ── Validate: header portion is valid bash + marker appears exactly once. ──
_pl="$(awk -v m="$PAYLOAD_MARKER" '$0==m{print NR; exit}' "$OUT")"
[[ -n "$_pl" ]] || { echo "ERROR: payload marker not found in output" >&2; exit 1; }
if ! head -n $((_pl - 1)) "$OUT" | bash -n; then
  echo "ERROR: header portion has bash syntax errors" >&2; exit 1
fi
_mcount="$(grep -ac "^${PAYLOAD_MARKER}\$" "$OUT" || true)"
[[ "$_mcount" == "1" ]] || { echo "ERROR: marker line count is $_mcount (want 1)" >&2; exit 1; }

echo "✓ one-file installer built: $OUT ($(du -h "$OUT" | cut -f1))"
ls -lh "$OUT" "${OUT}.sha256"
