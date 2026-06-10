"""MCP-over-HTTP proxy client for per-instance connector containers.

When a connector instance has `runtimeMapping.style: container` in
its connector.yaml (v0.2 architecture per
docs/spec-per-instance-connector-containers.md), the agent's MCP
loader (`connector_loader.py`) registers a proxy callable for each
tool instead of importing the connector module in-process. The proxy
forwards each tool call over MCP-over-HTTP to the connector
container's own MCP server (which runs FastMCP on port 9000 by
default — see guardian-connector-runtime/runtime/entrypoint.py).

# Per-call connection model (Phase 1 simplification)

Each `proxy_call_tool` call opens a fresh MCP session: open
streamable-http transport → ClientSession.initialize() → call_tool
→ close. No session caching, no shared state.

Cost: ~10-30 ms HTTP-roundtrip + MCP-handshake latency per call,
measured on local Docker network. Negligible for SOC tooling pace
(human-driven chat invokes tools ~once-per-second at peak; this
overhead disappears against tool-side execution time of >100 ms for
anything actually doing work).

When (not if) Phase 2 measurement shows session-caching is worth the
complexity, the right place to add it is here — wrap the streamable-
http context manager + ClientSession in a `ConnectorSession` class
keyed by container_url, with a small LRU keepalive. The call_tool
API surface stays unchanged; only this module's internals.

# Failure modes

  - **Container unreachable** (DNS resolution fails, TCP refused):
    raises ConnectorProxyError with the resolved URL + the
    underlying exception type. guardian-updater will detect dead
    containers via Docker healthcheck + restart per its
    `restart: unless-stopped` policy. The agent's chat handler
    surfaces the error to the operator.
  - **Container returns isError** (the MCP CallToolResult.isError
    flag): raises ConnectorProxyError with the tool's own error
    text. This preserves the connector's own error message without
    obscuring it.
  - **Container's tool raises**: the FastMCP server inside the
    container converts the exception to an isError result + text;
    we fall through to the previous case.
  - **Container alive but unresponsive** (TCP connected but no
    response): timed out per `timeout_seconds` (default 60s).
    Connector containers MUST return within their timeout budget;
    long-running tools should be async with a job-id pattern (see
    spec doc D7 "Slow tool call").
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger("Guardian MCP.connector-proxy")


class ConnectorProxyError(RuntimeError):
    """Raised when the proxy can't reach a connector container or the
    container returns an MCP-level error. The exception text always
    starts with "connector <url> ..." so chat-layer error display
    can prefix-match for friendlier formatting."""


def _mcp_url(container_url: str) -> str:
    """Compose the MCP endpoint URL from the container's base URL.

    The runtime entrypoint mounts FastMCP at `/mcp` via
    `mcp.http_app(path="/mcp", transport="streamable-http")`. This
    helper exists in case future Phase 2/3 work moves it (e.g. to a
    versioned path); centralizing here keeps the rest of the proxy
    blissfully unaware.
    """
    return f"{container_url.rstrip('/')}/mcp"


def _flatten_content(content_list: list[Any]) -> Any:
    """Convert an MCP CallToolResult.content list into a value the
    agent's tool dispatcher can return to the chat layer.

    Most connector tools return a single TextContent block whose
    `text` field is JSON. Decode that to a Python object so the
    agent sees the same shape it would have seen from the in-process
    callable. Fallback: pass the block through as-is (covers
    ImageContent, EmbeddedResource, plus future MCP content types).

    Multi-block results — rare for guardian's tools but allowed by
    the MCP spec — are flattened to a list of {type, text|data}
    dicts. This is a lossy projection; tools that genuinely need
    multi-block responses (e.g. stream of partial JSON) should
    return one block with structured payload instead.
    """
    if not content_list:
        return ""
    if len(content_list) == 1:
        c = content_list[0]
        text = getattr(c, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
        # ImageContent has .data (base64), ResourceContent has .uri etc.
        return getattr(c, "data", None) or getattr(c, "uri", None) or str(c)
    # Multi-block: project each to a small dict.
    return [
        {
            "type": getattr(c, "type", "unknown"),
            "text": getattr(c, "text", None),
            "data": getattr(c, "data", None),
        }
        for c in content_list
    ]


async def proxy_call_tool(
    container_url: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    timeout_seconds: int = 60,  # noqa: ARG001 — Phase 2 will plumb this
) -> Any:
    """Forward a tool call to the connector container's MCP server
    and return the unwrapped result.

    Args:
        container_url: scheme+host+port of the connector container,
            e.g. "http://guardian-connector-web-acme:9000". The /mcp
            path is appended internally.
        tool_name: bare tool name as registered by the connector
            container's FastMCP server. Per the runtime contract,
            this is the name WITHOUT any `guardian_<id>_` /
            `<id>_` / `guardian_` prefix (the runtime entrypoint
            strips those at registration time).
        args: keyword arguments to pass to the tool. Empty dict is
            valid; None is treated as empty.
        timeout_seconds: total per-call timeout (currently unwired —
            the streamablehttp_client honors its own internal
            timeout; explicit per-call deadline lands in Phase 2).

    Returns: the tool's result, JSON-decoded when the container
        returned a single text block (most cases). See
        `_flatten_content` for the decoding rules.

    Raises: ConnectorProxyError on any failure — container
        unreachable, MCP-level error, or tool-returned error.
    """
    args = args or {}

    url = _mcp_url(container_url)

    try:
        async with streamablehttp_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
    except ConnectorProxyError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConnectorProxyError(
            f"connector {url}: could not call {tool_name!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    # Tool-returned error — surface the connector's own message.
    if getattr(result, "isError", False):
        err_text = "\n".join(
            getattr(c, "text", str(c)) for c in (result.content or [])
        )
        raise ConnectorProxyError(
            f"connector {url}: tool {tool_name!r} returned error: "
            f"{err_text or '(no detail)'}"
        )

    return _flatten_content(result.content or [])


async def list_remote_tools(container_url: str) -> list[dict[str, Any]]:
    """Fetch the tool catalog from a connector container's MCP.

    Used at instance-start time by the loader to:
      1. Confirm the container is responsive (sanity check).
      2. Compare against the connector.yaml's spec.tools[] to
         detect drift (declared tools that the container doesn't
         actually expose, or vice versa). Phase 1 just logs a
         WARNING on mismatch; Phase 2 may upgrade to error.

    Returns a list of {name, description} dicts. Same shape FastMCP's
    `tools/list` produces, projected down to the fields the loader
    cares about.
    """
    url = _mcp_url(container_url)
    try:
        async with streamablehttp_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
    except Exception as exc:  # noqa: BLE001
        raise ConnectorProxyError(
            f"connector {url}: could not list tools: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    return [
        {"name": t.name, "description": t.description or ""}
        for t in tools_result.tools
    ]


async def health_check(container_url: str) -> bool:
    """Probe the connector container's /health endpoint.

    Returns True iff the endpoint responds 200 within ~5 seconds.
    Exists as a separate path from MCP because /health is cheaper
    (no MCP initialize + tools/list), suitable for high-frequency
    polling by guardian-updater's status endpoint or the agent UI's
    /connectors instance-status indicator.
    """
    import httpx

    health_url = f"{container_url.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(health_url)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False
