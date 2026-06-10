/**
 * Per-key memory proxy — guardian's MCP keys memory rows by `key`
 * (per `/api/v1/memories/by-key/{key}`). The route folder is named
 * `[key]` and the destructured param matches, so callers using the
 * memory's `key` field from the list/search responses can address
 * a row directly.
 *
 * Pre-v0.1.14 this folder was named `[id]` for symmetry with other
 * admin proxies, but that misled callers into passing the row's UUID
 * `id` field (which 404'd because the upstream is keyed by `key`).
 * Renamed for clarity per v0.1.12 deep-smoke finding #4.
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ key: string }> },
) {
  const { key } = await params;
  return proxyToMcp(request, `/api/v1/memories/by-key/${encodeURIComponent(key)}`);
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ key: string }> },
) {
  const { key } = await params;
  return proxyToMcp(request, `/api/v1/memories/by-key/${encodeURIComponent(key)}`);
}
