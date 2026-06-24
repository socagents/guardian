/**
 * Next.js middleware — server-side session-cookie enforcement for all
 * agent-control surfaces.
 *
 * v0.9.1 — closes the gap behind issue #70 (*"API auth gate is client-side
 * only; /api/agent/* mutations callable without auth headers"*).
 *
 * # Threat model
 *
 * Pre-v0.9.1, AuthGate (`components/auth/auth-gate.tsx`) decided what the
 * BROWSER rendered but imposed zero protection on the server-side API. Any
 * caller that reached port 3000 — by VM lateral movement, misconfigured
 * firewall, accidentally-exposed cloud LB, container escape — could POST
 * `/api/agent/memory`, `/api/agent/jobs`, `/api/chat`, `/api/skills`, etc.
 * with NO cookies and get 200/201 back. The deployment relied on the
 * network boundary (IAP tunnel) as the only auth gate. Defense-in-shallow.
 *
 * v0.9.1 adds a session-cookie check at the SERVER tier. Same `guardian_session`
 * cookie AuthGate reads on the client; same `validateSession` call the
 * `/api/auth/status` route makes. The cookie's value must validate against
 * the MCP-side session store; absence OR invalid value → 401 JSON.
 *
 * # Coverage
 *
 * The matcher (see `config.matcher` below) targets every server endpoint that
 * exposes the agent or its data:
 *
 *   /api/agent/**   — 84 routes including memory, jobs, hooks, sessions,
 *                     skills CRUD, tool dispatch, secrets-adjacent metadata
 *   /api/chat       — kicks off a full LLM turn with real tool calls
 *   /api/skills/**  — skill CRUD outside the /api/agent/ prefix
 *
 * `/api/auth/*` is INTENTIONALLY excluded — login can't require login, and
 * AuthGate polls `/api/auth/status` BEFORE any cookie exists.
 *
 * `/api/marketplace/connectors` and `/api/marketplace/connectors/[id]` are
 * ALSO intentionally excluded (silently — they're outside the `/api/agent/`
 * prefix). They serve hardcoded read-only connector catalog JSON: no
 * secrets, no mutation surface, no credential access. Leaving them open
 * lets pre-login pages render the marketplace card list. **If these routes
 * ever grow write handlers, extend the matcher to cover them in the same
 * PR** — the silent exclusion becomes dangerous the moment they mutate.
 *
 * # Exemptions (paths the matcher hits but cookie-check skips)
 *
 *   /api/agent/health           — Docker compose healthcheck calls this
 *                                  from inside the container with no cookies.
 *                                  Gating it makes the container unhealthy.
 *
 *   /api/agent/internal/fire-hook — Called by the embedded MCP subprocess,
 *                                  uses `MCP_TOKEN` bearer (not the session
 *                                  cookie). Has its own auth layer. Gating
 *                                  it with a session check would break hook
 *                                  dispatch.
 *
 * # Edge runtime
 *
 * Next.js 15.1.6 — middleware runs on the Edge runtime (Node.js runtime is
 * GA in 15.2+). `validateSession` uses only `fetch` + in-memory cache, so it
 * works in Edge. `mcpPost` resolves the MCP URL from runtime-config, which
 * also only uses fetch.
 *
 * # Performance
 *
 * `validateSession` has a 30-second positive cache (in-memory Map inside
 * `lib/auth-store.ts`). First request per cookie: one fetch to the embedded
 * MCP's `/api/v1/ui/auth/session` (~10ms loopback). Cached requests: 0 ms.
 * Negative results NOT cached (revocation must surface immediately).
 */

import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE_NAME } from "@/lib/auth-defaults";
import { validateSession, validateApiKey, postAudit } from "@/lib/auth-store";
import {
  requiredScope,
  isCredentialRoute,
  scopeSatisfied,
} from "@/lib/agent-scopes";

// Paths the matcher catches that should bypass the session check entirely.
// Kept as a Set so the membership check is O(1) per request.
const EXEMPT_PATHS = new Set<string>([
  "/api/agent/health",
  "/api/agent/internal/fire-hook",
]);

