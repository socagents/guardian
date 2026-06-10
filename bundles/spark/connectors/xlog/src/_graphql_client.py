"""GraphQL client for the xlog HTTP + GraphQL API."""

import logging
import os
import re
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("Phantom MCP")


# Strawberry wraps any input-coercion failure (Pydantic, enum, custom
# scalar) as: "Variable '$X' got invalid value <input-echo> at '<path>';
# <detail>". The <input-echo> can be 400+ chars when the variable is a
# whole `steps` array; the <detail> at the end carries the actionable
# info (field name + "Did you mean..." suggestions). Pre-v0.3.5 the MCP
# wrapper joined raw `error.message` strings as-is, so the agent saw
# the giant echo and the suggestion buried deep inside; it had to
# binary-search by retrying with different fields dropped.
#
# The pattern below matches the start of the actionable suffix. We keep
# the path (so the agent knows WHICH step/log/field is wrong) and the
# detail (so the agent gets the "Did you mean" list). We drop the
# "Variable '$X' got invalid value <echo>" prefix because it's noise.
_STRAWBERRY_VARIABLE_ECHO_RE = re.compile(r" at '([^']+)';\s*", re.DOTALL)


def simplify_strawberry_error(message: str) -> str:
    """Strip the giant input-echo from Strawberry's wrapped variable
    validation error, leaving just the path + actionable detail.

    Before:
        Variable '$steps' got invalid value {<huge-payload>} at
        'steps[0].logs[0].observablesDict'; Field 'sessionState' is not
        defined by type 'WorkerObservablesInput'. Did you mean
        'sessionStart', 'sessionType', 'serviceState', 'leaseState', or
        'sessionEnd'?

    After:
        at 'steps[0].logs[0].observablesDict': Field 'sessionState' is
        not defined by type 'WorkerObservablesInput'. Did you mean
        'sessionStart', 'sessionType', 'serviceState', 'leaseState', or
        'sessionEnd'?

    For messages that don't match the wrapper pattern (e.g. a flat
    "Field X is required" error), returns the message unchanged.
    """
    m = _STRAWBERRY_VARIABLE_ECHO_RE.search(message)
    if not m:
        return message
    path = m.group(1)
    detail = message[m.end():]
    return f"at '{path}': {detail}"


def _resolve_verify() -> bool:
    """
    Whether httpx clients should verify the xlog server's TLS cert.

    PHANTOM_TLS_VERIFY=0  (default, self-signed mode):
        Skip verification — accept self-signed certs the operator
        generated via installer/generate-self-signed-certs.sh.
    PHANTOM_TLS_VERIFY=1  (CA-signed mode):
        Verify normally — the operator installed certs from a trusted
        CA, so standard chain validation should succeed.

    On plain-HTTP xlog deployments this is a no-op (no TLS to verify).
    """
    return os.environ.get("PHANTOM_TLS_VERIFY", "0") == "1"


_HTTPX_VERIFY = _resolve_verify()


def _resolve_api_token() -> Optional[str]:
    """Read the per-instance xlog_api_token from the contextvar-backed
    config proxy. Returns None when no token is configured (xlog will
    accept the request in permissive mode if its own XLOG_API_KEY is
    also unset)."""
    try:
        from config.config import get_config
        cfg = get_config()
        token = getattr(cfg, "xlog_api_token", None)
        if token and isinstance(token, str) and token.strip():
            return token.strip()
        return None
    except Exception:  # pragma: no cover
        # Don't let a config-read glitch prevent the call entirely;
        # xlog will return 401 if it actually needs the token.
        return None


class PhantomGraphQLClient:
    """Client for interacting with the xlog HTTP + GraphQL API.

    Authentication: every request carries `Authorization: <token>`
    when an API token is resolvable. xlog's middleware accepts both
    the bare-value form and `Bearer <token>`; we use the bare form
    historically.

    The token is resolved at construction time via _resolve_api_token,
    which reads the contextvar-backed config proxy. The agent's tool-
    call wrapper sets the per-instance config (decrypted from the
    SecretStore) onto the contextvar BEFORE invoking the connector
    function, so client construction inside that function sees the
    correct per-instance token.

    When no token is resolvable, the client omits the Authorization
    header — xlog falls back to permissive mode when its own
    XLOG_API_KEY is unset, so the call still succeeds for pre-auth
    legacy deploys.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        api_token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_token = api_token if api_token is not None else _resolve_api_token()

    def _auth_headers(self, base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Merge `Authorization: <token>` into the headers when set."""
        headers: Dict[str, str] = dict(base or {})
        if self._api_token:
            headers["Authorization"] = self._api_token
        return headers

    async def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        async with httpx.AsyncClient(timeout=self.timeout, verify=_HTTPX_VERIFY) as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self._auth_headers({"Content-Type": "application/json"}),
            )
            response.raise_for_status()
            result = response.json()
            if "errors" in result:
                error_messages = [
                    simplify_strawberry_error(error.get("message", str(error)))
                    for error in result["errors"]
                ]
                raise ValueError(f"GraphQL errors: {'; '.join(error_messages)}")
            return result.get("data", {})

    async def get_json(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fetch a JSON response from an xlog REST endpoint."""
        async with httpx.AsyncClient(timeout=self.timeout, verify=_HTTPX_VERIFY) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Post JSON to an xlog REST endpoint."""
        async with httpx.AsyncClient(timeout=self.timeout, verify=_HTTPX_VERIFY) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._auth_headers({"Content-Type": "application/json"}),
            )
            response.raise_for_status()
            return response.json()

    async def patch_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Patch JSON to an xlog REST endpoint."""
        async with httpx.AsyncClient(timeout=self.timeout, verify=_HTTPX_VERIFY) as client:
            response = await client.patch(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._auth_headers({"Content-Type": "application/json"}),
            )
            response.raise_for_status()
            return response.json()
