/**
 * Personality reset proxy (#PLAT-F2).
 *
 * POST /api/agent/personality/reset → POST /api/v1/personality/reset
 *
 * The MCP's SqlitePersonalityStore.reset_to_default() restores the
 * server-side BUNDLE default — the single source of truth. Before this
 * route, the /settings/personality "Reset Defaults" button PUT the
 * Next.js-side DEFAULT_CONFIG constant, which drifts from the bundle
 * default across releases and bypasses the reset endpoint's gating.
 */

import { NextResponse } from "next/server";

import { deriveMcpBaseUrl, getEffectiveRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

export async function POST() {
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

  try {
    const upstream = await fetch(`${base}/api/v1/personality/reset`, {
      method: "POST",
      headers: { Authorization: `Bearer ${mcpToken}` },
      signal: AbortSignal.timeout(10000),
    });
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "personality reset failed" },
      { status: 502 },
    );
  }
}
