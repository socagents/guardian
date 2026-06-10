/**
 * Proxy for /api/v1/jobs/yaml-issues — v0.3.13.
 *
 * Read-only endpoint surfacing YAML-load failures that were previously
 * buried as WARN-per-file lines in docker compose logs. The /jobs page
 * polls this on render; when count > 0 it shows a banner pointing the
 * operator at the offending files.
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  return proxyToMcp(request, '/api/v1/jobs/yaml-issues');
}
