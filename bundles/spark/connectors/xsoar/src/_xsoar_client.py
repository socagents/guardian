"""Cortex XSOAR REST API HTTP client — minimal, async, stateless.

Standard Guardian connector-client pattern: POST/GET a JSON body and
surface 401/403/429/5xx as distinct exception types so the connector
wrapper maps them to operator-actionable error envelopes. Adapts the
base-URL + header construction for XSOAR's dual-generation auth model.

Dual-generation detection is config-driven via `api_id`:

  - XSOAR 6 (on-prem): `api_id` is None/empty.
      base    = api_url                      (e.g. https://xsoar.example.com)
      headers = Authorization: <api_key>
  - XSOAR 8 / Cortex cloud: `api_id` is set.
      base    = api_url + "/xsoar/public/v1" (e.g. https://api-tenant.xdr.us...)
      headers = Authorization: <api_key>  +  x-xdr-auth-id: <api_id>

Logical paths + request bodies are identical across both generations —
only the base URL and headers change. That keeps every tool function in
connector.py generation-agnostic: it POSTs to "/incidents/search" and
this client prepends the right prefix for the configured generation.

No retry logic in this layer — the connector wrapper handles transient
retries at the tool level if needed. No global state — each tool
invocation builds its own client from the resolved instance config.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


# v8 / Cortex-cloud logical-path prefix. Appended to the base URL ONLY
# when the instance is detected as v8 (api_id present).
_V8_PATH_PREFIX = "/xsoar/public/v1"
# v8 INTERNAL-API prefix. The Cortex API gateway serves the full XSOAR API
# under /xsoar/* (what the Core REST API integration's !core-api-* commands
# reach), in addition to the limited public surface under /xsoar/public/v1.
# `internal=True` on post()/get() targets this path so the connector can call
# endpoints not exposed on the public gateway (e.g. /investigation/{id}/workplan,
# /playbook/save) DIRECTLY — no Core REST API integration / playground needed.
# Same api_key + x-xdr-auth-id auth. On v6 there is no prefix either way.
_V8_INTERNAL_PREFIX = "/xsoar"


class XSOARError(Exception):
    """Base for Cortex XSOAR API errors."""


class XSOARAuthError(XSOARError):
    """401/403 — bad api_key, missing/wrong api_id, or insufficient scope."""


class XSOARRateLimitError(XSOARError):
    """429 — per-tenant rate limit. Caller can retry after a delay."""


class XSOARServerError(XSOARError):
    """5xx — upstream XSOAR side. Caller can retry."""


class XSOARRequestError(XSOARError):
    """4xx other than 401/403/429 — caller's request shape is bad.

    A 404 here commonly means the v8 path prefix is missing (api_id not
    set on a Cortex-cloud tenant); a 409 means a stale incident version
    was sent to an upsert (optimistic concurrency — re-read first).
    """


class XSOARResponseError(XSOARError):
    """2xx OK but body isn't valid JSON or has an unexpected shape."""


