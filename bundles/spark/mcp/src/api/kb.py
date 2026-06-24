"""Knowledge-base HTTP endpoints — Phase 10 of the v1.2 architecture.

The Next.js agent's "knowledge browser" view calls these to render the
bundle's loaded KBs. All endpoints are READ-ONLY at the API surface,
matching the manifest's `kbWrites: []` declaration. Operators who
want to add docs do it the right way: edit the bundle, redeploy, the
loader picks up the new files at boot.

Endpoints (all require `Authorization: Bearer <MCP_TOKEN>`):

  GET  /api/v1/kbs                            list all KBs (with counts)
  GET  /api/v1/kbs/{name}/docs                list docs in one KB
  GET  /api/v1/kbs/{name}/docs/{doc_id}       fetch one doc (audited)
  POST /api/v1/kbs/{name}/search              KB-scoped semantic search
  POST /api/v1/kbs/search                     cross-KB search (no scope)
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import require_bearer
from usecase.audit_log import (
    ACTION_KB_DOC_READ,
    ACTION_KB_SEARCHED,
    record_event,
)
from usecase.kb_store import SqliteKnowledgeBase

logger = logging.getLogger("Guardian MCP")


def register_kb_routes(mcp: FastMCP, kb: SqliteKnowledgeBase) -> None:
    """Register /api/v1/kbs/* routes."""

    def _kb_exists_or_404(name: str) -> JSONResponse | None:
        """Return a 404 JSONResponse if `name` isn't a loaded KB, else None.

        Why this matters: previously, `GET /kbs/ghost/docs` returned an
        empty list and `POST /kbs/ghost/search` returned `count: 0` —
        silent typos masquerading as "no results". Operators couldn't
        distinguish "this KB has no entries matching" from "this KB
        doesn't exist". Now a typo gets a 404 with the full list of
        valid names so the operator (or agent) can self-correct.
        """
        if name in kb.kb_summary():
            return None
        valid = sorted(kb.kb_summary().keys())
        return JSONResponse(
            {
                "error": f"unknown knowledge base {name!r}",
                "valid_kbs": valid,
            },
            status_code=404,
        )

    @mcp.custom_route("/api/v1/kbs", methods=["GET"], include_in_schema=False)
    async def list_kbs(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        summary = kb.kb_summary()
        return JSONResponse(
            {
                "kbs": [
                    {"name": name, **stats}
                    for name, stats in sorted(summary.items())
                ],
                "count": len(summary),
            }
        )

    @mcp.custom_route(
        "/api/v1/kbs/{name}/docs", methods=["GET"], include_in_schema=False
    )
    async def list_kb_docs(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        name = request.path_params["name"]
        if (resp := _kb_exists_or_404(name)) is not None:
            return resp
        q = request.query_params
        try:
            limit = int(q.get("limit") or 100)
            offset = int(q.get("offset") or 0)
        except ValueError:
            limit, offset = 100, 0
        category = q.get("category") or None
        # v0.2.20 — optional `tags` filter (comma-separated, AND semantics)
        tags = [t for t in (q.get("tags") or "").split(",") if t.strip()] or None
        docs = kb.list_docs(
            name,
            category=category,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        # v0.7.1: expose total_count + has_more so callers can paginate
        # correctly. Pre-v0.7.1 the response had only `count` (slice
        # size) which silently hid the true total — a 787-row KB
        # returned 500 with no signal of the 287 remaining rows.
        total = kb.count_docs(name, category=category, tags=tags)
        # #KB-F6 — operator-driven KB doc listing now leaves a trace.
        record_event(
            ACTION_KB_SEARCHED,
            target=f"kb:{name}",
            status="success",
            metadata={
                "mode": "list",
                "kb_name": name,
                "category": category,
                "tags": tags,
                "limit": limit,
                "offset": offset,
                "count": len(docs),
            },
        )
        return JSONResponse(
            {
                # Default to NOT including content here — the list view
                # is for browsing, not bulk retrieval. Operators fetch
                # full content via /docs/{doc_id}.
                "documents": [d.to_dict(include_content=False) for d in docs],
                "count": len(docs),
                "total_count": total,
                "offset": offset,
                "limit": limit,
                "has_more": (offset + len(docs)) < total,
            }
        )

    @mcp.custom_route(
        "/api/v1/kbs/{name}/tags", methods=["GET"], include_in_schema=False
    )
    async def list_kb_tags(request: Request) -> JSONResponse:
        """v0.2.20 — distinct tags in a KB with doc counts, for UI filter chips."""
        if (resp := require_bearer(request)) is not None:
            return resp
        name = request.path_params["name"]
        if (resp := _kb_exists_or_404(name)) is not None:
            return resp
        return JSONResponse({"tags": kb.kb_tags(name)})

    @mcp.custom_route(
        "/api/v1/kbs/{name}/docs/{doc_id}",
        methods=["GET"],
        include_in_schema=False,
    )
    async def get_kb_doc(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        name = request.path_params["name"]
        if (resp := _kb_exists_or_404(name)) is not None:
            return resp
        doc_id = request.path_params["doc_id"]
        doc = kb.get_doc(name, doc_id)
        if doc is None:
            return JSONResponse(
                {"error": f"doc {doc_id!r} not found in kb {name!r}"},
                status_code=404,
            )
        # #KB-F6 — the module docstring claimed this endpoint was audited but
        # it emitted nothing. Now it does (kb_doc_read).
        record_event(
            ACTION_KB_DOC_READ,
            target=f"kb:{name}/docs/{doc_id}",
            status="success",
            metadata={
                "kb_name": name,
                "doc_id": doc_id,
                "title": getattr(doc, "title", None),
            },
        )
        return JSONResponse({"document": doc.to_dict()})

    @mcp.custom_route(
        "/api/v1/kbs/{name}/search",
        methods=["POST"],
        include_in_schema=False,
    )
    async def search_one_kb(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        name = request.path_params["name"]
        if (resp := _kb_exists_or_404(name)) is not None:
            return resp
        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse(
                {"error": f"invalid JSON body: {exc}"}, status_code=400
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "body must be a JSON object"}, status_code=400
            )
        query = body.get("query")
        if not isinstance(query, str) or not query.strip():
            return JSONResponse(
                {"error": "'query' is required (non-empty string)"},
                status_code=400,
            )
        _tags = body.get("tags")
        _tags = [t for t in _tags if isinstance(t, str)] if isinstance(_tags, list) else None
        hits = kb.search(
            query,
            kb_name=name,
            category=body.get("category") or None,
            tags=_tags or None,
            limit=int(body.get("limit") or 5),
            offset=int(body.get("offset") or 0),
            min_score=float(body.get("min_score") or 0.0),
        )
        return JSONResponse(
            {
                "results": [doc.to_dict(score=score) for doc, score in hits],
                "count": len(hits),
            }
        )

    @mcp.custom_route(
        "/api/v1/kbs/search", methods=["POST"], include_in_schema=False
    )
    async def search_all_kbs(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse(
                {"error": f"invalid JSON body: {exc}"}, status_code=400
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "body must be a JSON object"}, status_code=400
            )
        query = body.get("query")
        if not isinstance(query, str) or not query.strip():
            return JSONResponse(
                {"error": "'query' is required (non-empty string)"},
                status_code=400,
            )
        _tags = body.get("tags")
        _tags = [t for t in _tags if isinstance(t, str)] if isinstance(_tags, list) else None
        hits = kb.search(
            query,
            kb_name=body.get("kb_name") or None,
            category=body.get("category") or None,
            tags=_tags or None,
            limit=int(body.get("limit") or 5),
            offset=int(body.get("offset") or 0),
            min_score=float(body.get("min_score") or 0.0),
        )
        return JSONResponse(
            {
                "results": [doc.to_dict(score=score) for doc, score in hits],
                "count": len(hits),
            }
        )
