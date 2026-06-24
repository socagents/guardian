/**
 * Issues-by-playbook proxy (#INV-F13).
 *
 * GET /api/agent/playbooks/{docId}/issues
 *   → GET /api/v1/playbooks/{doc_id}/issues
 *
 * Returns issues matched to a playbook doc ({ issues: [...], count }).
 * Previously reachable only via a direct MCP_TOKEN call.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ docId: string }> },
) {
  const { docId } = await params;
  return proxyToMcp(
    request,
    `/api/v1/playbooks/${encodeURIComponent(docId)}/issues`,
  );
}
