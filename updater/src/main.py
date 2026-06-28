"""
Guardian — on-prem updater service.

Runs as a sidecar container in the customer's compose stack. Drives
the host's docker daemon via the mounted /var/run/docker.sock and
shells out to `docker compose` (using the host install dir mounted at
/host) to swap services after a pull.

Why a separate service (not a guardian-agent route): during an update,
guardian-agent's container is replaced. If the updater code lived inside
that image, the user's progress stream would die mid-update. Living in
its own container — its own image, its own version — means the updater
keeps streaming even when guardian-agent restarts.

V1 scope (per product direction):
  - No rollback. If a post-update healthcheck times out, we surface the
    error and stop; recovery is a manual SSH job.
  - No data-volume snapshots. Customers may lose in-flight jobs/chats
    during an update; this is acceptable for the early version where
    the goal is "push-button-update-when-something-breaks."
  - Updater never updates itself. A future `update-updater.sh` ships
    with the install kit for the rare cases that's needed.

API:
  GET  /healthz                       no auth, container healthcheck
  GET  /api/v1/version/current        running container image versions
  GET  /api/v1/version/check          compare running vs GHCR latest
  GET  /api/v1/update/status          {in_progress: bool}
  POST /api/v1/update                 SSE stream of update progress

Auth: every endpoint except /healthz requires
  Authorization: Bearer <MCP_TOKEN>
where MCP_TOKEN matches the env var (same shared secret guardian-agent
uses for its own MCP coordination). If MCP_TOKEN is unset, all
authenticated routes return 401 — fail-closed by design.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import re
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import docker
import httpx
from docker.errors import DockerException, ImageNotFound, NotFound
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


# ─── Configuration ────────────────────────────────────────────────────
# All knobs come from env vars. Defaults match the customer compose.

REGISTRY = os.environ.get("GUARDIAN_REGISTRY", "ghcr.io")
OWNER = os.environ.get("GUARDIAN_OWNER", "kite-production")
REGISTRY_USER = os.environ.get("GUARDIAN_REGISTRY_USER", "")
REGISTRY_TOKEN = os.environ.get("GUARDIAN_REGISTRY_TOKEN", "")
MCP_TOKEN = os.environ.get("MCP_TOKEN", "")
HOST_INSTALL_DIR = os.environ.get("HOST_INSTALL_DIR", "/host")

# How long we'll wait for a service to become healthy after restart
# before declaring the update failed. Longer than the longest
# healthcheck.start_period in the customer compose.
HEALTHY_TIMEOUT_S = int(os.environ.get("HEALTHY_TIMEOUT_S", "240"))


# ─── /host/.env reads (v0.5.51) ───────────────────────────────────────
# Pre-v0.5.51, GUARDIAN_VERSION + DIGEST_GUARDIAN_* were passed to the
# guardian-updater container as `environment:` entries in the customer
# compose. That gave docker compose's config-hash a reason to recreate
# this container on every upgrade — even when guardian-updater's own
# image digest hadn't changed — because the resolved env block flipped
# any time the stack version flipped. v0.5.51 moves these reads to
# /host/.env at runtime so the updater's container config stays
# stable across stack upgrades that don't touch its image.
#
# Cache: parses /host/.env once per `_HOST_ENV_TTL_S` seconds. Long
# enough to amortize hot-path API calls (e.g. /api/v1/version/current
# fires on every observability-panel refresh), short enough that an
# operator's manual .env edit or a successful _apply_manifest_to_env
# call propagates within ~30s.
import time as _time_for_env_cache

_HOST_ENV_CACHE: dict[str, str] = {}
_HOST_ENV_CACHE_AT: float = 0.0
_HOST_ENV_TTL_S = 30.0


def _read_host_env() -> dict[str, str]:
    """Parse /host/.env, return {KEY: VALUE}. Cached with a 30s TTL.

    Bypassed (cache cleared) when `_apply_manifest_to_env` writes a
    new manifest — that path calls `_invalidate_host_env_cache()` to
    force the next read to re-parse fresh.

    Failure semantics: a missing /host/.env returns {} (callers
    handle missing keys gracefully). A malformed line is skipped
    with a debug log; we don't crash the updater over .env edits.
    """
    global _HOST_ENV_CACHE_AT
    now = _time_for_env_cache.monotonic()
    if _HOST_ENV_CACHE and (now - _HOST_ENV_CACHE_AT) < _HOST_ENV_TTL_S:
        return _HOST_ENV_CACHE
    env_path = pathlib.Path(HOST_INSTALL_DIR) / ".env"
    if not env_path.is_file():
        # Empty cache, freshly stamped — avoid hammering the FS while
        # /host isn't writable yet (compose timing edge case at boot).
        _HOST_ENV_CACHE_AT = now
        return _HOST_ENV_CACHE
    parsed: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key:
                continue
            # Strip surrounding quotes if present (the installer doesn't
            # quote, but operators editing by hand might).
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            parsed[key] = value
    except OSError as exc:
        log.warning("Failed reading %s: %s", env_path, exc)
    _HOST_ENV_CACHE.clear()
    _HOST_ENV_CACHE.update(parsed)
    _HOST_ENV_CACHE_AT = now
    return _HOST_ENV_CACHE


def _invalidate_host_env_cache() -> None:
    """Force the next _read_host_env() to re-parse fresh. Called by
    _apply_manifest_to_env after writing the new digest manifest so
    the in-process state reflects on-disk reality immediately."""
    global _HOST_ENV_CACHE_AT
    _HOST_ENV_CACHE_AT = 0.0


def _host_env_get(key: str, default: str | None = None) -> str | None:
    """Lookup `key` in /host/.env. Returns `default` if absent."""
    return _read_host_env().get(key, default)


def _running_guardian_version() -> str | None:
    """Currently-running stack version, sourced from /host/.env. Pre-
    v0.5.51 this came from `os.environ['GUARDIAN_VERSION']` — moved to
    .env read so changes (via _apply_manifest_to_env or operator hand-
    edit) propagate without a container restart."""
    return _host_env_get("GUARDIAN_VERSION")


def _stack_digest_env_var(service: str) -> str:
    """Map a compose service name to its DIGEST_GUARDIAN_<SVC> env-var
    name. Centralized so callers don't duplicate the casing rule."""
    return f"DIGEST_GUARDIAN_{service.replace('guardian-', '').upper().replace('-', '_')}"


def _stack_digest(service: str) -> str | None:
    """Currently-pinned digest for `service`, sourced from /host/.env.
    Returns None if missing."""
    return _host_env_get(_stack_digest_env_var(service))


def _connector_digest_env_var(connector_id: str) -> str:
    """Map a connector id to its DIGEST_GUARDIAN_CONNECTOR_<ID> env-var
    name. Centralized so callers don't duplicate the casing rule."""
    return f"DIGEST_GUARDIAN_CONNECTOR_{connector_id.upper().replace('-', '_')}"


# ─── /host/connector-digests.env reads (v0.6.7) ────────────────────────
# Pre-v0.6.7, DIGEST_GUARDIAN_CONNECTOR_* lived in /host/.env alongside
# service credentials + core compose-substitution digests. That broke
# the operator config-file separation principle (see CLAUDE.md):
#   - .env is for service credentials + the core compose-substitution
#     variables that docker-compose interpolates.
#   - Per-instance connector image refs are NOT compose substitutions;
#     they're runtime data this updater uses to spawn dynamic instance
#     containers. They belong in a dedicated file.
#
# v0.6.7+: read connector image digests from /host/connector-digests.env.
# Same env-format as .env (KEY=VALUE per line), but isolated. The
# installer writes this file when applying a release manifest, with one
# DIGEST_GUARDIAN_CONNECTOR_* key per published connector.
#
# Backward-compat: during the transition (operators upgrading from
# pre-v0.6.7 customer releases), the .env may still carry stale
# connector digests. We fall through to /host/.env if the new file
# is missing, AND log a one-shot deprecation warning so the operator
# (or their next installer re-run) cleans it up.

_HOST_CONNECTOR_DIGESTS_CACHE: dict[str, str] = {}
_HOST_CONNECTOR_DIGESTS_CACHE_AT: float = 0.0
_LEGACY_CONNECTOR_FALLBACK_WARNED: bool = False


def _read_host_connector_digests_env() -> dict[str, str]:
    """Parse /host/connector-digests.env, return {KEY: VALUE}. 30s TTL.

    Failure semantics: a missing file returns {} (callers handle
    missing keys gracefully; the legacy /host/.env path will be
    consulted as fallback by _connector_digest()).
    """
    global _HOST_CONNECTOR_DIGESTS_CACHE_AT
    now = _time_for_env_cache.monotonic()
    if (
        _HOST_CONNECTOR_DIGESTS_CACHE
        and (now - _HOST_CONNECTOR_DIGESTS_CACHE_AT) < _HOST_ENV_TTL_S
    ):
        return _HOST_CONNECTOR_DIGESTS_CACHE
    env_path = pathlib.Path(HOST_INSTALL_DIR) / "connector-digests.env"
    if not env_path.is_file():
        _HOST_CONNECTOR_DIGESTS_CACHE_AT = now
        return _HOST_CONNECTOR_DIGESTS_CACHE
    parsed: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            parsed[key] = value
    except OSError as exc:
        log.warning("Failed reading %s: %s", env_path, exc)
    _HOST_CONNECTOR_DIGESTS_CACHE.clear()
    _HOST_CONNECTOR_DIGESTS_CACHE.update(parsed)
    _HOST_CONNECTOR_DIGESTS_CACHE_AT = now
    return _HOST_CONNECTOR_DIGESTS_CACHE


def _invalidate_host_connector_digests_cache() -> None:
    """Force re-parse on next _read_host_connector_digests_env() call."""
    global _HOST_CONNECTOR_DIGESTS_CACHE_AT
    _HOST_CONNECTOR_DIGESTS_CACHE_AT = 0.0


# v0.6.12 build-updater.yml — this file is now in the dev cycle.
# Source changes here trigger build-updater.yml → push :dev →
# build-dev-installer.yml cascade → auto-deploy on guardian-vm.
# Pre-v0.6.12 updater changes only shipped via customer release.

# ─── Agent URL resolution (v0.6.11 — TLS-aware) ────────────────────────
# Pre-v0.6.11 guardian-updater hard-coded `http://guardian-agent:8080`
# for its agent calls (instance container_url updates, audit log
# writes, reconcile's `/api/v1/instances` fetch). v0.4.0+ the agent
# runs behind a TLS proxy on that port — HTTP requests fail with
# "Server disconnected without sending a response" (TLS handshake
# rejects plain HTTP). This is the bug that surfaced when the
# operator first tried POST /api/v1/connectors/reconcile.
#
# Per CLAUDE.md § "Rule 3 — Derive runtime state from observable
# evidence, not env vars that mid-process scripts mutate" (v0.4.0
# retrospective): we derive the agent URL scheme from observable
# state. The agent's TLS config lives in /host/.env under
# SSL_CERT_PEM. If that's non-empty, the agent serves HTTPS; if
# empty, HTTP. Same source of truth the agent's entrypoint uses
# to flip MCP_URL.

_DEFAULT_AGENT_URL = "https://guardian-agent:8080"


def _agent_tls_verify() -> bool:
    """Return whether to verify TLS for agent calls.

    v0.6.14 — the architectural truth: when guardian-updater hits
    the DEFAULT compose-internal URL (https://guardian-agent:8080),
    the agent's cert is the auto-generated self-signed one in
    /tls/cert.pem. That cert has no CA chain, so verify=True can
    NEVER succeed. The intra-cluster trust boundary is the docker
    network alias (only the legitimate guardian-agent container
    answers on that DNS name), not the cert chain.

    Pre-v0.6.14 the call sites read GUARDIAN_TLS_VERIFY with default
    "1" (verify=True). On every customer install + dev install
    this produced
        SSL: CERTIFICATE_VERIFY_FAILED: self-signed certificate
    Empirically reproduced on the v0.6.13 deploy of guardian-vm:
    the v0.6.13 always-https fix got us past the TLS handshake,
    only to land at the verify step.

    v0.6.14 default: verify=False when using the default agent URL.
    When the operator explicitly overrides GUARDIAN_AGENT_INTERNAL_URL
    to a CA-signed endpoint, they can also set GUARDIAN_TLS_VERIFY=1
    to opt in to chain validation.

    v0.6.18 (bug-family audit completion for the v0.6.17 KEK fix) —
    GUARDIAN_AGENT_INTERNAL_URL + GUARDIAN_TLS_VERIFY are read from
    /host/.env via _host_env_get(), NOT from os.environ. Same pattern
    as GUARDIAN_SECRET_KEK (v0.6.17), GUARDIAN_VERSION, and the
    DIGEST_GUARDIAN_* reads. Reason: the compose guardian-updater.environment
    block INTENTIONALLY doesn't pass them — per v0.5.51's stability
    invariant, any env-block change there forces guardian-updater
    container recreate on stack upgrade and defeats digest-pinning
    state preservation. So os.environ.get() would always return ""
    even when the operator had set the override in .env, silently
    making the escape hatch a no-op.
    """
    override = (_host_env_get("GUARDIAN_AGENT_INTERNAL_URL", "") or "").strip()
    if override:
        # Honor operator's verify preference for non-default URLs.
        return (_host_env_get("GUARDIAN_TLS_VERIFY", "1") or "1").strip() not in (
            "0", "false", "False", "no", "NO",
        )
    # Default URL is compose-internal self-signed; never verify.
    return False


