"""Trigger-context middleware — populates the trigger contextvar from
the inbound `X-Guardian-Trigger` header for the duration of one HTTP
request.

The header is set by upstream callers that want their downstream
audit rows tagged with a stable identifier:

  - The job_scheduler sets `X-Guardian-Trigger: job:<name>` on its
    POST to /api/chat (see usecase/job_scheduler.py:_dispatch_chat).
  - The agent's chat route forwards the same header to every
    downstream MCP tool call so the trigger flows from "job fires"
    → "agent /api/chat handles" → "MCP tool dispatch" → "audit row".
  - Future per-operator session attribution can add
    `X-Guardian-Trigger: operator:<id>` here without further wiring.

Without this middleware, every audit row's `trigger` column would
be NULL and operators couldn't filter the audit feed by source.
With it, /observability/events grows a "trigger" column that
distinguishes scheduler-driven activity from interactive turns.

# Why a contextvar, not request.state

We could stash the trigger on `request.state.trigger` and have the
audit recorder read it from there — but the audit recorder is
called from deeply-nested code paths (SecretStore reads,
connector-loader tool wrappers) that don't have a Request object
in scope. ContextVars propagate naturally across `await` calls
within the same task without anyone having to pass them down.
That's exactly the same pattern actor attribution already uses
(`set_current_actor` / `get_current_actor`).
"""

from __future__ import annotations

import logging

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from usecase.audit_log import (
    reset_current_actor,
    reset_current_approval_bypass,
    reset_current_chain_id,
    reset_current_trigger,
    set_current_actor,
    set_current_approval_bypass,
    set_current_chain_id,
    set_current_trigger,
)

logger = logging.getLogger("Guardian MCP.trigger")

HEADER_NAME = "X-Guardian-Trigger"

# #API-F18/OBS-F8/CHAT-F2 — the authenticated principal, set by the Next.js
# middleware after it validates the request (apikey:<id> | user:operator).
# Lets audit attribute a REST mutation to the specific operator session or
# API key instead of the hardcoded "user:operator". Same per-request
# contextvar lifetime as the trigger header.
ACTOR_HEADER_NAME = "X-Guardian-Actor"
MAX_ACTOR_LEN = 128


def actor_from_request(request: Request) -> str:
    """#CONN-F-actor/JOBS-F12 — resolve the audit actor for a mutating REST
    handler from the request, preferring the X-Guardian-Actor header that the
    Next.js middleware stamps post-auth (apikey:<id> | user:operator) over the
    legacy hardcoded "user:operator" default.

    Mutating route handlers must call `set_current_actor(actor_from_request(
    request))` instead of `set_current_actor("user:operator")` — the latter
    clobbers the real principal that TriggerContextMiddleware already placed in
    the contextvar from the header, collapsing every API-key operator mutation
    to a generic "user:operator" in the audit trail.

    Reads the HEADER directly (not get_current_actor(), which would pick up the
    MCP's ambient "system" default) so the absent-header case preserves the
    prior "user:operator" default. Mirrors api/audit.py's record_event handler.
    """
    raw = request.headers.get(ACTOR_HEADER_NAME)
    if raw:
        actor = raw.strip()[:MAX_ACTOR_LEN]
        if actor:
            return actor
    return "user:operator"

# v0.1.27: optional bypass header. Same lifetime as the trigger header
# (per-request contextvar). Truthy values activate bypass; anything
# else (or absent) leaves the default of False in place.
BYPASS_HEADER_NAME = "X-Guardian-Approval-Bypass"
_BYPASS_TRUTHY = frozenset({"1", "true", "yes", "on"})

# Cap the trigger string so a malformed/oversized header can't bloat
# the audit table. Real triggers are short — "job:nightly-coverage"
# is 22 chars; the cap is 5x that to leave headroom.
MAX_TRIGGER_LEN = 128

