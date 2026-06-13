import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

// One indicator + the issues it appears in.
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/indicators/${encodeURIComponent(id)}`);
}
