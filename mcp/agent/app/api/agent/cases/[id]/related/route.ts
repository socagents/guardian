/**
 * Related cases proxy (#INV-F13).
 *
 * GET /api/agent/cases/{id}/related → GET /api/v1/cases/{id}/related
 *
 * Returns cross-case relationships ({ related: [...], count }) for the
 * campaign view. Previously reachable only via a direct MCP_TOKEN call.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/cases/${encodeURIComponent(id)}/related`);
}
