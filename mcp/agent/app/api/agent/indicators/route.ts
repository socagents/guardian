import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

// List indicators (query: type?, issue_id?). The agent writes indicators via
// the indicator_upsert MCP tool during investigations; this surface is read-only.
export async function GET(request: Request) {
  return proxyToMcp(request, '/api/v1/indicators');
}
