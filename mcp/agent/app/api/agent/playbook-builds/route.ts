/**
 * Playbook-build history proxy. Forwards:
 *   GET  /api/agent/playbook-builds        → MCP GET  /api/v1/playbook-builds
 *        (query: status?, order?) — list recorded builds (compact rows).
 *   POST /api/agent/playbook-builds        → MCP POST /api/v1/playbook-builds
 *        (body: { use_case, product?, playbook_name?, playbook_yaml?,
 *                 status?, validation_json?, session_id? }) — record a build.
 * The /playbooks/build UI reads/writes its build history through here.
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  return proxyToMcp(request, '/api/v1/playbook-builds');
}

export async function POST(request: Request) {
  return proxyToMcp(request, '/api/v1/playbook-builds');
}
