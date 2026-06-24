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
from starlette.responses import JSONResponse

from api.auth import require_bearer
from usecase.audit_log import record_event
from usecase.investigation_store import InvestigationStore

logger = logging.getLogger("Guardian MCP")


def _issue_dict(issue: Any) -> dict:
    d = dataclasses.asdict(issue)
    # v0.2.45 — `report` is a full markdown document; keep it OFF the lean list
    # payload (same treatment as the SVGs). The detail endpoint adds it back.
    d.pop("report", None)
    return d


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
        # v0.2.11 — parity with the issues_list tool: structural filters the
        # autonomous loop relies on (skip sourceless Issues; oldest-first).
        srnn = request.query_params.get("source_ref_not_null")
        source_ref_not_null = str(srnn).lower() in ("1", "true", "yes")
        order = request.query_params.get("order") or "desc"
        issues = store.list_issues(
            status=status,
            case_id=case_id,
            source_ref_not_null=source_ref_not_null,
            order=order,
        )
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
            # v0.1.8 — the attack-chain SVG rides on the detail only (kept off
            # the lean list). Null until the agent generates one.
            "attack_chain_svg": store.get_attack_chain(issue.id),
            # v0.2.1 — the relations canvas SVG (same treatment).
            "relations_canvas_svg": store.get_relations_canvas(issue.id),
            # v0.2.45 (stage A) — structured outcome detail: the closure report
            # (off the lean list) + the queryable ATT&CK technique mappings.
            "report": issue.report,
            "techniques": [
                dataclasses.asdict(t) for t in store.list_technique_mappings(issue.id)
            ],
            # v0.2.47 (stage C) — KB playbooks this investigation was routed through.
            "playbook_matches": [
                dataclasses.asdict(p) for p in store.list_playbook_matches(issue.id)
            ],
        })

    @mcp.custom_route("/api/v1/issues/{id}/report", methods=["GET"], include_in_schema=False)
    async def get_issue_report(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        issue = store.get_issue(request.path_params["id"])
        if issue is None:
            return JSONResponse({"error": "issue not found"}, status_code=404)
        if not issue.report:
            return JSONResponse(
                {"error": "no report generated for this issue yet"}, status_code=404,
            )
        return JSONResponse({"issue_id": issue.id, "report": issue.report})

    @mcp.custom_route(
        "/api/v1/techniques/{technique_id}/issues", methods=["GET"], include_in_schema=False,
    )
    async def issues_by_technique(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        issues = store.list_issues_by_technique(request.path_params["technique_id"])
        return JSONResponse(
            {"issues": [_issue_dict(i) for i in issues], "count": len(issues)}
        )

    @mcp.custom_route(
        "/api/v1/playbooks/{doc_id}/issues", methods=["GET"], include_in_schema=False,
    )
    async def issues_by_playbook(request: Request) -> JSONResponse:
        # v0.2.47 (stage C) — every issue typed by a given KB playbook.
        if (resp := require_bearer(request)) is not None:
            return resp
        issues = store.list_issues_by_playbook(request.path_params["doc_id"])
        return JSONResponse(
            {"issues": [_issue_dict(i) for i in issues], "count": len(issues)}
        )

    @mcp.custom_route("/api/v1/cases/{id}/related", methods=["GET"], include_in_schema=False)
    async def case_related_route(request: Request) -> JSONResponse:
        # v0.2.47 (stage C) — typed cross-case edges touching this case.
        if (resp := require_bearer(request)) is not None:
            return resp
        case = store.get_case(request.path_params["id"])
        if case is None:
            return JSONResponse({"error": "case not found"}, status_code=404)
        out = []
        for r in store.list_case_relationships(case.id):
            outgoing = r.source_case_id == case.id
            other = store.get_case(r.target_case_id if outgoing else r.source_case_id)
            out.append({
                "relationship_type": r.relationship_type, "note": r.note,
                "direction": "outgoing" if outgoing else "incoming",
                "other_case": {"id": other.id, "title": other.title, "status": other.status} if other else None,
            })
        return JSONResponse({"related": out, "count": len(out)})

    @mcp.custom_route("/api/v1/issues/{id}/stix", methods=["GET"], include_in_schema=False)
    async def issue_stix(request: Request) -> JSONResponse:
        # v0.2.48 (stage D) — STIX 2.1 bundle for one issue (read/assemble only).
        if (resp := require_bearer(request)) is not None:
            return resp
        from usecase.builtin_components import _stix  # noqa: PLC0415
        issue = store.get_issue(request.path_params["id"])
        if issue is None:
            return JSONResponse({"error": "issue not found"}, status_code=404)
        return JSONResponse(_stix.build_issue_bundle(store, issue))

    @mcp.custom_route("/api/v1/cases/{id}/stix", methods=["GET"], include_in_schema=False)
    async def case_stix(request: Request) -> JSONResponse:
        # v0.2.48 (stage D) — campaign-level STIX 2.1 bundle for one case.
        if (resp := require_bearer(request)) is not None:
            return resp
        from usecase.builtin_components import _stix  # noqa: PLC0415
        case = store.get_case(request.path_params["id"])
        if case is None:
            return JSONResponse({"error": "case not found"}, status_code=404)
        return JSONResponse(_stix.build_case_bundle(store, case))

    @mcp.custom_route("/api/v1/issues/{id}", methods=["PATCH"], include_in_schema=False)
    async def patch_issue(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        body, err = await _json(request)
        if err:
            return err
        issue_id = request.path_params["id"]
        updated = store.update_issue(issue_id, **body)
        if updated is None:
            return JSONResponse({"error": "issue not found"}, status_code=404)
        # #INV-F2 — the Activity tab reads issue_events only; an operator
        # REST patch left no timeline entry. Append one naming the fields
        # touched (values omitted — they may be large free-text).
        changed_fields = sorted(
            k for k in body if isinstance(body.get(k), (str, int, float, bool, list, dict))
        )
        if changed_fields:
            store.add_event(
                issue_id, "issue_patched",
                "Issue fields updated: " + ", ".join(changed_fields),
            )
        # #INV-F15 — emit an investigation-domain audit event (not just the
        # coarse proxy_request_admitted row) so operator REST mutations are
        # attributable in /observability/events with the changed field set.
        try:
            record_event(
                "issue_updated",
                target=f"issue:{issue_id}",
                status="success",
                metadata={"issue_id": issue_id, "fields_changed": changed_fields},
            )
        except Exception:  # noqa: BLE001 — audit is best-effort
            pass
        return JSONResponse(_issue_dict(updated))

    @mcp.custom_route("/api/v1/issues/{id}", methods=["DELETE"], include_in_schema=False)
    async def delete_issue(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        # #INV-F14 — store.delete_issue emits the `issue_deleted` audit row
        # (with the destroyed issue's title/kind) before the cascade delete.
        deleted = store.delete_issue(request.path_params["id"])
        return JSONResponse({"deleted": deleted})

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
        # v0.2.47 (stage C) — typed cross-case edges, each with the other case's
        # title/status so the Campaign tab can link without a second round-trip.
        related = []
        for r in store.list_case_relationships(case.id):
            outgoing = r.source_case_id == case.id
            other = store.get_case(r.target_case_id if outgoing else r.source_case_id)
            related.append({
                "relationship_type": r.relationship_type, "note": r.note,
                "direction": "outgoing" if outgoing else "incoming",
                "other_case": {"id": other.id, "title": other.title, "status": other.status} if other else None,
            })
        return JSONResponse({
            **dataclasses.asdict(case),
            "issues": [_issue_dict(i) for i in issues],
            "issue_count": len(issues),
            "related": related,
            # v0.2.2 — campaign-level diagram SVGs (kept off the lean case list,
            # surfaced only on the detail). Null until the agent draws them.
            "attack_chain_svg": store.get_case_attack_chain(case.id),
            "relations_canvas_svg": store.get_case_relations_canvas(case.id),
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
    async def delete_case(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        deleted = store.delete_case(request.path_params["id"])
        return JSONResponse({"deleted": deleted})

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

    # ─── Indicators (IoCs) ─────────────────────────────────────────

    @mcp.custom_route("/api/v1/indicators", methods=["GET"], include_in_schema=False)
    async def list_indicators(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        type_ = request.query_params.get("type") or None
        issue_id = request.query_params.get("issue_id") or None
        inds = store.list_indicators(type=type_, issue_id=issue_id)
        return JSONResponse({"indicators": inds, "count": len(inds)})

    @mcp.custom_route("/api/v1/indicators/{id}", methods=["GET"], include_in_schema=False)
    async def get_indicator(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        ind = store.get_indicator(request.path_params["id"])
        if ind is None:
            return JSONResponse({"error": "indicator not found"}, status_code=404)
        # v0.2.1 — the indicator's STIX relationship edges.
        ind["relationships"] = store.list_relationships(request.path_params["id"])
        return JSONResponse(ind)

    logger.info("Investigation routes registered (issues + cases + indicators)")
