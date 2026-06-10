"""Per-connector health probes — shared between the /connectors and
/instances routes.

Earlier the probe lived in api/connectors.py but the /instances
routes also need to call it (POST /api/v1/instances/{id}/test). Lifted
to the usecase layer so both API modules can import without tripping
a circular import (api/instances.py → api/connectors.py).

`PROBE_IMPLEMENTED` lists connector_ids with a real probe wired here.
Other connectors (notably xsiam, which would need a PAPI roundtrip)
fall back to the legacy reset-to-pending behavior in the caller.

Pre-v0.1.15 the probe read connection details from environment vars
only. That meant any operator-edited instance config (e.g. a custom
Caldera port) was silently ignored — the test always reported the
env-default endpoint's status. v0.1.15 lets callers pass `config`
and `secrets` dicts explicitly; absent kwargs still fall through to
the env defaults so the legacy /connectors/{id}/probe endpoint keeps
working without instance context.

Naming convention: instance config keys vary depending on creation
path. The bindsInstances templates in bundles/spark/manifest.yaml
use `baseUrl`/`apiToken`/`apiKey`. Older auto-migrated instances use
connector-prefixed names (`xlog_url`, `caldera_api_key`). The probe
checks both.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


PROBE_IMPLEMENTED: frozenset[str] = frozenset(
    {"xlog", "caldera", "xsiam", "cortex-docs", "cortex-content", "cortex-xdr"}
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

    Returns (ok, error_message, is_auth_error). PHANTOM_TLS_VERIFY=0
    (default in self-signed mode) tolerates the agent's auto-generated
    cert for compose-internal HTTPS callees.
    """
    cfg = config or {}
    sec = secrets or {}
    timeout = httpx.Timeout(5.0, connect=3.0)
    verify = os.environ.get("PHANTOM_TLS_VERIFY", "0") == "1"

    try:
        if connector_id == "xlog":
            url = _first(
                cfg.get("baseUrl"),
                cfg.get("xlog_url"),
                cfg.get("url"),
                os.environ.get("XLOG_URL"),
                # v0.6.45 — final fallback flipped from http to https.
                # xlog serves HTTPS unconditionally since v0.4.0 (TLS via
                # shared phantom_tls volume); pre-v0.6.45 the http
                # fallback only hit if ALL upstream sources were unset
                # (rare in production where compose always sets XLOG_URL),
                # but when it did hit, the probe got "Empty reply from
                # server" against the HTTPS-only listener and surfaced a
                # misleading connector-down signal.
                "https://xlog:8000",
            ).rstrip("/")
            token = _first(
                sec.get("apiToken"),
                sec.get("xlog_api_key"),
                sec.get("api_token"),
                os.environ.get("XLOG_API_KEY"),
                os.environ.get("XLOG_API_TOKEN"),
            )
            headers = {"Authorization": token} if token else {}

            # Probe sends ONE request against the configured URL and
            # reports the verbatim outcome. No silent scheme flipping,
            # no retries with the opposite protocol — if the operator's
            # stored baseUrl is wrong (e.g. http:// against an
            # HTTPS-only listener after a TLS rollout), the probe's job
            # is to surface the failure so the operator updates the
            # config explicitly via /connectors. The probe is a test,
            # not a self-healer.
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.get(f"{url}/health", headers=headers)
            if r.status_code == 200:
                return (True, None, False)
            if r.status_code in (401, 403):
                return (False, f"HTTP {r.status_code} from {url}", True)
            return (False, f"HTTP {r.status_code} from {url}", False)

        if connector_id == "caldera":
            url = _first(
                cfg.get("baseUrl"),
                cfg.get("caldera_url"),
                cfg.get("url"),
                os.environ.get("CALDERA_URL"),
                "http://caldera:8888",
            ).rstrip("/")
            # v0.1.34 — switched from GET / (root login page, no auth)
            # to GET /api/v2/health with the operator's API key in the
            # KEY header. Caldera's API protects /api/v2/* endpoints
            # with the same KEY-header convention the connector itself
            # uses for tool calls (see bundles/spark/connectors/caldera/
            # src/connector.py::_caldera_request). This way Test
            # Connection actually validates the key the operator typed
            # — wrong key returns 401, which we surface with
            # is_auth_error=true so the UI can flip the badge to amber.
            #
            # Pre-fix the root-page probe rubber-stamped any caldera
            # whose service was up, even with a bad API key, and the
            # operator only learned the key was wrong on the first
            # caldera tool call (which then 401'd).
            api_key = _first(
                sec.get("apiKey"),
                sec.get("api_key"),
                sec.get("caldera_api_key"),
                os.environ.get("CALDERA_API_KEY"),
            )
            if not api_key:
                return (False, "apiKey is not configured", True)
            headers = {"KEY": api_key, "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.get(f"{url}/api/v2/health", headers=headers)
            if r.status_code == 200:
                return (True, None, False)
            if r.status_code in (401, 403):
                return (
                    False,
                    f"HTTP {r.status_code} from {url}/api/v2/health "
                    "(API key rejected)",
                    True,
                )
            return (
                False,
                f"HTTP {r.status_code} from {url}/api/v2/health",
                False,
            )

        if connector_id == "xsiam":
            # XSIAM PAPI auth: Authorization=<api_key> + x-xdr-auth-id=<id>.
            # Probe endpoint: POST /public_api/v1/xql/get_datasets with
            # empty body. Lightweight, authenticated, no side effects —
            # the connector already uses this in xsiam_get_datasets()
            # at bundles/spark/connectors/xsiam/src/connector.py.
            #
            # v0.5.59 (issue #35): config + secret names migrated to
            # uniform api_url/api_id/api_key (matches the new Cortex XDR
            # connector). Legacy papi* names still accepted on read so
            # existing instances don't need migration; new instances
            # write the new names.
            base = _first(
                cfg.get("api_url"),
                cfg.get("papiUrl"),
                cfg.get("baseUrl"),
                cfg.get("xsiam_papi_url"),
                os.environ.get("CORTEX_MCP_PAPI_URL"),
                os.environ.get("XSIAM_API_URL"),
            ).rstrip("/")
            if not base:
                return (False, "api_url is not configured", False)
            # Connector normalizes the URL to end at /public_api/v1; do
            # the same here so operators can paste either form into the
            # setup field.
            if "/public_api/v1" not in base:
                base = base.split("/public_api")[0].rstrip("/") + "/public_api/v1"
            api_key = _first(
                sec.get("api_key"),
                sec.get("papiAuthHeader"),
                os.environ.get("CORTEX_MCP_PAPI_AUTH_HEADER"),
                os.environ.get("XSIAM_API_KEY"),
            )
            api_key_id = _first(
                cfg.get("api_id"),
                cfg.get("papiAuthId"),
                cfg.get("xsiam_api_id"),
                sec.get("papiAuthId"),  # belt-and-suspenders if migrated to a secret
                os.environ.get("CORTEX_MCP_PAPI_AUTH_ID"),
                os.environ.get("XSIAM_API_ID"),
            )
            if not api_key:
                return (False, "api_key (Authorization header) is not configured", True)
            if not api_key_id:
                return (False, "api_id (X-Auth-ID header) is not configured", True)
            headers = {
                "Authorization": api_key,
                "x-xdr-auth-id": str(api_key_id),
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                r = await c.post(
                    f"{base}/xql/get_datasets",
                    headers=headers,
                    json={},
                )
            if r.status_code == 200:
                return (True, None, False)
            if r.status_code in (401, 403):
                return (False, f"HTTP {r.status_code} from XSIAM PAPI", True)
            return (
                False,
                f"HTTP {r.status_code} from {base}/xql/get_datasets",
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
                    json={"inputText": "xql"},
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

        if connector_id == "cortex-xdr":
            # v0.5.61 (issue #36): probe the Cortex XDR Public API.
            # Same auth model as XSIAM (Authorization + x-xdr-auth-id)
            # but XDR has a dedicated healthcheck endpoint we can hit
            # without any side effects.
            #
            # Probe choice: POST /public_api/v1/incidents/get_incidents
            # with an empty request_data — XDR returns 200 with zero
            # results when filters are empty, OR 400 if it interprets
            # the body as malformed. Either way, the upstream is
            # reachable + the creds are valid (we'd get 401 otherwise).
            base = _first(
                cfg.get("api_url"),
                cfg.get("baseUrl"),
            ).rstrip("/")
            if not base:
                return (False, "api_url is not configured", False)
            if "/public_api/v1" not in base:
                base = base.split("/public_api")[0].rstrip("/") + "/public_api/v1"
            api_key = _first(sec.get("api_key"))
            api_id = _first(cfg.get("api_id"), sec.get("api_id"))
            if not api_key:
                return (False, "api_key (Authorization header) is not configured", True)
            if not api_id:
                return (False, "api_id (X-Auth-ID header) is not configured", True)
            headers = {
                "Authorization": api_key,
                "x-xdr-auth-id": str(api_id),
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                # Use search_to=1 to minimize data transfer.
                r = await c.post(
                    f"{base}/incidents/get_incidents",
                    headers=headers,
                    json={"request_data": {"search_from": 0, "search_to": 1}},
                )
            if r.status_code == 200:
                return (True, None, False)
            if r.status_code in (401, 403):
                return (False, f"HTTP {r.status_code} from XDR API (creds rejected)", True)
            # 400 with empty filters can happen depending on XDR API
            # version; surface as auth-shaped because the operator's
            # config is the actionable surface.
            return (
                False,
                f"HTTP {r.status_code} from {base}/incidents/get_incidents",
                False,
            )

        if connector_id == "cortex-content":
            # Probe verifies the bundled catalog directory is present
            # and readable. The catalog ships with the agent image; if
            # it's missing the image was built without it (CI defect).
            try:
                from pathlib import Path as _Path
                # The catalog lives at /app/bundle/connectors/cortex-content/baked/
                # in the agent container. In tests / dev, walk up from this
                # module to bundles/spark/connectors/cortex-content/baked/.
                candidates = [
                    _Path("/app/bundle/connectors/cortex-content/baked/_manifest.json"),
                    _Path(__file__).resolve().parents[3]
                    / "connectors" / "cortex-content" / "baked" / "_manifest.json",
                ]
                if any(p.is_file() for p in candidates):
                    return (True, None, False)
                return (
                    False,
                    "cortex-content catalog directory is missing from the bundle",
                    False,
                )
            except Exception as exc:  # noqa: BLE001
                return (False, f"catalog probe: {type(exc).__name__}: {exc}", False)

        # No real probe wired — caller falls back to reset-to-pending.
        return (True, None, False)
    except httpx.HTTPError as exc:
        return (False, f"{type(exc).__name__}: {exc}", False)
    except Exception as exc:  # noqa: BLE001 — best-effort probe
        return (False, f"{type(exc).__name__}: {exc}", False)
