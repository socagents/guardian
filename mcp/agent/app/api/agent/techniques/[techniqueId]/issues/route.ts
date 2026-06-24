/**
 * Issues-by-ATT&CK-technique proxy (#INV-F13).
 *
 * GET /api/agent/techniques/{techniqueId}/issues
 *   → GET /api/v1/techniques/{technique_id}/issues
 *
 * Returns issues mapped to an ATT&CK technique ({ issues: [...], count }).
 * Previously reachable only via a direct MCP_TOKEN call.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ techniqueId: string }> },
) {
  const { techniqueId } = await params;
  return proxyToMcp(
    request,
    `/api/v1/techniques/${encodeURIComponent(techniqueId)}/issues`,
  );
}
