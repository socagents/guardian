import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

// List issues (query: status?, case_id?).
export async function GET(request: Request) {
  return proxyToMcp(request, '/api/v1/issues');
}

// Create an issue (operator-initiated; agent uses the issue_create MCP tool).
export async function POST(request: Request) {
  return proxyToMcp(request, '/api/v1/issues');
}
