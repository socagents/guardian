"""Bearer-token auth for the MCP admin/setup HTTP endpoints.

Two acceptable bearer shapes:

  1. **MCP_TOKEN** (bundle-internal): the Next.js agent's setup screen
     and internal tools send `Authorization: Bearer <MCP_TOKEN>`. This
     is the unrestricted admin path — same trust as the embedded MCP
     itself. Generated at container start (or pinned in `.env`).

  2. **API key** (`guardian_ak_<id>_<secret>`): operator-minted long-
     lived keys for external integrations. Looked up in the
     SqliteApiKeyStore; verified by hash; scoped per-row. Active keys
     are accepted on routes that match their scope list.

`require_bearer()` accepts either shape and returns:
  * None on success
  * JSONResponse(401/403/503) on failure

`require_scope(scope)` adds an additional check — used by routes that
want to gate on a specific scope (e.g. `audit:read` on the audit-list
endpoint). Pass-through for MCP_TOKEN (admin); enforced for API keys.
"""

from __future__ import annotations

import hmac

from starlette.requests import Request
from starlette.responses import JSONResponse

from config.config import config
from usecase.api_keys import api_key_store
from usecase.audit_log import ACTION_MCP_BEARER_AUTH_FAILED, record_event


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header[len("bearer "):].strip()


def _audit_bearer_failure(request: Request, reason: str, token: str | None) -> None:
    """#API-F7 — record a direct-to-MCP bearer auth failure. Best-effort:
    never let an audit error break the auth response. Only the key PREFIX
    (≤12 chars, the guardian_ak_ tag) is logged — no secret material."""
    try:
        record_event(
            ACTION_MCP_BEARER_AUTH_FAILED,
            target="mcp_bearer",
            status="failure",
            actor="anonymous",
            metadata={
                "reason": reason,
                "path": str(request.url.path),
                "key_prefix": (token[:12] if token else ""),
            },
        )
    except Exception:  # pragma: no cover - audit must never break auth
        pass


def require_bearer(request: Request) -> JSONResponse | None:
    """Accept MCP_TOKEN OR an active API key.

    Side effect for API keys: the row's last_used_at is updated and the
    resolved scopes are stashed on `request.state.api_key_scopes`. Routes
    that care can then call `require_scope()` to enforce.
    """
    expected = config.mcp_token
    if not expected:
        return JSONResponse(
            {"error": "MCP_TOKEN is not configured on this server"},
            status_code=503,
        )
    token = _extract_token(request)
    if token is None:
        _audit_bearer_failure(request, "missing_or_malformed_header", None)
        return JSONResponse(
            {"error": "missing or malformed Authorization header"},
            status_code=401,
        )

    # Path 1: MCP_TOKEN (admin). Constant-time compare so an attacker
    # can't infer prefix matches via timing.
    if hmac.compare_digest(token, expected):
        request.state.auth_principal = "mcp_token"
        request.state.api_key_scopes = ["*"]
        return None

    # Path 2: API key. Only consult the store when the token has the
    # API-key prefix — saves a sqlite hit on every malformed bearer.
    if token.startswith("guardian_ak_"):
        store = api_key_store()
        if store is not None:
            row = store.verify(token)
            if row is not None:
                request.state.auth_principal = f"api_key:{row.id}"
                request.state.api_key_scopes = row.scopes
                return None

    _audit_bearer_failure(request, "invalid_bearer", token)
    return JSONResponse(
        {"error": "invalid bearer token"},
        status_code=403,
    )


def require_scope(request: Request, scope: str) -> JSONResponse | None:
    """Per-route scope gate. Call AFTER `require_bearer()`.

    Wildcard `*` in the principal's scope list grants any scope. Used
    by routes that want stricter granularity than "valid token == full
    access". MCP_TOKEN principals always carry `*`.
    """
    scopes: list[str] = getattr(request.state, "api_key_scopes", []) or []
    if "*" in scopes or scope in scopes:
        return None
    return JSONResponse(
        {"error": f"token lacks required scope: {scope}"},
        status_code=403,
    )
