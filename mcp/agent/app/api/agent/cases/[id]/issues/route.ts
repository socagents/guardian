import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

// List issues grouped under a case.
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/cases/${encodeURIComponent(id)}/issues`);
}

// Add an issue to a case. Body: {issue_id}.
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/cases/${encodeURIComponent(id)}/issues`);
}
