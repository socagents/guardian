"""MCP Server creation and lifecycle management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("Guardian MCP")


def create_mcp_lifespan():
    """
    Factory function to create mcp_lifespan.

    The lifespan context is intentionally minimal — connector tools
    resolve their per-instance config (URLs, credentials) through the
    InstanceStore contextvar wrapping in connector_loader, not through
    lifespan state. The context dict stays as the extension point for
    future cross-tool shared state.
    """

    @asynccontextmanager
    async def mcp_lifespan(mcp_server: FastMCP) -> AsyncIterator[dict]:
        try:
            logger.info("Initializing Guardian MCP Server...")
            context: dict = {}
            logger.info("Guardian MCP Server initialized successfully")
            yield context
        except Exception as e:
            logger.exception(f"Error during MCP server initialization: {e}")
            raise

    return mcp_lifespan


def create_mcp_server() -> FastMCP:
    """Create FastMCP server. Connector config is resolved lazily from
    the InstanceStore at each tool call — see connector_loader."""
    lifespan = create_mcp_lifespan()

    mcp = FastMCP(
        name="Guardian MCP Server",
        instructions="""
# Guardian MCP Server - AI Incident-Investigation Agent for Cortex XSOAR

You are connected to the Guardian MCP Server, an AI agent that investigates the cases (incidents) opened on a Cortex XSOAR tenant:

## Core Capabilities

### 1. Cortex XSOAR Case Integration
- List the cases (incidents) open on the XSOAR tenant, with filters
- Fetch a single case's full detail: fields, evidence, work notes
- Summarize case context and build evidence-grounded timelines
- Document findings back to the case (work notes) and update or close it
- Supports both XSOAR 6 (on-prem) and XSOAR 8 / Cortex cloud tenants

### 2. Cortex Documentation Lookup (optional connector)
- Search the public Palo Alto Networks Cortex documentation (XSOAR / Cortex Cloud) to ground answers in canonical product behavior

### 3. Web Research (optional connector)
- Headless-browser fetch of threat-intel pages, vendor advisories, and CTI portals

## Common Use Cases

**Case Triage**: List the cases open on XSOAR, identify which need attention, and pull each case's context

**Case Investigation**: Fetch a case's fields and evidence, build an evidence-grounded timeline, and document findings back to the case

**Case Closure**: After investigation, record the conclusion as a work note and update or close the case

## Best Practices

1. **Identify the case scope first** — case ID, time window, affected entities — before acting
2. **Ground every conclusion in retrieved evidence** — cite case IDs and evidence references; never speculate where a case lookup can answer
3. **Document findings back to the case** so the investigation trail lives on the XSOAR case, not just in chat
4. **Prefer bundled skills and documented workflows** before inventing a new investigation flow
5. **Require operator confirmation** before any action that changes case state (update, close)

Always verify connectivity to the configured Cortex XSOAR tenant before starting an investigation.
""",
        lifespan=lifespan,
    )

    @mcp.custom_route("/ping/", methods=["GET"], include_in_schema=False)
    async def _health_check_route(request: Request) -> JSONResponse:
        """Liveness + lightweight readiness probe.

        Returns:
            status:        "ok" — process is up
            embedder_mode: "vertex" | "stub" — set by main.py at boot.
                           "stub" means search returns hash-similarity
                           scores, NOT semantic matches; the UI should
                           show a degradation badge until creds are
                           submitted. Reads from GUARDIAN_EMBEDDER_MODE
                           env var because the embedder is constructed
                           in async_main but the route handler runs in
                           Starlette's worker context — sharing a
                           module-global would race; env vars are the
                           cheapest cross-coroutine read.
        """
        import os
        import importlib.util
        # #CHAT-F30 — surface whether PyYAML is importable so the UI can
        # disable the YAML transcript-export option instead of offering a
        # dead click that only fails (501) after the download is attempted.
        pyyaml_available = importlib.util.find_spec("yaml") is not None
        return JSONResponse(
            {
                "status": "ok",
                "embedder_mode": os.environ.get("GUARDIAN_EMBEDDER_MODE", "unknown"),
                "pyyaml_available": pyyaml_available,
            },
        )

    return mcp
