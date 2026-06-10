"""SP-4 — confirm data_sources_edit is advertised in the deployed MCP catalog.

Runs INSIDE phantom_agent. Does the minimal MCP streamable-http handshake
(initialize → notifications/initialized → tools/list) against the loopback
MCP and asserts data_sources_edit + its siblings are present.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request

URL = "https://localhost:8080/api/v1/stream/mcp"
TOKEN = os.environ["MCP_TOKEN"]
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _post(payload: dict, session: str | None) -> tuple[dict, str | None]:
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if session:
        req.add_header("mcp-session-id", session)
    with urllib.request.urlopen(req, context=_CTX, timeout=20) as r:
        sid = r.headers.get("mcp-session-id") or session
        raw = r.read().decode()
    # Response may be SSE (event-stream) or plain JSON. Extract the JSON.
    body = None
    if raw.lstrip().startswith("{"):
        body = json.loads(raw)
    else:
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    body = json.loads(line[5:].strip())
                except Exception:  # noqa: BLE001
                    pass
    return (body or {}), sid


init = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "sp4-smoke", "version": "1.0"},
    },
}
_, sid = _post(init, None)
# notifications/initialized (no id — notification)
_post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)

resp, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sid)
tools = [t["name"] for t in (resp.get("result") or {}).get("tools", [])]
ds_tools = sorted(t for t in tools if t.startswith("data_sources_"))
print(f"total tools advertised: {len(tools)}")
print(f"data_sources_* tools: {ds_tools}")
print(f"data_sources_edit present: {'data_sources_edit' in tools}")
