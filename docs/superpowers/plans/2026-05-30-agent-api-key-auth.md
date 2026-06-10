# Agent API-key Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an `Authorization: Bearer phantom_ak_*` API key authenticate the Next.js agent surface (`/api/chat` + `/api/agent/*` + `/api/skills/*`), as an alternative to the session cookie, gated by coarse scopes and excluding credential-management routes.

**Architecture:** Reuse the existing api_keys store + UI + mint/verify. Add (1) an MCP `verify_key` endpoint, (2) a `validateApiKey()` in `auth-store.ts` mirroring `validateSession()`, (3) a pure `agent-scopes.ts` helper, (4) a middleware branch that runs before the cookie check. The cookie path is untouched (zero regression).

**Tech Stack:** Next.js 15 middleware (Edge), TypeScript, Python FastMCP (Starlette routes), pytest, vitest/jest (agent tests).

**Issue:** #107 · **Release:** v0.17.108 (Scenario 1, code-only)

---

### Task 1: MCP `verify_key` endpoint

**Files:**
- Modify: `bundles/spark/mcp/src/api/ui_auth.py` (add a route in `register_ui_auth_routes`)
- Test: `bundles/spark/mcp/tests/test_ui_auth_verify_key.py`

- [ ] **Step 1: Write the failing test**

```python
# bundles/spark/mcp/tests/test_ui_auth_verify_key.py
"""verify_key endpoint — validates a phantom_ak_* key, returns scopes."""
from __future__ import annotations
import json
from starlette.applications import Starlette
from starlette.testclient import TestClient
from api.ui_auth import register_ui_auth_routes
from usecase.api_keys import SqliteApiKeyStore


class _FakeMcp:
    def __init__(self):
        self.routes = {}
    def custom_route(self, path, methods=None, include_in_schema=True):
        def deco(fn):
            for m in (methods or ["GET"]):
                self.routes[(path, m)] = fn
            return fn
        return deco


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "test-mcp-token")
    # Point the singleton store at a temp DB.
    store = SqliteApiKeyStore(data_root=tmp_path)
    import usecase.api_keys as ak
    monkeypatch.setattr(ak, "_STORE", store, raising=False)
    monkeypatch.setattr(ak, "api_key_store", lambda: store)
    mcp = _FakeMcp()
    register_ui_auth_routes(mcp)
    app = Starlette()
    for (path, method), fn in mcp.routes.items():
        app.add_route(path, fn, methods=[method])
    return TestClient(app), store


def test_verify_key_valid(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    created = store.create(label="t", scopes=["agent:*"], actor="ayman")
    r = client.post("/api/v1/ui/auth/verify_key",
                    json={"api_key": created.plaintext},
                    headers={"Authorization": "Bearer test-mcp-token"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert body["scopes"] == ["agent:*"]
    assert body["key_id"] == created.record.id


def test_verify_key_unknown(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/api/v1/ui/auth/verify_key",
                    json={"api_key": "phantom_ak_deadbeef_" + "0" * 32},
                    headers={"Authorization": "Bearer test-mcp-token"})
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_verify_key_requires_mcp_token(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/api/v1/ui/auth/verify_key", json={"api_key": "x"})
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/test_ui_auth_verify_key.py -x`
Expected: FAIL (route not registered → 404, or import error).

> NOTE before Step 3: confirm the store API. Run `grep -nE "def create|def verify|def api_key_store|_STORE" bundles/spark/mcp/src/usecase/api_keys.py`. The test assumes `store.create(label=, scopes=, actor=) -> CreatedApiKey(record, plaintext)` and `store.verify(token) -> ApiKey | None`. If `create`'s kwarg is `created_by=` not `actor=`, adjust the test + endpoint to match the real signature (do NOT invent — read it).

- [ ] **Step 3: Add the endpoint**

In `bundles/spark/mcp/src/api/ui_auth.py`, inside `register_ui_auth_routes(mcp)`, add (mirror the existing `/session` route; import `require_bearer` + `api_key_store` at top of file if not present):

