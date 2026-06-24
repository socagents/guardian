/**
 * /api/agent/operator-state/{key}
 *
 * Thin proxy to the MCP operator-state surface (v0.5.1).
 *
 * Pre-v0.5.1 the per-operator workflow state (tested journeys,
 * metrics bookmarks) lived in browser localStorage with all the
 * drawbacks the operator flagged: volume wipes didn't clear it,
 * cross-device + cross-browser inconsistency, missing from backups.
 * v0.5.1 collapses to ONE canonical home in MCP — same pattern
 * v0.4.0 used for auth + v0.5.0 used for marketplace.
 *
 * Routes:
 *   GET     /api/agent/operator-state/{key}   — returns {key, value, updated_at} or 404
 *   PUT     /api/agent/operator-state/{key}   — body {value: <json>}
 *   DELETE  /api/agent/operator-state/{key}   — idempotent 204
 *
 * The hooks (use-tested-journeys, metrics-bookmarks) drive these from
 * the browser. Each does optimistic-update + fire-and-forget PUT so
 * the UI is snappy and the persistence is auditable server-side.
 *
 * Auth: cookie-gated via the standard auth-gate middleware that
 * fronts every /api/agent/* route. The Next.js layer forwards to MCP
 * with the bundle-internal MCP_TOKEN bearer.
 */

import { NextRequest, NextResponse } from "next/server";

import { resolveMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

async function forward(
  request: NextRequest,
  key: string,
  method: "GET" | "PUT" | "DELETE",
): Promise<NextResponse> {
  if (!key) {
    return NextResponse.json(
      { error: "key path segment is required" },
      { status: 400 },
    );
  }

  const r = await resolveMcp();
  if (r instanceof NextResponse) return r;

  const url = `${r.base}/api/v1/operator-state/${encodeURIComponent(key)}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${r.token}`,
  };
  // #CHAT-F14 — forward the principal the middleware attributed
  // (X-Guardian-Actor) so the MCP-side PUT/DELETE audit row attributes the
  // operator-state mutation (e.g. the chat subagents-enabled toggle) to the
  // real caller instead of the hardcoded user:operator default. Mirrors
  // lib/mcp-proxy.ts; this route hand-rolls its forward() so it must do the
  // same explicitly.
  const fwdActor = request.headers.get("x-guardian-actor");
  if (fwdActor) headers["X-Guardian-Actor"] = fwdActor;
  const fwdTrigger = request.headers.get("x-guardian-trigger");
  if (fwdTrigger) headers["X-Guardian-Trigger"] = fwdTrigger;
  const init: RequestInit = {
    method,
    headers,
    cache: "no-store",
  };

  if (method === "PUT") {
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json(
        { error: "invalid JSON body" },
        { status: 400 },
      );
    }
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] =
      "application/json";
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch (err) {
    return NextResponse.json(
      {
        error: "MCP unreachable",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 502 },
    );
  }

  // DELETE returns 204 with empty body — don't try to parse.
  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const payload = await upstream.json().catch(() => null);
  if (!upstream.ok) {
    return NextResponse.json(
      payload ?? { error: `MCP returned ${upstream.status}` },
      { status: upstream.status },
    );
  }
  return NextResponse.json(payload);
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> },
) {
  const { key } = await params;
  return forward(request, key, "GET");
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> },
) {
  const { key } = await params;
  return forward(request, key, "PUT");
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> },
) {
  const { key } = await params;
  return forward(request, key, "DELETE");
}
