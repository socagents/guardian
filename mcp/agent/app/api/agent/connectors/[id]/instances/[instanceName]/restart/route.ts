/**
 * Connector-instance restart proxy (#CONN-F11).
 *
 * POST /api/agent/connectors/{id}/instances/{instanceName}/restart
 *   → POST {updater}/api/v1/connectors/{id}/instances/{instanceName}/restart
 *     (Bearer MCP_TOKEN)
 *
 * The updater owns the per-instance connector containers. Before this
 * route an operator whose connector container had wedged had no in-UI
 * recovery — they'd have to call the updater directly with MCP_TOKEN.
 * The connectors page's instance row now has a Restart button that hits
 * this proxy. Optional body { instance_id } is forwarded; the updater
 * also resolves it from the running container's labels when absent.
 *
 * Same MCP_TOKEN → updater proxying pattern as
 * /api/agent/services/{service}/restart.
 */

import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; instanceName: string }> },
) {
  const { id, instanceName } = await params;
  const updaterUrl =
    process.env.GUARDIAN_UPDATER_URL?.replace(/\/$/, "") ||
    "http://guardian-updater:8090";
  const mcpToken = process.env.MCP_TOKEN || "";

  let body = "{}";
  try {
    const text = await request.text();
    if (text.trim()) body = text;
  } catch {
    body = "{}";
  }

  try {
    const r = await fetch(
      `${updaterUrl}/api/v1/connectors/${encodeURIComponent(id)}/instances/${encodeURIComponent(
        instanceName,
      )}/restart`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${mcpToken}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body,
        signal: AbortSignal.timeout(60000),
      },
    );
    return new NextResponse(await r.text(), {
      status: r.status,
      headers: {
        "Content-Type": r.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "updater restart failed" },
      { status: 502 },
    );
  }
}