```python
    @mcp.custom_route("/api/v1/ui/auth/verify_key", methods=["POST"], include_in_schema=False)
    async def verify_key(request: Request) -> JSONResponse:
        # MCP_TOKEN-gated internal loopback (the Next.js middleware calls this).
        from api.auth import require_bearer
        err = require_bearer(request)
        if err is not None:
            return err
        try:
            body = await request.json()
        except Exception:
            body = {}
        api_key = (body or {}).get("api_key")
        if not isinstance(api_key, str) or not api_key:
            return JSONResponse({"valid": False, "reason": "missing_api_key"}, status_code=200)
        from usecase.api_keys import api_key_store
        store = api_key_store()
        if store is None:
            return JSONResponse({"valid": False, "reason": "store_unavailable"}, status_code=200)
        row = store.verify(api_key)
        if row is None:
            return JSONResponse({"valid": False, "reason": "unknown_or_revoked"}, status_code=200)
        return JSONResponse({
            "valid": True,
            "scopes": row.scopes,
            "key_id": row.id,
            "label": row.label,
        }, status_code=200)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/test_ui_auth_verify_key.py -x`
Expected: 3 passed. (If the `require_bearer` import path differs, fix to the real module path.)

- [ ] **Step 5: Commit**

```bash
git add bundles/spark/mcp/src/api/ui_auth.py bundles/spark/mcp/tests/test_ui_auth_verify_key.py
git commit -m "feat(mcp): verify_key endpoint for agent API-key auth (Refs #107)"
```

---

### Task 2: `agent-scopes.ts` pure helper

**Files:**
- Create: `mcp/agent/lib/agent-scopes.ts`
- Test: `mcp/agent/lib/agent-scopes.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// mcp/agent/lib/agent-scopes.test.ts
import { describe, it, expect } from "vitest";
import { requiredScope, isCredentialRoute, scopeSatisfied } from "./agent-scopes";

describe("requiredScope", () => {
  it("GET → agent:read", () => expect(requiredScope("/api/agent/jobs", "GET")).toBe("agent:read"));
  it("POST → agent:write", () => expect(requiredScope("/api/agent/jobs", "POST")).toBe("agent:write"));
  it("DELETE → agent:write", () => expect(requiredScope("/api/agent/jobs/1", "DELETE")).toBe("agent:write"));
  it("/api/chat always write", () => expect(requiredScope("/api/chat", "GET")).toBe("agent:write"));
});

describe("isCredentialRoute", () => {
  it("providers", () => expect(isCredentialRoute("/api/agent/providers/config")).toBe(true));
  it("instances", () => expect(isCredentialRoute("/api/agent/instances/abc/test")).toBe(true));
  it("api-keys", () => expect(isCredentialRoute("/api/agent/api-keys")).toBe(true));
  it("non-credential", () => expect(isCredentialRoute("/api/agent/jobs")).toBe(false));
  it("chat", () => expect(isCredentialRoute("/api/chat")).toBe(false));
});

describe("scopeSatisfied", () => {
  it("wildcard grants read", () => expect(scopeSatisfied(["agent:*"], "agent:read")).toBe(true));
  it("wildcard grants write", () => expect(scopeSatisfied(["agent:*"], "agent:write")).toBe(true));
  it("exact match", () => expect(scopeSatisfied(["agent:read"], "agent:read")).toBe(true));
  it("read does not grant write", () => expect(scopeSatisfied(["agent:read"], "agent:write")).toBe(false));
  it("legacy * grants all", () => expect(scopeSatisfied(["*"], "agent:write")).toBe(true));
  it("empty denies", () => expect(scopeSatisfied([], "agent:read")).toBe(false));
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mcp/agent && npx vitest run lib/agent-scopes.test.ts`
Expected: FAIL (module not found). (If the repo uses jest not vitest, run `ls mcp/agent/*.config.* mcp/agent/vitest.config.*` and `grep '"test"' mcp/agent/package.json` to confirm the runner; adjust the import + command.)

- [ ] **Step 3: Implement the helper**