class XSOARFetcher:
    """Stateless Cortex XSOAR REST API client.

    Usage:
        f = XSOARFetcher(api_url, api_key, api_id=None, verify_ssl=True)
        result = await f.post("/incidents/search", {"filter": {...}})
        data   = await f.get("/health")

    Generation is fixed at construction time from `api_id`:
        api_id is None/empty  → v6  (no prefix, no x-xdr-auth-id header)
        api_id is set         → v8  (/xsoar/public/v1 prefix + x-xdr-auth-id)
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        api_id: Optional[str] = None,
        verify_ssl: bool = True,
        version: Optional[str] = None,
        account: Optional[str] = None,
    ):
        # Normalize base url: strip trailing /. Do NOT bake the v8 prefix
        # into self.base here — we prepend it per-request in _full_url so
        # the prefix is applied uniformly + a caller that accidentally
        # passes a prefixed path is de-duplicated.
        self.base = api_url.rstrip("/")
        self.api_key = api_key
        # XSOAR 6 MSSP child-account scoping: requests to a child account go
        # to /acc_<account>/<path>. Only meaningful on v6 (XSOAR 8 / Cortex
        # multi-tenant uses a per-tenant connector instance, not a path
        # prefix); applied in _full_url for v6 only. Empty → main account.
        self.account = str(account).strip() if account not in (None, "") else None
        # Empty string is treated the same as None (v6). The flat config
        # may surface a blank api_id for v6 instances.
        self.api_id = str(api_id) if api_id not in (None, "") else None
        self.verify_ssl = bool(verify_ssl)
        # Generation resolution precedence: an EXPLICIT version config field
        # wins; otherwise fall back to the legacy api_id inference (api_id
        # present → v8). This keeps existing instances (no version set)
        # working while letting an operator pin the generation directly.
        ver = str(version).strip().lower() if version not in (None, "") else None
        if ver == "v8":
            self._is_v8 = True
        elif ver == "v6":
            self._is_v8 = False
        else:
            self._is_v8 = self.api_id is not None

    @property
    def is_v8(self) -> bool:
        """True when this instance is XSOAR 8 / Cortex cloud.

        Resolved at construction: explicit `version` (v6/v8) wins, else
        inferred from whether `api_id` is set (legacy behavior).
        """
        return self._is_v8

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # x-xdr-auth-id is attached ONLY for v8 AND only when an api_id is
        # present. Keying on the resolved generation (not api_id alone) lets
        # an explicit version="v6" correctly suppress the v8 auth header even
        # if an api_id happens to be configured. v6 on-prem rejects this header.
        if self.is_v8 and self.api_id:
            headers["x-xdr-auth-id"] = self.api_id
        return headers

    def _full_url(self, path: str, internal: bool = False) -> str:
        """Compose the absolute URL for a logical path.

        base + ("/xsoar/public/v1" (public) | "/xsoar" (internal) if v8 else "")
              + <logical-path>

        `internal=True` targets the full XSOAR API under /xsoar/* (v8) — used
        for endpoints not on the public gateway. On v6 internal and public are
        identical (no prefix). Defensive de-dup: if a caller passes a path that
        already carries a v8 prefix, strip it first so we never double it.
        """
        if not path.startswith("/"):
            path = "/" + path
        # Don't double a v8 prefix if the caller already included one. Strip the
        # longer (public) prefix first so "/xsoar/public/v1/x" doesn't get
        # mis-stripped to "/public/v1/x" by the shorter internal prefix.
        for pfx in (_V8_PATH_PREFIX, _V8_INTERNAL_PREFIX):
            if path.startswith(pfx + "/") or path == pfx:
                path = path[len(pfx):] or "/"
                if not path.startswith("/"):
                    path = "/" + path
                break
        if self.is_v8:
            prefix = _V8_INTERNAL_PREFIX if internal else _V8_PATH_PREFIX
            acc = ""  # v8 MSSP is a per-tenant instance, not a /acc_ path prefix
        else:
            prefix = ""
            # v6 MSSP: scope the request to a child account when configured.
            acc = f"/acc_{self.account}" if self.account else ""
        return f"{self.base}{acc}{prefix}{path}"

    def _raise_for_status(self, r: httpx.Response, path: str) -> None:
        """Map a non-2xx XSOAR response onto a typed exception."""
        if r.status_code in (401, 403):
            raise XSOARAuthError(
                f"HTTP {r.status_code} from {path} (auth failed — check "
                f"api_key{', api_id (x-xdr-auth-id)' if self.is_v8 else ''})"
            )
        if r.status_code == 429:
            raise XSOARRateLimitError(
                f"HTTP 429 from {path} (per-tenant rate limit)"
            )
        if r.status_code >= 500:
            raise XSOARServerError(
                f"HTTP {r.status_code} from {path}: {r.text[:200]}"
            )
        # Other 4xx (incl. 404 missing-v8-prefix, 409 stale-version).
        raise XSOARRequestError(
            f"HTTP {r.status_code} from {path}: {r.text[:200]}"
        )

    def _parse(self, r: httpx.Response, path: str) -> dict:
        """Parse a 2xx body as JSON, tolerating an empty body."""
        if not r.content:
            return {}
        try:
            data = r.json()
        except json.JSONDecodeError as exc:
            raise XSOARResponseError(
                f"non-JSON {r.status_code} from {path}: {r.text[:200]}"
            ) from exc
        # XSOAR endpoints return either an object or (rarely) a bare
        # array; normalize the array case so callers always get a dict.
        if isinstance(data, list):
            return {"data": data}
        if not isinstance(data, dict):
            return {"value": data}
        return data

    async def post(
        self,
        path: str,
        body: Optional[Any] = None,
        *,
        internal: bool = False,
        timeout_seconds: float = 30.0,
    ) -> dict:
        """POST to the logical `path` with the auth headers. Returns parsed JSON.

        `internal=True` targets the v8 full internal API (/xsoar/*) instead of
        the public gateway (/xsoar/public/v1) — for endpoints the public surface
        doesn't expose. `body` may be a dict OR a list (some XSOAR endpoints,
        e.g. /playbook/save, take a JSON array). Raises one of the XSOARError
        subclasses on a non-2xx response.
        """
        full_url = self._full_url(path, internal=internal)
        timeout = httpx.Timeout(timeout_seconds, connect=10.0)

        try:
            async with httpx.AsyncClient(
                timeout=timeout, verify=self.verify_ssl
            ) as client:
                r = await client.post(
                    full_url, headers=self._headers(), json=body or {}
                )
        except httpx.HTTPError as exc:
            raise XSOARError(
                f"network error talking to XSOAR: {type(exc).__name__}: {exc}"
            ) from exc

        if 200 <= r.status_code < 300:
            return self._parse(r, path)
        self._raise_for_status(r, path)
        return {}  # unreachable — _raise_for_status always raises

    async def post_multipart(
        self,
        path: str,
        files: dict,
        *,
        data: Optional[dict] = None,
        internal: bool = False,
        timeout_seconds: float = 60.0,
    ) -> dict:
        """POST a multipart/form-data body (file upload) to the logical path.

        XSOAR's playbook-import endpoint takes the playbook YAML as an
        uploaded file, not a JSON body — so we drop the JSON Content-Type
        and let httpx set the multipart boundary. Redirects are NOT followed
        (`follow_redirects=False`): on Cortex 8 some v6 REST endpoints
        303-redirect, and surfacing that as an error (rather than silently
        following to an HTML login) makes the generation mismatch visible.
        """
        full_url = self._full_url(path, internal=internal)
        timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        headers = self._headers()
        headers.pop("Content-Type", None)  # httpx sets multipart boundary

        try:
            async with httpx.AsyncClient(
                timeout=timeout, verify=self.verify_ssl, follow_redirects=False
            ) as client:
                r = await client.post(
                    full_url, headers=headers, files=files, data=data or {}
                )
        except httpx.HTTPError as exc:
            raise XSOARError(
                f"network error talking to XSOAR: {type(exc).__name__}: {exc}"
            ) from exc

        if 200 <= r.status_code < 300:
            return self._parse(r, path)
        # Make a 3xx (redirect) visibly diagnosable for the spike.
        if 300 <= r.status_code < 400:
            raise XSOARRequestError(
                f"HTTP {r.status_code} from {path} (redirect to "
                f"{r.headers.get('location', '?')}) — endpoint not served on "
                f"this XSOAR generation"
            )
        self._raise_for_status(r, path)
        return {}  # unreachable — _raise_for_status always raises

    async def get(
        self,
        path: str,
        *,
        params: Optional[dict] = None,
        internal: bool = False,
        timeout_seconds: float = 30.0,
    ) -> dict:
        """GET the logical `path` with the auth headers. Returns parsed JSON.

        `internal=True` targets the v8 full internal API (/xsoar/*) instead of
        the public gateway — for endpoints the public surface doesn't expose.
        """
        full_url = self._full_url(path, internal=internal)
        timeout = httpx.Timeout(timeout_seconds, connect=10.0)

        try:
            async with httpx.AsyncClient(
                timeout=timeout, verify=self.verify_ssl
            ) as client:
                r = await client.get(
                    full_url, headers=self._headers(), params=params
                )
        except httpx.HTTPError as exc:
            raise XSOARError(
                f"network error talking to XSOAR: {type(exc).__name__}: {exc}"
            ) from exc

        if 200 <= r.status_code < 300:
            return self._parse(r, path)
        self._raise_for_status(r, path)
        return {}  # unreachable — _raise_for_status always raises

    async def delete(
        self,
        path: str,
        *,
        internal: bool = False,
        timeout_seconds: float = 30.0,
    ) -> dict:
        """DELETE the logical `path` with the auth headers. Returns parsed JSON.

        `internal=True` targets the v8 full internal API (/xsoar/*). Used for
        REST-path deletes like `DELETE /jobs/{id}`.
        """
        full_url = self._full_url(path, internal=internal)
        timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, verify=self.verify_ssl
            ) as client:
                r = await client.delete(full_url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise XSOARError(
                f"network error talking to XSOAR: {type(exc).__name__}: {exc}"
            ) from exc

        if 200 <= r.status_code < 300:
            return self._parse(r, path)
        self._raise_for_status(r, path)
        return {}  # unreachable — _raise_for_status always raises
