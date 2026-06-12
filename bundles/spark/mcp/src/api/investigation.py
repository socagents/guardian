"""Investigation API — Issues + Cases REST surface (v0.1.3).

The MCP-side HTTP surface the Next.js agent proxies for the Investigation
UI (sidebar → Issues / Cases). Backed by `investigation_store`. All routes
require `Authorization: Bearer <MCP_TOKEN>` (the Next.js proxy attaches it;
these are NOT credential routes — both operator + agent may read/write
investigation metadata, per the catalog boundary).

Endpoints:
  GET    /api/v1/issues               → list (query: status?, case_id?)
  POST   /api/v1/issues               → create {title, kind?, severity?, origin?, source_ref?, scope?, summary?}
  GET    /api/v1/issues/{id}          → one issue (+ events + case)
  PATCH  /api/v1/issues/{id}          → partial update
  DELETE /api/v1/issues/{id}          → remove (cascades events)
  GET    /api/v1/issues/{id}/events   → activity timeline
  POST   /api/v1/issues/{id}/events   → append {type, content}
  GET    /api/v1/cases                → list (+ issue_count each)
  POST   /api/v1/cases                → create {title, description?}
  GET    /api/v1/cases/{id}           → one case (+ its issues)
  PATCH  /api/v1/cases/{id}           → partial update
  DELETE /api/v1/cases/{id}           → remove (issues survive, ungrouped)
  POST   /api/v1/cases/{id}/issues    → add {issue_id} to the case
  GET    /api/v1/cases/{id}/issues    → list issues in the case
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.auth import require_bearer
from usecase.investigation_store import InvestigationStore

logger = logging.getLogger("Guardian MCP")


def _issue_dict(issue: Any) -> dict:
    return dataclasses.asdict(issue)


def register_investigation_routes(mcp: FastMCP, store: InvestigationStore) -> None:
    """Wire the issues + cases HTTP surface onto the given FastMCP."""

    async def _json(request: Request) -> tuple[dict | None, JSONResponse | None]:
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return None, JSONResponse({"error": f"invalid JSON body: {exc}"}, status_code=400)
        if not isinstance(body, dict):
            return None, JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        return body, None

    # ─── Issues ────────────────────────────────────────────────────

    @mcp.custom_route("/api/v1/issues", methods=["GET"], include_in_schema=False)
    async def list_issues(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        status = request.query_params.get("status") or None
        case_id = request.query_params.get("case_id") or None
        issues = store.list_issues(status=status, case_id=case_id)
        return JSONResponse(
            {"issues": [_issue_dict(i) for i in issues], "count": len(issues)}
        )

    @mcp.custom_route("/api/v1/issues", methods=["POST"], include_in_schema=False)
    async def create_issue(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        title = (body.get("title") or "").strip()
        if not title:
            return JSONResponse({"error": "title is required"}, status_code=400)
        issue = store.create_issue(
            title=title,
            kind=body.get("kind") or "other",
            severity=body.get("severity") or "medium",
            origin=body.get("origin") or "operator",
            source_ref=body.get("source_ref"),
            scope=body.get("scope"),
            summary=body.get("summary"),
        )
        return JSONResponse(_issue_dict(issue), status_code=201)

    @mcp.custom_route("/api/v1/issues/{id}", methods=["GET"], include_in_schema=False)
    async def get_issue(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        issue = store.get_issue(request.path_params["id"])
        if issue is None:
            return JSONResponse({"error": "issue not found"}, status_code=404)
        events = store.list_events(issue.id)
        case = store.get_case(issue.case_id) if issue.case_id else None
        return JSONResponse({
            **_issue_dict(issue),
            "events": [dataclasses.asdict(e) for e in events],
            "case": dataclasses.asdict(case) if case else None,
        })

    @mcp.custom_route("/api/v1/issues/{id}", methods=["PATCH"], include_in_schema=False)
    async def patch_issue(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        updated = store.update_issue(request.path_params["id"], **body)
        if updated is None:
            return JSONResponse({"error": "issue not found"}, status_code=404)
        return JSONResponse(_issue_dict(updated))

    @mcp.custom_route("/api/v1/issues/{id}", methods=["DELETE"], include_in_schema=False)
    async def delete_issue(request: Request) -> Response:
        if (resp := require_bearer(request)) is not None:
            return resp
        store.delete_issue(request.path_params["id"])
        return Response(status_code=204)

    @mcp.custom_route("/api/v1/issues/{id}/events", methods=["GET"], include_in_schema=False)
    async def list_events(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        events = store.list_events(request.path_params["id"])
        return JSONResponse(
            {"events": [dataclasses.asdict(e) for e in events], "count": len(events)}
        )

    @mcp.custom_route("/api/v1/issues/{id}/events", methods=["POST"], include_in_schema=False)
    async def add_event(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        event = store.add_event(
            request.path_params["id"],
            body.get("type") or "note",
            body.get("content") or "",
        )
        if event is None:
            return JSONResponse({"error": "issue not found"}, status_code=404)
        return JSONResponse(dataclasses.asdict(event), status_code=201)

    # ─── Cases ─────────────────────────────────────────────────────

    @mcp.custom_route("/api/v1/cases", methods=["GET"], include_in_schema=False)
    async def list_cases(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        cases = store.list_cases()
        return JSONResponse({"cases": cases, "count": len(cases)})

    @mcp.custom_route("/api/v1/cases", methods=["POST"], include_in_schema=False)
    async def create_case(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        title = (body.get("title") or "").strip()
        if not title:
            return JSONResponse({"error": "title is required"}, status_code=400)
        case = store.create_case(title=title, description=body.get("description"))
        return JSONResponse(dataclasses.asdict(case), status_code=201)

    @mcp.custom_route("/api/v1/cases/{id}", methods=["GET"], include_in_schema=False)
    async def get_case(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        case = store.get_case(request.path_params["id"])
        if case is None:
            return JSONResponse({"error": "case not found"}, status_code=404)
        issues = store.list_issues(case_id=case.id)
        return JSONResponse({
            **dataclasses.asdict(case),
            "issues": [_issue_dict(i) for i in issues],
            "issue_count": len(issues),
        })

    @mcp.custom_route("/api/v1/cases/{id}", methods=["PATCH"], include_in_schema=False)
    async def patch_case(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        updated = store.update_case(request.path_params["id"], **body)
        if updated is None:
            return JSONResponse({"error": "case not found"}, status_code=404)
        return JSONResponse(dataclasses.asdict(updated))

    @mcp.custom_route("/api/v1/cases/{id}", methods=["DELETE"], include_in_schema=False)
    async def delete_case(request: Request) -> Response:
        if (resp := require_bearer(request)) is not None:
            return resp
        store.delete_case(request.path_params["id"])
        return Response(status_code=204)

    @mcp.custom_route("/api/v1/cases/{id}/issues", methods=["GET"], include_in_schema=False)
    async def list_case_issues(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        issues = store.list_issues(case_id=request.path_params["id"])
        return JSONResponse(
            {"issues": [_issue_dict(i) for i in issues], "count": len(issues)}
        )

    @mcp.custom_route("/api/v1/cases/{id}/issues", methods=["POST"], include_in_schema=False)
    async def add_issue_to_case(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        issue_id = body.get("issue_id")
        if not issue_id:
            return JSONResponse({"error": "issue_id is required"}, status_code=400)
        updated = store.add_issue_to_case(issue_id, request.path_params["id"])
        if updated is None:
            return JSONResponse(
                {"error": "issue or case not found"}, status_code=404
            )
        return JSONResponse(_issue_dict(updated))

    logger.info("Investigation routes registered (issues + cases)")
