/**
 * Cross-KB semantic search proxy. Forwards POST /api/agent/knowledge/search
 * → MCP's /api/v1/kbs/search (searches every loaded KB when no kb_name is
 * given). Mirrors the MCP surface; the per-KB variant is at /{name}/search.
 *
 * Body: { query: string, kb_name?: string, category?: string, tags?: string[],
 *         limit?: number, offset?: number, min_score?: number }
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  return proxyToMcp(request, `/api/v1/kbs/search`);
}
