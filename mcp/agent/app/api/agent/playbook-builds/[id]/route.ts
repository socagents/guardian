/**
 * Single playbook-build proxy. Forwards:
 *   GET    /api/agent/playbook-builds/:id  → MCP GET    /api/v1/playbook-builds/:id
 *          (full record incl. playbook_yaml + deploy_summary)
 *   PATCH  /api/agent/playbook-builds/:id  → MCP PATCH  /api/v1/playbook-builds/:id
 *          (lifecycle update: status / deploy_summary / test_incident_id / …)
 *   DELETE /api/agent/playbook-builds/:id  → MCP DELETE /api/v1/playbook-builds/:id
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/playbook-builds/${encodeURIComponent(id)}`);
}

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/playbook-builds/${encodeURIComponent(id)}`);
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToMcp(request, `/api/v1/playbook-builds/${encodeURIComponent(id)}`);
}
