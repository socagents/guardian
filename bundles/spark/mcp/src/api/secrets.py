"""Secret resolution HTTP surface — #HOOK-F14 (v0.2.81).

One route, MCP_TOKEN-bearer only:

  POST /api/v1/secrets/resolve   body: {ref: "<secret-store-path>"}
                                 → 200 {value: "<resolved>"}
                                 → 400 {error, code:"bad_ref"}     (malformed)
                                 → 404 {error, code:"not_found"}   (no such secret)

# Why this endpoint exists

The agent's hook-runner (`mcp/agent/lib/hook-runner.ts:resolveSecretEnv`)
historically read `secret:<X>` references straight out of the agent
container's `process.env` — an UNMANAGED env var, never minted by the
SecretStore, never audited, and a widening of the trust boundary the
SecretStore exists to enforce. This route is the honest backing for
that affordance: the hook-runner resolves a `secret:<ref>` by POSTing
the ref here, and the MCP resolves it through `SecretStore.read(ref)`.

`SecretStore.read` already:
  - honors the GUARDIAN_SECRET__<PATH> env-var overlay (operator-baked
    secrets), the file backend, and AES-256-GCM-at-rest;
  - emits an AUDITED `secret_read` row (success gated by the v0.2.77
    GUARDIAN_AUDIT_SECRET_READ env; FAILED reads are always audited);
  - validates the path (rejects traversal / illegal chars).

So this route is a thin, fail-closed proxy: it resolves through the
store and NEVER falls back to raw process.env. A ref that doesn't
resolve in the store returns 404 and the hook-runner passes nothing
(fail-closed, consistent with v0.2.52/59) rather than leaking an
unmanaged env var.

# Trust boundary

The MCP_TOKEN bearer authenticates that the caller is the agent
process (the only holder of the token from /proc/1/environ inside the
guardian_agent container). The same trust level that already lets the
agent read instance/provider secrets to dispatch connector tools — so
exposing per-ref resolution to the same principal does NOT widen the
boundary. The response carries the value (the caller needs it to run
the hook); we never LOG the value (only the path, via the store's
audit row).
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import require_bearer
from usecase.secret_store import SecretStore, SecretStoreError

logger = logging.getLogger("Guardian MCP")


def register_secret_routes(
    mcp: FastMCP,
    secret_store: SecretStore,
) -> None:
    """Register /api/v1/secrets/* routes on the FastMCP server."""

    @mcp.custom_route(
        "/api/v1/secrets/resolve",
        methods=["POST"],
        include_in_schema=False,
    )
    async def resolve_secret(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        # MCP_TOKEN principal ONLY — secret resolution must never be reachable
        # with an operator API key (require_bearer also admits apikey:<id>);
        # otherwise a leaked key could exfiltrate secret values. Mirrors the
        # plugin-install credential-route invariant (PLAT-F11).
        if getattr(request.state, "auth_principal", "") != "mcp_token":
            return JSONResponse(
                {"error": "secret resolution requires MCP_TOKEN",
                 "code": "secrets_mcp_token_required"},
                status_code=403,
            )
        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse(
                {"error": f"invalid JSON body: {exc}", "code": "bad_ref"},
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "body must be a JSON object", "code": "bad_ref"},
                status_code=400,
            )
        ref = body.get("ref")
        if not isinstance(ref, str) or not ref.strip():
            return JSONResponse(
                {
                    "error": "'ref' is required and must be a non-empty string",
                    "code": "bad_ref",
                },
                status_code=400,
            )
        ref = ref.strip()
        try:
            # SecretStore.read validates the path, honors the env-var
            # overlay + file backend, and emits the audited secret_read
            # row. A missing/malformed secret raises SecretStoreError —
            # we translate that to a fail-closed 4xx; the caller passes
            # NOTHING for that ref (no raw-env fallback).
            value = secret_store.read(ref)
        except SecretStoreError as exc:
            msg = str(exc)
            # Distinguish "malformed path" (operator typo in the hook
            # config) from "no such secret" so the caller's log is
            # actionable. Never echo a value; the message is path-only.
            code = "not_found" if "not found" in msg.lower() else "bad_ref"
            status = 404 if code == "not_found" else 400
            return JSONResponse(
                {"error": msg, "code": code}, status_code=status
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("secrets/resolve: unexpected error: %s", exc)
            return JSONResponse(
                {"error": "secret resolution failed", "code": "error"},
                status_code=500,
            )
        return JSONResponse({"value": value})
