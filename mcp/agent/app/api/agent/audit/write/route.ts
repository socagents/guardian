/**
 * Client → server audit beacon (#JOBS-F6).
 *
 *   POST /api/agent/audit/write   { action, target?, status?, metadata? }
 *
 * Some operator affordances run entirely in the browser — e.g. a job
 * export builds a Blob and triggers a download with no server round-trip,
 * so nothing reaches the audit log. Per Guardian's "no dead/untraceable
 * affordance" rule a client action like that must still leave a trace.
 *
 * This is a thin, best-effort beacon: a `"use client"` component does a
 * fire-and-forget `fetch("/api/agent/audit/write", …)` and this route
 * forwards to the MCP's `POST /api/v1/audit` with the server-side bearer
 * token attached (the browser never sees MCP_TOKEN). Auth is the UI
 * session cookie (enforced by middleware.ts before this handler runs),
 * and the actor is stamped to user:operator.
 *
 * The `action` is ALLOW-LISTED here. The MCP's /api/v1/audit accepts any
 * action string (it must, for the chat route's open-ended lifecycle
 * names), so without a gate the browser could forge arbitrary audit rows
 * (e.g. fake a `login_success` or `restore_applied`). This route only
 * relays the small set of genuinely client-originated UI actions.
 */

import { NextResponse } from "next/server";

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

// Client-originated UI actions that have no server round-trip of their
// own. Keep this list tight — anything that already mutates server state
// is audited server-side and must NOT be relayed from the browser.
const ALLOWED_ACTIONS = new Set(["jobs_exported"]);

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  if (!body || typeof body !== "object") {
    return NextResponse.json(
      { error: "body must be a JSON object" },
      { status: 400 },
    );
  }
  const { action, target, status, metadata } = body as {
    action?: unknown;
    target?: unknown;
    status?: unknown;
    metadata?: unknown;
  };
  if (typeof action !== "string" || !ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json(
      { error: "unsupported audit action" },
      { status: 400 },
    );
  }

  const forwarded = JSON.stringify({
    action,
    target: typeof target === "string" ? target : undefined,
    status: status === "failure" ? "failure" : "success",
    metadata:
      metadata && typeof metadata === "object" && !Array.isArray(metadata)
        ? (metadata as Record<string, unknown>)
        : {},
  });

  return proxyToMcp(request, "/api/v1/audit", {
    method: "POST",
    body: forwarded,
  });
}