```typescript
// mcp/agent/lib/agent-scopes.ts
/**
 * Pure scope-mapping helpers for API-key auth on the agent surface.
 * No I/O — unit-tested in isolation. Consumed by middleware.ts.
 *
 * Coarse model: GET → agent:read; mutations + /api/chat → agent:write;
 * agent:* (and legacy *) grant both. Credential-management routes are
 * NEVER reachable by an API key regardless of scope (security invariant).
 */

export type AgentScope = "agent:read" | "agent:write";

/** Route prefixes that manage credentials — API keys are denied here even
 *  with agent:*. Keep in sync with the MCP credential guardrail. */
const CREDENTIAL_PREFIXES = [
  "/api/agent/providers",
  "/api/agent/instances",
  "/api/agent/api-keys",
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mcp/agent && npx vitest run lib/agent-scopes.test.ts`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add mcp/agent/lib/agent-scopes.ts mcp/agent/lib/agent-scopes.test.ts
git commit -m "feat(agent): pure scope/credential-route helper for API-key auth (Refs #107)"
```

---

### Task 3: `validateApiKey()` in auth-store.ts

**Files:**
- Modify: `mcp/agent/lib/auth-store.ts` (add types + cache + function, mirroring `validateSession`)

- [ ] **Step 1: Add types + cache + function**

Add near the `SessionValid`/`SessionInvalid` types:

```typescript
export interface ApiKeyValid {
  valid: true;
  scopes: string[];
  keyId: string;
  label: string;
}
export interface ApiKeyInvalid {
  valid: false;
  reason: "missing" | "unknown_or_revoked" | "mcp_unreachable";
}
export type ApiKeyResult = ApiKeyValid | ApiKeyInvalid;
```

Add near `sessionCache`:

```typescript
interface ApiKeyCacheEntry { result: ApiKeyValid; expiresAt: number; }
const apiKeyCache = new Map<string, ApiKeyCacheEntry>();
export function bustApiKeyCache(token: string): void { apiKeyCache.delete(token); }
```

Add the public function (mirror `validateSession`; reuse `mcpPost` + `SESSION_CACHE_TTL_MS`):

```typescript
/** Validate a phantom_ak_* API key against the MCP store. 30s positive
 *  cache (negative results are NOT cached so revocation surfaces fast). */
export async function validateApiKey(token: string): Promise<ApiKeyResult> {
  if (!token) return { valid: false, reason: "missing" };
  const now = Date.now();
  const cached = apiKeyCache.get(token);
  if (cached && cached.expiresAt > now) return cached.result;

  const resp = await mcpPost("/api/v1/ui/auth/verify_key", { api_key: token });
  if (!resp.ok) {
    switch (resp.reason) {
      case "mcp_unreachable":
      case "transport_error":
      case "http_error":
        return { valid: false, reason: "mcp_unreachable" };
    }
  }
  if (!resp.data.valid) return { valid: false, reason: "unknown_or_revoked" };

  const result: ApiKeyValid = {
    valid: true,
    scopes: Array.isArray(resp.data.scopes) ? (resp.data.scopes as string[]) : [],
    keyId: typeof resp.data.key_id === "string" ? resp.data.key_id : "",
    label: typeof resp.data.label === "string" ? resp.data.label : "",
  };
  apiKeyCache.set(token, { result, expiresAt: now + SESSION_CACHE_TTL_MS });
  return result;
}
```

- [ ] **Step 2: Type-check**

Run: `cd mcp/agent && npx tsc --noEmit`
Expected: no errors. (If `SESSION_CACHE_TTL_MS` isn't in scope, grep for its definition and reuse it; do not redefine.)

- [ ] **Step 3: Commit**

```bash
git add mcp/agent/lib/auth-store.ts
git commit -m "feat(agent): validateApiKey() mirrors validateSession (Refs #107)"
```

---

### Task 4: Middleware API-key branch

**Files:**
- Modify: `mcp/agent/middleware.ts`
- Test: `mcp/agent/middleware.test.ts`

- [ ] **Step 1: Write the failing test** (mock auth-store + agent-scopes)

```typescript
// mcp/agent/middleware.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth-store", () => ({
  validateSession: vi.fn(),
  validateApiKey: vi.fn(),
}));

import { middleware } from "./middleware";
import { validateSession, validateApiKey } from "@/lib/auth-store";

function req(path: string, { method = "GET", apiKey = "", cookie = "" } = {}) {
  const headers = new Headers();
  if (apiKey) headers.set("authorization", `Bearer ${apiKey}`);
  const cookies = new Map<string, { value: string }>();
  if (cookie) cookies.set("phantom_session", { value: cookie });
  return {
    nextUrl: { pathname: path },
    method,
    headers,
    cookies: { get: (n: string) => cookies.get(n) },
  } as any;
}

beforeEach(() => vi.clearAllMocks());

