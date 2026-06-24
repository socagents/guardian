/**
 * Internal hook fire-site — Issue #28 fire-sites (v0.5.32).
 *
 * MCP-side code paths (notification publish, approval request) can't
 * call the TS-side `dispatchHooks()` directly. This endpoint bridges:
 * MCP POSTs `{event, payload}` here; we run the dispatcher and return
 * the aggregate result. Fire-and-forget on the MCP side, so the
 * response is mostly informational.
 *
 * Authentication: MCP_TOKEN bearer (same loopback-trust pattern the
 * agent uses for every other MCP-to-agent call).
 *
 * Why "internal" in the path: this route is for in-cluster
 * loopback calls only — never reachable from the operator's browser
 * (NextAuth gates the `/api/agent/*` surface; the bearer auth here
 * is independent). The path name is the contract that lets future
 * routing layers (e.g. an ingress that filters internal paths)
 * distinguish the loopback surface from the operator-facing one.
 */

import { NextRequest, NextResponse } from "next/server";

import {
  dispatchHooks,
  type HookAggregateResult,
} from "@/lib/hook-runner";
import { HOOK_EVENTS, type HookEvent, type HookPayload } from "@/lib/hooks";
import { callMcpServer } from "@/lib/mcp-proxy";
import { getEffectiveRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest): Promise<NextResponse> {
  // Auth: bearer == MCP_TOKEN. The MCP carries this in its callback.
  const auth = req.headers.get("authorization") ?? "";
  const expected = (
    await getEffectiveRuntimeConfig()
  ).MCP_TOKEN || process.env.MCP_TOKEN || "";
  if (!expected || auth !== `Bearer ${expected}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: { event?: string; payload?: HookPayload };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return NextResponse.json(
      { error: "body must be JSON" },
      { status: 400 },
    );
  }
  const event = body.event;
  if (!event || !HOOK_EVENTS.includes(event as HookEvent)) {
    return NextResponse.json(
      { error: `event must be one of ${HOOK_EVENTS.join(", ")}` },
      { status: 400 },
    );
  }
  const payload = body.payload;
  if (!payload || typeof payload !== "object") {
    return NextResponse.json(
      { error: "payload must be an object" },
      { status: 400 },
    );
  }

  // #F-hook-event — matchesHook() discriminates on `payload.event`
  // (hooks.ts: `hook.event !== payload.event`). MCP-side loopback callers
  // dispatch with the event as the TOP-LEVEL field and don't always echo it
  // inside `payload`, so a payload missing the inner `event` made
  // `payload.event` undefined → EVERY hook silently failed to match and the
  // fire was dropped with no trace. Default the inner event to the validated
  // top-level one so a payload without an explicit `event` still matches the
  // dispatched event. (An explicit inner `event` is left untouched.)
  if (
    (payload as Partial<HookPayload>).event === undefined ||
    (payload as Partial<HookPayload>).event === null
  ) {
    (payload as { event: HookEvent }).event = event as HookEvent;
  }

  let result: HookAggregateResult;
  try {
    result = await dispatchHooks(event as HookEvent, payload);
  } catch (err) {
    return NextResponse.json(
      {
        error: "dispatch failed",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 500 },
    );
  }

  // #HOOK-F4 — audit the dispatch. Notification + PermissionRequest hooks
  // fire ONLY through this loopback route (not the chat route's
  // fireHookEvent), so without this they were invisible in
  // /observability/events — a Slack-mirror / PagerDuty hook firing left no
  // trace. Mirror the chat route's gating: only write when at least one
  // hook actually fired. Best-effort — never fail the dispatch response on
  // an audit hiccup.
  if (result.decisions.length > 0) {
    const auditBody = {
      action: "hook_dispatched",
      target: `hook-event:${event}`,
      status: result.decision === "deny" ? "failure" : "success",
      metadata: {
        event,
        decision: result.decision ?? "allow",
        // #HOOK-F3 — record injected-context presence/size here too (this
        // loopback route is the only fire-site for Notification +
        // PermissionRequest hooks), so the audit row reflects what the hook
        // added without re-running.
        inject_context_present: Boolean(result.injectContext),
        inject_context_chars: result.injectContext?.length ?? 0,
        inject_context_preview: result.injectContext?.slice(0, 200),
        hooks: result.decisions.map((d) => ({
          id: d.hookId,
          name: d.name,
          decision: d.decision,
          error: d.error,
          duration_ms: d.durationMs,
        })),
      },
    };
    // #HOOK-F16 — this loopback is the ONLY fire-site for Notification +
    // PermissionRequest hooks, so a dropped hook_dispatched row here means
    // those dispatches are invisible in /observability/events with no other
    // trace. The bare fire-and-forget swallowed a transient MCP blip; add a
    // one-shot short-backoff retry (mirroring the chat route's safeAudit) so a
    // momentary outage doesn't silently lose the row — without ever awaiting
    // in a way that gates the loopback response.
    void (async () => {
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          await callMcpServer("/api/v1/audit", {
            method: "POST",
            body: auditBody,
          });
          return;
        } catch (err) {
          if (attempt === 0) {
            await new Promise((r) => setTimeout(r, 250));
            continue;
          }
          console.warn(
            "fire-hook: hook_dispatched audit write failed after retry:",
            err instanceof Error ? err.message : err,
          );
        }
      }
    })();
  }

  // #HOOK-F6 — feed a PermissionRequest hook's verdict back into the
  // blocked approval gate. The MCP-side gate blocks on the bus until
  // /api/v1/approvals/{id}/resolve is called; a hook that decides
  // allow/deny previously went nowhere, so a Slack-clicked approval that
  // didn't separately POST /resolve hung the full 5-minute timeout. When
  // a PermissionRequest hook returns a definitive allow/deny, resolve the
  // matching approval now. ("ask"/undefined → leave it for a human.)
  if (
    event === "PermissionRequest" &&
    (result.decision === "allow" || result.decision === "deny")
  ) {
    const requestId = (payload as Extract<HookPayload, { event: "PermissionRequest" }>).requestId;
    if (requestId) {
      void callMcpServer(
        `/api/v1/approvals/${encodeURIComponent(requestId)}/resolve`,
        {
          method: "POST",
          body: {
            decision: result.decision === "allow" ? "approved" : "denied",
            reason:
              result.reason ||
              `Resolved by PermissionRequest hook (${result.decision}).`,
          },
        },
      ).catch(() => {
        /* best-effort; the bus stays pending for human resolution on failure */
      });
    }
  }

  return NextResponse.json({
    dispatched: true,
    decision: result.decision,
    decisions: result.decisions,
  });
}
