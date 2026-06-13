"""Instance CRUD HTTP endpoints — Stage 3C of the v1.2 architecture.

The Next.js agent's setup screen + admin tools call these to materialize
connector instances declared by `manifest.yaml:setup.bindsInstances[]`.
Tools advertised by the MCP gate on the existence of instances (see
`usecase/connector_loader.py:iter_registrations`).

Endpoints (all require `Authorization: Bearer <MCP_TOKEN>`):

  GET    /api/v1/instances                 → list all instances
  GET    /api/v1/instances?connector_id=X  → list instances for a connector
  POST   /api/v1/instances                 → create one instance
  GET    /api/v1/instances/{instance_id}   → fetch one
  DELETE /api/v1/instances/{instance_id}   → delete one

NOTE: tool re-advertisement after CRUD is NOT yet live — the MCP needs
a process restart to re-run iter_registrations and pick up new
instances. The CRUD response includes `requires_mcp_restart: true` so
clients (the agent) can show the right UX. Live re-advertisement is a
follow-up — the simplest path is to fire `docker compose restart
guardian-mcp` after a successful CRUD; fastmcp 2.13+ may support
notifications/tools/list_changed but I haven't validated that path yet.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import require_bearer
from usecase.audit_log import audit_log, reset_current_actor, set_current_actor
from usecase.connector_probes import PROBE_IMPLEMENTED, real_probe
from usecase.connector_state import get_connector_state_store
from usecase.instance_store import Instance, InstanceStore

logger = logging.getLogger("Guardian MCP")


def _instance_to_dict(
    inst: Instance,
    *,
    redact_secrets: bool = True,
    secret_store: Any | None = None,
) -> dict[str, Any]:
    """Serialize for HTTP response. Secrets are redacted by default.

    v0.1.15: `enabled` is now per-instance (instances.enabled column),
    independent of connector_state. `state` is still sourced from
    connector_state — that captures the *connection health* of the
    upstream (connected/failed/needs-auth/pending), which is a
    different axis from "is this the operator's chosen instance".
    Both must be true for tools to actually work in chat.

    v0.1.36: when ``redact_secrets=False`` AND ``secret_store`` is
    provided, the secrets dict is returned as cleartext via
    ``inst.resolved_secrets(secret_store)`` — used by the backup
    feature so the resulting zip is restore-complete on a different
    deployment with a different GUARDIAN_SECRET_KEK. Without
    ``secret_store`` (legacy callers), the raw secret_refs (paths,
    not values) are returned for back-compat.
    """
    cs_store = get_connector_state_store()
    state = "pending"
    if cs_store is not None:
        cs = cs_store.get(inst.connector_id)
        if cs is not None:
            state = cs.state
    if redact_secrets:
        secrets_out: dict[str, Any] = {k: "***" for k in inst.secrets}
    elif secret_store is not None:
        secrets_out = inst.resolved_secrets(secret_store)
    else:
        secrets_out = inst.secrets
    return {
        "id": inst.id,
        "connector_id": inst.connector_id,
        "name": inst.name,
        "config": inst.config,
        "secrets": secrets_out,
        "created_at": inst.created_at,
        "enabled": inst.enabled,
        "state": state,
        # v0.6.50 — added container_url to the response shape. Field
        # exists on the Instance dataclass (set by guardian-updater's
        # _agent_set_container_url callback for style:container
        # connectors) but this serializer was silently dropping it.
        # Caught during a bug-scan pass: SQLite row had a valid
        # container_url for xsoar and cortex-docs but
        # API consumers got None. Same gap is fixed in the
        # instances_list + instances_get MCP tools in self_mod_tools.py
        # (bug-family). None is the expected value for in-process
        # style:module connectors.
        "container_url": inst.container_url,
        # v0.14.0 R4.0 — per-instance disabled-tools list. Drives the
        # /connectors instance Tools tab. Empty = all tools enabled.
        "disabled_tools": list(inst.disabled_tools),
    }


def register_instance_routes(mcp: FastMCP, store: InstanceStore) -> None:
    """Register /api/v1/instances/* routes on the FastMCP server."""

    @mcp.custom_route("/api/v1/instances", methods=["GET"], include_in_schema=False)
    async def list_instances(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        connector_id = request.query_params.get("connector_id")
        # v0.1.36 — backup feature reads cleartext secrets from the
        # InstanceStore via this flag. Mirrors v0.1.34's ProviderStore
        # ?include_secrets=true pattern. Bearer auth is the gate; the
        # agent's /api/agent/backup route is the public-facing surface
        # and verifies the operator's session cookie before proxying
        # here. Default REMAINS redacted — every existing caller gets
        # the masked "***" sentinel as before.
        include_secrets = (
            request.query_params.get("include_secrets", "").lower() == "true"
        )
        if connector_id:
            instances = store.list_for(connector_id)
        else:
            instances = store.list_all()
        return JSONResponse(
            {
                "instances": [
                    _instance_to_dict(
                        i,
                        redact_secrets=not include_secrets,
                        secret_store=(
                            store._secret_store if include_secrets else None
                        ),
                    )
                    for i in instances
                ]
            }
        )

    # ─── v0.1.31 — connector container lifecycle helpers (Phase 2) ───────
    #
    # When a connector's connector.yaml has runtimeMapping.style: container,
    # the agent's instance create/delete handlers also call guardian-updater
    # to start/stop the per-instance container. Without these calls, the
    # connector_loader's container branch (P1.7) finds container-style
    # instances with no container_url set and tool calls error out at the
    # proxy with "container_url not set."
    #
    # guardian-updater is at GUARDIAN_UPDATER_URL (default
    # http://guardian-updater:8090) and authenticated by the same MCP_TOKEN
    # the agent uses for /api/v1 — both services inherit it from the host
    # .env at startup.

    def _load_connector_spec(connector_id: str) -> dict[str, Any] | None:
        """Read connector.yaml from disk for the given id.

        v0.5.0: also scans /app/data/user_connectors/<id>/ for
        user-uploaded connectors. Returns the parsed YAML (or None
        when the file is missing/unparseable). Callers tolerate
        None as "unknown connector" (the install gate above
        prevents instance creation from unknown ids anyway).
        """
        from pathlib import Path
        import yaml

        bundle_root = Path(os.environ.get("BUNDLE_ROOT", "/app/bundle"))
        candidates = [
            bundle_root / "connectors" / connector_id / "connector.yaml",
            Path(os.environ.get("DATA_ROOT", "/app/data"))
            / "user_connectors"
            / connector_id
            / "connector.yaml",
        ]
        for cy in candidates:
            if cy.is_file():
                try:
                    doc = yaml.safe_load(cy.read_text(encoding="utf-8")) or {}
                    if isinstance(doc, dict):
                        return doc
                except Exception:  # noqa: BLE001
                    continue
        return None

    def _connector_runtime_style(connector_id: str) -> str:
        """Read runtimeMapping.style from a connector's connector.yaml.

        v0.5.0+: defaults to 'container' when the YAML is missing or
        the field is unset — module/class were deleted. Callers
        that hit the default still produce a useful behavior (start
        a container) rather than silently falling back to a deleted
        in-process path.
        """
        doc = _load_connector_spec(connector_id) or {}
        return ((doc.get("runtimeMapping") or {}).get("style") or "container")

    def _connector_image_ref(connector_id: str) -> str | None:
        """Read the optional `image` field from a connector.yaml.

        v0.5.0: bundle connectors leave this empty (guardian-updater
        derives ghcr.io/<owner>/guardian-connector-<id>:<version>).
        User-uploaded connectors MUST declare an `image` ref (enforced
        at upload time by api/marketplace.py). Returns None when no
        explicit image is declared.
        """
        doc = _load_connector_spec(connector_id) or {}
        image = doc.get("image")
        if isinstance(image, str) and image.strip():
            return image.strip()
        return None

    def _slug_instance_name(name: str) -> str:
        """Slug an instance name for safe use in URL paths + docker
        container names.

        guardian-updater validates path segments against
        `^[a-zA-Z0-9_-]+$` (updater/src/main.py:_validate_path_segments)
        and uses the segment verbatim in `guardian-connector-<id>-<name>`
        docker container names. Display names with spaces, slashes, or
        accented characters break BOTH the URL routing AND the docker-
        name constraint.

        v0.5.75 (issue #48): pre-v0.5.75 the agent passed
        `instance_name` raw to the updater. An instance named "Cortex
        XDR" (with a space — accepted at the UI level since the form
        had no validation) produced a URL like
        `/instances/Cortex%20XDR/start` which the updater rejected
        with HTTP 400 "invalid path segment". The instance row got
        created, but no container ever spawned, and the operator saw
        "container_url not configured" at tool-call time with no clean
        link back to the root cause.

        This slug:
        - Replaces any non-allowed char with `_`
        - Collapses consecutive underscores
        - Strips leading/trailing underscores
        - Falls back to `i<first-8-chars-of-instance-id>` if the slug
          would be empty (defense against a name made entirely of
          excluded chars)

        The display name in instances.db is unchanged — operators
        still see "Cortex XDR" in the UI. Only the docker container
        name uses the slug.
        """
        import re

        slugged = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
        slugged = re.sub(r"_+", "_", slugged).strip("_-")
        return slugged or "instance"

    async def _updater_start(
        connector_id: str, instance_name: str, instance_id: str,
    ) -> dict[str, Any] | None:
        """Call guardian-updater to start a connector container. Returns
        the response body on success; None on failure (logged, not
        re-raised — the instance row is created either way; operators
        can retry the start via UI/API).

        v0.5.0: passes an optional `image_ref` body field for
        user-uploaded connectors. Guardian-updater uses the explicit
        image when present (skipping its own derivation), or falls
        back to its derivation for bundle connectors.

        v0.5.75 (issue #48): slug the instance_name before passing it
        to the updater. Display names with spaces/slashes/etc. broke
        the updater's path-segment validation. The slug is purely a
        wire-format concern — instances.db still stores the original
        display name.
        """
        import httpx

        instance_slug = _slug_instance_name(instance_name)
        updater_url = os.environ.get(
            "GUARDIAN_UPDATER_URL", "http://guardian-updater:8090"
        ).rstrip("/")
        url = (
            f"{updater_url}/api/v1/connectors/{connector_id}"
            f"/instances/{instance_slug}/start"
        )
        token = os.environ.get("MCP_TOKEN", "")
        body: dict[str, Any] = {"instance_id": instance_id}
        image_ref = _connector_image_ref(connector_id)
        if image_ref is not None:
            body["image_ref"] = image_ref
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )
            if resp.status_code >= 300:
                logger.warning(
                    "guardian-updater start returned %d for %s/%s "
                    "(body=%.300s)",
                    resp.status_code, connector_id, instance_name, resp.text,
                )
                return None
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "could not call guardian-updater start for %s/%s: %s",
                connector_id, instance_name, exc,
            )
            return None

    async def _updater_stop(
        connector_id: str, instance_name: str,
    ) -> bool:
        """Call guardian-updater to stop a connector container. Returns
        True on success or 'not_running' (idempotent), False on actual
        failure. Synchronous so the row delete waits for the container
        to be gone.

        v0.5.75 (issue #48): slug instance_name for the same reason
        _updater_start does — _validate_path_segments rejects spaces
        and other display-name characters.
        """
        import httpx

        instance_slug = _slug_instance_name(instance_name)
        updater_url = os.environ.get(
            "GUARDIAN_UPDATER_URL", "http://guardian-updater:8090"
        ).rstrip("/")
        url = (
            f"{updater_url}/api/v1/connectors/{connector_id}"
            f"/instances/{instance_slug}/stop"
        )
        token = os.environ.get("MCP_TOKEN", "")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )
            if resp.status_code >= 300:
                logger.warning(
                    "guardian-updater stop returned %d for %s/%s",
                    resp.status_code, connector_id, instance_name,
                )
                return False
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "could not call guardian-updater stop for %s/%s: %s",
                connector_id, instance_name, exc,
            )
            return False

    @mcp.custom_route("/api/v1/instances", methods=["POST"], include_in_schema=False)
    async def create_instance(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        # Phase 6: tag the actor for audit attribution. Anyone hitting
        # an admin endpoint with a valid MCP_TOKEN is a human operator,
        # so the cascading audit events from store.create (instance_created
        # + secret_write) all attribute to "user:operator".
        actor_token = set_current_actor("user:operator")
        try:
            try:
                body = await request.json()
            except Exception as exc:
                return JSONResponse({"error": f"invalid JSON body: {exc}"}, status_code=400)
            if not isinstance(body, dict):
                return JSONResponse({"error": "body must be a JSON object"}, status_code=400)

            connector_id = body.get("connector_id")
            name = body.get("name")
            config_in = body.get("config") or {}
            secrets_in = body.get("secrets") or {}
            # v0.15.6 — optional list of tool names to disable at create time.
            # Pairs with the toggle UX on the existing-instance row (PATCH path).
            # Empty/missing → all tools enabled (legacy behaviour).
            disabled_tools_in = body.get("disabled_tools") or []

            if not isinstance(connector_id, str) or not connector_id:
                return JSONResponse({"error": "connector_id is required (string)"}, status_code=400)
            if not isinstance(name, str) or not name:
                return JSONResponse({"error": "name is required (string)"}, status_code=400)
            if not isinstance(config_in, dict) or not isinstance(secrets_in, dict):
                return JSONResponse(
                    {"error": "config and secrets must be JSON objects"}, status_code=400
                )
            if not isinstance(disabled_tools_in, list) or not all(
                isinstance(t, str) for t in disabled_tools_in
            ):
                return JSONResponse(
                    {"error": "disabled_tools must be a list of strings"},
                    status_code=400,
                )

            # v0.5.0 install gate — instance creation requires the
            # connector to be marketplace-installed first. Pre-v0.5.0
            # any connector in the bundle could have an instance
            # created from it freely; v0.5.0 makes the marketplace
            # the canonical entry point. The upgrade migration in
            # main.py auto-installs every connector with existing
            # instances on first v0.5.0 boot, so customers don't see
            # this 409 for connectors they were already using.
            from usecase.marketplace_store import get_marketplace_store
            _mp = get_marketplace_store()
            if _mp is not None and not _mp.is_installed(connector_id):
                return JSONResponse(
                    {
                        "error": (
                            f"connector {connector_id!r} is not installed. "
                            f"Install it from /connectors first (or POST "
                            f"/api/v1/marketplace/{connector_id}/install)."
                        ),
                        "code": "connector_not_installed",
                        "connector_id": connector_id,
                    },
                    status_code=409,
                )

            try:
                instance = store.create(
                    connector_id,
                    name,
                    config_in,
                    secrets_in,
                    disabled_tools=disabled_tools_in,
                )
            except ValueError as exc:
                return JSONResponse({"error": str(exc)}, status_code=409)

            logger.info(
                "Created instance via API: connector_id=%s name=%s id=%s",
                connector_id, name, instance.id,
            )

            # v0.1.31 (Phase 2): if this connector has style: container,
            # also start the per-instance container via guardian-updater.
            # Returns the updater response (with container_url) on
            # success; None on failure — we still return 201 because
            # the row was created. Operators can retry the start via
            # POST /api/v1/connectors/<id>/instances/<name>/start.
            updater_response: dict[str, Any] | None = None
            style = _connector_runtime_style(connector_id)
            if style == "container":
                updater_response = await _updater_start(
                    connector_id, name, instance.id,
                )

            return JSONResponse(
                {
                    "instance": _instance_to_dict(instance),
                    "requires_mcp_restart": True,
                    # Echo container-mode start outcome when applicable.
                    # UI can surface "container starting…" / "container
                    # start failed — see logs" based on this.
                    "runtime_style": style,
                    "container_start": updater_response,
                },
                status_code=201,
            )
        finally:
            reset_current_actor(actor_token)

    @mcp.custom_route(
        "/api/v1/instances/{instance_id}",
        methods=["GET"],
        include_in_schema=False,
    )
    async def get_instance(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        instance_id = request.path_params["instance_id"]
        instance = store.get(instance_id)
        if instance is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        # v0.6.19 — symmetric with /api/v1/instances (the list endpoint)
        # which has honored `?include_secrets=true` since v0.1.36. The
        # single-instance GET handler was missed when that flag landed
        # — it always called `_instance_to_dict(instance)` with no
        # kwargs, hitting the redact-by-default path. Bearer auth is
        # still the gate; the agent's surface that proxies here
        # (mcp/agent/app/api/agent/instances/[id]) verifies session
        # cookie before forwarding. Same threat model + same caller
        # contract as the list endpoint — just plug the asymmetric
        # API surface here.
        include_secrets = (
            request.query_params.get("include_secrets", "").lower() == "true"
        )
        return JSONResponse(
            {
                "instance": _instance_to_dict(
                    instance,
                    redact_secrets=not include_secrets,
                    secret_store=(
                        store._secret_store if include_secrets else None
                    ),
                )
            }
        )

    @mcp.custom_route(
        "/api/v1/instances/{instance_id}",
        methods=["DELETE"],
        include_in_schema=False,
    )
    async def delete_instance(request: Request) -> JSONResponse:
        if (resp := require_bearer(request)) is not None:
            return resp
        actor_token = set_current_actor("user:operator")
        try:
            instance_id = request.path_params["instance_id"]
            # v0.1.31 (Phase 2): for style: container connectors, stop
            # the container BEFORE deleting the row. If we delete first
            # and the container is still running, the agent's loader
            # would have a dangling proxy callable + the container
            # itself would be orphaned.
            existing = store.get(instance_id)
            if existing is not None:
                style = _connector_runtime_style(existing.connector_id)
                if style == "container":
                    await _updater_stop(existing.connector_id, existing.name)
            deleted = store.delete(instance_id)
            if not deleted:
                return JSONResponse({"error": "not found"}, status_code=404)
            logger.info("Deleted instance via API: id=%s", instance_id)
            return JSONResponse(
                {"deleted": True, "id": instance_id, "requires_mcp_restart": True}
            )
        finally:
            reset_current_actor(actor_token)

    @mcp.custom_route(
        "/api/v1/instances/{instance_id}",
        methods=["PATCH"],
        include_in_schema=False,
    )
    async def patch_instance(request: Request) -> JSONResponse:
        """Partial update for an instance.

        Honored body fields:
          * enabled: bool         — toggles connector_state.disabled
                                    (instance↔connector is 1:1 in
                                    single-tenant Guardian)
          * name: str             — rename
          * config: dict          — replace the config blob
          * secrets: dict         — rotate one or more secret slots
                                    Per-slot "***" sentinel = leave
                                    that slot unchanged (so resubmitting
                                    the redacted form doesn't clobber
                                    stored secrets).
        Unrecognized keys are ignored.
        """
        if (resp := require_bearer(request)) is not None:
            return resp
        actor_token = set_current_actor("user:operator")
        try:
            instance_id = request.path_params["instance_id"]
            instance = store.get(instance_id)
            if instance is None:
                return JSONResponse({"error": "not found"}, status_code=404)
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

            # Collect every field we'll forward to store.update — enabled
            # joins name/config/secrets there so the one-active-per-
            # connector check happens atomically with the row write.
            update_kwargs: dict[str, Any] = {}
            if "enabled" in body:
                if not isinstance(body["enabled"], bool):
                    return JSONResponse(
                        {"error": "enabled must be a boolean"}, status_code=400
                    )
                update_kwargs["enabled"] = body["enabled"]
            if "name" in body:
                if not isinstance(body["name"], str) or not body["name"].strip():
                    return JSONResponse(
                        {"error": "name must be a non-empty string"},
                        status_code=400,
                    )
                update_kwargs["name"] = body["name"].strip()
            if "config" in body:
                if not isinstance(body["config"], dict):
                    return JSONResponse(
                        {"error": "config must be a JSON object"},
                        status_code=400,
                    )
                update_kwargs["config"] = body["config"]
            if "secrets" in body:
                if not isinstance(body["secrets"], dict):
                    return JSONResponse(
                        {"error": "secrets must be a JSON object"},
                        status_code=400,
                    )
                update_kwargs["secrets"] = body["secrets"]

            # v0.14.0 R4.0 — disabled_tools is updated via a dedicated
            # store method (not the generic update) because:
            #   1. It's per-instance metadata that doesn't touch
            #      connector_state, the one-active-per-connector rule,
            #      or secret rotation — keeping the path separate avoids
            #      accidental coupling.
            #   2. The audit event shape is tool-toggle-specific (records
            #      which tools were added/removed), distinct from the
            #      generic instance_update event.
            disabled_tools_change: list[str] | None = None
            if "disabled_tools" in body:
                if not isinstance(body["disabled_tools"], list):
                    return JSONResponse(
                        {"error": "disabled_tools must be a JSON array of tool name strings"},
                        status_code=400,
                    )
                # All entries must be strings (cleaning happens in the store).
                for t in body["disabled_tools"]:
                    if not isinstance(t, str):
                        return JSONResponse(
                            {"error": "disabled_tools entries must be strings"},
                            status_code=400,
                        )
                disabled_tools_change = body["disabled_tools"]

            if update_kwargs:
                try:
                    instance = store.update(instance_id, **update_kwargs)
                except ValueError as exc:
                    msg = str(exc)
                    # Surface "active-instance-conflict" as 409 so the UI
                    # can render a specific message instead of a generic
                    # 400. Substring match on the store's exception text;
                    # the message shape is shared with the create path.
                    is_conflict = "already has an active instance" in msg
                    return JSONResponse(
                        {"error": msg},
                        status_code=409 if is_conflict else 400,
                    )
                if instance is None:
                    return JSONResponse(
                        {"error": "not found"}, status_code=404
                    )

            if disabled_tools_change is not None:
                old_disabled = set(instance.disabled_tools)
                new_disabled = set(disabled_tools_change)
                added = sorted(new_disabled - old_disabled)
                removed = sorted(old_disabled - new_disabled)
                store.update_disabled_tools(instance_id, disabled_tools_change)
                instance = store.get(instance_id)
                if added or removed:
                    a = audit_log()
                    if a is not None:
                        a.record(
                            action="instance_tool_toggle",
                            target=f"instance:{instance_id}",
                            status="success",
                            metadata={
                                "instance_id": instance_id,
                                "connector_id": instance.connector_id,
                                "instance_name": instance.name,
                                "disabled_added": added,
                                "disabled_removed": removed,
                                "disabled_count_after": len(new_disabled),
                            },
                        )

            # v0.2.10 (#24) — propagate config/secret edits to the RUNNING
            # connector container. The container reads instances.db ONCE at
            # boot into a ContextVar and never reloads by design (see
            # guardian-connector-runtime/config/config.py), so writing the
            # DB alone never reaches the live process — the edit silently
            # took effect only after a manual restart. Recreate the container
            # (idempotent: _updater_start removes the old one first) so it
            # re-reads the freshly-written config + secrets at boot. Mirrors
            # the create_instance start path. Gated on: a config/secret field
            # actually changed AND the instance is enabled (a disabled
            # instance has no running container; it picks up the new config
            # when next enabled) AND the connector is container-style.
            # Non-fatal on failure — the row is already updated; the operator
            # can retry via POST /connectors/<id>/instances/<name>/start.
            container_restarted: dict[str, Any] | None = None
            config_or_secret_changed = (
                "config" in update_kwargs or "secrets" in update_kwargs
            )
            if (
                config_or_secret_changed
                and instance is not None
                and instance.enabled
                and _connector_runtime_style(instance.connector_id) == "container"
            ):
                container_restarted = await _updater_start(
                    instance.connector_id, instance.name, instance.id,
                )

            return JSONResponse(
                {
                    "instance": _instance_to_dict(instance),
                    "container_restarted": container_restarted,
                }
            )
        finally:
            reset_current_actor(actor_token)

    @mcp.custom_route(
        "/api/v1/instances/{instance_id}/container_url",
        methods=["PUT"],
        include_in_schema=False,
    )
    async def set_instance_container_url(request: Request) -> JSONResponse:
        """v0.1.30 — set or clear the per-instance container_url for
        connectors with `runtimeMapping.style: container` in their
        connector.yaml. Called by guardian-updater after each
        start/stop/restart of a connector container (P1.9 endpoints).

        Body:
          * container_url: str | null — the URL where the connector
                                        container's MCP listens
                                        (e.g. http://guardian-connector-
                                        web-acme:9000). null clears
                                        the routing entry (used by
                                        the stop endpoint).

        Returns 404 if the instance doesn't exist; 200 with
        {updated: true, instance_id, container_url} on success.

        Auth: same MCP_TOKEN bearer the rest of /api/v1 uses.
        Guardian-updater holds this token via env-var inheritance from
        the same .env file.
        """
        if (resp := require_bearer(request)) is not None:
            return resp
        actor_token = set_current_actor("system:guardian-updater")
        try:
            instance_id = request.path_params["instance_id"]
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
            url = body.get("container_url")
            if url is not None and (
                not isinstance(url, str) or not url.strip()
            ):
                return JSONResponse(
                    {"error": "container_url must be a non-empty string or null"},
                    status_code=400,
                )
            ok = store.set_container_url(instance_id, url)
            if not ok:
                return JSONResponse(
                    {"error": f"instance {instance_id!r} not found"},
                    status_code=404,
                )
            logger.info(
                "instance %s: container_url %s",
                instance_id, "cleared" if url is None else f"= {url}",
            )
            # Trigger an in-place tool-registry reload so the proxy
            # closures pick up the new container_url. Without this,
            # the cached Instance objects (loaded at startup with
            # container_url=None) keep returning None from
            # merged_config(), and tool calls fail with "container_url
            # not set" until the agent restarts. See connector_loader's
            # _build_container_proxy — it reads container_url from
            # get_config() on each tool call but the underlying Instance
            # is the one captured by the closure.
            reloaded: tuple[int, int] | None = None
            try:
                from usecase.connector_loader import reload_tools_now  # noqa: PLC0415
                reloaded = reload_tools_now()
            except Exception as exc:  # noqa: BLE001
                # Best-effort — log and keep going. The DB row IS
                # updated; the operator can recover with a restart.
                logger.warning(
                    "instance %s: container_url stored but tool reload "
                    "failed: %s. Connector tool calls will fail with "
                    "stale container_url until agent restart.",
                    instance_id, exc,
                )
            return JSONResponse({
                "updated": True,
                "instance_id": instance_id,
                "container_url": url,
                "tools_reloaded": reloaded is not None,
                "tool_counts": {
                    "namespaced": reloaded[0] if reloaded else None,
                    "legacy": reloaded[1] if reloaded else None,
                },
            })
        finally:
            reset_current_actor(actor_token)

    @mcp.custom_route(
        "/api/v1/instances/{instance_id}/test",
        methods=["POST"],
        include_in_schema=False,
    )
    async def test_instance(request: Request) -> JSONResponse:
        """Run a real health probe for the instance's connector and
        update connector_state accordingly.

        Body (all optional):
          * config:  dict — override the persisted instance.config for
                            this probe. Lets the operator dry-run new
                            values from the edit dialog without saving.
          * secrets: dict — override the persisted secret slots. Per-
                            slot "***" sentinel = use the persisted
                            value (operator didn't change that slot).
          * dry_run: bool — when true (default if config/secrets given),
                            skip writing to connector_state. Lets the
                            operator try-before-save without polluting
                            connection-history. Default true if any
                            override is present, false otherwise.

        For connectors without a wired probe returns the
        current state unchanged with a `probe_implemented: false`
        flag so the UI can render an explanatory message.

        v0.1.15: probe now reads instance.config + resolved secrets.
        Pre-fix it always read env vars only, so changing instance
        config had zero effect on probe outcome.
        """
        if (resp := require_bearer(request)) is not None:
            return resp
        actor_token = set_current_actor("user:operator")
        try:
            instance_id = request.path_params["instance_id"]
            instance = store.get(instance_id)
            if instance is None:
                return JSONResponse({"error": "not found"}, status_code=404)

            # Optional body — operator may dry-run with form values.
            config_override: dict[str, Any] | None = None
            secrets_override: dict[str, Any] | None = None
            dry_run_explicit: bool | None = None
            if request.headers.get("content-length", "0") not in ("", "0"):
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                if isinstance(body, dict):
                    if isinstance(body.get("config"), dict):
                        config_override = body["config"]
                    if isinstance(body.get("secrets"), dict):
                        secrets_override = body["secrets"]
                    if isinstance(body.get("dry_run"), bool):
                        dry_run_explicit = body["dry_run"]

            has_override = (
                config_override is not None or secrets_override is not None
            )
            # Default: dry_run on when overrides present (form-test
            # before-save case), off when probing the persisted state
            # (post-save or card-level test).
            dry_run = (
                dry_run_explicit
                if dry_run_explicit is not None
                else has_override
            )

            cs_store = get_connector_state_store()
            cid = instance.connector_id

            if cid not in PROBE_IMPLEMENTED:
                # No real probe — return current state with a flag so
                # the UI doesn't claim the test "passed" misleadingly.
                current = cs_store.get(cid) if cs_store else None
                return JSONResponse(
                    {
                        "instance": _instance_to_dict(instance),
                        "probe_implemented": False,
                        "connector_state": (
                            current.to_dict() if current else None
                        ),
                    }
                )

            # Resolve effective config/secrets for the probe.
            effective_config: dict[str, Any] = (
                dict(config_override)
                if config_override is not None
                else dict(instance.config)
            )
            persisted_secrets = instance.resolved_secrets(store.secret_store)
            if secrets_override is None:
                effective_secrets: dict[str, Any] = persisted_secrets
            else:
                # Override mode — replace per-slot, with "***" sentinel
                # meaning "use persisted value" (operator didn't change
                # that slot in the form).
                effective_secrets = {}
                for slot, value in secrets_override.items():
                    if value == "***":
                        effective_secrets[slot] = persisted_secrets.get(slot, "")
                    else:
                        effective_secrets[slot] = value

            ok, err, is_auth = await real_probe(
                cid, config=effective_config, secrets=effective_secrets
            )

            # Only write to connector_state when probing the persisted
            # config — a dry-run shouldn't pollute the connection
            # history with results that don't reflect the running stack.
            if cs_store is not None and not dry_run:
                if ok:
                    cs_store.record_success(cid)
                else:
                    cs_store.record_failure(
                        cid, error=err or "probe failed", is_auth_error=is_auth
                    )

            current = cs_store.get(cid) if cs_store else None
            return JSONResponse(
                {
                    "instance": _instance_to_dict(instance),
                    "probe_implemented": True,
                    "ok": ok,
                    "error": err,
                    "is_auth_error": is_auth,
                    "dry_run": dry_run,
                    "connector_state": current.to_dict() if current else None,
                }
            )
        finally:
            reset_current_actor(actor_token)
