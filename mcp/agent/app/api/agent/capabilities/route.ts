/**
 * Capabilities probe (#CHAT-F30).
 *
 *   GET /api/agent/capabilities
 *
 * Surfaces the MCP's lightweight readiness body (`/ping/`) so the UI can
 * gate optional affordances on what the backend actually supports —
 * rather than offering a dead click that only fails after the operator
 * triggers it. Today it carries `pyyaml_available`, which the chat
 * export menu reads to disable the YAML transcript export when PyYAML
 * isn't installed (the MCP otherwise returns 501 only after a download
 * is attempted).
 *
 * Unauthenticated MCP route (`/ping/`), so no bearer needed; we still
 * read MCP_URL the same way every proxy does.
 */

import { NextResponse } from "next/server";

import { getEffectiveRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

function mcpPingUrl(mcpUrl: string): string {
  try {
    const url = new URL(mcpUrl);
    url.pathname = "/ping/";
    url.search = "";
    return url.toString();
  } catch {
    return "http://guardian-mcp:8080/ping/";
  }
}

export async function GET() {
  const config = await getEffectiveRuntimeConfig();
  const mcpUrl =
    (config.MCP_URL || "").trim() ||
    process.env.MCP_URL?.trim() ||
    "http://guardian-mcp:8080/api/v1/stream/mcp";
  try {
    const r = await fetch(mcpPingUrl(mcpUrl), {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
    return NextResponse.json({
      status: typeof body.status === "string" ? body.status : "unknown",
      embedder_mode:
        typeof body.embedder_mode === "string" ? body.embedder_mode : "unknown",
      // Default true on an older MCP that doesn't report the flag — the
      // worst case is the existing behaviour (YAML offered, may 501).
      pyyaml_available: body.pyyaml_available !== false,
    });
  } catch {
    // MCP unreachable — don't block the UI; assume the prior behaviour.
    return NextResponse.json(
      { status: "unreachable", embedder_mode: "unknown", pyyaml_available: true },
      { status: 200 },
    );
  }
}