def _resolve_agent_internal_url() -> str:
    """Return https://guardian-agent:8080 (or operator override).

    v0.6.13 — corrected from the v0.6.11 SSL_CERT_PEM-based detection.
    Per CLAUDE.md § "Rule 3 — Derive runtime state from observable
    evidence, not env vars that mid-process scripts mutate"
    (v0.4.0 retrospective):

    The agent's TLS state was never reliably signaled by .env's
    `SSL_CERT_PEM`. That env var is non-empty only when the operator
    EXPLICITLY pasted a cert at install time. In every customer
    install we've seen, the agent's entrypoint auto-generates a
    self-signed cert at `/tls/cert.pem` if SSL_CERT_PEM is empty,
    and the TLS proxy serves HTTPS unconditionally on port 8080.
    So guardian-agent:8080 is ALWAYS https from any compose-network
    client's perspective.

    The v0.6.11 SSL_CERT_PEM-based detection was the wrong signal:
    on dev-installer'd installs (where SSL_CERT_PEM is never set in
    .env), the helper picked http and the TLS proxy rejected the
    connection. "Server disconnected without sending a response."

    v0.6.13 default: always https. Operator override stays for
    legacy non-TLS configurations (none in practice today, but
    keeps the escape hatch).

    The TLS verify=False path that callers already use is still
    correct — the agent's self-signed cert isn't chain-validatable;
    trust boundary is at the compose network edge, not the cert.

    v0.6.18 — read GUARDIAN_AGENT_INTERNAL_URL from /host/.env via
    _host_env_get(), NOT from os.environ. See the matching note in
    _agent_tls_verify(). Same v0.5.51 env-stability invariant as
    GUARDIAN_SECRET_KEK (v0.6.17 fix). Pre-v0.6.18 the override
    branch was dead code: os.environ.get() always returned ""
    because the compose env block intentionally doesn't pass it
    through, so an operator's .env override was silently ignored.
    """
    override = (_host_env_get("GUARDIAN_AGENT_INTERNAL_URL", "") or "").strip()
    if override:
        return override.rstrip("/")
    return "https://guardian-agent:8080"


# httpx-equivalent verify flag for intra-cluster HTTPS calls. The
# agent's TLS cert is self-signed (per /tls/cert.pem); we don't
# verify here because the connection is within the compose
# internal network — trust boundary is at the docker network edge,
# not the cert chain. Used by the .get/.put/.post calls below.
_INTERNAL_HTTPS_VERIFY = False


def _connector_digest(connector_id: str) -> str | None:
    """Currently-pinned digest for the named connector.

    v0.6.7+ source of truth: /host/connector-digests.env. Falls back to
    /host/.env for the transition period (operators upgrading from
    pre-v0.6.7 customer releases will have stale connector digests in
    .env; we read them with a one-shot deprecation warning so the next
    installer re-run cleans them up).

    Returns None if missing in both sources.
    """
    global _LEGACY_CONNECTOR_FALLBACK_WARNED
    key = _connector_digest_env_var(connector_id)
    value = _read_host_connector_digests_env().get(key)
    if value:
        return value
    # Fallback: legacy /host/.env path. Log once per process; we don't
    # want to flood the logs while the operator's installer-upgrade
    # path lands.
    legacy = _host_env_get(key)
    if legacy and not _LEGACY_CONNECTOR_FALLBACK_WARNED:
        log.warning(
            "%s read from /host/.env (legacy pre-v0.6.7 path). The "
            "operator config-file separation principle (CLAUDE.md) "
            "moves connector digests to /host/connector-digests.env "
            "in v0.6.7+. Re-run guardian-installer to migrate.",
            key,
        )
        _LEGACY_CONNECTOR_FALLBACK_WARNED = True
    return legacy

# Maps compose service name → (GHCR package name, container_name).
# The container_name comes from the `container_name:` field in the
# customer compose; we look up containers by that. Order of this dict
# is the order updates are applied.
MANAGED_SERVICES: dict[str, tuple[str, str]] = {
    "guardian-agent": ("guardian-agent",   "guardian_agent"),
}


# ─── Logging ──────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("guardian-updater")


# ─── Globals ──────────────────────────────────────────────────────────
# Single-update mutex: prevents two browser tabs from triggering
# concurrent updates against the same daemon. The lock is module-level
# (process-scoped). The updater is single-instance per compose stack
# so this is sufficient.

_update_lock = asyncio.Lock()
_update_active = False
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ─── Helpers ──────────────────────────────────────────────────────────


def _registry_auth() -> "dict | None":
    """Explicit registry credentials for image pulls.

    Passing auth_config to images.pull / api.pull makes pulls work
    consistently across Docker AND Podman's Docker-compat socket. On
    Podman the daemon-side auth.json lookup diverges from dockerd, so a
    bare pull (relying on the creds `docker login` stored) can fail with
    401/403 even after a successful login; passing the creds explicitly
    sidesteps that. Harmless on Docker — same creds the daemon holds.
    Returns None when creds aren't configured (falls back to daemon store).
    """
    if REGISTRY_USER and REGISTRY_TOKEN:
        return {"username": REGISTRY_USER, "password": REGISTRY_TOKEN}
    return None


def _docker_client() -> docker.DockerClient:
    """
    Lazy-construct a Docker SDK client. Done per-request so failures
    surface as 503s rather than crashing the whole service at startup
    (e.g. when /var/run/docker.sock isn't mounted yet).

    Honors DOCKER_HOST explicitly (Podman points it at the podman socket;
    docker-py's from_env() can mis-parse some podman socket URLs) and pins
    version="auto" so API-version negotiation works against both dockerd
    and Podman's Docker-compatible endpoint. Defaults are unchanged for
    Docker hosts (no DOCKER_HOST set → from_env over /var/run/docker.sock).

    Note: version="auto" makes the SDK probe the daemon at construction, so a
    fully unreachable socket surfaces here rather than at first call. Callers
    already construct per-request and map exceptions to 503, so the failure is
    still returned as a clean 503 — just raised slightly earlier.
    """
    host = os.environ.get("DOCKER_HOST")
    if host:
        return docker.DockerClient(base_url=host, version="auto")
    return docker.from_env(version="auto")


# Memoized at first use; never changes for the lifetime of the
# container so a module-global is safe.
_COMPOSE_PROJECT_NAME: str | None = None


def _compose_project_name() -> str:
    """Return the docker compose project name THIS container belongs to.

    Why this is needed: when we shell out to `docker compose -f
    /host/docker-compose.yml ... up -d <service>` from inside the
    updater container, compose derives the project name from the
    directory containing the compose file → "host". But the host
    started the stack from /opt/guardian → project "guardian". The
    customer compose pins `container_name: guardian_agent` etc., so the
    existing project-"guardian" guardian_agent owns the name. Compose's
    project-"host" view tries to CREATE a fresh guardian_agent and 409s
    on the name conflict → restart fails with rc=1.

    Reading our own container's `com.docker.compose.project` label
    aligns the project name automatically, so it works for any
    install dir (customer's /opt/guardian → "guardian", a developer's
    ~/dev/guardian → "guardian", a CI worktree → whatever). No
    customer-side env var to set, no installer-side stamping needed.

    Falls back to "guardian" if label lookup fails for any reason —
    that's the right default for the customer installer path which
    is overwhelmingly the deployment shape this code runs in.
    """
    global _COMPOSE_PROJECT_NAME
    if _COMPOSE_PROJECT_NAME is not None:
        return _COMPOSE_PROJECT_NAME
    try:
        # /etc/hostname inside a container is the container's short id
        # (12-hex), which the docker socket can resolve to the full
        # container object.
        own_id = pathlib.Path("/etc/hostname").read_text().strip()
        client = _docker_client()
        c = client.containers.get(own_id)
        proj = c.labels.get("com.docker.compose.project")
        if proj:
            _COMPOSE_PROJECT_NAME = proj
            log.info("compose project detected from labels: %s", proj)
            return proj
    except Exception as exc:
        log.warning(
            "could not auto-detect compose project (%s); "
            "falling back to default 'guardian'",
            exc,
        )
    _COMPOSE_PROJECT_NAME = "guardian"
    return _COMPOSE_PROJECT_NAME


def _parse_image_ref(image_ref: str) -> tuple[str, str, str]:
    """
    Parse 'ghcr.io/kite-production/guardian-agent:1.2.0' into
    (registry, package, tag). Tolerates short forms like
    'guardian-agent' (no registry, no tag → defaults to 'latest').
    """
    if "/" in image_ref:
        first, rest = image_ref.split("/", 1)
        registry = first if "." in first else ""
        package = rest if registry else image_ref
    else:
        registry = ""
        package = image_ref
    if ":" in package:
        package, tag = package.rsplit(":", 1)
    else:
        tag = "latest"
    return registry, package, tag


def _semver_gt(a: str, b: str) -> bool:
    """True iff a > b as semver tuples. Strings must match N.N.N."""
    if not (_SEMVER_RE.match(a) and _SEMVER_RE.match(b)):
        return False
    return tuple(int(x) for x in a.split(".")) > tuple(
        int(x) for x in b.split(".")
    )


def _current_version_for(service: str) -> dict:
    """
    Inspect the running container for `service` and return its version.
    Returns {service, image, version, digest, container_id, running}
    where `version` is the parsed tag (e.g. "1.2.0") or None if the
    container isn't running or its image has no semver tag.

    v0.3.0+: also returns `digest` — the sha256:... content digest of
    the running image, sourced from the image's RepoDigests if the
    image was pulled (vs. built locally). For dev/CI builds with no
    RepoDigests entry, returns None for digest. The /observability/connectors
    panel uses this to show a "running digest" column.
    """
    package, container_name = MANAGED_SERVICES[service]
    client = _docker_client()
    try:
        c = client.containers.get(container_name)
    except NotFound:
        return {
            "service": service,
            "image": None,
            "version": None,
            "digest": None,
            "container_id": None,
            "running": False,
        }
    image_tags = c.image.tags or []
    image_ref = image_tags[0] if image_tags else (c.image.id or "")
    _, _, tag = _parse_image_ref(image_ref)

    # v0.3.0+: extract digest from RepoDigests. Format is
    # ['ghcr.io/.../package@sha256:abc...', ...]. Multiple entries
    # possible if the image was tagged from multiple repos; pick the
    # first that matches our REGISTRY/OWNER/package shape.
    digest: str | None = None
    repo_digests = c.image.attrs.get("RepoDigests") or []
    expected_prefix = f"{REGISTRY}/{OWNER}/{package}@"
    for rd in repo_digests:
        if rd.startswith(expected_prefix):
            digest = rd.split("@", 1)[1]
            break
    if digest is None and repo_digests:
        # Fallback: take the first RepoDigest's hash even if the prefix
        # doesn't match (e.g. operator built locally with different tag).
        digest = repo_digests[0].split("@", 1)[1] if "@" in repo_digests[0] else None

    return {
        "service": service,
        "image": image_ref,
        # Don't return non-semver tags as `version` — they confuse the
        # comparison logic. Customers running off `:latest` for some
        # reason will see version=None and `update=False`.
        "version": tag if _SEMVER_RE.match(tag) else None,
        "digest": digest,
        "container_id": c.short_id,
        "running": c.status == "running",
    }


