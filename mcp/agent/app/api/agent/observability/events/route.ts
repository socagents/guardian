/**
 * Runtime events feed proxy — surfaces the MCP's
 * /api/v1/observability/events endpoint to the UI.
 *
 * NOT to be confused with /api/agent/audit, which is the Phase-6
 * audit log of state-changing operations. The runtime events feed is
 * the high-signal stream declared in manifest.observability.events
 * (rt.simulation.*, rt.caldera.*, rt.coverage.*, rt.validation.*,
 * rt.tool.failed). They overlap on tool failures but are intended for
 * different consumers — audit for forensics, runtime events for
 * operator-facing alerts and dashboards.
 *
 * Pre-v0.1.14 the feed had no agent-side proxy at all, so the events
 * recorded by MCP were invisible to the UI. Found via v0.1.12 deep
 * smoke (finding #10).
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const qs = url.search; // includes "?event=...&limit=...&since=..." passthrough
  return proxyToMcp(request, `/api/v1/observability/events${qs}`);
}

export async function POST(request: Request) {
  return proxyToMcp(request, '/api/v1/observability/events');
}
