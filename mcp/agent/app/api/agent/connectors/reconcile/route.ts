/**
 * Connector reconcile proxy (#CONN-F11).
 *
 * POST /api/agent/connectors/reconcile
 *   → POST {updater}/api/v1/connectors/reconcile  (Bearer MCP_TOKEN)
 *
 * Idempotent sweep: the updater queries the agent's enabled instances
 * and (re)starts any whose container is missing or stale. Surfaced as a
 * "Reconcile containers" action on the connectors page so an operator
 * can self-heal a partial-start without a direct MCP_TOKEN call to the
 * updater. Same proxying pattern as the per-instance restart route.
 */

import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST() {
  const updaterUrl =
    process.env.GUARDIAN_UPDATER_URL?.replace(/\/$/, "") ||
    "http://guardian-updater:8090";
  const mcpToken = process.env.MCP_TOKEN || "";

  try {
    const r = await fetch(`${updaterUrl}/api/v1/connectors/reconcile`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${mcpToken}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: "{}",
      signal: AbortSignal.timeout(120000),
    });
    return new NextResponse(await r.text(), {
      status: r.status,
      headers: {
        "Content-Type": r.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "updater reconcile failed" },
      { status: 502 },
    );
  }
}
