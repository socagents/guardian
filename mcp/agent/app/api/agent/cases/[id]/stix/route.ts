import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

// v0.2.48 (stage D) — campaign-level STIX 2.1 bundle for one case (download).
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/cases/${encodeURIComponent(id)}/stix`);
}