// #API-F18/OBS-F8 — stamp the authenticated principal on the request so the
// MCP-side audit attributes a mutation to the specific operator session or
// API key (forwarded by lib/mcp-proxy → TriggerContextMiddleware → audit
// actor), instead of a hardcoded "user:operator". We OVERWRITE any inbound
// X-Guardian-Actor so a client can't spoof attribution.
function nextWithActor(request: NextRequest, actor: string): NextResponse {
  const headers = new Headers(request.headers);
  headers.set("x-guardian-actor", actor);
  // #API-F8 — stamp a trace id on every admitted request (free, Edge-safe via
  // Web Crypto) so MCP-side logs/audit rows can be correlated to the proxy
  // request that produced them. Respect an inbound id if the caller set one.
  if (!headers.get("x-request-id")) {
    headers.set("x-request-id", crypto.randomUUID());
  }
  // #API-F8 — record an admission trace for STATE-CHANGING requests only
  // (POST/PUT/PATCH/DELETE). Fire-and-forget; GETs are excluded so high-rate
  // polling (e.g. the 250ms approval poll) doesn't flood audit.db. This gives
  // a per-mutation proxy-tier trail (method + path + actor) the tier lacked.
  const method = request.method.toUpperCase();
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    postAudit("proxy_request_admitted", {
      target: `route:${request.nextUrl.pathname}`,
      status: "success",
      actor,
      metadata: {
        method,
        path: request.nextUrl.pathname,
        request_id: headers.get("x-request-id"),
      },
    });
  }
  return NextResponse.next({ request: { headers } });
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const pathname = request.nextUrl.pathname;

  if (EXEMPT_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  // API-key bearer path (v0.17.108) — checked BEFORE the cookie. An
  // `Authorization: Bearer guardian_ak_*` authenticates programmatic
  // clients; absence falls through to the session-cookie path below
  // (human UI auth, unchanged → zero regression). Coarse scopes gate
  // read vs write; credential-management routes are denied even with
  // `agent:*` (security invariant — those stay session-only).
  const authz = request.headers.get("authorization") ?? "";

  // Internal-service auth (v0.17.126) — the embedded MCP subprocess calls
  // back into the agent (the job scheduler firing a scheduled prompt via
  // /api/chat) using the container's MCP_TOKEN as a bearer, the same
  // loopback trust the exempt /api/agent/internal/* routes use. MCP_TOKEN
  // is the per-boot agent↔MCP secret, never exposed to the browser; a
  // caller that already holds it has full embedded-MCP access, so honoring
  // it here doesn't widen the trust boundary. Credential-management routes
  // stay blocked (same invariant as API keys). Without this, every
  // scheduled prompt job 401'd with no_session_cookie once the v0.9.1
  // middleware gate landed.
  const internalToken = process.env.MCP_TOKEN?.trim();
  if (internalToken && authz === `Bearer ${internalToken}`) {
    if (isCredentialRoute(pathname)) {
      return NextResponse.json(
        { error: "forbidden", code: "internal_token_credential_route_forbidden" },
        { status: 403 },
      );
    }
    return NextResponse.next();
  }

  if (authz.toLowerCase().startsWith("bearer guardian_ak_")) {
    const apiKey = authz.slice("bearer ".length).trim();
    const keyResult = await validateApiKey(apiKey);
    if (!keyResult.valid) {
      // #API-F7 — invalid/revoked key probing now leaves a trace. Key did
      // not authenticate → actor anonymous. Log only the prefix.
      postAudit("api_key_auth_failed", {
        target: `api_key:${apiKey.slice(0, 20)}`,
        actor: "anonymous",
        metadata: { reason: keyResult.reason, path: pathname, method: request.method },
      });
      return NextResponse.json(
        { error: "unauthenticated", code: keyResult.reason },
        { status: 401 },
      );
    }
    if (isCredentialRoute(pathname)) {
      // #API-F7 — a valid key blocked from a credential route is a real
      // authz event; record it (actor known — the key authenticated).
      postAudit("api_key_credential_route_denied", {
        target: `route:${pathname}`,
        actor: `apikey:${keyResult.keyId || "unknown"}`,
        metadata: { key_id: keyResult.keyId, path: pathname, method: request.method },
      });
      return NextResponse.json(
        { error: "forbidden", code: "api_key_credential_route_forbidden" },
        { status: 403 },
      );
    }
    const needed = requiredScope(pathname, request.method);
    if (!scopeSatisfied(keyResult.scopes, needed)) {
      // #API-F7 — scope denial is now audited (under-scoped key probing
      // write routes leaves a trace).
      postAudit("api_key_scope_denied", {
        target: `route:${pathname}`,
        actor: `apikey:${keyResult.keyId || "unknown"}`,
        metadata: {
          key_id: keyResult.keyId,
          required_scope: needed,
          key_scopes: keyResult.scopes,
          path: pathname,
          method: request.method,
        },
      });
      return NextResponse.json(
        { error: "forbidden", code: "insufficient_scope", required: needed },
        { status: 403 },
      );
    }
    return nextWithActor(request, `apikey:${keyResult.keyId || "unknown"}`);
  }

  const cookie = request.cookies.get(SESSION_COOKIE_NAME);
  const token = cookie?.value;
  if (!token) {
    return NextResponse.json(
      { error: "unauthenticated", code: "no_session_cookie" },
      { status: 401 },
    );
  }

  // validateSession returns { valid: true, ... } | { valid: false, reason }.
  // Anything other than `valid: true` → 401. The reason is included in the
  // body so operators debugging "why am I getting 401" see the actual cause.
  const result = await validateSession(token);
  if (!result.valid) {
    return NextResponse.json(
      { error: "unauthenticated", code: result.reason },
      { status: 401 },
    );
  }

  return nextWithActor(request, "user:operator");
}

// Next.js requires `matcher` to be statically analyzable — string literals,
// no template strings or computed values. The two distinct prefix patterns
// below cover /api/agent/**, /api/chat, /api/skills + /api/skills/**.
export const config = {
  matcher: [
    "/api/agent/:path*",
    "/api/chat",
    "/api/chat/:path*",
    "/api/skills",
    "/api/skills/:path*",
  ],
};
