/**
 * /api/agent/log-destinations — list + create proxy (v0.17.1 R6).
 *
 * GET   → list (?type_id=&enabled_only=)
 * POST  → create new destination
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const qs = url.search; // preserves ?type_id= etc.
  return proxyToMcp(request, `/api/v1/log-destinations${qs}`);
}

export async function POST(request: Request) {
  return proxyToMcp(request, "/api/v1/log-destinations");
}
