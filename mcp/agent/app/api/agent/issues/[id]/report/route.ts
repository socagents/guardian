/**
 * Investigation issue report proxy (#INV-F13).
 *
 * GET /api/agent/issues/{id}/report → GET /api/v1/issues/{id}/report
 *
 * Returns the generated investigation report for a resolved issue
 * ({ issue_id, report }), or 404 when none has been generated. Before
 * this route the endpoint was reachable only via a direct MCP_TOKEN
 * bearer call — invisible to the operator UI.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/issues/${encodeURIComponent(id)}/report`);
}
