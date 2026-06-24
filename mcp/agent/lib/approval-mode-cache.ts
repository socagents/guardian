/**
 * #CHAT-F13 — shared approval-mode cache.
 *
 * The chat handler caches each session's `approval_mode` (manual | bypass)
 * for 30s to avoid a session-meta read on every turn. Previously that cache
 * lived module-private inside app/api/chat/route.ts, and the session-meta
 * PATCH route (the chat-header dropdown's write path) lives in a DIFFERENT
 * module — so it could never invalidate the chat route's copy. A
 * `invalidateSessionApprovalModeCache` helper existed but was never called.
 * Result: after an operator flipped a session from bypass → manual (re-
 * enabling approvals), the chat handler kept auto-approving gated tools for
 * up to 30s — a security footgun.
 *
 * Hoisting the cache here lets both the chat route (read/populate) and the
 * sessions PATCH route (invalidate-on-write) share one Map, so a mode change
 * takes effect on the very next turn. The Map is a per-process singleton; in
 * Guardian's single-container deployment that's the whole stack.
 */

import type { ApprovalMode } from "@/lib/system-prompt";

interface ApprovalModeCacheEntry {
  value: ApprovalMode;
  expiresAt: number;
}

export const APPROVAL_MODE_CACHE_TTL_MS = 30_000;

const approvalModeCache = new Map<string, ApprovalModeCacheEntry>();

/** Return the cached approval mode for a session, or undefined if absent or
 *  expired. */
export function getCachedApprovalMode(sessionId: string): ApprovalMode | undefined {
  const entry = approvalModeCache.get(sessionId);
  if (entry && entry.expiresAt > Date.now()) return entry.value;
  return undefined;
}

/** Populate the cache for a session with the default TTL. */
export function setCachedApprovalMode(sessionId: string, value: ApprovalMode): void {
  approvalModeCache.set(sessionId, {
    value,
    expiresAt: Date.now() + APPROVAL_MODE_CACHE_TTL_MS,
  });
}

/** Drop a session's cached approval mode so the next read re-fetches from the
 *  session store. Called by the session-meta PATCH route on every update —
 *  a PATCH may change approval_mode, and re-reading once is cheap. */
export function invalidateApprovalModeCache(sessionId: string): void {
  approvalModeCache.delete(sessionId);
}
