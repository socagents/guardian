import { proxyToMcp } from '@/lib/mcp-proxy';
import { bustApiKeyCacheByKeyId } from '@/lib/auth-store';

export const dynamic = 'force-dynamic';

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const res = await proxyToMcp(request, `/api/v1/api_keys/${encodeURIComponent(id)}`);
  // #API-F11 — evict the revoked key from the middleware validation cache so
  // it stops passing auth immediately rather than for up to the 30s TTL.
  // Safe to call unconditionally: evicting an id that wasn't revoked just
  // forces one re-validation against the MCP on the next request.
  bustApiKeyCacheByKeyId(id);
  return res;
}
