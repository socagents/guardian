"""Benchmark HTTP endpoints — Issue #24 UI gap fill (v0.5.35).

Surfaces the BenchRunStore (v0.5.29 storage) for the /observability/bench
UI page added in v0.5.35. Three endpoints:

  GET    /api/v1/bench/runs                  → list recent runs
  GET    /api/v1/bench/runs/{run_id}         → per-run detail
  POST   /api/v1/bench/runs                  → invoke bench_run tool

The POST is a thin convenience layer over the bench_run MCP tool —
operators can trigger a benchmark from the UI without going through
chat. Auth via bearer MCP_TOKEN like every other /api/v1/* endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import require_bearer
from api.trigger_context import actor_from_request
from usecase.audit_log import ACTION_BENCH_RUN_STARTED, record_event
from usecase.benchmark import BenchRunStore

logger = logging.getLogger("Guardian MCP")


def register_bench_routes(mcp: FastMCP, store: BenchRunStore) -> None:
    """Register /api/v1/bench/* routes on the FastMCP server."""

    @mcp.custom_route(
        "/api/v1/bench/runs", methods=["GET"], include_in_schema=False,
    )
    async def list_runs(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        # v0.6.10 — no default limit, no hard cap. Pre-v0.6.10 was
        # `limit=20` with `min(limit, 100)` cap. /observability/bench
        # could silently truncate the run history. Pagination opt-in.
        raw = request.query_params.get("limit")
        try:
            limit: int | None = int(raw) if raw not in (None, "") else None
        except ValueError:
            limit = None
        if limit is not None and limit <= 0:
            limit = None
        rows = store.list_recent(limit=limit)
        return JSONResponse({"runs": rows, "count": len(rows)})

    @mcp.custom_route(
        "/api/v1/bench/runs/{run_id}",
        methods=["GET"],
        include_in_schema=False,
    )
    async def get_run(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        run_id = request.path_params["run_id"]
        row = store.get(run_id)
        if row is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"run": row})

    @mcp.custom_route(
        "/api/v1/bench/runs",
        methods=["POST"],
        include_in_schema=False,
    )
    async def start_run(request: Request) -> JSONResponse:
        """Trigger a bench run from the UI. Returns the recorded
        summary. Synchronous — bench runs are typically 1-5 minutes
        for the bundled corpus, fits in HTTP request scope."""
        if (resp := require_bearer(request)) is not None:
            return resp
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "body must be JSON"}, status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "body must be a JSON object"}, status_code=400,
            )
        manifest = body.get("manifest")
        if not isinstance(manifest, str) or not manifest.strip():
            return JSONResponse(
                {"error": "'manifest' is required (path or bundled id)"},
                status_code=400,
            )
        router_preset = body.get("router_preset_model")
        if router_preset is not None and not isinstance(router_preset, str):
            return JSONResponse(
                {"error": "router_preset_model must be a string"},
                status_code=400,
            )
        thinking_enabled = bool(body.get("thinking_enabled", False))

        # #OBS-F13 — the /observability/bench UI button hits this REST endpoint
        # directly (not the chat bench_run tool), so previously a UI-triggered
        # run left NO audit row. Record who invoked it + the run parameters.
        actor = actor_from_request(request)
        bench_meta = {
            "manifest": manifest,
            "router_preset_model": router_preset,
            "thinking_enabled": thinking_enabled,
            "via": "rest",
        }

        from usecase.benchmark_runner import run_manifest
        try:
            summary = await run_manifest(
                manifest,
                router_preset_model=router_preset,
                thinking_enabled=thinking_enabled,
                record=True,
            )
        except ValueError as exc:
            record_event(
                ACTION_BENCH_RUN_STARTED,
                target=f"bench:{manifest}",
                status="failure",
                actor=actor,
                metadata={**bench_meta, "error": str(exc)},
            )
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:  # noqa: BLE001
            logger.exception("bench run failed for manifest %s", manifest)
            record_event(
                ACTION_BENCH_RUN_STARTED,
                target=f"bench:{manifest}",
                status="failure",
                actor=actor,
                metadata={**bench_meta, "error": f"{type(exc).__name__}: {exc}"},
            )
            return JSONResponse(
                {"error": f"run failed: {exc}"}, status_code=500,
            )
        record_event(
            ACTION_BENCH_RUN_STARTED,
            target=f"bench:{summary.run_id}",
            status="success",
            actor=actor,
            metadata={**bench_meta, "run_id": summary.run_id},
        )
        return JSONResponse(
            {"run_id": summary.run_id, "summary": summary.to_dict()},
            status_code=201,
        )
