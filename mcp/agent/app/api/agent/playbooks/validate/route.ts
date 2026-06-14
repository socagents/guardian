/**
 * Playbook validation proxy. Forwards POST /api/agent/playbooks/validate
 * → MCP's /api/v1/playbooks/validate. Body: { playbook_yaml: string }.
 * Returns { valid, errors, warnings, task_count } for the /playbooks/build UI.
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  return proxyToMcp(request, `/api/v1/playbooks/validate`);
}