async def _latest_version_for(package: str) -> str | None:
    """
    Hit GHCR's package-versions endpoint to find the highest semver
    tag. Returns 'N.N.N' string, or None if no auth/no tags/error.

    Endpoint:
      GET /orgs/{owner}/packages/container/{package}/versions
    Requires Bearer auth with read:packages scope (the customer's
    GUARDIAN_REGISTRY_TOKEN — same one docker uses to pull).
    """
    if not REGISTRY_TOKEN:
        log.warning("GUARDIAN_REGISTRY_TOKEN unset; cannot query GHCR.")
        return None
    url = (
        f"https://api.github.com/orgs/{OWNER}"
        f"/packages/container/{package}/versions"
    )
    headers = {
        "Authorization": f"Bearer {REGISTRY_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            versions = r.json()
    except httpx.HTTPError as e:
        log.error("GHCR API error for %s: %s", package, e)
        return None

    # GHCR's `versions` list has many entries (one per pushed digest);
    # each carries .metadata.container.tags. Flatten and pick the
    # highest semver tag. Non-semver tags (latest, 1.2, etc.) are
    # ignored intentionally — the floating tags can shift unexpectedly.
    semver_tags: list[tuple[int, int, int]] = []
    for v in versions:
        tags = (
            (v.get("metadata") or {}).get("container", {}).get("tags") or []
        )
        for t in tags:
            if _SEMVER_RE.match(t):
                semver_tags.append(tuple(int(x) for x in t.split(".")))
    if not semver_tags:
        return None
    semver_tags.sort(reverse=True)
    return ".".join(str(x) for x in semver_tags[0])


# ─── v0.3.0+ manifest-driven update helpers ─────────────────────────────

async def _latest_release_version() -> str | None:
    """Return the highest semver tag published as a GitHub Release.

    v0.3.0+: this replaces _latest_version_for() (which queried GHCR
    package-versions) as the primary mechanism for "what version is
    available?". The reason for the switch:
      - GHCR carries every pushed image, including pre-release CI builds
        and manual debug pushes. Tags there don't always correspond to
        a customer-installable release.
      - GitHub Releases carry exactly the customer-installable releases
        (one Release per `release.yml` run on a v*.*.* tag push). The
        manifest needed for the upgrade is attached as a Release asset.

    So: ask GitHub Releases "what's the latest version?", then fetch
    its manifest. One question, one source of truth.

    Returns 'N.N.N' string or None on error.
    """
    if not REGISTRY_TOKEN:
        log.warning("GUARDIAN_REGISTRY_TOKEN unset; cannot query GitHub.")
        return None
    url = f"https://api.github.com/repos/{OWNER}/guardian/releases/latest"
    headers = {
        "Authorization": f"Bearer {REGISTRY_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            release = r.json()
    except httpx.HTTPError as e:
        log.error("GitHub Releases API error: %s", e)
        return None
    tag = release.get("tag_name", "").lstrip("v")
    if not _SEMVER_RE.match(tag):
        log.warning("Latest release tag is not semver: %r", tag)
        return None
    return tag


async def _fetch_release_manifest(version: str) -> dict[str, str] | None:
    """Fetch release-manifest-vX.Y.Z.env from the GitHub Release for
    `version` and parse it into a dict of env-var-style key→value.

    Returns None on any error (network, missing asset, parse failure).
    The caller decides what to surface as an SSE error event.

    Authoritative source for digest values during in-app updates. The
    same manifest is embedded in the guardian-installer binary for fresh
    installs; this fetcher is the upgrade path's equivalent.
    """
    if not REGISTRY_TOKEN:
        log.warning("GUARDIAN_REGISTRY_TOKEN unset; cannot fetch manifest.")
        return None
    asset_name = f"release-manifest-v{version}.env"
    download_url = (
        f"https://github.com/{OWNER}/guardian/releases/download/"
        f"v{version}/{asset_name}"
    )
    headers = {
        # Release assets allow Bearer token auth for private repos.
        "Authorization": f"Bearer {REGISTRY_TOKEN}",
        "Accept": "application/octet-stream",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(download_url, headers=headers)
            r.raise_for_status()
            content = r.text
    except httpx.HTTPError as e:
        log.error("Manifest fetch error for v%s: %s", version, e)
        return None

    # Parse env-style. Skip blank lines and # comments. Each remaining
    # line should be KEY=VALUE; we split on first `=` only because
    # digest values like sha256:... don't contain `=`.
    parsed: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            log.warning("Skipping malformed manifest line: %r", line)
            continue
        k, v = line.split("=", 1)
        parsed[k.strip()] = v.strip()

    # Validate required keys are present. We need at minimum
    # GUARDIAN_VERSION + 3 stack digests; per-instance connectors are
    # validated by guardian-updater at runtime (look up DIGEST_GUARDIAN_CONNECTOR_*
    # only when an instance is created). If the stack-tier validation
    # fails, the manifest is corrupted and we shouldn't proceed.
    required = [
        "GUARDIAN_VERSION",
        "DIGEST_GUARDIAN_AGENT",
        "DIGEST_GUARDIAN_UPDATER",
        "DIGEST_GUARDIAN_BROWSER",
    ]
    missing = [k for k in required if k not in parsed]
    if missing:
        log.error("Manifest for v%s is missing required keys: %s",
                  version, missing)
        return None
    if parsed["GUARDIAN_VERSION"] != version:
        log.error("Manifest version mismatch: asked for v%s, got v%s",
                  version, parsed["GUARDIAN_VERSION"])
        return None
    return parsed


def _apply_manifest_to_env(manifest: dict[str, str]) -> None:
    """Mirror the guardian-installer's .env-update logic: strip stale
    GUARDIAN_VERSION + DIGEST_GUARDIAN_* lines from /host/.env, then
    append the new manifest as a clean block.

    The updater operates on /host/.env (the customer's install dir
    bind-mounted read-write). Read-only mode is incompatible with this
    operation — see the note on the volume mount in installer/docker-compose.yml.
    """
    env_path = pathlib.Path(HOST_INSTALL_DIR) / ".env"
    if not env_path.is_file():
        raise RuntimeError(
            f"{env_path} not found — updater cannot apply manifest. "
            "Verify /host is mounted read-write in the updater compose service."
        )

    # Read existing content, strip stale lines.
    existing = env_path.read_text()
    kept_lines: list[str] = []
    for line in existing.splitlines():
        # Match the same patterns the installer strips: lines starting
        # with GUARDIAN_VERSION= or DIGEST_GUARDIAN_ (with the trailing _
        # ensuring we don't false-positive on GUARDIAN_VERSION_<other>).
        if line.startswith("GUARDIAN_VERSION="):
            continue
        if line.startswith("DIGEST_GUARDIAN_"):
            continue
        kept_lines.append(line)

    # Trim trailing blank lines from the original (they'd accumulate
    # otherwise across repeat updates) and ensure exactly one
    # separator before the manifest block.
    while kept_lines and not kept_lines[-1].strip():
        kept_lines.pop()

    new_lines = list(kept_lines) + [
        "",
        f"# ─── Digest manifest (managed by guardian-updater "
        f"v{manifest['GUARDIAN_VERSION']}) ──",
        "# DO NOT EDIT BY HAND. Re-running guardian-installer or the in-app "
        "updater",
        "# strips and rewrites these lines as a unit.",
    ]
    # Preserve a deterministic order for diff-readability.
    ordered_keys = ["GUARDIAN_VERSION"] + sorted(
        k for k in manifest if k.startswith("DIGEST_GUARDIAN_")
    )
    for k in ordered_keys:
        if k in manifest:
            new_lines.append(f"{k}={manifest[k]}")

    new_lines.append("")  # trailing newline
    env_path.write_text("\n".join(new_lines))
    # v0.5.51 — invalidate the in-process /host/.env cache so the next
    # _running_guardian_version() / _stack_digest() / _connector_digest()
    # call sees the freshly-applied values, not a stale cache hit.
    _invalidate_host_env_cache()
    log.info("Applied manifest v%s to %s (%d digest entries)",
             manifest["GUARDIAN_VERSION"], env_path,
             sum(1 for k in manifest if k.startswith("DIGEST_GUARDIAN_")))


async def _pull_streaming(
    package: str, ref: str, service_name: str,
) -> AsyncGenerator[dict, None]:
    """
    Pull `<REGISTRY>/<OWNER>/<package>` at the given ref (a tag like
    "1.3.0" OR a digest like "sha256:abc...") and yield progress events
    suitable for SSE forwarding. Each event is a dict like:
      {
        "service": "guardian-agent",
        "package": "guardian-agent",
        "ref": "sha256:abc..." or "1.3.0",
        "ref_kind": "digest" | "tag",
        "raw": {"status": "Downloading", "id": "abc123",
                "progressDetail": {"current": 12345, "total": 67890}},
      }

    v0.3.0+: digest pulls use the `name@digest` form (set as repository,
    no tag arg). Tag pulls keep the existing (repository, tag) shape.
    docker-py's `client.api.pull()` accepts both — when the repository
    string contains `@`, the tag arg is ignored.

    docker-py's pull() returns a blocking generator of the dockerd
    pull-event JSON; we run it in a thread and bridge to asyncio via
    a queue so we don't block the event loop.
    """
    client = _docker_client()
    repository = f"{REGISTRY}/{OWNER}/{package}"
    is_digest = ref.startswith("sha256:")
    ref_kind = "digest" if is_digest else "tag"

    # docker-py's `pull(repository, tag)` builds the image reference as
    # `repository:tag` (or `repository@digest` if repository has `@`).
    # For digest pulls we pre-join into the repository arg; for tag
    # pulls we pass them separately (existing v0.2.x behavior).
    if is_digest:
        pull_repository = f"{repository}@{ref}"
        pull_tag = None
    else:
        pull_repository = repository
        pull_tag = ref

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    SENTINEL = object()

    def _producer():
        try:
            for event in client.api.pull(
                repository=pull_repository, tag=pull_tag,
                stream=True, decode=True,
                auth_config=_registry_auth(),
            ):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as e:
            # Podman's Docker-compat socket does not always implement the
            # Moby streaming-pull event protocol the way dockerd does, so the
            # streaming pull above can fail where a plain pull would succeed.
            # Fall back once to the non-streaming high-level pull (same auth)
            # and synthesize a completion event so the UI still progresses.
            # Harmless on Docker — only reached when streaming actually fails.
            try:
                ref = f"{pull_repository}:{pull_tag}" if pull_tag else pull_repository
                client.images.pull(ref, auth_config=_registry_auth())
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"status": f"pulled {ref} (non-streaming fallback)"},
                )
            except Exception as e2:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"error": f"{e} | non-streaming fallback also failed: {e2}"},
                )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

    loop.run_in_executor(None, _producer)

    while True:
        event = await queue.get()
        if event is SENTINEL:
            break
        yield {
            "service": service_name,
            "package": package,
            "ref": ref,
            "ref_kind": ref_kind,
            "raw": event,
        }


def _compose_base_args() -> list[str]:
    """Common flags shared by every compose subprocess we spawn."""
    return [
        "docker", "compose",
        # --project-name aligns with the project we're a member of so
        # compose recognizes the existing containers as ours. Without
        # this, compose derives the project from the compose-file
        # directory ("/host" inside us) and treats the running stack
        # as a different project, which then collides on container_name
        # pins. See _compose_project_name() for the full story.
        "--project-name", _compose_project_name(),
        "-f", f"{HOST_INSTALL_DIR}/docker-compose.yml",
        "--env-file", f"{HOST_INSTALL_DIR}/.env",
    ]


