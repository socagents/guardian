"""Playbook-builder HTTP endpoints (v0.2.24).

Backs the /playbooks/build UI. The generative step runs through the agent
(the build_xsoar_playbook skill + knowledge_search over soar-playbooks); this
surface exposes the deterministic structural validator so the page can show a
clear valid/invalid verdict + actionable errors before the operator imports a
draft into Cortex XSOAR.

  POST /api/v1/playbooks/validate   body: {playbook_yaml: str} -> validator result
"""
from __future__ import annotations

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import require_bearer
from usecase.builtin_components.playbook_tools import playbook_validate

logger = logging.getLogger("Guardian MCP")


def register_playbook_routes(mcp: FastMCP) -> None:
    """Register /api/v1/playbooks/* routes."""

    @mcp.custom_route(
        "/api/v1/playbooks/validate", methods=["POST"], include_in_schema=False
    )
    async def validate_playbook(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse({"error": f"invalid JSON body: {exc}"}, status_code=400)
        if not isinstance(body, dict) or not isinstance(body.get("playbook_yaml"), str):
            return JSONResponse(
                {"error": "body must be {playbook_yaml: string}"}, status_code=400
            )
        return JSONResponse(playbook_validate(body["playbook_yaml"]))
