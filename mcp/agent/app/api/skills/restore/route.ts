/**
 * Skill restore proxy (#SKILL-F15).
 *
 * POST /api/skills/restore → POST /api/v1/skills/restore
 *   body: { backup_name: string, category?: string }
 *
 * Restores a soft-deleted skill from /app/skills/.deleted/ back into the
 * live skills tree. The click IS the approval (operator-direct REST,
 * gate-bypassing — same pattern as the delete REST path). Audited as
 * skill_restored on the MCP side.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  return proxyToMcp(request, "/api/v1/skills/restore");
}
