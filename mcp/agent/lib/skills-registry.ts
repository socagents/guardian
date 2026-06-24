/**
 * Server-side helper for fetching the live skills registry to inject
 * into the chat system prompt. Used by `app/api/chat/route.ts` to
 * make the model aware of available skills WITHOUT shipping their
 * full bodies in the prompt — just metadata (name, displayName,
 * category, description, ATT&CK tactics).
 *
 * Why a dedicated helper:
 * - Centralizes the fetch shape so route.ts doesn't grow another
 *   inline call.
 * - Catches errors so a transient MCP hiccup degrades to "no skills
 *   block" rather than failing the whole chat turn.
 * - Maps the broad LiveSkillRow shape (which has filesystem-level
 *   fields the model doesn't need) down to the SkillSummary shape
 *   the prompt builder expects. Extra fields would be wasted tokens.
 */

import { GuardianMCPClient } from '@/lib/mcp-client';
import { getEffectiveRuntimeConfig } from '@/lib/runtime-config';
import { postAudit } from '@/lib/auth-store';
import type { SkillSummary } from '@/lib/system-prompt';

interface SkillsListResponse {
  // Shape from skills_crud.py::get_all_skills (post v0.1.33 frontmatter
  // migration). We only consume a subset here.
  name: string;
  displayName?: string;
  category: string;
  description?: string;
  attack?: string[];
  // #SKILL-F7 — per-skill enable flag from frontmatter (default true).
  // A skill with enabled:false is excluded from the system prompt below.
  enabled?: boolean;
}

/**
 * Fetch the skills registry from the embedded MCP and return the
 * minimal metadata shape the prompt builder needs. Returns an empty
 * array on any failure — callers should treat that as "no skills
 * block in the prompt this turn" rather than escalating.
 */
export async function fetchSkillsForPrompt(): Promise<SkillSummary[]> {
  try {
    const config = await getEffectiveRuntimeConfig();
    const mcpToken =
      (config.MCP_TOKEN || '').trim() || process.env.MCP_TOKEN?.trim() || '';
    const mcpUrl =
      (config.MCP_URL || '').trim() ||
      process.env.MCP_URL?.trim() ||
      'http://localhost:8080/api/v1/stream/mcp';
    if (!mcpToken || !mcpUrl) return [];

    const client = new GuardianMCPClient(mcpUrl, mcpToken);
    const result = await client.callTool('skills_list_all', {});
    const raw = result.content?.[0]?.text || '[]';
    const rows = JSON.parse(raw) as SkillsListResponse[];
    if (!Array.isArray(rows)) return [];

    return rows
      // #SKILL-F7 — honor the /skills enable toggle. A skill the operator
      // disabled (enabled:false in frontmatter) is dropped from the prompt
      // so the agent neither sees nor loads it. Absence = enabled.
      .filter((row) => row.enabled !== false)
      .map((row) => ({
      name: row.name,
      displayName: row.displayName || row.name,
      category: row.category,
      description:
        row.description ||
        '(no description in frontmatter — operator should add one)',
      attack: row.attack && row.attack.length > 0 ? row.attack : undefined,
    }));
  } catch (err) {
    // Silent failure on purpose — a chat turn without the skills
    // block is still a useful turn. We log to server stderr so
    // operators can see drift via docker logs, but the chat
    // continues.
    if (typeof console !== 'undefined') {
      // eslint-disable-next-line no-console
      console.warn(
        '[skills-registry] failed to fetch skills for system prompt:',
        err instanceof Error ? err.message : err,
      );
    }
    // #SKILL-F2 — the console.warn above only reaches `docker logs`; from the
    // product UI an operator had NO way to know the <available_skills> block
    // was silently dropped for this turn (the model just never saw the skills).
    // Emit a best-effort audit row so /observability/events surfaces it. Still
    // returns [] — a turn without the skills block is degraded, not fatal.
    postAudit('skills_unavailable', {
      target: 'skills:registry',
      status: 'failure',
      metadata: {
        error: err instanceof Error ? err.message : String(err),
      },
    });
    return [];
  }
}
