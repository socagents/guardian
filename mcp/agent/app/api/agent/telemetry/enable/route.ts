/**
 * Telemetry enable/disable proxy (#OBS-F17).
 *
 * POST /api/agent/telemetry/enable → POST /api/v1/telemetry/enable
 *   body: { enabled: boolean, actor?: string }
 *
 * Toggles the opt-in usage-counter posture. The MCP store audits the
 * change (telemetry_toggled). Used by the observability telemetry page's
 * on/off switch.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  return proxyToMcp(request, "/api/v1/telemetry/enable");
}
