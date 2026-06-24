/**
 * Personality history proxy (#PLAT-F3).
 *
 * GET /api/agent/personality/history?limit=N
 *   → GET /api/v1/personality/history?limit=N
 *
 * Returns recent personality versions newest-first ({ versions, count })
 * so the settings UI can show edit history / diffs. Before this route the
 * MCP endpoint was reachable only with a direct MCP_TOKEN bearer call and
 * undocumented in the agent's API catalog.
 *
 * Mirrors the inline _resolveMcp pattern in ../reset/route.ts.
 */

import { NextResponse } from "next/server";

import { deriveMcpBaseUrl, getEffectiveRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const config = await getEffectiveRuntimeConfig();
  const mcpToken =
    (config.MCP_TOKEN || "").trim() || process.env.MCP_TOKEN?.trim() || "";
  if (!mcpToken)
    return NextResponse.json({ error: "MCP_TOKEN not configured" }, { status: 503 });
  const mcpUrl =
    (config.MCP_URL || "").trim() ||
    process.env.MCP_URL?.trim() ||
    "http://guardian-mcp:8080/api/v1/stream/mcp";
  const base = deriveMcpBaseUrl(mcpUrl);
  if (!base) return NextResponse.json({ error: "bad MCP URL" }, { status: 500 });

  const url = new URL(request.url);
  const search = url.search; // forward ?limit=N verbatim

  try {
    const upstream = await fetch(
      `${base}/api/v1/personality/history${search}`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${mcpToken}` },
        signal: AbortSignal.timeout(10000),
      },
    );
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error ? err.message : "personality history failed",
      },
      { status: 502 },
    );
  }
}
