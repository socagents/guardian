"""Playbook-build history API — REST surface (v0.2.50).

The MCP-side HTTP surface the Next.js agent proxies for the playbook-
build history (the /playbooks/build UI's "builds" panel). Backed by
`playbook_build_store`. All routes require `Authorization: Bearer
<MCP_TOKEN>` (the Next.js proxy attaches it).

These are NOT credential routes — they read/write build METADATA
(use-case, drafted YAML, status) in playbook_builds.db and touch no
SecretStore value (the XSOAR creds live in the connector instance's
SecretStore, never in a build row). Per the catalog boundary, both
operator + agent may read/write playbook-build metadata.

Endpoints:
  GET    /api/v1/playbook-builds            → list (query: status?, order?)
  POST   /api/v1/playbook-builds            → create {use_case, product?, playbook_name?, playbook_yaml?, status?, validation_json?, session_id?}
  GET    /api/v1/playbook-builds/{build_id} → one build (full record + YAML)
  PATCH  /api/v1/playbook-builds/{build_id} → partial update
  DELETE /api/v1/playbook-builds/{build_id} → remove
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import require_bearer
from api.trigger_context import actor_from_request
from usecase.playbook_build_store import PlaybookBuildStore

logger = logging.getLogger("Guardian MCP")


def _compact(build: Any) -> dict:
    """Lean per-build view for the list payload — drops the two large
    free-text fields (playbook_yaml + deploy_summary). The detail
    endpoint returns the full record."""
    d = dataclasses.asdict(build)
    d.pop("playbook_yaml", None)
    d.pop("deploy_summary", None)
    return d


def register_playbook_build_routes(mcp: FastMCP, store: PlaybookBuildStore) -> None:
    """Wire the playbook-build history HTTP surface onto the given FastMCP."""

    async def _json(request: Request) -> tuple[dict | None, JSONResponse | None]:
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return None, JSONResponse({"error": f"invalid JSON body: {exc}"}, status_code=400)
        if not isinstance(body, dict):
            return None, JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        return body, None

    # ─── Builds ────────────────────────────────────────────────────

    @mcp.custom_route("/api/v1/playbook-builds", methods=["GET"], include_in_schema=False)
    async def list_builds(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        status = request.query_params.get("status") or None
        order = request.query_params.get("order") or "desc"
        builds = store.list_builds(status=status, order=order)
        return JSONResponse(
            {"builds": [_compact(b) for b in builds], "count": len(builds)}
        )

    @mcp.custom_route("/api/v1/playbook-builds", methods=["POST"], include_in_schema=False)
    async def create_build(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        use_case = (body.get("use_case") or "").strip()
        if not use_case:
            return JSONResponse({"error": "use_case is required"}, status_code=400)
        build = store.create_build(
            use_case=use_case,
            product=body.get("product"),
            playbook_name=body.get("playbook_name"),
            playbook_yaml=body.get("playbook_yaml"),
            status=body.get("status") or "drafted",
            validation_json=body.get("validation_json"),
            session_id=body.get("session_id"),
            created_by=actor_from_request(request),
        )
        return JSONResponse(dataclasses.asdict(build), status_code=201)

    @mcp.custom_route(
        "/api/v1/playbook-builds/{build_id}", methods=["GET"], include_in_schema=False,
    )
    async def get_build(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        build = store.get_build(request.path_params["build_id"])
        if build is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(dataclasses.asdict(build))

    @mcp.custom_route(
        "/api/v1/playbook-builds/{build_id}", methods=["PATCH"], include_in_schema=False,
    )
    async def patch_build(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        # Only the lifecycle-update fields are patchable from REST; the
        # store ignores unknown keys + skips None values (leaving that
        # field alone). Setting status to deployed/tested/failed emits
        # the matching audit event inside update_build.
        updated = store.update_build(
            request.path_params["build_id"],
            status=body.get("status"),
            playbook_name=body.get("playbook_name"),
            playbook_yaml=body.get("playbook_yaml"),
            validation_json=body.get("validation_json"),
            deploy_summary=body.get("deploy_summary"),
            test_incident_id=body.get("test_incident_id"),
        )
        if updated is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(dataclasses.asdict(updated))

    @mcp.custom_route(
        "/api/v1/playbook-builds/{build_id}", methods=["DELETE"], include_in_schema=False,
    )
    async def delete_build(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        deleted = store.delete_build(request.path_params["build_id"])
        if not deleted:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"deleted": True})

    logger.info("Playbook-build routes registered (playbook-builds)")
