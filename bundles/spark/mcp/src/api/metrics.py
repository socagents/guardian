"""Metrics HTTP endpoints — Prometheus exposition + JSON snapshot.

  GET /api/v1/metrics             → Prometheus 0.0.4 text exposition.
                                     scrape directly from this URL.
  GET /api/v1/metrics/snapshot    → JSON snapshot {name: kind} for
                                     the agent UI's debug panel.

Both endpoints require bearer auth (MCP_TOKEN or an API key). #API-F16/
#OBS-F12 — the Prometheus exposition was previously un-gated, so anything
reaching the MCP port read every counter name + value without auth. The MCP
port is loopback-only and the only in-stack caller is the Next.js
`/api/agent/metrics` proxy (which already attaches the MCP_TOKEN bearer), so
gating is transparent to the metrics panel. There is no external Prometheus
scraper pointed at this endpoint in the shipped compose; an operator who
wants to scrape it directly should mint an API key rather than reopen the
endpoint.

# Embedder stats refreshed at scrape time

The Prometheus exposition path looks up the live VertexEmbedder via
its singleton accessor and SETs gauges from `embedder.stats()` before
rendering. This avoids the embedder needing to know about the
registry — stats are a pull, not a push. Three reasons it's done at
scrape rather than on every embed() call:

  1. Decoupling: the embedder doesn't need to grow a metrics import.
  2. Correctness: at the moment Prometheus scrapes, the gauge equals
     the embedder's current cumulative count. No lock contention from
     the hot path having to update a separate counter.
  3. Cheap: gauges are SET, not incremented; the cost is one
     dict-write per gauge per scrape.

When the embedder is the boot-time TextHashEmbedder (Vertex not yet
configured), `get_embedder()` returns None and the gauges stay 0 —
which is correct: there are no upstream calls to count.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.auth import require_bearer
from usecase.metrics_registry import MetricsRegistry

logger = logging.getLogger("Guardian MCP")


def register_metrics_routes(mcp: FastMCP, registry: MetricsRegistry) -> None:
    # Pre-register the embedder gauges so they appear in the exposition
    # even before the first call (scrape returns 0). Counter-style
    # cumulative stats are exposed as Gauges because Counters in our
    # registry only support inc(), and the source-of-truth lives in
    # the embedder — we mirror it at scrape time.
    g_upstream = registry.gauge(
        "guardian_embedder_upstream_calls_total",
        "Total Vertex embed() calls that hit the upstream API.",
    )
    g_cache_hits = registry.gauge(
        "guardian_embedder_cache_hits_total",
        "Total Vertex embed() calls served from the LRU cache.",
    )
    g_fallback = registry.gauge(
        "guardian_embedder_fallback_calls_total",
        "Total Vertex embed() calls that fell back to TextHashEmbedder. "
        "Should always be 0 post-tightening — non-zero indicates an old "
        "build is running.",
    )
    g_errors = registry.gauge(
        "guardian_embedder_errors_total",
        "Total Vertex embed() calls that raised (provider error, malformed "
        "response, dim mismatch). Alert on rate(...) > 0 over 5m.",
    )
    g_cache_size = registry.gauge(
        "guardian_embedder_cache_entries",
        "Current number of (text → vector) entries in the LRU cache.",
    )

    def _refresh_embedder_gauges() -> None:
        """Pull current stats from the live embedder. No-op if the boot
        path chose TextHash (singleton returns None)."""
        try:
            from usecase.vertex_embedder import get_embedder
            e = get_embedder()
            if e is None:
                return
            s = e.stats()
            g_upstream.set(s["upstream_calls"])
            g_cache_hits.set(s["cache_hits"])
            g_fallback.set(s["fallback_calls"])
            g_errors.set(s["error_count"])
            g_cache_size.set(s["cache_size"])
        except Exception as exc:  # noqa: BLE001
            # Don't ever let metrics-collection break the scrape itself.
            # Operators have alerts on /metrics responding 5xx; we don't
            # want a transient issue in the embedder accessor to cascade
            # into an alert storm.
            logger.warning(
                "metrics: could not refresh embedder gauges (%s); "
                "leaving previous values in place.", exc,
            )

    @mcp.custom_route(
        "/api/v1/metrics", methods=["GET"], include_in_schema=False
    )
    async def prometheus_exposition(request: Request) -> Response:
        # #API-F16/#OBS-F12 — require bearer auth. Was previously open; see
        # module docstring. The only in-stack caller (the Next.js
        # /api/agent/metrics proxy) already attaches the MCP_TOKEN bearer.
        if (resp := require_bearer(request)) is not None:
            return resp
        _refresh_embedder_gauges()
        body = registry.format_prometheus()
        return Response(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @mcp.custom_route(
        "/api/v1/metrics/snapshot", methods=["GET"], include_in_schema=False
    )
    async def json_snapshot(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        snapshot: dict[str, str] = {}
        for name in registry.names():
            metric = registry.get(name)
            kind = type(metric).__name__.lower() if metric else "unknown"
            snapshot[name] = kind
        return JSONResponse({"metrics": snapshot, "count": len(snapshot)})
