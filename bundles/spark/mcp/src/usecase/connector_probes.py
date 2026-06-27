"""Per-connector health probes — shared between the /connectors and
/instances routes.

Earlier the probe lived in api/connectors.py but the /instances
routes also need to call it (POST /api/v1/instances/{id}/test). Lifted
to the usecase layer so both API modules can import without tripping
a circular import (api/instances.py → api/connectors.py).

`PROBE_IMPLEMENTED` lists connector_ids with a real probe wired here.
Other connectors fall back to the legacy reset-to-pending behavior
in the caller.

Pre-v0.1.15 the probe read connection details from environment vars
only. That meant any operator-edited instance config (e.g. a custom
upstream port) was silently ignored — the test always reported the
env-default endpoint's status. v0.1.15 lets callers pass `config`
and `secrets` dicts explicitly; absent kwargs still fall through to
the env defaults so the legacy /connectors/{id}/probe endpoint keeps
working without instance context.

Naming convention: instance config keys come from the bindsInstances
templates in bundles/spark/manifest.yaml, which use the uniform
`api_url`/`api_id`/`api_key` names. The probe also accepts the legacy
`baseUrl` key as a fallback.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import string
import time
from typing import Any

import httpx


def _xsiam_papi_headers(api_key: str, api_id: str, auth_type: str) -> dict[str, str]:
    """Build Cortex public-API auth headers for the XSIAM probe, matching the
    connector's Fetcher (_papi_client.Fetcher._build_headers). `standard` sends
    the key verbatim; `advanced` signs api_key + nonce + timestamp with SHA-256.
    An Advanced key 401s under standard auth and vice-versa."""
    common = {"Content-Type": "application/json", "Accept": "application/json"}
    if (auth_type or "standard").strip().lower() != "advanced":
        return {"Authorization": api_key, "x-xdr-auth-id": str(api_id), **common}
    nonce = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))
    timestamp = str(int(time.time() * 1000))
    api_key_hash = hashlib.sha256(f"{api_key}{nonce}{timestamp}".encode("utf-8")).hexdigest()
    return {
        "x-xdr-timestamp": timestamp,
        "x-xdr-nonce": nonce,
        "x-xdr-auth-id": str(api_id),
        "Authorization": api_key_hash,
        **common,
    }


PROBE_IMPLEMENTED: frozenset[str] = frozenset(
    {"xsoar", "xsiam", "cortex-docs", "web"}
)


def _first(*candidates: Any) -> str:
    """Return the first non-empty stringable candidate, or ''."""
    for c in candidates:
        if c is None:
            continue
        s = str(c).strip()
        if s:
            return s
    return ""


async def real_probe(
    connector_id: str,
    *,
    config: dict[str, Any] | None = None,
    secrets: dict[str, Any] | None = None,
) -> tuple[bool, str | None, bool]:
    """Run a real health probe against the connector's upstream.

    Resolution order for connection details:
      1. explicit `config`/`secrets` kwargs (operator's form values)
      2. environment variables (legacy default; used when no
         instance context is available, e.g. the /connectors probe)

    Returns (ok, error_message, is_auth_error). GUARDIAN_TLS_VERIFY=0
    (default in self-signed mode) tolerates the agent's auto-generated
    cert for compose-internal HTTPS callees.
    """
    cfg = config or {}
    sec = secrets or {}
    timeout = httpx.Timeout(5.0, connect=3.0)
    verify = os.environ.get("GUARDIAN_TLS_VERIFY", "0") == "1"

    try:
        if connector_id == "xsoar":
            # Cortex XSOAR supports two deployment shapes; the connector
            # detects them by whether `api_id` is set:
            #   v6 (on-prem): single API key in the Authorization header,
            #     base https://<server>, no path prefix.
            #   v8 / Cortex cloud: API key + key id (Authorization +
            #     x-xdr-auth-id headers), base https://api-<fqdn>, path
            #     prefix /xsoar/public/v1.
            #
            # Probe endpoint: POST /incidents/search with a minimal
            # filter (page 0, size 1). Lightweight, authenticated, no
            # side effects — the same endpoint the connector's
            # xsoar_list_incidents tool uses. A 401/403 means the creds
            # are rejected; 200 (or a 4xx that isn't auth-shaped) means
            # the upstream is reachable and the creds are valid.
            base = _first(
                cfg.get("api_url"),
                cfg.get("baseUrl"),
            ).rstrip("/")
            if not base:
                return (False, "api_url is not configured", False)
            api_key = _first(sec.get("api_key"))
            if not api_key:
                return (False, "api_key (Authorization header) is not configured", True)
            api_id = _first(cfg.get("api_id"), sec.get("api_id"))

            headers = {
                "Authorization": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if api_id:
                # v8 / Cortex cloud: add the key id + the public-API path
                # prefix (only when the base doesn't already carry it).
                headers["x-xdr-auth-id"] = str(api_id)
                if "/xsoar/public/v1" not in base:
                    base = base + "/xsoar/public/v1"

            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.post(
                    f"{base}/incidents/search",
                    headers=headers,
                    json={"filter": {"page": 0, "size": 1}},
                )
            if r.status_code == 200:
                # #XSOAR-F5 — upstream + creds are good, but six tools
                # (run_command, enrich_indicator, complete_task, get_list,
                # set_list, append_to_list) need `playground_id`. If it's
                # blank, those tools fail only at call-time with a confusing
                # {ok:false}. The probe can't fail-closed the whole instance
                # (the non-playground tools work fine), so surface a warning
                # in the message slot — the route returns `error` in the body
                # even when ok=True — so the operator learns at setup, not
                # mid-investigation.
                playground = _first(cfg.get("playground_id"))
                if not playground:
                    return (
                        True,
                        "connected — but playground_id is not set, so the "
                        "command tools (run_command, enrich_indicator, "
                        "complete_task, get_list, set_list, append_to_list) "
                        "will fail at call-time. Set playground_id in the "
                        "instance config if you use them.",
                        False,
                    )
                return (True, None, False)
            if r.status_code in (401, 403):
                return (False, f"HTTP {r.status_code} from XSOAR API (creds rejected)", True)
            return (
                False,
                f"HTTP {r.status_code} from {base}/incidents/search",
                False,
            )

        if connector_id == "xsiam":
            # #XSIAM-F12 — wire a real probe. Previously xsiam fell through
            # to the default branch returning (True, None, False), so a
            # misconfigured api_key/api_id/url reported healthy and the first
            # error only surfaced on a real (billable) PAPI call. Cortex XSIAM
            # uses the same public-API auth pair as XSOAR v8: api_key in the
            # Authorization header + api_id in x-xdr-auth-id. The connector
            # appends /public_api/v1 to api_url.
            #
            # Probe endpoint: POST /public_api/v1/incidents/get_incidents/
            # with a minimal request (search_to: 1). Authenticated, no side
            # effects — proves creds + reachability without an XQL run.
            base = _first(
                cfg.get("api_url"),
                cfg.get("baseUrl"),
            ).rstrip("/")
            if not base:
                return (False, "api_url is not configured", False)
            api_key = _first(sec.get("api_key"))
            if not api_key:
                return (False, "api_key (Authorization header) is not configured", True)
            api_id = _first(cfg.get("api_id"), sec.get("api_id"))
            if not api_id:
                return (False, "api_id (x-xdr-auth-id header) is not configured", True)

            if "/public_api/v1" not in base:
                base = base + "/public_api/v1"
            # Honor the instance's auth_type — Advanced keys must be signed, or
            # the probe 401s a perfectly valid Advanced key (the connector's
            # Fetcher signs correctly; this probe must match it).
            auth_type = _first(cfg.get("auth_type"), sec.get("auth_type")) or "standard"
            headers = _xsiam_papi_headers(api_key, str(api_id), auth_type)
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.post(
                    f"{base}/incidents/get_incidents/",
                    headers=headers,
                    json={"request_data": {"search_from": 0, "search_to": 1}},
                )
            if r.status_code == 200:
                return (True, None, False)
            if r.status_code in (401, 403):
                return (False, f"HTTP {r.status_code} from XSIAM API (creds rejected)", True)
            return (
                False,
                f"HTTP {r.status_code} from {base}/incidents/get_incidents/",
                False,
            )

        if connector_id == "cortex-docs":
            # v0.5.58 (issue #34): wire a real probe for the Cortex
            # public docs search/lookup connector. Upstream is the
            # unauthenticated Fluid Topics docs API at
            # docs-cortex.paloaltonetworks.com.
            #
            # Probe choice: POST /api/khub/suggest with a tiny input.
            # Lightweight, public, returns 200 + small JSON. Doesn't
            # require auth and doesn't trigger expensive search/fetch.
            # The connector itself uses /api/khub/clustered-search
            # for search and /api/khub/maps/.../topics/... for fetch;
            # suggest is the cheapest endpoint that proves the
            # upstream is alive and responding.
            base = _first(
                cfg.get("baseUrl"),
                "https://docs-cortex.paloaltonetworks.com",
            ).rstrip("/")
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.post(
                    f"{base}/api/khub/suggest",
                    headers={"Content-Type": "application/json"},
                    json={"inputText": "incident"},
                )
            # The suggest API may return 200 (matches) or 200 with
            # empty list (no matches) — either is healthy. 4xx (e.g.
            # 400 for malformed body) still proves the service is up
            # — surface as healthy with a note. 5xx and connection
            # errors are real failures.
            if r.status_code == 200:
                return (True, None, False)
            if 400 <= r.status_code < 500:
                # API reachable but rejected our request shape. The
                # connector's real tool calls use a different request
                # shape that's known to work; report healthy.
                return (True, None, False)
            return (
                False,
                f"HTTP {r.status_code} from {base}/api/khub/suggest",
                False,
            )

        if connector_id == "web":
            # #CDW-F11 — real probe for the headless-browser connector.
            # Pre-fix the instance test returned probe_implemented:false
            # WITHOUT contacting anything, so the operator couldn't tell a
            # down browser sidecar from a healthy one. Hit the Chromium CDP
            # HTTP endpoint /json/version — a 200 + JSON proves the sidecar
            # is up and CDP is reachable (same endpoint Playwright connects
            # over). No auth; the connector is gated by allowed_domains, not
            # credentials, so this is purely a reachability check.
            cdp = _first(
                cfg.get("cdp_url"),
                "http://guardian-browser:9222",
            ).rstrip("/")
            # CDP config may be a ws:// URL; the version endpoint is HTTP.
            http_cdp = cdp.replace("ws://", "http://").replace("wss://", "https://")
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.get(f"{http_cdp}/json/version")
            if r.status_code == 200:
                return (True, None, False)
            return (
                False,
                f"HTTP {r.status_code} from {http_cdp}/json/version",
                False,
            )

        # No real probe wired — caller falls back to reset-to-pending.
        return (True, None, False)
    except httpx.HTTPError as exc:
        return (False, f"{type(exc).__name__}: {exc}", False)
    except Exception as exc:  # noqa: BLE001 — best-effort probe
        return (False, f"{type(exc).__name__}: {exc}", False)
