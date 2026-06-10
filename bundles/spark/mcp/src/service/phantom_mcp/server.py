"""MCP Server creation and lifecycle management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("Phantom MCP")


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
            logger.info("Initializing Phantom MCP Server...")
            context: dict = {}
            logger.info("Phantom MCP Server initialized successfully")
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
# Guardian MCP Server - AI Incident Response Platform

You are connected to the Guardian MCP Server, an AI incident-response platform that investigates security incidents in integration with Cortex XSOAR and XSIAM:

## Core Capabilities

### 1. Cortex XSIAM Security Platform Integration
- Execute XQL queries for threat hunting and investigation
- Manage security cases, assets, and issues
- Interact with lookup tables for enrichment data
- Access datasets and field information
- AI-powered XQL query assistance with knowledge-base retrieval

### 2. Cortex XDR Integration
- List and inspect incidents from a Cortex XDR tenant
- Execute XQL queries against XDR telemetry for evidence gathering

### 3. Cortex Documentation & Content Lookup
- Search the public Palo Alto Networks Cortex documentation (XDR / XSIAM / XSOAR / XQL)
- Fetch XSIAM/XSOAR content packs from the public demisto/content repository (modeling rules, parsing rules, correlation rules)

### 4. Web Research (optional connector)
- Headless-browser fetch of threat-intel pages, vendor advisories, and CTI portals

## Common Use Cases

**Incident Investigation**: Pull an incident's alerts and artifacts, query the tenant for related telemetry, and build an evidence-grounded timeline

**Threat Hunting**: Author and execute XQL queries against XSIAM/XDR datasets, refining hypotheses iteratively

**Alert Enrichment**: Correlate alerts with lookup tables, asset inventory, and external threat intelligence

**Detection Context**: Reference canonical detection/parsing content from the Cortex marketplace when interpreting alerts

## Best Practices

1. **Identify the incident scope first** — incident ID, time window, affected assets — before running queries
2. **Ground every conclusion in retrieved evidence** — cite incident IDs, alert IDs, and query results; never speculate where a query can answer
3. **Use XSIAM/XDR queries** to validate hypotheses against tenant telemetry
4. **Prefer bundled skills and documented workflows** before inventing a new investigation flow
5. **Record incident IDs, alert IDs, and evidence references** in every final answer

Always verify connectivity to the configured Cortex tenant before starting an investigation.
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
                           submitted. Reads from PHANTOM_EMBEDDER_MODE
                           env var because the embedder is constructed
                           in async_main but the route handler runs in
                           Starlette's worker context — sharing a
                           module-global would race; env vars are the
                           cheapest cross-coroutine read.
        """
        import os
        return JSONResponse(
            {
                "status": "ok",
                "embedder_mode": os.environ.get("PHANTOM_EMBEDDER_MODE", "unknown"),
            },
        )

    return mcp
