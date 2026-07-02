#!/usr/bin/env bash
# Builds the customer-facing single-file installer.
#
# Combines:
#   installer/guardian-installer.template.sh   (the script body)
#   installer/docker-compose.yml              (the compose YAML)
#   (reset-ui-password.sh retired in v0.4.0 — see notes below)
#   ${MANIFEST_PATH}                          (digest manifest, v0.3.0+)
# into a single executable `guardian-installer` file by substituting
# four markers in the template:
#
#   __INSTALLER_COMPOSE_DOCKER__       ← replaced with docker-compose.yml
#   __INSTALLER_COMPOSE_PODMAN__       ← replaced with podman-compose.yml
#   __INSTALLER_VERSION__              ← replaced with the literal version
#   (the __INSTALLER_RESET_PASSWORD_SH__ marker was retired in v0.4.0
#    along with the recovery script — see notes below)
#   __INSTALLER_DIGEST_MANIFEST__      ← replaced with the digest manifest
#                                        (v0.3.0+; tag-based fallback when absent)
#
# Usage:
#   VERSION=0.3.0 MANIFEST_PATH=/path/to/release-manifest-v0.3.0.env \
#     ./installer/build-guardian-installer.sh
#
# When MANIFEST_PATH is not set (e.g. local dev builds without a full
# release pipeline), an empty placeholder manifest is embedded — the
# installer detects this at runtime and prints a clear error. Customer
# release builds via release.yml ALWAYS pass MANIFEST_PATH.
#
# Why a Python one-liner for the substitution: sed and awk both have
# special-character handling problems with multi-kilobyte payloads
# that contain shell metacharacters. Python's str.replace is bulletproof.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# v0.5.3 — recovery utility paths. These are the canonical sources for
# the two host-side scripts that get embedded into the installer binary.
# Both can be overridden via env var for forks or vendored builds.
FACTORY_RESET_SH="${FACTORY_RESET_SH:-$SCRIPT_DIR/guardian-factory-reset.sh}"
RESET_ADMIN_SH="${RESET_ADMIN_SH:-$SCRIPT_DIR/guardian-reset-admin-password.sh}"

VERSION="${VERSION:-}"
if [[ -z "$VERSION" ]]; then
  echo "ERROR: VERSION env var required (e.g. VERSION=0.3.0 $0)" >&2
  exit 1
fi
# v0.4.0+: accept either semver (release builds) or 'dev-<short-sha>'
# (build.yml dev installer). Both shapes get baked into the binary's
# version string so operators can `guardian-installer --version` and
# see what they're running. Strict semver is enforced for release
# binaries via the v* tag gate in release.yml; this script accepts
# both forms because the dev-installer path doesn't have that gate.
if ! printf '%s' "$VERSION" | grep -Eq '^([0-9]+\.[0-9]+\.[0-9]+|dev-[0-9a-f]{7,40})$'; then
  echo "ERROR: VERSION must be N.N.N semver or 'dev-<short-sha>' (got: $VERSION)" >&2
  exit 1
fi

TEMPLATE="$SCRIPT_DIR/guardian-installer.template.sh"

# v0.2.93+ — RUNTIME selects the container runtime the generated installer
# targets. Default 'docker' (unchanged behavior; release.yml/build-dev-installer
# don't set it). 'podman' produces the RHEL/Podman-native installer:
# same template (runtime-branched at __INSTALLER_RUNTIME__) but the
# Podman compose variant (SELinux security_opt on the socket-mounting updater).
RUNTIME="${RUNTIME:-docker}"
case "$RUNTIME" in
  docker|podman|auto) : ;;
  *) echo "ERROR: RUNTIME must be 'docker', 'podman', or 'auto' (got: $RUNTIME)" >&2; exit 1 ;;
esac
# Both compose variants are ALWAYS embedded; the installer writes the one
# matching the runtime — fixed at build time for docker/podman builds, or
# detected at install time for the one-file 'auto' (self-extracting) build.
COMPOSE_DOCKER="$SCRIPT_DIR/docker-compose.yml"
COMPOSE_PODMAN="$SCRIPT_DIR/podman-compose.yml"

# INSTALLER_OWNER selects the GHCR org the generated installer targets: the
# default kite-production for the dev + private-release builds; socagents for
# the public customer installer (release.yml passes INSTALLER_OWNER=socagents).
# Baked into the template's __INSTALLER_OWNER__ markers (GHCR_OWNER + the
# release/upgrade URLs) AND the embedded compose image refs at build time, so
# the dev auto-deploy cycle is never repointed.
INSTALLER_OWNER="${INSTALLER_OWNER:-kite-production}"
if ! printf '%s' "$INSTALLER_OWNER" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9-]*$'; then
  echo "ERROR: INSTALLER_OWNER must be a GitHub org/user slug (got: $INSTALLER_OWNER)" >&2; exit 1
