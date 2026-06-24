/**
 * Telemetry status proxy (#OBS-F17).
 *
 * GET  /api/agent/telemetry        → GET  /api/v1/telemetry  (status snapshot)
 * POST /api/agent/telemetry/enable → POST /api/v1/telemetry/enable (separate file)
 *
 * Surfaces the opt-in usage-counter status ({ enabled, declared_events,
 * total_recorded, counts_by_event }) so the observability UI can render
 * the privacy posture + per-event counts. Before this route the entire
 * telemetry surface was MCP-internal — unreachable from the browser.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyToMcp(request, "/api/v1/telemetry");
}
