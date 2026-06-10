import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  return proxyToMcp(request, '/api/v1/instances');
}

/**
 * Create a connector instance.
 *
 * Body shape: {connector_id, name, config?, secrets?}. Mirrors the
 * setup-form materialization but for ad-hoc additions from the UI's
 * "+ Create Instance" button. Pre-v0.1.15 the proxy wasn't wired so
 * the button silently 404'd; this completes the CRUD.
 */
export async function POST(request: Request) {
  return proxyToMcp(request, '/api/v1/instances');
}
