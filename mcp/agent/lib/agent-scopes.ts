/**
 * Pure scope-mapping helpers for API-key auth on the agent surface.
 * No I/O — consumed by `middleware.ts`. Kept framework-free + side-effect-free
 * so the logic is trivially auditable (this is security code).
 *
 * Coarse model (v0.17.108): `GET` → `agent:read`; mutations + `/api/chat` →
 * `agent:write`; `agent:*` (and the legacy `*`) grant both. Credential-
 * management routes are NEVER reachable by an API key regardless of scope —
 * see `isCredentialRoute` (security invariant; mirrors the MCP api_keys
 * surface which already refuses API-key auth on itself).
 */

export type AgentScope = "agent:read" | "agent:write";

/**
 * Route prefixes that manage credentials (provider secrets, per-instance
 * connector secrets, API keys themselves). API keys are denied here even with
 * `agent:*`; these stay session-only. Keep in sync with the credential
 * guardrail in the root CLAUDE.md.
 */
const CREDENTIAL_PREFIXES = [
  "/api/agent/providers",
  "/api/agent/instances",
  "/api/agent/api-keys",
  // #79/#80 — backup EXPORTS cleartext connector/provider/webhook secrets and
  // restore OVERWRITES them. Both must stay session-only (API keys denied even
  // with agent:*), same as the credential routes above.
  "/api/agent/backup",
  "/api/agent/restore",
];

export function isCredentialRoute(pathname: string): boolean {
  return CREDENTIAL_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

export function requiredScope(pathname: string, method: string): AgentScope {
  if (pathname === "/api/chat" || pathname.startsWith("/api/chat/")) {
    return "agent:write"; // a chat turn invokes tools + an LLM call
  }
  return method.toUpperCase() === "GET" ? "agent:read" : "agent:write";
}

export function scopeSatisfied(scopes: string[], required: AgentScope): boolean {
  if (scopes.includes("*") || scopes.includes("agent:*")) return true;
  return scopes.includes(required);
}