fi
# v0.4.0: reset-ui-password.sh retired (replaced by image-baked
# /app/cli/reset-admin.mjs — see template comment in the template
# for context). The RESET_SH path is no longer read.
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/dist}"
# v0.4.0+: OUTPUT_NAME selects the binary filename. release.yml uses
# the default (guardian-installer); build.yml passes
# OUTPUT_NAME=guardian-installer-dev. The script body is identical
# between the two — the divergence lives in the manifest, not here.
# Default output name: guardian-installer for docker, guardian-installer-podman
# for podman (CI passes OUTPUT_NAME explicitly for the dev variants).
if [[ "$RUNTIME" == "podman" ]]; then
  OUTPUT_NAME="${OUTPUT_NAME:-guardian-installer-podman}"
else
  OUTPUT_NAME="${OUTPUT_NAME:-guardian-installer}"
fi
OUTPUT="$OUTPUT_DIR/$OUTPUT_NAME"

# v0.3.0+: embed the digest manifest. If MANIFEST_PATH is unset or
# missing, fall through with a synthetic placeholder so the installer
# can produce a clear runtime error.
MANIFEST_PATH="${MANIFEST_PATH:-}"
if [[ -n "$MANIFEST_PATH" && -f "$MANIFEST_PATH" ]]; then
  MANIFEST_CONTENTS=$(cat "$MANIFEST_PATH")
  echo "ℹ Embedding digest manifest from $MANIFEST_PATH"
else
  echo "⚠ MANIFEST_PATH unset or missing (got: '$MANIFEST_PATH')." >&2
  echo "  The installer will be built with a placeholder manifest that" >&2
  echo "  fails loudly at install time. Customer-facing release builds" >&2
  echo "  must pass MANIFEST_PATH (release.yml does this automatically)." >&2
  MANIFEST_CONTENTS="# PLACEHOLDER MANIFEST — installer was built without MANIFEST_PATH.
# This is expected for local dev builds; customer releases always embed
# a real manifest captured from release.yml's image-push step.
GUARDIAN_VERSION=${VERSION}
DIGEST_MANIFEST_MISSING=1"
fi

[[ -f "$TEMPLATE" ]]          || { echo "ERROR: $TEMPLATE missing" >&2; exit 1; }
[[ -f "$COMPOSE_DOCKER" ]]    || { echo "ERROR: $COMPOSE_DOCKER missing" >&2; exit 1; }
[[ -f "$COMPOSE_PODMAN" ]]    || { echo "ERROR: $COMPOSE_PODMAN missing" >&2; exit 1; }
[[ -f "$FACTORY_RESET_SH" ]]  || { echo "ERROR: $FACTORY_RESET_SH missing (v0.5.3+)" >&2; exit 1; }
[[ -f "$RESET_ADMIN_SH" ]]    || { echo "ERROR: $RESET_ADMIN_SH missing (v0.5.3+)" >&2; exit 1; }

mkdir -p "$OUTPUT_DIR"

# Substitution. Run via `python3 - <<PY` so the script body lives
# inline (no separate .py file to ship). Note: VERSION + MANIFEST_CONTENTS
# are passed in via env var (not interpolation) so any future change in
# the template's escaping rules can't bleed into the build script.
VERSION="$VERSION" \
  RUNTIME="$RUNTIME" \
  TEMPLATE="$TEMPLATE" \
  COMPOSE_DOCKER="$COMPOSE_DOCKER" \
  COMPOSE_PODMAN="$COMPOSE_PODMAN" \
  FACTORY_RESET_SH="$FACTORY_RESET_SH" \
  RESET_ADMIN_SH="$RESET_ADMIN_SH" \
  MANIFEST_CONTENTS="$MANIFEST_CONTENTS" \
  INSTALLER_OWNER="$INSTALLER_OWNER" \
  python3 - "$OUTPUT" <<'PY'
import os
import sys

out_path = sys.argv[1]
version = os.environ["VERSION"]
runtime = os.environ["RUNTIME"]

with open(os.environ["TEMPLATE"]) as f:
    template = f.read()
with open(os.environ["COMPOSE_DOCKER"]) as f:
    compose_docker = f.read()
with open(os.environ["COMPOSE_PODMAN"]) as f:
    compose_podman = f.read()
with open(os.environ["FACTORY_RESET_SH"]) as f:
    factory_reset = f.read()
with open(os.environ["RESET_ADMIN_SH"]) as f:
    reset_admin = f.read()
manifest = os.environ["MANIFEST_CONTENTS"]

