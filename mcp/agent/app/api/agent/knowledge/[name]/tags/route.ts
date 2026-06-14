/**
 * KB tag-facet proxy. Forwards GET /api/agent/knowledge/{name}/tags
 * → MCP's /api/v1/kbs/{name}/tags. Returns { tags: [{tag, count}] }
 * for the /knowledge/{name} filter chips (v0.2.20).
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> },
) {
  const { name } = await params;
  return proxyToMcp(
    request,
    `/api/v1/kbs/${encodeURIComponent(name)}/tags`,
  );
}