# #XSIAM-F13 — turn-correlation chain id, generated once per turn by the
# agent chat route and forwarded on every downstream MCP tool dispatch.
# The middleware stamps it on the chain-id contextvar so audit rows for
# that turn's tool calls share it. Same per-request contextvar lifetime
# as the trigger/actor headers. A real value is a UUID-ish token
# ("ch_<uuid4>"), well under the cap.
CHAIN_ID_HEADER_NAME = "X-Guardian-Chain-Id"
MAX_CHAIN_ID_LEN = 128


class TriggerContextMiddleware:
    """Read X-Guardian-Trigger / -Actor / -Chain-Id / -Approval-Bypass from
    the request, set the contextvars for the request lifetime, reset on exit.
    Pairs with audit_log's record() (trigger/actor/chain_id) and
    _approval_gate.gate_and_execute (bypass).

    #F-ctxvar — this is a PURE ASGI middleware (``async def __call__(scope,
    receive, send)``), deliberately NOT a ``BaseHTTPMiddleware``. The old
    BaseHTTPMiddleware ran its ``dispatch`` in a SEPARATE anyio task from the
    endpoint, so contextvars it set were invisible to the endpoint task — and
    in particular to FastMCP's streamable-HTTP tool dispatcher, which captures
    the current context when it spawns the tool-execution task. On the
    ``/api/agent/tool/call`` (``^tool``) path that meant ``trigger`` and
    ``chain_id`` intermittently dropped to NULL on the tool_call rows (the
    normal chat path was unaffected). A pure ASGI middleware sets the
    contextvars in the SAME task that then ``await``s the downstream app, so
    the context FastMCP captures already carries them and they survive to
    ``record_event``. (Documented empirically in api/skills.py's module
    docstring; this fixes the propagation at the source instead of working
    around it per-route.)
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        # Only HTTP requests carry these headers; pass lifespan/websocket
        # scopes straight through untouched.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        raw = headers.get(HEADER_NAME)
        token = None
        if raw:
            trigger = raw.strip()[:MAX_TRIGGER_LEN] or None
            if trigger:
                token = set_current_trigger(trigger)

        # Principal attribution (set by the Next.js middleware post-auth).
        actor_token = None
        actor_raw = headers.get(ACTOR_HEADER_NAME)
        if actor_raw:
            actor = actor_raw.strip()[:MAX_ACTOR_LEN] or None
            if actor:
                actor_token = set_current_actor(actor)

        # #XSIAM-F13 — turn-correlation chain id. The agent chat route
        # mints one per turn and forwards it on each tool dispatch; we
        # stamp it so the turn's tool_call audit rows share the id.
        chain_token = None
        chain_raw = headers.get(CHAIN_ID_HEADER_NAME)
        if chain_raw:
            chain_id = chain_raw.strip()[:MAX_CHAIN_ID_LEN] or None
            if chain_id:
                chain_token = set_current_chain_id(chain_id)

        # Bypass header: any of the truthy strings activates it.
        # Logged at INFO when active so operators can see post-hoc that
        # an approval was skipped due to bypass policy.
        bypass_token = None
        bypass_raw = headers.get(BYPASS_HEADER_NAME, "")
        if bypass_raw and bypass_raw.strip().lower() in _BYPASS_TRUTHY:
            bypass_token = set_current_approval_bypass(True)
            logger.info(
                "approval bypass active for this request (trigger=%s)",
                raw or "(none)",
            )

        try:
            await self.app(scope, receive, send)
        finally:
            if token is not None:
                reset_current_trigger(token)
            if actor_token is not None:
                reset_current_actor(actor_token)
            if chain_token is not None:
                reset_current_chain_id(chain_token)
            if bypass_token is not None:
                reset_current_approval_bypass(bypass_token)


def install(app) -> None:  # noqa: ANN001 — Starlette/FastAPI app
    """Install the middleware on the app.

    Call AFTER the request_log middleware so the trigger is already
    in scope when request_log records its access line — useful when
    the structured access log grows a `trigger=` field later.
    """
    app.add_middleware(TriggerContextMiddleware)
    logger.info("TriggerContextMiddleware installed (header=%s)", HEADER_NAME)
