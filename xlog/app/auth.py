"""xlog API auth — bearer-token check against XLOG_API_KEY env.

Until this module shipped, xlog accepted any caller. The agent's
xlog connector instance always presented `xlogApiToken` from the
setup form, but xlog itself never validated it — the field was
scaffolded for spec compliance, not enforced.

This middleware closes that gap. The check:

  1. Routes whitelisted via SKIP_AUTH_PATHS bypass the check
     unconditionally — `/health` so docker healthchecks work
     without baking the token into a probe URL.
  2. If XLOG_API_KEY is unset (e.g. local dev or upgrade-in-progress),
     the middleware logs a startup warning and lets requests through
     — preserves backwards compatibility for deploys that haven't
     yet set the env var.
  3. Otherwise, the request must carry `Authorization: Bearer <token>`
     (or `Authorization: <token>` — accept both shapes since the
     phantom agent's xlog connector historically used the bare-value
     form). Constant-time compare to avoid timing leaks.
  4. Mismatch → 401. Missing header → 401.

The expected token's source of truth is whatever env var the
container booted with. CI populates this from
`${{ secrets.XLOG_API_KEY }}`; self-hosted operators put it in
their own `.env`. The agent's setup form `xlogApiToken` field
must match the same value (validated by xlog at every request
once enforcement is on).
"""

from __future__ import annotations

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from typing import Awaitable, Callable

logger = logging.getLogger("xlog.auth")

# Paths that bypass the bearer check. /health is the docker healthcheck
# probe; / is the GraphQL endpoint which has its own scrutiny via
# Strawberry but historically permitted unauth queries — keeping that
# behavior for now to avoid breaking existing tooling that introspects
# the schema. Future tightening: gate / on the same bearer.
SKIP_AUTH_PATHS = {"/health", "/"}

ENV_VAR = "XLOG_API_KEY"


class XLogBearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without a matching `Authorization: Bearer <token>`."""

    def __init__(self, app, *, expected_token: str | None = None) -> None:
        super().__init__(app)
        # Snapshot the expected token at middleware construction (boot time).
        # Reading per-request would let an operator hot-rotate without a
        # restart; we explicitly want restart-bound rotation so audit/
        # log correlation stays consistent with deploy events.
        self._expected = (expected_token or os.getenv(ENV_VAR) or "").strip()
        if not self._expected:
            logger.warning(
                "%s is NOT set — xlog accepting requests WITHOUT bearer "
                "authentication. Set %s in .env to enforce.",
                ENV_VAR, ENV_VAR,
            )
        else:
            logger.info(
                "xlog bearer auth ENABLED (token length: %d chars). "
                "Requests must carry `Authorization: Bearer <token>`.",
                len(self._expected),
            )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Whitelist pass-through.
        if request.url.path in SKIP_AUTH_PATHS:
            return await call_next(request)

        # No expected token configured → permissive (logged once at boot).
        if not self._expected:
            return await call_next(request)

        header = request.headers.get("authorization") or ""
        if not header:
            return JSONResponse(
                {"error": "missing Authorization header"}, status_code=401,
            )

        # Accept both "Bearer <token>" and bare "<token>" forms — the
        # phantom-agent's xlog connector has historically used the bare
        # form. Strip the "Bearer " prefix when present.
        if header.lower().startswith("bearer "):
            presented = header[len("bearer "):].strip()
        else:
            presented = header.strip()

        if not hmac.compare_digest(presented, self._expected):
            return JSONResponse(
                {"error": "invalid xlog API token"}, status_code=401,
            )
        return await call_next(request)