def _compose_up_services(services: list[str]) -> tuple[int, str]:
    """
    Run `docker compose ... up -d --no-deps <services>` in the host
    install dir. Returns (exitcode, combined_output).

    Used by the update flow (POST /api/v1/update) — `up -d` is the
    right verb there because that's where compose detects new image
    tags pulled by the updater and recreates the containers with
    them. For containers whose config didn't change, `up -d` is a
    no-op, which is what we want during an update.

    NOT the right verb for the restart endpoint — that needs to
    bounce the container even when nothing about its config has
    changed, so the entrypoint re-runs (re-reads mounted files,
    re-templates configs, etc.). Use `_compose_restart_service` for
    that path.

    CRITICAL: never include 'guardian-updater' in `services` — that
    would recreate THIS container mid-update and kill the SSE stream
    we're feeding the UI. Compose only acts on the services listed.
    """
    if "guardian-updater" in services:
        raise ValueError("refusing to recreate self")
    cmd = _compose_base_args() + ["up", "-d", "--no-deps", *services]
    log.info("compose up: %s", " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=180,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _compose_restart_service(service: str) -> tuple[int, str]:
    """
    Run `docker compose ... restart <service>` in the host install dir.
    Returns (exitcode, combined_output).

    Used by the restart endpoint (POST /api/v1/services/{svc}/restart).
    `restart` (NOT `up -d`) is the right verb here: it kills the main
    process inside the existing container with SIGTERM and starts it
    back up, which means the image entrypoint runs again. That's what
    we need for services whose entrypoint re-reads mounted files on
    every startup (e.g. guardian-agent re-reading regenerated TLS
    material under /tls/).

    `up -d --no-deps` would be a no-op here for an already-running
    healthy container — compose sees no config diff and exits 0 with
    "Container guardian_agent Running". The endpoint would return 200
    but nothing actually restarted (silent failure of the user's
    actual intent).

    CRITICAL: 'guardian-updater' is rejected upstream by the route
    handler — same reason as _compose_up_services.
    """
    cmd = _compose_base_args() + ["restart", service]
    log.info("compose restart: %s", " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


async def _wait_healthy(service: str, timeout_s: int = HEALTHY_TIMEOUT_S) -> bool:
    """
    Poll the docker daemon until `service`'s container reports healthy
    (or `running` for containers without a healthcheck). Returns True
    on healthy, False on timeout.

    We deliberately re-fetch the container each iteration because
    `docker compose up -d` replaces it — the previous Container
    object's id becomes stale.
    """
    _, container_name = MANAGED_SERVICES[service]
    client = _docker_client()
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        try:
            c = client.containers.get(container_name)
            state = c.attrs.get("State") or {}
            health = (state.get("Health") or {}).get("Status")
            if health == "healthy":
                return True
            # Containers without healthchecks: accept "running".
            if health is None and state.get("Status") == "running":
                return True
        except NotFound:
            # Container was just torn down — keep polling for the
            # replacement to come up.
            pass
        await asyncio.sleep(2)
    return False


def _docker_login() -> bool:
    """
    `docker login` against REGISTRY using the customer's PAT. Idempotent
    — safe to call on every startup. Returns True on success.

    Uses --password-stdin so the token never appears in `ps` output or
    in any process inspection of the updater container.
    """
    if not (REGISTRY_USER and REGISTRY_TOKEN):
        log.warning(
            "GUARDIAN_REGISTRY_USER/TOKEN unset; pulls will fail unless "
            "the host's docker is already logged in.",
        )
        return False
    try:
        proc = subprocess.run(
            [
                "docker", "login", REGISTRY,
                "-u", REGISTRY_USER,
                "--password-stdin",
            ],
            input=REGISTRY_TOKEN.encode(),
            capture_output=True, timeout=15,
        )
    except Exception as e:
        log.error("docker login raised: %s", e)
        return False
    if proc.returncode == 0:
        log.info("docker login OK against %s", REGISTRY)
        return True
    log.error("docker login FAILED: %s", proc.stderr.decode(errors="replace"))
    return False


# ─── Lifespan ─────────────────────────────────────────────────────────


# v0.17.128 (#123) — how often the PERIODIC digest-drift reconcile runs.
# The v0.6.66 reconcile fired only at updater startup; but guardian-updater
# rarely restarts (its image isn't rebuilt on the dev cycle), so a connector
# pin that changes while it keeps running was never reconciled into the
# running container until the next restart — the cortex-xdr container went
# stale TWICE this way. A periodic loop closes that gap. Override via
# GUARDIAN_UPDATER_RECONCILE_INTERVAL_S; default 5 minutes.
PERIODIC_RECONCILE_INTERVAL_S = float(
    os.environ.get("GUARDIAN_UPDATER_RECONCILE_INTERVAL_S", "300")
)


async def _periodic_reconcile(interval_s: float) -> None:
    """Run the full connector reconcile forever on a timer.

    Two complementary passes per tick (issue #42 — the v0.6.66/v0.17.128
    loop only did the first):

      1. ``reconcile_connector_containers()`` — ensure every enabled
         instance in the agent's store has a RUNNING container. This is the
         self-heal: a create-time start failure (transient docker/registry
         hiccup) used to leave the instance container-less forever because
         nothing started the missing container after the fact. Idempotent —
         already-running instances are skipped.
      2. ``_reconcile_connector_digest_drift()`` — recreate any RUNNING
         container whose image digest diverged from its pin.

    Order matters: start missing containers first (on the pinned digest, so
    they're born current), then digest-reconcile the rest. Each pass is
    error-isolated; a failure in one tick is logged and the loop continues.
    """
    while True:
        await asyncio.sleep(interval_s)
        try:
            cresult = await reconcile_connector_containers()
            started = cresult.get("reconciled") or []
            cfailed = cresult.get("failed") or []
            if started or cfailed:
                log.info(
                    "periodic container reconcile: started=%d skipped=%d failed=%d",
                    len(started), len(cresult.get("skipped") or []), len(cfailed),
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("periodic container reconcile errored: %s", exc)
        try:
            result = await _reconcile_connector_digest_drift()
            if result["recreated"] or result["failed"]:
                log.info(
                    "periodic digest-drift reconcile: drifted=%d recreated=%d "
                    "unchanged=%d failed=%d",
                    len(result["drifted"]), len(result["recreated"]),
                    len(result["unchanged"]), len(result["failed"]),
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("periodic digest-drift reconcile errored: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup tasks. v0.6.66 adds the digest-drift auto-reconcile.

    Sequence:
      1. `docker login` — needed for subsequent image pulls. Always
         runs synchronously before serving requests (the original
         contract since v0.1.x).
      2. Schedule an async digest-drift reconcile that fires ~30s
         after startup. Backgrounded because: (a) it does HTTP calls
         to ourselves + to the agent, which means we must be serving
         requests already; (b) the agent (which the recreate path
         calls back into for container_url tracking) takes 10-30s to
         come up after guardian-updater. The delay covers both.

    Why background rather than yield-wait: blocking startup on the
    drift reconcile would delay /healthz responses, which can fail
    docker-compose's healthcheck + cascade. Background-tasks fire
    asynchronously and any errors are logged + don't crash the
    process. Operators can call POST /api/v1/connectors/reconcile/digests
    if they want to wait for the result synchronously.
    """
    _docker_login()

    # v0.6.66 — fire-and-forget reconcile after a delay.
    # asyncio.create_task without awaiting lets us yield immediately.
    async def _delayed_boot_reconcile() -> None:
        try:
            await asyncio.sleep(30.0)  # let the agent finish booting
            # issue #42 — start any missing per-instance container first.
            # A create-time start failure used to leave the instance
            # container-less until the next updater restart; reconciling at
            # boot recovers it. Idempotent (running instances are skipped).
            log.info("startup: reconciling connector containers (start missing)")
            try:
                cresult = await reconcile_connector_containers()
                log.info(
                    "startup container reconcile: started=%d skipped=%d failed=%d",
                    len(cresult.get("reconciled") or []),
                    len(cresult.get("skipped") or []),
                    len(cresult.get("failed") or []),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("startup container reconcile errored: %s", exc)

            log.info("startup: running auto digest-drift reconcile")
            result = await _reconcile_connector_digest_drift()
            log.info(
                "digest-drift reconcile finished: "
                "drifted=%d recreated=%d unchanged=%d failed=%d",
                len(result["drifted"]),
                len(result["recreated"]),
                len(result["unchanged"]),
                len(result["failed"]),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "startup reconcile errored: %s",
                exc,
            )

    asyncio.create_task(_delayed_boot_reconcile())

    # v0.17.128 (#123) — and keep reconciling on a timer. The one-shot above
    # only catches state present at boot; the updater rarely restarts, so a
    # periodic sweep lands both missing-container recovery (#42) and pin
    # changes that happen between restarts.
    asyncio.create_task(_periodic_reconcile(PERIODIC_RECONCILE_INTERVAL_S))

    yield


app = FastAPI(
    lifespan=lifespan,
    title="guardian-updater",
    version="1.0.0",
    docs_url=None,        # no docs UI — internal API
    redoc_url=None,
    openapi_url=None,
)


# ─── Auth middleware ──────────────────────────────────────────────────


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Validate MCP_TOKEN bearer auth on every endpoint except /healthz."""
    if request.url.path == "/healthz":
        return await call_next(request)
    if not MCP_TOKEN:
        # Fail closed: never run unauthenticated even if the operator
        # forgot to set MCP_TOKEN. The compose default sets one.
        return JSONResponse(
            status_code=401,
            content={"detail": "MCP_TOKEN unset on updater; denying."},
        )
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            status_code=401, content={"detail": "missing bearer token"},
        )
    if auth.removeprefix("Bearer ") != MCP_TOKEN:
        return JSONResponse(
            status_code=401, content={"detail": "invalid token"},
        )
    return await call_next(request)


# ─── Routes ───────────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/version/current")
async def version_current():
    """Read currently-running image versions from the docker daemon."""
    try:
        return {svc: _current_version_for(svc) for svc in MANAGED_SERVICES}
    except DockerException as e:
        raise HTTPException(503, f"docker unavailable: {e}")


@app.get("/api/v1/version/check")
async def version_check():
    """
    Compare currently-running stack against the latest GitHub Release.

    v0.3.0+: this is now manifest-driven, not GHCR-tag-driven. Steps:
      1. Find the latest released version (highest `v*.*.*` tag with a
         GitHub Release). If we can't query GitHub, return None for
         latest and updates_available=False — the UI shows a graceful
         "couldn't reach GitHub" indicator instead of pretending we're
         current.
      2. If our running GUARDIAN_VERSION already matches latest, we're
         up to date at the version level. We still report per-service
         digest comparisons so the UI can show "v0.3.0 → v0.3.0 (no
         change)" rather than just being silent.
      3. Otherwise, fetch the manifest for the latest version and
         compare each service's current digest vs. target digest.
         updates_available is true iff at least one service's digest
         differs.

    Returns:
      {
        running_version: str | None,
        latest_version: str | None,
        updates_available: bool,
        services: {
          svc: {current_version, current_digest, target_digest,
                update: bool, running: bool},
          ...
        },
        checked_at: ISO timestamp,
        error: str | None  (set if the GitHub query failed)
      }
    """
    running_version = _running_guardian_version()
    services: dict[str, dict] = {}

    latest_version = await _latest_release_version()
    if not latest_version:
        # Can't reach GitHub. Still return per-service current state
        # so the UI's diagnostics aren't blank.
        for svc in MANAGED_SERVICES:
            try:
                cur = _current_version_for(svc)
            except DockerException as e:
                log.error("docker error reading %s: %s", svc, e)
                cur = {"version": None, "digest": None, "running": False}
            services[svc] = {
                "current_version": cur.get("version"),
                "current_digest": cur.get("digest"),
                "target_digest": None,
                "update": False,
                "running": cur.get("running", False),
            }
        return {
            "running_version": running_version,
            "latest_version": None,
            "updates_available": False,
            "services": services,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": "could not reach GitHub Releases API",
        }

    # Got a latest version — fetch its manifest to compare digests.
    target_manifest: dict[str, str] | None = None
    if latest_version != running_version:
        target_manifest = await _fetch_release_manifest(latest_version)

    any_update = False
    for svc, (package, _) in MANAGED_SERVICES.items():
        try:
            cur = _current_version_for(svc)
        except DockerException as e:
            log.error("docker error reading %s: %s", svc, e)
            cur = {"version": None, "digest": None, "running": False}
        # Map service name to manifest env-var name.
        # guardian-agent → DIGEST_GUARDIAN_AGENT, etc. (v0.5.51 centralized
        # in `_stack_digest_env_var`.)
        env_var = _stack_digest_env_var(svc)
        target_digest = target_manifest.get(env_var) if target_manifest else None
        update = bool(
            target_digest and cur.get("digest") != target_digest
        )
        services[svc] = {
            "current_version": cur.get("version"),
            "current_digest": cur.get("digest"),
            "target_digest": target_digest,
            "update": update,
            "running": cur.get("running", False),
        }
        if update:
            any_update = True

    return {
        "running_version": running_version,
        "latest_version": latest_version,
        "updates_available": any_update,
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }


@app.get("/api/v1/update/status")
async def update_status():
    """Whether an update is currently in progress on this updater."""
    return {"in_progress": _update_active}


def _sse(event: str, data: dict) -> bytes:
    """
    Format an SSE event. Each event MUST end with a blank line — that's
    how the SSE protocol delimits records. Newlines inside the JSON
    payload would also break the protocol; json.dumps escapes them.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@app.post("/api/v1/update")
async def update_apply():
    """
    Trigger a manifest-driven update.

    v0.3.0+ flow:
      1. Resolve target version from latest GitHub Release.
      2. Fetch release-manifest-vX.Y.Z.env from the GH Release.
      3. For each MANAGED_SERVICE, compare current digest vs target
         digest. If unchanged, skip (no recreate). Build to_update list.
      4. Pull each to-update image by digest (digest pulls are no-op
         when the digest is already in the local cache).
      5. Apply manifest to /host/.env (strip stale, append new).
      6. docker compose up -d --no-deps <to_update services>. Compose
         sees the new digests in .env, recreates only those services.
      7. Wait for healthy.

    Concurrent requests get rejected via _update_lock — only one
    update can run at a time per process.

    Event types streamed:
      phase           {phase: "checking" | "fetching_manifest" |
                       "comparing_digests" | "pulling" | "pulled" |
                       "applying_manifest" | "swapping" | "waiting_healthy" |
                       "complete" | "noop", service?, target?, target_version?}
      pull_progress   raw docker pull events with service/package/ref/ref_kind
      error           {phase, detail, ...}
    """
    global _update_active

    # Reject early so the client gets 409, not a stuck SSE stream.
    if _update_lock.locked():
        raise HTTPException(409, "update already in progress")

    async def stream() -> AsyncGenerator[bytes, None]:
        global _update_active
        async with _update_lock:
            _update_active = True
            try:
                # ── Phase 1: resolve target version. ─────────────────
                yield _sse("phase", {"phase": "checking"})
                target_version = await _latest_release_version()
                if not target_version:
                    yield _sse("error", {
                        "phase": "checking",
                        "detail": (
                            "could not reach GitHub Releases API. "
                            "Check GUARDIAN_REGISTRY_TOKEN scope + network "
                            "egress to api.github.com."
                        ),
                    })
                    return

                running_version = _running_guardian_version()
                if running_version == target_version:
                    yield _sse("phase", {
                        "phase": "noop",
                        "message": (
                            f"already at v{running_version} (latest)"
                        ),
                    })
                    yield _sse("phase", {"phase": "complete"})
                    return

                # ── Phase 2: fetch + validate the manifest. ─────────
                yield _sse("phase", {
                    "phase": "fetching_manifest",
                    "target_version": target_version,
                })
                manifest = await _fetch_release_manifest(target_version)
                if not manifest:
                    yield _sse("error", {
                        "phase": "fetching_manifest",
                        "detail": (
                            f"failed to fetch or validate "
                            f"release-manifest-v{target_version}.env from "
                            f"GitHub Release. The asset may be missing or "
                            f"the registry token may not have read access."
                        ),
                    })
                    return

                # ── Phase 3: compare digests, decide what to update. ─
                yield _sse("phase", {
                    "phase": "comparing_digests",
                    "target_version": target_version,
                })
                to_update: list[tuple[str, str, str]] = []
                for svc, (package, _) in MANAGED_SERVICES.items():
                    cur = _current_version_for(svc)
                    env_var = _stack_digest_env_var(svc)
                    target_digest = manifest.get(env_var)
                    if target_digest and cur.get("digest") != target_digest:
                        to_update.append((svc, package, target_digest))

                if not to_update:
                    # GUARDIAN_VERSION differs but no service's digest
                    # actually changed (e.g. release.yml retagged
                    # everything from the previous version with
                    # conditional rebuild). Apply the manifest anyway
                    # so .env reflects the new version label, but
                    # don't touch any container.
                    yield _sse("phase", {
                        "phase": "applying_manifest",
                        "target_version": target_version,
                        "note": "no digest changes; only version label updates",
                    })
                    _apply_manifest_to_env(manifest)
                    yield _sse("phase", {
                        "phase": "noop",
                        "message": (
                            f"v{running_version} → v{target_version}: "
                            "all service digests unchanged. .env updated, "
                            "containers not recreated."
                        ),
                    })
                    yield _sse("phase", {"phase": "complete"})
                    return

                # ── Phase 4: pull each changed image by digest. ──────
                for svc, package, target_digest in to_update:
                    yield _sse("phase", {
                        "phase": "pulling",
                        "service": svc,
                        "target": target_digest[:19] + "…",
                    })
                    async for ev in _pull_streaming(package, target_digest, svc):
                        yield _sse("pull_progress", ev)
                    yield _sse("phase", {
                        "phase": "pulled",
                        "service": svc,
                        "target": target_digest[:19] + "…",
                    })

                # ── Phase 5: apply the manifest to /host/.env. ───────
                # Done AFTER pulling so a pull failure leaves .env
                # intact (operators can retry without partial state).
                yield _sse("phase", {
                    "phase": "applying_manifest",
                    "target_version": target_version,
                })
                try:
                    _apply_manifest_to_env(manifest)
                except Exception as e:
                    yield _sse("error", {
                        "phase": "applying_manifest",
                        "detail": str(e),
                    })
                    return

                # ── Phase 6: swap services via `docker compose up -d`.
                # IMPORTANT ordering: MANAGED_SERVICES iteration order
                # is the order services are swapped (dependencies
                # first, guardian-agent last) so guardian-agent's
                # depends_on healthcheck sees its dependencies up
                # before it restarts. _compose_up_services respects
                # MANAGED_SERVICES iteration order.
                update_services = [s[0] for s in to_update]
                yield _sse("phase", {
                    "phase": "swapping",
                    "services": update_services,
                })
                rc, output = _compose_up_services(update_services)
                if rc != 0:
                    yield _sse("error", {
                        "phase": "swapping",
                        "exitcode": rc,
                        "detail": output[-2000:],
                    })
                    return

                # ── Phase 7: wait for each service to be healthy. ────
                for svc, _, _ in to_update:
                    yield _sse("phase", {
                        "phase": "waiting_healthy",
                        "service": svc,
                    })
                    healthy = await _wait_healthy(svc)
                    if not healthy:
                        yield _sse("error", {
                            "phase": "waiting_healthy",
                            "service": svc,
                            "detail": (
                                f"service {svc} did not become healthy "
                                f"within {HEALTHY_TIMEOUT_S}s"
                            ),
                        })
                        return

                # #CONN-F10 — record the completed stack update.
                await _audit_event(
                    "stack_update_applied",
                    status="success",
                    metadata={
                        "target_version": target_version,
                        "services_updated": update_services,
                    },
                )
                yield _sse("phase", {
                    "phase": "complete",
                    "target_version": target_version,
                    "services_updated": update_services,
                })

            except Exception as e:
                # Any unhandled exception is a service-level bug. Log
                # the traceback for ops, surface a sanitized message
                # to the UI.
                log.exception("update failed")
                yield _sse("error", {"detail": str(e)})
            finally:
                _update_active = False

    # Headers chosen for SSE: text/event-stream, no buffering, keep
    # connection alive. Cache-Control:no-cache prevents intermediaries
    # from holding events. X-Accel-Buffering:no is for nginx (no-op
    # if no proxy is in front, which is our default).
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/v1/services/{service}/restart")
async def restart_service(service: str):
    """Restart a single managed service.

    Used by guardian-agent when a managed service needs its entrypoint
    to re-run — e.g. to re-read regenerated TLS material or other
    mounted files written after the container last started.

    Calls `docker compose restart` (NOT `up -d`). The restart verb
    actually bounces the container — kills the main process with
    SIGTERM and starts it back up — so the image entrypoint runs
    again and re-reads any mounted files. `up -d` would be a no-op
    for an already-running healthy container with unchanged config
    (silent failure of the user's actual intent; pre-v0.1.19 bug).

    Refuses to act on guardian-updater (would kill self mid-call) and
    on services not in MANAGED_SERVICES (no need to expose arbitrary
    docker-compose action).
    """
    if service == "guardian-updater":
        return JSONResponse(
            status_code=400,
            content={"detail": "refusing to recreate self"},
        )
    if service not in MANAGED_SERVICES:
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"unknown service {service!r}",
                "known": sorted(MANAGED_SERVICES.keys()),
            },
        )

    try:
        rc, output = _compose_restart_service(service)
    except Exception as exc:
        log.exception("restart failed for %s", service)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )
    if rc != 0:
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"compose restart exited {rc}",
                "output": output[-2000:],
            },
        )
    # #CONN-F10 — record the managed-service restart.
    await _audit_event(
        "managed_service_restarted",
        target=f"service:{service}",
        status="success",
        metadata={"service": service},
    )
    return {"restarted": service, "output": output[-500:]}


# ─── Per-instance connector container lifecycle (v0.1.30+) ────────────
#
# Endpoints used by guardian-agent's /connectors UI (or future
# automation) to start/stop/restart per-instance connector
# containers introduced by the v0.2 architecture (see
# docs/spec-per-instance-connector-containers.md).
#
# Phase 1 (v0.1.30) ships these endpoints DORMANT — no connector
# instance has runtime: container yet, so the endpoints exist but
# operators don't hit them. Phase 2 (v0.1.31) flips the web
# connector to runtime: container, which is the first real
# exercise of this code path.
#
# Naming convention (matches docs/spec-per-instance-connector-containers.md
# §D6):
#
#   container_name = f"guardian-connector-{connector_id}-{instance_name}"
#
#   image          = f"{REGISTRY}/{OWNER}/guardian-connector-{connector_id}:{VERSION}"
#                    where VERSION defaults to GUARDIAN_VERSION env var
#                    (= the running stack's version), falls back to
#                    "latest" if unset.
#
# After start/stop/restart, the endpoint POSTs back to the agent's
# MCP at PUT /api/v1/instances/{id}/container_url to update the
# routing entry the loader's container branch reads at tool-call time.

# Connectors that have a guardian-connector-<id> image published. Used
# to validate the connector_id path param. Mirrors the per-connector
# images in release.yml (P1.4); when a new connector ships, add its
# id here.
#
# v0.3.1 — cortex-docs added. Module-style today (style: "module" in
# connector.yaml), so per-instance container creation isn't exercised
# from here, but the image IS published so the digest manifest can
# pin it. Future container-mode flip is automatic once we add the
# style: "container" override; no additional code changes needed
# beyond this set membership.
# The connector roster the updater is allowed to spawn containers for.
# The agent's container-start path posts to guardian-updater's
# /api/v1/connectors/<id>/instances/<name>/start which validates
# connector_id against THIS set. A connector missing here → updater
# returns 400 "unknown connector_id" → no container spawns → tool calls
# later error with "container_url — guardian-updater hasn't started the
# container yet". Adding a connector to bundles/spark/connectors/ + the
# manifest + the marketplace card REQUIRES adding it here too (the
# new-connector checklist in docs/CICD.md lists this file).
#
# Guardian XSOAR pivot: roster is xsoar + cortex-docs + web. The former
# cortex-xdr / cortex-content connectors were removed; xsiam was re-added
# in v0.2.27 (Cortex XSIAM investigation + EDR response).
KNOWN_CONNECTORS = {
    "xsoar",
    "cortex-docs",
    "web",
    "xsiam",
}

# v0.2.42 — emulated services (kind:service). Unlike connectors, a
# service container PUBLISHES a host port so an EXTERNAL system (e.g.
# an XSOAR server) reaches it; the agent never calls it. The start
# endpoint accepts these ids the same way it accepts KNOWN_CONNECTORS,
# and publishes the ports from the request body's `service_ports`.
KNOWN_SERVICES = {
    "splunk-mimic",
}

# Fallback published ports for a service when the start request carries
# no `service_ports` AND no existing container exists to inherit from —
# e.g. a boot-time reconcile spawning a MISSING service container. The
# updater has no connector.yaml to read, so this mirrors the well-known
# default. connector.yaml's service.ports stays the source of truth for
# the operator-create path (which passes service_ports through the body);
# this map only covers the paths where ports aren't otherwise available.
SERVICE_DEFAULT_PORTS: dict[str, list[dict]] = {
    "splunk-mimic": [
        {"container_port": 8089, "host_port": 8089, "protocol": "tcp"},
    ],
}


def _is_known_id(connector_id: str) -> bool:
    """True for any bundle connector OR emulated service id (v0.2.42)."""
    return connector_id in KNOWN_CONNECTORS or connector_id in KNOWN_SERVICES


def _ports_kwarg_from_spec(service_ports: list) -> dict | None:
    """Build a docker-py ``ports`` kwarg from a connector.yaml
    ``service.ports`` list ([{container_port, host_port?, protocol?}]).

    Returns None when empty so non-service starts pass ``ports=None``
    (Docker publishes nothing — connectors stay internal-only).
    """
    ports: dict[str, int] = {}
    for p in service_ports or []:
        if not isinstance(p, dict):
            continue
        cport = p.get("container_port")
        if cport is None:
            continue
        proto = str(p.get("protocol") or "tcp").lower()
        hport = p.get("host_port", cport)
        try:
            ports[f"{cport}/{proto}"] = int(hport)
        except (TypeError, ValueError):
            continue
    return ports or None


def _published_ports_of(container) -> dict | None:
    """Read a running container's published-port bindings into a docker-py
    ``ports`` kwarg, so a recreate re-publishes the SAME host ports.

    The digest-drift reconcile path POSTs only {instance_id} to the start
    endpoint, so a service container would otherwise lose its published
    port on every dev-cycle recreate. Inheriting the bindings keeps the
    recreate idempotent w.r.t. the published port.
    """
    try:
        bindings = (container.attrs or {}).get("HostConfig", {}).get(
            "PortBindings"
        ) or {}
    except Exception:  # noqa: BLE001 — defensive; inspect shouldn't fail
        return None
    ports: dict[str, int] = {}
    for cport, host_list in bindings.items():
        if isinstance(host_list, list) and host_list:
            hp = host_list[0].get("HostPort")
            if hp:
                try:
                    ports[cport] = int(hp)
                except (TypeError, ValueError):
                    continue
    return ports or None


def _split_connector_container_name(name: str) -> tuple[str, str] | None:
    """Parse ``guardian-connector-<id>-<instance>`` → (connector_id, instance_name).

    A connector_id may itself contain hyphens (``cortex-docs``), so we
    can't naively split on the first hyphen — ``str.partition("-")`` yielded
    connector_id ``cortex`` for a ``guardian-connector-cortex-docs-<inst>``
    container, which then failed the KNOWN_CONNECTORS check and was silently
    dropped from digest reconcile + the digests listing (issue #42). Match
    against KNOWN_CONNECTORS by longest id-prefix instead; connector ids are
    a closed set, so the longest-prefix match is unambiguous. Returns None
    for non-connector names, malformed names, or unknown connector ids.
    """
    if not name.startswith("guardian-connector-"):
        return None
    rest = name[len("guardian-connector-"):]
    # Longest id first so e.g. "cortex-docs" wins over any shorter id that
    # might be a prefix of it. v0.2.42 — include KNOWN_SERVICES so a
    # service container (guardian-connector-splunk-mimic-<inst>) is also
    # parsed + covered by the digest-drift reconcile loop.
    for cid in sorted(KNOWN_CONNECTORS | KNOWN_SERVICES, key=len, reverse=True):
        prefix = f"{cid}-"
        if rest.startswith(prefix):
            instance_name = rest[len(prefix):]
            if instance_name:
                return cid, instance_name
    return None


def _connector_image_ref(connector_id: str, version: str | None = None) -> str:
    """Compose the connector image ref using digest pinning (v0.3.0+).

    Resolution order:
      1. If `version` arg is set AND matches the running stack's
         GUARDIAN_VERSION → use the corresponding DIGEST_GUARDIAN_CONNECTOR_<ID>
         from env (set by the installer-managed manifest in /opt/guardian/.env).
         This is the typical happy path: operator creates a connector
         instance, agent passes no `version`, we pin to the running
         stack's manifest digest.
      2. If `version` arg is set AND differs from running GUARDIAN_VERSION
         → unsupported in v0.3.0+ (operator can't legitimately ask for a
         different version's digest because we don't have its manifest in
         our env). Fall back to tag-pinning with a loud warning so the
         drift is observable in /observability/connectors.
      3. If env doesn't have the matching DIGEST_*_CONNECTOR var (e.g. an
         operator-managed compose missing the bare-name forwarding) →
         tag fallback with a loud warning.

    The function NEVER raises. Returns a usable image ref, with the
    warning logged in failure cases. The observability layer queries
    `image_pinning_for(connector_id)` (below) to surface the pinning
    mode in the connectors panel.
    """
    running_version = _running_guardian_version()
    requested_version = version or running_version

    # Happy path: requested version matches running stack version.
    # Use the digest from /host/.env (v0.5.51 — formerly os.environ).
    if running_version and requested_version == running_version:
        env_var = _connector_digest_env_var(connector_id)
        digest = _connector_digest(connector_id)
        if digest and digest.startswith("sha256:"):
            return f"{REGISTRY}/{OWNER}/guardian-connector-{connector_id}@{digest}"
        log.warning(
            "%s missing or invalid in /host/.env (got: %r); falling back to tag-pinning. "
            "This indicates the customer's .env is missing manifest-managed "
            "DIGEST_* values — re-run guardian-installer to refresh.",
            env_var, digest,
        )

    # Fallback: tag pinning. Logged loudly so the drift surfaces in
    # observability + structured-log searches. Operators should never
    # be in this path on a clean install.
    v = requested_version or "latest"
    log.warning(
        "Tag-pinning connector %s to v%s. Pre-v0.3.0 fallback path; "
        "the connector instance will be recreated on the next stack "
        "upgrade even if its image content didn't change.",
        connector_id, v,
    )
    return f"{REGISTRY}/{OWNER}/guardian-connector-{connector_id}:{v}"


def image_pinning_for(connector_id: str) -> dict:
    """Return {pinning: 'digest'|'tag', digest|tag: '...'} for the given
    connector_id. Used by the /observability/connectors panel to render
    a pinning-mode badge per connector instance.

    v0.5.51 — sources from /host/.env via the cached reader, not env
    vars. See module-level "/host/.env reads" block for the rationale.
    """
    digest = _connector_digest(connector_id)
    if digest and digest.startswith("sha256:"):
        return {"pinning": "digest", "digest": digest}
    return {
        "pinning": "tag",
        "tag": _running_guardian_version() or "latest",
    }


def _connector_container_name(connector_id: str, instance_name: str) -> str:
    """Container name = guardian-connector-<id>-<instance_name>.

    Both segments are validated against [a-zA-Z0-9_-]+ at the
    endpoint surface so a malicious instance name can't break out
    into shell-meta territory. Operators have free rein over
    instance names within that character class.
    """
    return f"guardian-connector-{connector_id}-{instance_name}"


def _compose_network_name() -> str:
    """The compose default network name = `<project>_default`. The
    connector container needs to attach to this network so the agent
    (also on it) can reach the connector at <container-name>:9000."""
    return f"{_compose_project_name()}_default"


def _compose_data_volume_name() -> str:
    """Volume holding instance_store.db + secrets/. The connector
    container mounts this read-only at /app/data so the runtime
    entrypoint can resolve INSTANCE_ID → config + secrets."""
    return f"{_compose_project_name()}_guardian_mcp_data"


def _pull_with_retry(
    client: docker.DockerClient,
    image: str,
    *,
    max_attempts: int = 5,
    base_delay_s: float = 1.0,
    max_delay_s: float = 30.0,
) -> str:
    """Pull a connector image with exponential backoff.

    Returns one of:
      "pulled"           — fresh pull from registry succeeded
      "cached"           — pull failed but image is in local cache
                           (offline-deploy success path)

    Raises HTTPException(502) when:
      - Pull failed AND image not in local cache (no way to start
        the container)
      - All retry attempts exhausted on a transient error

    Why retry: Guardian customers run on-prem with variable network
    quality (corporate proxies, slow VPNs). A single transient
    DNS / TLS / connection-reset error during `docker pull`
    shouldn't fail the whole start endpoint. The exponential
    backoff (1s → 2s → 4s → 8s → 16s, capped at 30s) gives ~30s
    of total recovery window, then bails.

    Why fall through to local cache: customers may run with the
    registry temporarily unreachable (firewall change, registry
    outage). If the image was previously pulled, the start should
    still work — that's the customer's "we're offline today, but
    we already have what we need" scenario. Surface this to the
    operator via the return value so audit logs show "cached"
    when the registry was down.

    Why not retry forever: if the registry is genuinely
    unreachable AND the image isn't local, no amount of retrying
    helps. Bail at max_attempts so the operator gets a fast,
    actionable error instead of a 5-minute hang.
    """
    import time as _time

    last_exc: Exception | None = None
    delay = base_delay_s
    for attempt in range(1, max_attempts + 1):
        try:
            client.images.pull(image, auth_config=_registry_auth())
            log.info("pulled image %s (attempt %d)", image, attempt)
            return "pulled"
        except DockerException as exc:
            last_exc = exc
            log.warning(
                "image pull attempt %d/%d failed for %s: %s",
                attempt, max_attempts, image, exc,
            )
            # Last attempt — fall through to cache check below
            if attempt == max_attempts:
                break
            _time.sleep(delay)
            delay = min(delay * 2, max_delay_s)

    # All attempts exhausted. Check local cache as a last resort.
    try:
        client.images.get(image)
        log.warning(
            "image %s pulled from cache after %d failed registry attempts "
            "(operator may be offline)",
            image, max_attempts,
        )
        return "cached"
    except NotFound:
        raise HTTPException(
            502,
            f"image {image!r} not in local cache and registry unreachable "
            f"after {max_attempts} attempts: {last_exc}",
        ) from last_exc


async def _agent_set_container_url(
    instance_id: str, container_url: str | None,
) -> None:
    """Call back to the agent's MCP to update the routing entry.

    This is the contract: guardian-updater starts/stops the container,
    then notifies the agent. The agent's MCP set_container_url
    endpoint (api/instances.py) updates the row; the connector_loader's
    container branch reads it via merged_config()→contextvar at the
    next tool call.

    Best-effort — failures here log a WARNING but don't fail the
    start/stop call. Reason: the container is up (or down); the
    routing entry is a downstream concern that an agent restart or
    a follow-up sync would correct. Hard-failing the start endpoint
    on a transient agent-MCP unreachable would be worse UX than
    succeeding with a warning.
    """
    # v0.6.11 — TLS-aware default. Pre-v0.6.11 defaulted to http;
    # v0.4.0+ the agent runs behind a TLS proxy on port 8080.
    agent_url = _resolve_agent_internal_url()
    url = f"{agent_url}/api/v1/instances/{instance_id}/container_url"
    headers = {"Content-Type": "application/json"}
    if MCP_TOKEN:
        headers["Authorization"] = f"Bearer {MCP_TOKEN}"
    body = {"container_url": container_url}
    # v0.6.14 — use the centralized helper. Default compose-internal
    # URL has a self-signed cert; verify=False is the architecturally
    # correct setting (trust boundary = docker network alias, not
    # cert chain). Operator override paths can opt in via
    # GUARDIAN_TLS_VERIFY=1.
    verify_tls = _agent_tls_verify()
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=verify_tls) as client:
            resp = await client.put(url, json=body, headers=headers)
        if resp.status_code >= 300:
            log.warning(
                "agent set_container_url returned %d for instance %s "
                "(body=%.200s)",
                resp.status_code, instance_id, resp.text,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "could not notify agent of container_url change for instance %s: %s",
            instance_id, exc,
        )


async def _audit_event(
    action: str,
    *,
    target: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> None:
    """#CONN-F10 — fire-and-forget audit row to the agent's MCP.

    The guardian-updater is a separate service; before this its container
    lifecycle (start/stop/restart), reconcile ticks, digest-drift repairs,
    managed-service restarts, and stack updates were observable only in the
    updater's own logs — invisible in /observability/events, /traces, and
    audit.db. This posts to the MCP's POST /api/v1/audit (same Bearer
    MCP_TOKEN + TLS-verify the container_url callback uses), tagged with
    X-Guardian-Actor: system:updater so the rows attribute to the automated
    service, not the operator. Strictly best-effort: never raises, never
    blocks a container op; a hiccup is logged at DEBUG, not WARNING.
    """
    agent_url = _resolve_agent_internal_url()
    url = f"{agent_url}/api/v1/audit"
    headers = {
        "Content-Type": "application/json",
        # Attribute updater-originated rows to the automated service.
        "X-Guardian-Actor": "system:updater",
    }
    if MCP_TOKEN:
        headers["Authorization"] = f"Bearer {MCP_TOKEN}"
    body: dict = {"action": action}
    if target is not None:
        body["target"] = target
    if status is not None:
        body["status"] = status
    if metadata:
        body["metadata"] = metadata
    try:
        async with httpx.AsyncClient(
            timeout=5.0, verify=_agent_tls_verify()
        ) as client:
            await client.post(url, json=body, headers=headers)
    except Exception as exc:  # noqa: BLE001 — audit is best-effort
        log.debug("audit_event %s: forward failed (non-fatal): %s", action, exc)


def _normalize_instance_name(name: str) -> str:
    """Normalize an operator-supplied instance name to a docker-safe
    form.

    Operators routinely create instances with names like "Cortex XDR"
    or "Cortex Docs Search" — spaces are valid in the agent's UI and
    in the underlying instances.db. But docker container names can't
    contain spaces, so we normalize whitespace → underscore at every
    use site that constructs a container name.

    Pre-v0.6.43 this normalization happened only at instance-CREATE
    time (the original container was named "Cortex_XDR" with an
    underscore). Other endpoints (reconcile, restart, stop) received
    the RAW name "Cortex XDR" from the agent's database, passed it
    through `_validate_path_segments`, and got rejected with
    "invalid path segment 'Cortex XDR'; allowed: A-Z, a-z, 0-9, _, -".
    The reconcile endpoint couldn't manage existing instances at all
    if their names had spaces.

    The normalization is conservative:
      - Whitespace → "_" (so "Cortex XDR" → "Cortex_XDR")
      - Other chars left alone (validator catches them after)

    Idempotent — re-applying produces the same string.
    """
    return re.sub(r"\s+", "_", name)


def _validate_path_segments(*parts: str) -> None:
    """Defense-in-depth: connector_id + instance_name come from URL
    path. FastAPI's path-param parsing is permissive; we explicitly
    validate against shell-meta and dangerous chars before passing
    them into Docker container names.

    Callers should pass instance_name already normalized via
    `_normalize_instance_name` so this validation accepts the
    docker-safe form (spaces have been replaced with underscores by
    that point).
    """
    safe = re.compile(r"^[a-zA-Z0-9_-]+$")
    for p in parts:
        if not safe.match(p):
            raise HTTPException(
                400, f"invalid path segment {p!r}; allowed: A-Z, a-z, 0-9, _, -",
            )


@app.post("/api/v1/connectors/{connector_id}/instances/{instance_name}/start")
async def start_connector_instance(
    connector_id: str, instance_name: str, request: Request,
):
    """Start a per-instance connector container.

    Body (JSON):
        instance_id: str    — the agent's instance row id (UUID)
        version:     str?   — optional image version override
                              (defaults to GUARDIAN_VERSION)

    The endpoint:
      1. Validates connector_id is known + path segments are safe.
      2. Removes any existing container with the same name (so
         start is idempotent / equivalent to recreate).
      3. Pulls the image (best-effort — falls back to local cache
         if registry is unreachable; see P1.10 for retry).
      4. Starts the container, attached to the compose default
         network with the data volume mounted read-only.
      5. POSTs back to the agent's MCP to populate the
         container_url routing entry.
    """
    # v0.6.43 — normalize spaces in operator-supplied names BEFORE
    # validation so the start endpoint can manage instances named
    # like "Cortex XDR" (spaces). Container names use underscore;
    # operator UI accepts spaces. See _normalize_instance_name docstring.
    instance_name = _normalize_instance_name(instance_name)
    _validate_path_segments(connector_id, instance_name)

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    instance_id = body.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise HTTPException(400, "instance_id (string) required in body")

    # v0.5.0: explicit image_ref support for user-uploaded connectors.
    # The agent's instances.py reads `image:` from connector.yaml (which
    # is required for user uploads, optional for bundle) and passes it
    # through here. When present, skips KNOWN_CONNECTORS gating + the
    # derivation path; uses the explicit ref directly. Bundle connectors
    # leave it empty and fall through to derivation as before.
    explicit_image = body.get("image_ref")
    if isinstance(explicit_image, str) and explicit_image.strip():
        image = explicit_image.strip()
    else:
        if not _is_known_id(connector_id):
            raise HTTPException(
                400,
                f"unknown connector_id {connector_id!r}; "
                f"allowed bundle ids: {sorted(KNOWN_CONNECTORS | KNOWN_SERVICES)}. "
                f"For user-uploaded connectors, pass image_ref in the "
                f"body — see api/marketplace.py upload route.",
            )
        image = _connector_image_ref(connector_id, body.get("version"))
    container_name = _connector_container_name(connector_id, instance_name)

    client = _docker_client()

    # v0.2.42 — service-kind starts PUBLISH host ports so external systems
    # reach the container. The primary path (operator create) carries
    # `service_ports` (from connector.yaml) in the body. The reconcile
    # path POSTs only {instance_id}, so for a service we inherit the
    # published ports from the existing container (below) — keeping the
    # recreate idempotent w.r.t. the published port. Connectors stay
    # internal-only: ports is None and Docker publishes nothing.
    is_service = (body.get("kind") == "service") or (connector_id in KNOWN_SERVICES)
    ports = _ports_kwarg_from_spec(body.get("service_ports") or [])

    # Remove any existing container with the same name (idempotent
    # restart). The Docker SDK raises NotFound if none exists; that's
    # the happy first-time-start case.
    try:
        existing = client.containers.get(container_name)
        if is_service and ports is None:
            # Reconcile path: re-publish whatever the running container
            # already had so a digest-drift recreate doesn't drop the port.
            ports = _published_ports_of(existing)
        log.info("removing existing container %s before start", container_name)
        try:
            existing.stop(timeout=10)
        except DockerException:
            pass
        existing.remove(force=True)
    except NotFound:
        pass

    # Boot-reconcile of a MISSING service container: no body ports and no
    # existing container to inherit from. Fall back to the well-known
    # default so a reboot re-publishes the port.
    if is_service and ports is None:
        ports = _ports_kwarg_from_spec(SERVICE_DEFAULT_PORTS.get(connector_id) or [])

    # Pull image with exponential backoff (P1.10). Returns "pulled"
    # on fresh pull success or "cached" when the registry was
    # unreachable but a previous pull still lives in local cache
    # (offline-deploy recovery path). Raises HTTPException(502) when
    # both fail.
    pull_status = _pull_with_retry(client, image)

    # Start the container. Env wiring + volume mount + network
    # attach mirrors what guardian-agent + guardian-browser
    # already do in customer compose.
    try:
        container = client.containers.run(
            image,
            name=container_name,
            environment={
                "CONNECTOR_ID": connector_id,
                "INSTANCE_ID": instance_id,
                "PORT": "9000",
                "DATA_ROOT": "/app/data",
                # v0.6.17 — read GUARDIAN_SECRET_KEK from /host/.env
                # (same pattern as GUARDIAN_VERSION / DIGEST_GUARDIAN_*
                # reads). Pre-v0.6.17 this was os.environ.get(...)
                # which assumed the customer compose's `environment:`
                # block passed it through. But the compose block
                # INTENTIONALLY doesn't pass it (per v0.5.51's
                # docker-compose env-stability invariant: any env
                # block change forces guardian-updater container
                # recreate on stack upgrade, defeating the digest-
                # pinning preservation). So pre-v0.6.17 guardian-
                # updater started connector containers with an
                # EMPTY GUARDIAN_SECRET_KEK env var → the connector-
                # runtime's SecretStoreReader.read() failed with
                # "GUARDIAN_SECRET_KEK is not set" → instance.secret_refs
                # all resolved to empty string → connectors errored
                # at first tool call with "no apiKey configured."
                # Surfaced when v0.6.16 finally got past the
                # connector-image-flow gap and the operator's
                # first connector container actually tried to
                # dispatch.
                "GUARDIAN_SECRET_KEK": _host_env_get("GUARDIAN_SECRET_KEK", "") or "",
                # v0.6.11 — TLS-aware default. Pre-v0.6.11 hard-coded
                # http://guardian-agent:8080; the connector-container
                # process would then fail to write audit rows when
                # TLS was on.
                "GUARDIAN_AUDIT_URL": os.environ.get(
                    "GUARDIAN_AUDIT_URL",
                    f"{_resolve_agent_internal_url()}/api/v1/audit",
                ),
                "MCP_TOKEN": MCP_TOKEN,
                "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
            },
            volumes={
                _compose_data_volume_name(): {
                    "bind": "/app/data",
                    "mode": "ro",
                },
            },
            network=_compose_network_name(),
            # v0.2.42 — publish host ports for service-kind containers
            # (None for connectors → nothing published). This is the one
            # genuinely new lifecycle capability services need: an
            # external system reaches the container on the host port.
            ports=ports,
            restart_policy={"Name": "unless-stopped"},
            detach=True,
            labels={
                # Tag with the compose project so the agent's UI can
                # filter "containers we manage" vs operator-side
                # containers running on the same host.
                "com.docker.compose.project": _compose_project_name(),
                "guardian.connector_id": connector_id,
                "guardian.instance_id": instance_id,
                "guardian.instance_name": instance_name,
                "guardian.role": "connector-runtime",
                # v0.2.42 — distinguishes an emulated service (published
                # host port, no agent tools) from a normal connector.
                "guardian.kind": "service" if is_service else "connector",
            },
        )
    except DockerException as exc:
        log.exception("container start failed for %s", container_name)
        # #CONN-F10 — a failed start must leave a trace too.
        await _audit_event(
            "container_started",
            target=f"connector:{connector_id}/{instance_name}",
            status="failure",
            metadata={
                "connector_id": connector_id,
                "instance_name": instance_name,
                "container_name": container_name,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise HTTPException(500, f"container start failed: {exc}") from exc

    # Build the URL the agent's loader will use to reach this container.
    # Compose-network DNS resolves <container_name> to the right IP.
    container_url = f"http://{container_name}:9000"

    # Notify agent of the routing entry. Best-effort.
    await _agent_set_container_url(instance_id, container_url)

    log.info(
        "started connector container: %s (instance_id=%s, image=%s)",
        container_name, instance_id, image,
    )

    # #CONN-F10 — record the container start in the agent's audit log so the
    # lifecycle is visible in /observability/events (covers reconcile-driven
    # starts too, since reconcile calls this function).
    await _audit_event(
        "container_started",
        target=f"instance:{instance_id}" if instance_id else f"connector:{connector_id}",
        status="success",
        metadata={
            "connector_id": connector_id,
            "instance_name": instance_name,
            "container_name": container_name,
            "image": image,
            "image_pull": pull_status,
        },
    )

    return {
        "container_id": container.id,
        "container_name": container_name,
        "container_url": container_url,
        "image": image,
        "image_pull": pull_status,  # "pulled" | "cached" — informational
        "status": "started",
    }


@app.post("/api/v1/connectors/{connector_id}/instances/{instance_name}/stop")
async def stop_connector_instance(connector_id: str, instance_name: str):
    """Stop + remove a per-instance connector container. Also clears
    the agent's routing entry."""
    # v0.6.43 — normalize spaces in operator-supplied names BEFORE
    # validation so reconcile/start/stop/restart can manage instances
    # named like "Cortex XDR" (spaces). Container names use underscore;
    # operator UI accepts spaces. See _normalize_instance_name docstring.
    instance_name = _normalize_instance_name(instance_name)
    _validate_path_segments(connector_id, instance_name)
    if not _is_known_id(connector_id):
        raise HTTPException(
            400,
            f"unknown connector_id {connector_id!r}; "
            f"allowed: {sorted(KNOWN_CONNECTORS | KNOWN_SERVICES)}",
        )

    container_name = _connector_container_name(connector_id, instance_name)
    client = _docker_client()

    # Best-effort: extract instance_id from labels BEFORE we kill the
    # container, so we can still notify the agent even if the operator
    # doesn't pass instance_id in the body.
    instance_id: str | None = None
    try:
        existing = client.containers.get(container_name)
        instance_id = existing.labels.get("guardian.instance_id")
    except NotFound:
        return {"status": "not_running", "container_name": container_name}

    try:
        existing.stop(timeout=10)
        existing.remove(force=True)
    except DockerException as exc:
        log.exception("stop failed for %s", container_name)
        raise HTTPException(500, f"stop failed: {exc}") from exc

    if instance_id:
        await _agent_set_container_url(instance_id, None)

    log.info("stopped connector container: %s", container_name)
    # #CONN-F10 — record the container stop/removal.
    await _audit_event(
        "container_stopped",
        target=f"instance:{instance_id}" if instance_id else f"connector:{connector_id}/{instance_name}",
        status="success",
        metadata={
            "connector_id": connector_id,
            "instance_name": instance_name,
            "container_name": container_name,
        },
    )
    return {"status": "stopped", "container_name": container_name}


@app.get("/api/v1/connectors/{connector_id}/instances/{instance_name}/status")
async def status_connector_instance(connector_id: str, instance_name: str):
    """Return Docker-side status for a per-instance connector
    container. Used by the /connectors UI's per-instance status
    badge + by guardian-updater's own readiness checks."""
    # v0.6.43 — normalize spaces in operator-supplied names BEFORE
    # validation so reconcile/start/stop/restart can manage instances
    # named like "Cortex XDR" (spaces). Container names use underscore;
    # operator UI accepts spaces. See _normalize_instance_name docstring.
    instance_name = _normalize_instance_name(instance_name)
    _validate_path_segments(connector_id, instance_name)
    if not _is_known_id(connector_id):
        raise HTTPException(
            400,
            f"unknown connector_id {connector_id!r}; "
            f"allowed: {sorted(KNOWN_CONNECTORS | KNOWN_SERVICES)}",
        )

    container_name = _connector_container_name(connector_id, instance_name)
    client = _docker_client()

    try:
        container = client.containers.get(container_name)
    except NotFound:
        return {
            "container_name": container_name,
            "status": "not_running",
            "container_url": None,
        }

    # Map docker container Status field to a small set of values the
    # agent UI cares about. Docker reports: created, restarting,
    # running, removing, paused, exited, dead.
    docker_status = (container.status or "").lower()
    health = None
    try:
        health = container.attrs.get("State", {}).get("Health", {}).get("Status")
    except Exception:  # noqa: BLE001
        pass

    if docker_status == "running":
        ui_status = "healthy" if health in ("healthy", None) else (
            "unhealthy" if health == "unhealthy" else "starting"
        )
    elif docker_status in ("restarting", "created"):
        ui_status = "starting"
    else:
        ui_status = "stopped"

    return {
        "container_name": container_name,
        "container_id": container.id,
        "status": ui_status,
        "docker_status": docker_status,
        "health": health,
        "restart_count": container.attrs.get("RestartCount", 0),
        "container_url": f"http://{container_name}:9000",
        "image": (container.image.tags or [container.image.id])[0],
    }


@app.get("/api/v1/connectors/digests")
async def list_connector_digests():
    """Return image-pinning info for every per-instance connector
    container managed by this updater.

    v0.3.0+ — used by the agent's /api/agent/digests proxy to populate
    the /observability/connectors panel's digest column. Each row
    reflects the actual running container's image (via docker inspect),
    not what the manifest says SHOULD be running. The two normally
    agree, but a divergence (e.g. operator manually swapped an image
    via `docker run`) is operationally interesting and worth surfacing.

    Returns:
      {connectors: [
        {connector_id, instance_id, instance_name, digest,
         pinning_mode: 'digest' | 'tag', image_ref},
        ...
      ]}

    `digest` is null when the container is in tag-pinning fallback
    mode (DIGEST_GUARDIAN_CONNECTOR_<ID> not set in updater env) or
    when the container isn't running.
    """
    client = _docker_client()
    rows: list[dict] = []

    # Enumerate every container whose name matches our per-instance
    # naming convention: guardian-connector-<id>-<instance>
    # (set by _connector_container_name() at create time).
    for container in client.containers.list(
        all=True, filters={"name": "guardian-connector-"}
    ):
        name = container.name or ""
        # Parse <id>-<instance> robustly: connector ids can contain hyphens
        # (cortex-docs), so longest-known-prefix match rather than a naive
        # first-hyphen split (issue #42 — cortex-docs containers used to be
        # dropped here).
        parsed = _split_connector_container_name(name)
        if parsed is None:
            # Non-connector name, malformed, or an unknown connector_id
            # (likely a legacy container from a past install). Skip rather
            # than misreport.
            continue
        connector_id, instance_name = parsed

        # The instance_id is set as a container env var when we start
        # the container (see _start_connector_instance). Read it back
        # from inspect for a faithful round-trip.
        env_pairs = container.attrs.get("Config", {}).get("Env", []) or []
        instance_id = ""
        for e in env_pairs:
            if e.startswith("INSTANCE_ID="):
                instance_id = e[len("INSTANCE_ID="):]
                break

        # Running digest, sourced from the container's image's
        # RepoDigests. Same logic as _current_version_for() for
        # stack-tier services.
        running_digest: str | None = None
        repo_digests = container.image.attrs.get("RepoDigests") or []
        expected_prefix = f"{REGISTRY}/{OWNER}/guardian-connector-{connector_id}@"
        for rd in repo_digests:
            if rd.startswith(expected_prefix):
                running_digest = rd.split("@", 1)[1]
                break
        if running_digest is None and repo_digests:
            # Fall back to the first RepoDigest for diagnostic visibility,
            # even if the prefix doesn't match (operator might have
            # built locally with a non-canonical tag).
            running_digest = (
                repo_digests[0].split("@", 1)[1]
                if "@" in repo_digests[0] else None
            )

        # Pinning mode: digest if the env var IS set AND matches the
        # running digest; tag otherwise. The image_pinning_for()
        # helper consults the same env var the container was started
        # with — so as long as the operator didn't manually swap, the
        # two agree.
        pinning = image_pinning_for(connector_id)
        image_ref = (container.image.tags or [container.image.id])[0] or ""

        rows.append({
            "connector_id": connector_id,
            "instance_id": instance_id,
            "instance_name": instance_name,
            "digest": running_digest,
            "pinning_mode": pinning["pinning"],
            "image_ref": image_ref,
        })

    return {"connectors": rows}


async def _reconcile_connector_digest_drift() -> dict:
    """v0.6.66 — recreate per-instance connector containers whose
    running image digest doesn't match the pinned digest in
    /host/connector-digests.env.

    Why this exists (the v0.6.65 bug story):
    Per-instance connector containers are spawned by guardian-updater
    when the operator first creates an instance via /connectors. After
    that, they stick around — docker-compose's `up -d` doesn't touch
    them because they're not in docker-compose.yml (they're managed
    dynamically by guardian-updater per-instance). Every dev-cycle
    install updates /host/connector-digests.env with new pinned
    digests, but the existing per-instance containers KEEP RUNNING the
    image digest they were originally spawned with. The operator's
    chat tests then exercise STALE connector code while the agent
    itself is current — confusing-as-hell debug story.

    Observed in operator session 26a7fdd3 (2026-05-20): cortex-xdr
    connector container was 17 hours old; the agent was on v0.6.63
    (4 minutes old). Manually `docker rm -f` + reconcile fixed it,
    but the operator shouldn't need to know this.

    v0.6.66 fix: guardian-updater detects digest drift on startup +
    via this endpoint, and recreates the divergent containers
    automatically. The recreate goes through start_connector_instance
    which already handles the lifecycle (stop+remove existing, pull
    new image, spawn new container, callback agent with the URL).

    Safety:
      - Only recreates when running digest != pinned digest. Fresh
        installs (no prior containers) skip; matched-digest containers
        skip.
      - Sequential, not parallel — one connector at a time so we
        don't thrash the docker daemon or the agent's callback path.
      - Errors per-container are logged + included in the response
        but don't abort the loop.

    Returns: {drifted: [...], recreated: [...], unchanged: [...], failed: [...]}.
    """
    import httpx as _httpx  # noqa: PLC0415
    summary: dict[str, list] = {
        "drifted": [],
        "recreated": [],
        "unchanged": [],
        "failed": [],
    }

    client = _docker_client()
    try:
        containers = client.containers.list(
            all=False, filters={"name": "guardian-connector-"},
        )
    except DockerException as exc:
        log.warning("digest-drift reconcile: docker list failed: %s", exc)
        return summary

    # Need to call start_connector_instance via HTTP to reuse its
    # complete lifecycle (stop + remove + pull + start + agent callback).
    # Self-loopback via localhost:8090 — same port the agent uses.
    self_url = "http://127.0.0.1:8090"
    headers = {"Authorization": f"Bearer {MCP_TOKEN}"} if MCP_TOKEN else {}

    for container in containers:
        name = container.name or ""
        # Longest-known-prefix parse so hyphenated ids (cortex-docs) round-trip
        # instead of being dropped by a first-hyphen split (issue #42).
        parsed = _split_connector_container_name(name)
        if parsed is None:
            continue
        connector_id, instance_name = parsed

        # Read pinned digest from /host/connector-digests.env.
        pinned = _connector_digest(connector_id)
        if not pinned:
            # No pinning configured — operator running in tag-mode.
            # Skip; the customer-install path doesn't use tag-mode.
            summary["unchanged"].append({
                "container": name,
                "reason": "no pinned digest",
            })
            continue

        # Read running container's image digest from its RepoDigests.
        # `container.image` re-inspects the image by id; if that image was
        # already pruned/replaced locally (common on the dev cycle once a new
        # image is pulled), docker-py raises ImageNotFound. The old image being
        # gone means the container is DEFINITELY drifted from the pinned digest
        # — force a recreate instead of crashing the whole reconcile (the bug
        # that made the operator-callable reconcile/digests endpoint 500).
        running_digest: str | None = None
        image_missing = False
        try:
            repo_digests = container.image.attrs.get("RepoDigests") or []
        except ImageNotFound:
            image_missing = True
            repo_digests = []
        expected_prefix = (
            f"{REGISTRY}/{OWNER}/guardian-connector-{connector_id}@"
        )
        for rd in repo_digests:
            if rd.startswith(expected_prefix):
                running_digest = rd.split("@", 1)[1]
                break

        if not image_missing and running_digest is None:
            # Locally-built image without a registry digest — can
            # happen in dev environments. Can't diff; skip.
            summary["unchanged"].append({
                "container": name,
                "reason": "no registry digest on running image",
            })
            continue

        if not image_missing and running_digest == pinned:
            summary["unchanged"].append({
                "container": name,
                "digest": running_digest[:19] + "...",
            })
            continue

        # Drift detected. Need the instance_id to call start.
        env_pairs = container.attrs.get("Config", {}).get("Env", []) or []
        instance_id = ""
        for e in env_pairs:
            if e.startswith("INSTANCE_ID="):
                instance_id = e[len("INSTANCE_ID="):]
                break
        if not instance_id:
            log.warning(
                "digest-drift: %s drifted but has no INSTANCE_ID label; "
                "skipping recreate (would need agent-side instance lookup)",
                name,
            )
            summary["failed"].append({
                "container": name,
                "reason": "no INSTANCE_ID label — can't safely recreate",
            })
            continue

        running_display = (
            (running_digest[:19] + "...") if running_digest else "(image pruned)"
        )
        drifted_entry = {
            "container": name,
            "connector_id": connector_id,
            "instance_name": instance_name,
            "instance_id": instance_id,
            "running_digest": running_display,
            "pinned_digest": pinned[:19] + "...",
        }
        summary["drifted"].append(drifted_entry)

        log.info(
            "digest-drift: %s running=%s pinned=%s — recreating",
            name, running_display, pinned[:19],
        )
        try:
            async with _httpx.AsyncClient(timeout=_httpx.Timeout(60.0)) as http:
                resp = await http.post(
                    f"{self_url}/api/v1/connectors/{connector_id}/"
                    f"instances/{instance_name}/start",
                    headers=headers,
                    json={"instance_id": instance_id},
                )
            if resp.status_code < 300:
                summary["recreated"].append({**drifted_entry,
                                              "response": resp.json()})
            else:
                summary["failed"].append({
                    **drifted_entry,
                    "status_code": resp.status_code,
                    "body": resp.text[:200],
                })
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "digest-drift: recreate of %s failed: %s", name, exc,
            )
            summary["failed"].append({**drifted_entry, "error": str(exc)})

    return summary


@app.post("/api/v1/connectors/reconcile/digests")
async def reconcile_connector_digest_drift_endpoint():
    """v0.6.66 — operator-callable digest-drift reconcile.

    Same logic as the startup-time auto-reconcile, exposed as an
    endpoint for manual trigger when the operator notices a
    connector container is running stale code (e.g. behavior doesn't
    match a recent release's CHANGELOG entry).
    """
    return await _reconcile_connector_digest_drift()


@app.post("/api/v1/connectors/reconcile")
async def reconcile_connector_containers():
    """Ensure every container-style instance has a running container.

    v0.1.31 (Phase 2) entry point for the upgrade path: a customer
    on v0.1.30 has an existing in-process web instance; after
    upgrading to v0.1.31, web's connector.yaml flips to style:
    container, but no container exists for the instance yet. The
    connector_loader's container branch would error with
    "container_url not set" on every tool call until something
    starts a container.

    This endpoint:
      1. Queries the agent's /api/v1/instances for the full list
         of instances.
      2. For each instance whose connector has style: container in
         its connector.yaml AND no container_url set, calls the
         start endpoint.
      3. Returns a summary of {reconciled: [...], skipped: [...],
         failed: [...]}.

    Idempotent — safe to call repeatedly. Operators (or boot-time
    agent reconciliation) can call this without checking state
    first.

    Auth: same MCP_TOKEN bearer as the rest of /api/v1.

    Body: optional {}; no input parameters today. Future versions
    might accept a connector_id filter.
    """
    # v0.6.11 — TLS-aware default. Pre-v0.6.11 defaulted to http;
    # v0.4.0+ the agent runs behind a TLS proxy on port 8080.
    agent_url = _resolve_agent_internal_url()
    headers = {"Authorization": f"Bearer {MCP_TOKEN}"} if MCP_TOKEN else {}

    # v0.6.14 — use the centralized helper. Default compose-internal
    # URL has a self-signed cert; verify=False is the architecturally
    # correct setting.
    verify_tls = _agent_tls_verify()

    # Query agent for all instances + each connector's runtime style.
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=verify_tls) as client:
            instances_resp = await client.get(
                f"{agent_url}/api/v1/instances", headers=headers,
            )
        if instances_resp.status_code >= 300:
            raise HTTPException(
                502,
                f"agent /api/v1/instances returned {instances_resp.status_code}: "
                f"{instances_resp.text[:200]}",
            )
        instances = instances_resp.json().get("instances") or []
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            502, f"could not list instances from agent: {exc}",
        ) from exc

    # Cache connector.yaml lookups since multiple instances may share
    # the same connector_id. We CAN'T read connector.yaml directly
    # from this container (the bundle isn't mounted here), so we ask
    # the agent for the runtime style. Fastest path: /api/v1/marketplace
    # endpoint OR a small /api/v1/connectors/<id>/style endpoint.
    # Phase 1 simplification: try a HEAD request to the agent's
    # set_container_url endpoint — if the connector is container-style,
    # the agent's loader will accept the call. Otherwise just trust
    # the per-instance container_url field — if it's NULL and the
    # connector_id is one we have a guardian-connector-<id> image for,
    # we attempt the start.

    reconciled: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    for inst in instances:
        cid = inst.get("connector_id")
        name = inst.get("name")
        iid = inst.get("id")
        existing_url = inst.get("container_url")

        # #CONN-F12 — user-uploaded connectors carry an explicit image_ref
        # (the agent surfaces it on /api/v1/instances). Self-heal those too,
        # not just bundle KNOWN_CONNECTORS|KNOWN_SERVICES. Only skip when the
        # id is unknown AND there's no image to start from (module-style /
        # in-process connectors get no per-instance container).
        inst_image_ref = inst.get("image_ref")
        if not _is_known_id(cid) and not inst_image_ref:
            skipped.append({
                "connector_id": cid, "instance_name": name,
                "reason": "unknown connector_id and no image_ref (module-style or unknown)",
            })
            continue

        if existing_url:
            # Already has a container_url — try to verify the container
            # is actually running. If it is, skip; if not, try start.
            container_name = _connector_container_name(cid, name)
            try:
                client = _docker_client()
                ctn = client.containers.get(container_name)
                if (ctn.status or "").lower() == "running":
                    skipped.append({
                        "connector_id": cid, "instance_name": name,
                        "reason": "already running with container_url",
                    })
                    continue
            except NotFound:
                # container_url set but no container — fall through to start.
                log.info(
                    "instance %s/%s has stale container_url (no container); "
                    "reconciling by starting fresh",
                    cid, name,
                )

        # Call our own start endpoint. Reuses all the validation +
        # image-pull-with-retry + lifecycle logic. #CONN-F12 — forward the
        # image_ref for user connectors so start_connector_instance takes its
        # explicit-image path instead of deriving a bundle image ref.
        class _StubReq:
            async def json(self, _img=inst_image_ref):
                body = {"instance_id": iid}
                if _img:
                    body["image_ref"] = _img
                return body

        try:
            result = await start_connector_instance(cid, name, _StubReq())
            reconciled.append({
                "connector_id": cid,
                "instance_name": name,
                "instance_id": iid,
                "container_url": result.get("container_url"),
                "image_pull": result.get("image_pull"),
            })
        except HTTPException as exc:
            failed.append({
                "connector_id": cid,
                "instance_name": name,
                "instance_id": iid,
                "error": f"HTTP {exc.status_code}: {exc.detail}",
            })
        except Exception as exc:  # noqa: BLE001
            failed.append({
                "connector_id": cid,
                "instance_name": name,
                "instance_id": iid,
                "error": str(exc),
            })

    log.info(
        "reconcile complete: reconciled=%d skipped=%d failed=%d",
        len(reconciled), len(skipped), len(failed),
    )
    return {
        "reconciled": reconciled,
        "skipped": skipped,
        "failed": failed,
        "total_instances": len(instances),
    }


@app.post("/api/v1/connectors/{connector_id}/instances/{instance_name}/restart")
async def restart_connector_instance(
    connector_id: str, instance_name: str, request: Request,
):
    """Restart a per-instance connector container. Internally:
    stop → start. The image version is preserved (re-read from the
    existing container's labels) unless overridden in the body —
    this is the typical "kick the container after wedge" path."""
    # v0.6.43 — normalize spaces in operator-supplied names BEFORE
    # validation so reconcile/start/stop/restart can manage instances
    # named like "Cortex XDR" (spaces). Container names use underscore;
    # operator UI accepts spaces. See _normalize_instance_name docstring.
    instance_name = _normalize_instance_name(instance_name)
    _validate_path_segments(connector_id, instance_name)
    if not _is_known_id(connector_id):
        raise HTTPException(
            400,
            f"unknown connector_id {connector_id!r}; "
            f"allowed: {sorted(KNOWN_CONNECTORS | KNOWN_SERVICES)}",
        )

    container_name = _connector_container_name(connector_id, instance_name)
    client = _docker_client()

    # Pull instance_id from labels of the existing container if the
    # caller didn't supply it. Restart should "just work" without
    # needing to know the instance UUID.
    instance_id: str | None = None
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict) and isinstance(body.get("instance_id"), str):
        instance_id = body["instance_id"]
    else:
        try:
            existing = client.containers.get(container_name)
            instance_id = existing.labels.get("guardian.instance_id")
        except NotFound:
            pass

    if not instance_id:
        raise HTTPException(
            400,
            "could not resolve instance_id (no running container; "
            "pass it in the body)",
        )

    # Reuse the start handler's logic by constructing a minimal Request-
    # like body. Could refactor into a shared helper later; for Phase 1
    # the duplication is small enough to live with.
    class _StubRequest:
        async def json(self):
            return {"instance_id": instance_id}

    return await start_connector_instance(
        connector_id, instance_name, _StubRequest(),
    )
