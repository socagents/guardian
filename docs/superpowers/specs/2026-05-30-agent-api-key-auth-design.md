# Agent API-key authentication — design spec

**Date:** 2026-05-30
**Issue:** (to open) — "API-key auth for the Next.js agent surface (`/api/chat` + `/api/agent/*`)"
**Status:** design approved (operator delegated remaining micro-decisions to recommendations; proceeding autonomously)

## Goal

Let programmatic clients (and the agent's own automation — e.g. the smoke campaign's Stage-2) authenticate to the **Next.js agent surface** (`/api/chat`, `/api/agent/*`) with an **API-key bearer**, as an alternative to the username/password **session cookie**. Today that surface is session-cookie-only (`middleware.ts`), which is why automated chat-agent testing can't run without a human-created session.

## What already exists (reuse, don't rebuild)

Phantom already ships a complete API-key system; the only gap is that the Next.js middleware doesn't accept these keys.

- **Store** — `bundles/spark/mcp/src/usecase/api_keys.py` (`SqliteApiKeyStore` / `api_key_store()`). Key shape `phantom_ak_<id>_<secret>`; DB stores `sha256(secret)` + `scopes_json` + `created_at` + `last_used_at`; `verify(token)` parses the id, hashes the secret, constant-time compares, updates `last_used_at`, returns the row (with scopes) or None for miss/revoked.
- **Mint/list/revoke REST** — `bundles/spark/mcp/src/api/api_keys.py` (`GET/POST/DELETE /api/v1/api_keys`). **MCP_TOKEN-gated; deliberately refuses API-key auth on itself** (no privilege escalation — a key can't mint more keys).
- **Bearer helpers** — `bundles/spark/mcp/src/api/auth.py`: `require_bearer()` accepts MCP_TOKEN (scope `*`) OR an active API key (scoped); `require_scope(scope)` enforces per-route. Used by MCP REST endpoints today (e.g. `audit:read`).
- **UI** — `mcp/agent/app/api-keys/page.tsx` + sidebar entry ("API Keys", `vpn_key`); agent proxies `mcp/agent/app/api/agent/api-keys/route.ts` (+ `[id]`).
- **Session-validate pattern (to mirror)** — `mcp/agent/middleware.ts` → `lib/auth-store.ts validateSession()` → MCP `POST /api/v1/ui/auth/session` (MCP_TOKEN bearer, 30s positive cache, `bustSessionCache()` on change-password).

## Design (recommended approach: MCP loopback verify)

### Decision: validation architecture
- **A — MCP loopback verify (chosen):** add `POST /api/v1/ui/auth/verify_key`; the middleware calls it with a 30s cache, exactly like `validateSession`. Reuses `store.verify()` → single source of truth, constant-time, revocation-aware.
- B — middleware reads the sqlite directly: reimplements hash-verify in TS, schema coupling + drift. **Rejected.**
- C — switch keys to JWTs for edge validation: new key format, breaks existing keys, over-engineered. **Rejected.**

### Data flow
A request hits a middleware-matched path. Middleware checks `Authorization: Bearer phantom_ak_*` **before** the cookie:
1. **API-key bearer present** → `validateApiKey(token)` (`auth-store.ts` → MCP `verify_key`, 30s cache) → `{valid, scopes, key_id, label}`.
   - invalid/expired/revoked → `401 { code: "invalid_api_key" }`.
   - valid → **coarse-scope check** against route + method (below). Pass → `NextResponse.next()` with principal headers; fail → `403`.
2. **No API-key bearer** → existing session-cookie path runs **unchanged** (zero regression risk for the human UI).

### Coarse scope model
- `GET` → requires `agent:read`. `POST/PUT/PATCH/DELETE` → requires `agent:write`. `/api/chat` (any method) → `agent:write` (it invokes an LLM turn). `agent:*` grants both.
- **Hard security invariant — credential exclusion:** requests to `/api/agent/providers/*`, `/api/agent/instances/*`, `/api/agent/api-keys/*` are **denied for API-key principals even with `agent:*`** → `403 { code: "api_key_credential_route_forbidden" }`. Those routes stay session-only. (Defense in depth: the MCP mint surface already refuses API-key auth; this denies the agent-side proxies too.) Implemented as an explicit, documented denylist with one extension point.

### Components touched
| File | Change |
|---|---|
| `bundles/spark/mcp/src/api/ui_auth.py` | Add `POST /api/v1/ui/auth/verify_key` (MCP_TOKEN-gated). Body `{api_key}` → `{valid, scopes, key_id, label}` via `api_key_store().verify()`. |
| `mcp/agent/lib/auth-store.ts` | Add `validateApiKey(token)` (+ 30s cache, `bustApiKeyCache()`). Mirror `validateSession`. |
| `mcp/agent/middleware.ts` | API-key branch (before cookie) + coarse-scope check + credential denylist. Cookie path unchanged. |
| `mcp/agent/lib/agent-scopes.ts` (new) | Pure helper: `requiredScope(path, method)` + `isCredentialRoute(path)` + `scopeSatisfied(scopes, required)`. Unit-testable in isolation. |
| `mcp/agent/app/api-keys/page.tsx` | Mint form offers `agent:read` / `agent:write` / `agent:*` (alongside existing scopes). |
| `bundles/spark/mcp/src/api/api_keys.py` | (If a scope allowlist exists) add the three `agent:*` scopes. Otherwise no change (free-form scopes). |

### Error handling + audit
- 401 invalid/expired/revoked key; 403 insufficient scope; 403 credential route.
- Audit rows attribute the API-key principal (`api_key:<id>` + label) — threaded via a request header the chat/audit path already reads for the actor. No user impersonation.

### Security invariants (all MUST hold)
1. API keys never reach credential-minting routes (providers/instances/api-keys) — enforced at the MCP mint surface (existing) AND the agent middleware (new denylist).
2. Keys hashed at rest (existing); constant-time verify (existing).
3. Revocation effective within 30s (cache TTL) and immediate when revoked via the UI/REST path (`bustApiKeyCache()`).
4. The `verify_key` endpoint is MCP_TOKEN-gated (internal loopback only).
5. No change to the session-cookie path → no regression for human UI auth.

### Testing
- **Unit (`agent-scopes.ts`):** GET→read, mutation→write, chat→write, `agent:*` grants both, credential routes flagged.
- **Middleware tests:** valid key + sufficient scope → pass; valid key + insufficient scope → 403; valid key + credential route → 403; invalid key → 401; no key + valid cookie → pass (regression guard); no key + no cookie → 401.
- **MCP `verify_key` tests:** valid/invalid/revoked key; MCP_TOKEN gate.
- **E2E:** mint an `agent:*` key via REST → `curl -H "Authorization: Bearer phantom_ak_..." /api/chat` → 200 + a real streamed turn; `curl` a credential route with the same key → 403.

### Docs (ship with the code — feature-completeness contract)
- `/help/architecture#authentication` — add the API-key bearer path + the coarse-scope + credential-exclusion model + the inter-service wire (middleware → MCP `verify_key`).
- `/help/user` — "Authenticate with an API key" subsection (mint in /api-keys, pick a scope, send as `Authorization: Bearer`).
- `mcp/agent/lib/journeys.ts` — "Mint an API key and call the agent API" journey.
- `CHANGELOG.md` + `mcp/agent/lib/release-notes.ts` — v0.17.108 entry.

## Release classification
Scenario 1 (code-only; `api_keys.db` already exists, no installer/storage change) → minor bump **v0.17.108**. Dev-cycle push + auto-deploy; no customer tag without operator approval.

## Stage-2 payoff (the motivating use)
After deploy: mint one scoped, revocable `agent:*` key via the MCP_TOKEN REST → the Stage-2 driver sends it as a bearer to `/api/chat` per vendor ("simulate \<vendor\>, use as many fields as possible, verify XDM") → fully autonomous chat-agent runs, no password, no session reuse. Key id recorded for revocation.

## Deferred (follow-up issues, not this release)
- Rate-limiting on API-key `/api/chat` (LLM-cost abuse) — keys are revocable + audited; defer.
- Per-key TTL/expiry — revoke-only today; defer.
- Granular per-resource scopes — coarse scopes ship now; granular later if a use case emerges.
