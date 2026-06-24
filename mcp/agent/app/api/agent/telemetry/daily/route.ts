/**
 * Telemetry daily-counts proxy (#OBS-F17).
 *
 * GET /api/agent/telemetry/daily?event=<name>&days=30
 *   → GET /api/v1/telemetry/daily?event=<name>&days=30
 *
 * Per-day event counts for charting. proxyToMcp forwards the query
 * string verbatim.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyToMcp(request, "/api/v1/telemetry/daily");
}