# Sanity: each placeholder must appear EXACTLY ONCE in the template.
# A second occurrence (e.g. in a docstring header that mentions the
# marker by name) gets blind-substituted by str.replace() and produces
# a corrupt installer where the embedded payload is duplicated and
# bash tries to execute the second copy as commands. Caught the hard
# way during v0.1.2 lab testing; same constraint applies to the v0.3.0
# digest-manifest marker added below.
#
# v0.5.3 — revived __INSTALLER_RESET_PASSWORD_SH__ (host-wrapper around
# /app/cli/reset-admin.mjs, NOT the pre-v0.4.0 parallel implementation
# that auto-detected from setup.json), and added a new
# __INSTALLER_FACTORY_RESET_SH__ for the operator-facing factory-reset
# utility. The wrapper pattern means the credential-write logic still
# lives in exactly one place (the in-container CLI); the host script
# just gives operators a clean invocation shape consistent with the
# factory-reset script's.
markers = (
    "__INSTALLER_COMPOSE_DOCKER__",
    "__INSTALLER_COMPOSE_PODMAN__",
    "__INSTALLER_VERSION__",
    "__INSTALLER_DIGEST_MANIFEST__",
    "__INSTALLER_FACTORY_RESET_SH__",
    "__INSTALLER_RESET_PASSWORD_SH__",
    "__INSTALLER_RUNTIME__",
)
for marker in markers:
    n = template.count(marker)
    if n != 1:
        print(f"ERROR: marker '{marker}' must appear EXACTLY ONCE in "
              f"the template (found {n}). Likely a documentation "
              "comment mentions it literally — rephrase so the literal "
              "token only appears at the substitution target.",
              file=sys.stderr)
        sys.exit(1)

# v0.3.0+: image refs in the compose are digest-pinned (`@${DIGEST_*}`),
# not version-tag-pinned. There's no VERSION_DEFAULT substitution any
# more — the compose is shipped verbatim and the digests come from .env.
# (Compose passes through unchanged; the substitution happens at runtime
# when docker compose interpolates ${DIGEST_*} from the customer's .env.)
# Pre-v0.3.0 compose files used `${GUARDIAN_VERSION:-VERSION_DEFAULT}`
# and we baked the version in here. That mechanism is gone in v0.3.0.

# Sanity: each embedded payload must not contain ITS OWN heredoc
# terminator, or it'll prematurely close the heredoc. Each payload
# uses its own terminator so they can't collide with each other.
embeddings = (
    (compose_docker, "_GUARDIAN_COMPOSE_DOCKER_END_",          "docker compose YAML"),
    (compose_podman, "_GUARDIAN_COMPOSE_PODMAN_END_",          "podman compose YAML"),
    (manifest,      "_GUARDIAN_DIGEST_MANIFEST_HEREDOC_END_",  "digest manifest"),
    (factory_reset, "_GUARDIAN_FACTORY_RESET_HEREDOC_END_",    "factory-reset script"),
    (reset_admin,   "_GUARDIAN_RESET_PASSWORD_HEREDOC_END_",   "reset-admin-password script"),
)
for payload, terminator, label in embeddings:
    if terminator in payload:
        print(f"ERROR: {label} contains '{terminator}' literal; "
              "rename the terminator in the template.", file=sys.stderr)
        sys.exit(1)

# Substitutions on the template.
out = template.replace("__INSTALLER_COMPOSE_DOCKER__", compose_docker)
out = out.replace("__INSTALLER_COMPOSE_PODMAN__", compose_podman)
out = out.replace("__INSTALLER_VERSION__", version)
out = out.replace("__INSTALLER_DIGEST_MANIFEST__", manifest)
out = out.replace("__INSTALLER_FACTORY_RESET_SH__", factory_reset)
out = out.replace("__INSTALLER_RESET_PASSWORD_SH__", reset_admin)
out = out.replace("__INSTALLER_RUNTIME__", runtime)
# Owner (GHCR org) is a GLOBAL token — it appears many times (GHCR_OWNER,
# the release/upgrade URLs, and every embedded compose image ref), so it is
# NOT in the single-occurrence `markers` tuple. Substitute it last, after the
# compose has been embedded, so both the template refs and the compose refs
# are covered in one pass.
out = out.replace("__INSTALLER_OWNER__", os.environ["INSTALLER_OWNER"])

# Sanity: every marker must have been substituted.
for marker in markers:
    if marker in out:
        print(f"ERROR: marker '{marker}' still present after build "
              f"(expected substitution didn't happen).", file=sys.stderr)
        sys.exit(1)
if "__INSTALLER_OWNER__" in out:
    print("ERROR: __INSTALLER_OWNER__ still present after build "
          "(INSTALLER_OWNER substitution didn't happen).", file=sys.stderr)
    sys.exit(1)

with open(out_path, "w") as f:
    f.write(out)

print(f"wrote {out_path} ({len(out):,} bytes)")
PY

chmod +x "$OUTPUT"

# Verify the output is at least syntactically valid bash.
if ! bash -n "$OUTPUT"; then
  echo "ERROR: generated guardian-installer has syntax errors" >&2
  exit 1
fi

# Compute SHA-256 alongside (matches the existing tarball pattern).
( cd "$OUTPUT_DIR" && sha256sum "$OUTPUT_NAME" > "${OUTPUT_NAME}.sha256" )

echo "✓ guardian-installer built for v$VERSION"
ls -lh "$OUTPUT" "${OUTPUT}.sha256"