describe("middleware API-key branch", () => {
  it("valid agent:* key on /api/chat → passes", async () => {
    (validateApiKey as any).mockResolvedValue({ valid: true, scopes: ["agent:*"], keyId: "k", label: "l" });
    const res = await middleware(req("/api/chat", { method: "POST", apiKey: "phantom_ak_x_y" }));
    expect(res.status).not.toBe(401);
    expect(res.status).not.toBe(403);
  });
  it("agent:read key on POST mutation → 403", async () => {
    (validateApiKey as any).mockResolvedValue({ valid: true, scopes: ["agent:read"], keyId: "k", label: "l" });
    const res = await middleware(req("/api/agent/jobs", { method: "POST", apiKey: "phantom_ak_x_y" }));
    expect(res.status).toBe(403);
  });
  it("agent:* key on credential route → 403", async () => {
    (validateApiKey as any).mockResolvedValue({ valid: true, scopes: ["agent:*"], keyId: "k", label: "l" });
    const res = await middleware(req("/api/agent/providers/config", { method: "GET", apiKey: "phantom_ak_x_y" }));
    expect(res.status).toBe(403);
  });
  it("invalid key → 401", async () => {
    (validateApiKey as any).mockResolvedValue({ valid: false, reason: "unknown_or_revoked" });
    const res = await middleware(req("/api/chat", { method: "POST", apiKey: "phantom_ak_bad" }));
    expect(res.status).toBe(401);
  });
  it("no key + valid cookie → passes (regression guard)", async () => {
    (validateSession as any).mockResolvedValue({ valid: true, username: "admin", expiresAtMs: 1, credentialsChanged: false });
    const res = await middleware(req("/api/chat", { method: "POST", cookie: "good" }));
    expect(res.status).not.toBe(401);
    expect(validateApiKey).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mcp/agent && npx vitest run middleware.test.ts`
Expected: FAIL (no API-key branch yet → 401 for key cases).

- [ ] **Step 3: Add the branch**

In `mcp/agent/middleware.ts`, add imports + the branch between the `EXEMPT_PATHS` check and the cookie check:

```typescript
import { validateSession, validateApiKey } from "@/lib/auth-store";
import { requiredScope, isCredentialRoute, scopeSatisfied } from "@/lib/agent-scopes";
```

```typescript
  // API-key bearer path (checked before the cookie). Absence → fall through
  // to the existing session-cookie check (human UI auth, unchanged).
  const authz = request.headers.get("authorization") ?? "";
  if (authz.toLowerCase().startsWith("bearer phantom_ak_")) {
    const apiKey = authz.slice("bearer ".length).trim();
    const result = await validateApiKey(apiKey);
    if (!result.valid) {
      return NextResponse.json(
        { error: "unauthenticated", code: result.reason },
        { status: 401 },
      );
    }
    if (isCredentialRoute(pathname)) {
      return NextResponse.json(
        { error: "forbidden", code: "api_key_credential_route_forbidden" },
        { status: 403 },
      );
    }
    const needed = requiredScope(pathname, request.method);
    if (!scopeSatisfied(result.scopes, needed)) {
      return NextResponse.json(
        { error: "forbidden", code: "insufficient_scope", required: needed },
        { status: 403 },
      );
    }
    return NextResponse.next();
  }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mcp/agent && npx vitest run middleware.test.ts`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add mcp/agent/middleware.ts mcp/agent/middleware.test.ts
git commit -m "feat(agent): middleware accepts API-key bearer with coarse scopes (Refs #107)"
```

---

### Task 5: UI mint-form scopes

**Files:**
- Modify: `mcp/agent/app/api-keys/page.tsx` (scope picker)

- [ ] **Step 1: Read the current scope input**

Run: `grep -nE "scope|Scope|checkbox|option|audit:read" mcp/agent/app/api-keys/page.tsx | head`
Identify how scopes are offered (a fixed list constant, or free text).

- [ ] **Step 2: Add the agent scopes**

If a scope-options constant exists, add `agent:read`, `agent:write`, `agent:*` with labels ("Agent API — read", "Agent API — read+write", "Agent API — full (non-credential)"). If it's free text, add helper text listing the three. Keep the Material-3 token styling (no hex literals). Show this is the scope that authenticates `/api/chat` + `/api/agent/*`.

- [ ] **Step 3: Verify build**

Run: `cd mcp/agent && npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add mcp/agent/app/api-keys/page.tsx
git commit -m "feat(agent): offer agent:read/write/* scopes in API-key mint form (Refs #107)"
```

---

### Task 6: Docs

**Files:**
- Modify: `mcp/agent/app/help/architecture/page.tsx` (`#authentication`)
- Modify: `mcp/agent/app/help/user/page.tsx`
- Modify: `mcp/agent/lib/journeys.ts`
- Modify: `CHANGELOG.md`, `mcp/agent/lib/release-notes.ts`

- [ ] **Step 1: Architecture page** — in `#authentication`, document the API-key bearer path: middleware checks `Authorization: Bearer phantom_ak_*` before the cookie → MCP `verify_key` (loopback, MCP_TOKEN, 30s cache) → coarse scope (GET=read, mutations+chat=write, `agent:*`=both) → credential routes (providers/instances/api-keys) denied even with `agent:*`. Add the inter-service wire (`middleware.ts → MCP /api/v1/ui/auth/verify_key`).

- [ ] **Step 2: User guide** — "Authenticate with an API key": mint in /api-keys with `agent:write` (or `agent:*`), send `Authorization: Bearer phantom_ak_...` to `/api/chat` / `/api/agent/*`. Tag with v0.17.108.

- [ ] **Step 3: Journey** — add to `journeys.ts`: "Mint an API key → call the agent API with it".

- [ ] **Step 4: Release notes** — CHANGELOG.md + release-notes.ts (newest first) v0.17.108 entry: "API-key auth for the agent API surface; coarse agent:read/write/* scopes; credential routes stay session-only."

- [ ] **Step 5: Commit**

```bash
git add mcp/agent/app/help/architecture/page.tsx mcp/agent/app/help/user/page.tsx mcp/agent/lib/journeys.ts CHANGELOG.md mcp/agent/lib/release-notes.ts
git commit -m "docs(agent): API-key auth — architecture/user/journey/release-notes (v0.17.108, Refs #107)"
```

---

### Task 7: Pre-deploy gate + ship + verify

- [ ] **Step 1: Full pre-deploy gate**

```bash
cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build
cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x
```
Expected: all green. (Includes the new verify_key + agent-scopes + middleware tests if the agent runner is wired into CI; if vitest isn't in CI, the agent tests still run locally here.)

- [ ] **Step 2: Push + watch the build chain**

```bash
git push origin main
```
Watch Build agent + Build dev installer → auto-deploy. Verify `PHANTOM_VERSION` on phantom-vm = HEAD.

- [ ] **Step 3: Deploy verify (E2E)** — on phantom-vm, mint a key via the MCP_TOKEN REST, then curl `/api/chat` with it:

```bash
# inside phantom_agent: mint agent:* key (MCP_TOKEN-gated), capture plaintext
# then: curl -sk -H "Authorization: Bearer $KEY" https://localhost:3000/api/chat -d '{"messages":[{"role":"user","content":"ping"}]}' → 200 stream
# and: curl a credential route with the same key → 403
```
Expected: chat 200 (real turn), credential route 403, no-auth 401.

- [ ] **Step 4: Apply `status:ready-for-testing` on #107.**

---

## Self-Review

**Spec coverage:** verify_key (Task 1) ✓; validateApiKey (Task 3) ✓; middleware branch + coarse scopes + credential exclusion (Tasks 2,4) ✓; UI scopes (Task 5) ✓; docs (Task 6) ✓; ship/verify (Task 7) ✓. All spec sections mapped.

**Placeholder scan:** Task 5 is intentionally adaptive (the page's scope-input shape is unknown until read) — Step 1 reads it first, so it's grounded, not a placeholder. Task 1 has a NOTE to confirm `store.create` kwargs before implementing — grounding, not a gap.

**Type consistency:** `validateApiKey → ApiKeyResult {valid, scopes, keyId, label}` used consistently in middleware. `requiredScope`/`isCredentialRoute`/`scopeSatisfied` signatures match between `agent-scopes.ts` and `middleware.ts` + their tests. `verify_key` returns `{valid, scopes, key_id, label}` (snake) consumed by `validateApiKey` (maps to camel). Consistent.

## Post-feature (campaign continuation, separate execution)

After v0.17.108 deploys: mint an `agent:*` key → build the Stage-2 driver (`scripts/maintainer/stage2_chat_drive.py`: POST `/api/chat` per vendor with the key, capture tool calls, verify XDM via the xsiam connector) → run all 22 → P6 report. Then investigate the azure_waf XDM-0 residual.
