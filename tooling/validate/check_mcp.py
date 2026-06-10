"""Validate the codebase-search MCP server with a real stdio handshake.

Spawns the server exactly as `.mcp.json` would, completes the MCP handshake,
lists tools, and actually calls all three — proving the server does real
AST-based structured search end to end, not just that the file imports.

Guardian-specific: the call-time assertions reference real symbols that live
in `bundles/spark/mcp/src/api/marketplace.py` so any regression in the
codebase-search index gets caught.

Run via:  python3 tooling/validate/check_mcp.py
Exit:     0 if handshake + tool calls return real AST results, 1 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class McpClient:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            # sys.executable (not bare "python3") so the server runs in the
            # same env as the validator — system python3 lacks `mcp[cli]`.
            [sys.executable, "tooling/mcp/codebase_search.py"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

    def send(self, message: dict) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def recv(self, want_id: int) -> dict:
        assert self.proc.stdout
        for _ in range(100):
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed the stream")
            message = json.loads(line)
            if message.get("id") == want_id:
                return message
        raise RuntimeError(f"no response with id {want_id}")

    def call(self, call_id: int, tool: str, arguments: dict) -> str:
        self.send(
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            }
        )
        return self.recv(call_id)["result"]["content"][0]["text"]

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main() -> int:
    client = McpClient()
    try:
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "guardian-validate", "version": "1.0"},
                },
            }
        )
        init = client.recv(1)
        server_name = init.get("result", {}).get("serverInfo", {}).get("name", "?")
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        client.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = [t["name"] for t in client.recv(2)["result"]["tools"]]
        expected = {"where_is", "find_references", "outline"}
        if not expected.issubset(tools):
            print(f"FAIL: expected structured tools {sorted(expected)} — got {tools}")
            return 1

        # where_is — must structurally locate _scan_catalogue, a real
        # function in bundles/spark/mcp/src/api/marketplace.py.
        where_text = client.call(3, "where_is", {"name": "_scan_catalogue"})
        if "marketplace" not in where_text or "[function]" not in where_text:
            print(
                f"FAIL: where_is did not structurally locate "
                f"_scan_catalogue — {where_text!r}"
            )
            return 1

        # find_references — the same function is called from multiple places
        # in the marketplace REST surface; at least one [call] reference
        # must surface.
        refs_text = client.call(
            4, "find_references", {"name": "_scan_catalogue"}
        )
        if "[call]" not in refs_text:
            print(
                f"FAIL: find_references did not find a call site for "
                f"_scan_catalogue — {refs_text!r}"
            )
            return 1

        # outline — module-level API for marketplace.py must list a few
        # known top-level functions defined in the file itself.
        outline_text = client.call(5, "outline", {"module": "marketplace"})
        if (
            "register_marketplace_routes" not in outline_text
            or "_connector_summary" not in outline_text
        ):
            print(
                f"FAIL: outline did not return the marketplace module API "
                f"— {outline_text!r}"
            )
            return 1

        print(
            f"PASS: MCP server '{server_name}' — handshake ok, tools {tools}; "
            f"where_is + find_references + outline returned real AST results"
        )
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
