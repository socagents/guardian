# Investigation Module Implementation Plan

> **For agentic workers:** Executed inline (single session, full context) with TDD + local gate per layer. Steps use checkbox (`- [ ]`) tracking. Spec: `docs/spec-investigation-module.md`.

**Goal:** A new first-class Investigation domain — local Issues + Cases the agent and operator create during investigations, with a rich issue UI under a sidebar Investigation area.

**Architecture:** New `investigations.db` SQLite store in the embedded MCP (catalog domain) → REST API (`/api/v1/issues`, `/api/v1/cases`) → agent-facing MCP tools (issue/case CRUD — catalog side of the credential guardrail) → Next.js agent proxies → UI (Investigation group: Issues + Cases lists + rich detail layouts) → investigation skill + system-prompt wiring so the agent opens/updates issues + groups cases during investigations.

**Tech Stack:** Python (sqlite3 + FastAPI in the embedded MCP), FastMCP tool registration, Next.js 15 App Router + React 19 (Material-3 tokens), pytest + tsc/lint/build.

**Build order (layers — each gated locally before the next):** Store → API → MCP tools → Proxies → UI → Skill/Docs. Push at milestones (backend, UI, docs) — not every commit.

---

## Layer 1 — InvestigationStore (backend)

**Files:**
- Create: `bundles/spark/connectors/../../mcp/src/usecase/investigation_store.py` → actual: `bundles/spark/mcp/src/usecase/investigation_store.py`
- Test: `bundles/spark/mcp/tests/test_investigation_store.py`
- Modify: `bundles/spark/mcp/src/main.py` (instantiate + expose the store at boot, mirroring InstanceStore)

**Design (from spec §2):** frozen DTOs `Issue`, `Case`, `IssueEvent`; `InvestigationStore` with threading.Lock + sqlite3 WAL at `<DATA_ROOT>/investigations.db`. Tables `issues`, `cases`, `issue_events` (per spec §2).

**Methods:**
- Issues: `create_issue(title, kind, severity="medium", origin="agent", source_ref=None, scope=None, summary=None) -> Issue`; `get_issue(id)`; `list_issues(status=None, case_id=None) -> list[Issue]`; `update_issue(id, **fields) -> Issue|None` (partial: status/severity/summary/scope/recommendations/conclusions/next_steps/title/kind); `delete_issue(id)`.
- Cases: `create_case(title, description=None) -> Case`; `get_case(id)`; `list_cases() -> list[Case]` (+ issue_count); `update_case(id, **fields)`; `delete_case(id)`.
- Membership: `add_issue_to_case(issue_id, case_id) -> Issue|None` (sets issues.case_id); `remove_issue_from_case(issue_id)`.
- Events: `add_event(issue_id, type, content) -> IssueEvent`; `list_events(issue_id) -> list[IssueEvent]`.

**TDD:** Write `test_investigation_store.py` first — create→get→list round-trips for issues + cases; partial update; add_issue_to_case sets case_id + list_issues(case_id=) filters; add_event + list_events ordering; status/severity filters; delete cascades events. Run (fail → implement → pass).

- [ ] Write tests → run (fail) → implement store → run (pass) → wire in main.py → run full MCP suite.

---

## Layer 2 — REST API (issues + cases routes)

**Files:**
- Create: `bundles/spark/mcp/src/api/issues.py`, `bundles/spark/mcp/src/api/cases.py`
- Modify: `bundles/spark/mcp/src/main.py` (register the routers, MCP_TOKEN-gated like the other `/api/v1/*` routes)
- Test: `bundles/spark/mcp/tests/test_investigation_api.py`

**Routes (mirror api/instances.py shapes, MCP_TOKEN bearer):**
- `GET /api/v1/issues` (query: status?, case_id?) · `POST /api/v1/issues` (body→create) · `GET/PATCH/DELETE /api/v1/issues/{id}` · `POST /api/v1/issues/{id}/events` (body: type, content) · `GET /api/v1/issues/{id}/events`
- `GET /api/v1/cases` · `POST /api/v1/cases` · `GET/PATCH/DELETE /api/v1/cases/{id}` · `POST /api/v1/cases/{id}/issues` (body: issue_id → add) · `GET /api/v1/cases/{id}/issues` (list issues in case)

**TDD:** route tests via the FastAPI TestClient (auth + shapes), modeled on existing api tests.

- [ ] Write tests → fail → implement routes + register → pass → full MCP suite.

---

## Layer 3 — MCP agent-facing tools

**Files:**
- Modify: `bundles/spark/mcp/src/usecase/connector_loader.py` (register the new builtins) OR a new `usecase/builtin_components/investigation_tools.py` mirroring `self_mod_tools.py`
- Test: `bundles/spark/mcp/tests/test_investigation_tools.py`

**Tools (catalog side — agent-accessible; NO SecretStore access → passes the guardrail). Each returns `{ok, …}`:**
- `issue_create(title, kind, severity="medium", source_ref=None, scope=None, summary=None)` · `issue_update(issue_id, status=None, severity=None, summary=None, scope=None, recommendations=None, conclusions=None, next_steps=None, title=None)` · `issue_add_event(issue_id, type, content)` · `issue_get(issue_id)` · `issues_list(status=None, case_id=None)`
- `case_create(title, description=None)` · `case_add_issue(case_id, issue_id)` · `cases_list()` · `case_get(case_id)`

**Docstring discipline:** each tool's docstring tells the agent WHEN to call it (e.g. issue_create: "call at the start of investigating an incident; pass source_ref = the XSOAR incident id"). These drive the autonomous loop.

**TDD:** tool round-trip tests (create→get→update→list; case grouping; event append; envelope shapes; the tools are registered + callable).

- [ ] Write tests → fail → implement tools + register → pass → full MCP suite + confirm guardrail (no credential access).

---

## Layer 4 — Agent proxy routes (Next.js)

**Files:**
- Create: `mcp/agent/app/api/agent/issues/route.ts` (GET list, POST), `app/api/agent/issues/[id]/route.ts` (GET/PATCH/DELETE), `app/api/agent/issues/[id]/events/route.ts` (GET/POST), `app/api/agent/cases/route.ts`, `app/api/agent/cases/[id]/route.ts`, `app/api/agent/cases/[id]/issues/route.ts`
- Pattern: `resolveMcp()` forward to `/api/v1/issues|cases` (mirror `app/api/agent/instances/route.ts`). NOT credential routes — operator-session OR API-key both allowed.
- Add typed helpers in `mcp/agent/lib/api/` if the codebase has an api-client layer (mirror existing).

- [ ] Implement proxies → `npx tsc --noEmit` clean.

---

## Layer 5 — UI (Investigation area)

**Files:**
- Create: `mcp/agent/app/investigation/issues/page.tsx`, `app/investigation/issues/[id]/page.tsx`, `app/investigation/cases/page.tsx`, `app/investigation/cases/[id]/page.tsx`
- Modify: `mcp/agent/components/sidebar.tsx` (Investigation group → Issues + Cases entries; v0.5.49 discipline — every page gets a nav entry)
- Reuse: the chat/markdown renderer for the rich text fields; Material-3 semantic tokens (no hex; `data-theme` aware); AuthGate wrapping per existing pages.

**Issues list:** table/cards — title, status badge, severity badge, kind, origin, case link, updated. Filters (status/kind). "New Issue" modal (title, kind, severity).

**Issue detail (the rich layout, spec §3.5):** header (title, status + severity controls, kind, origin, source_ref link, case assignment); structured investigation sections (Summary · Scope · Recommendations · Conclusions · Next steps — markdown, operator-editable inline); activity timeline (issue_events, newest/oldest, typed icons). "Assign to case" + status controls call the proxies.

**Cases list:** title, status, issue count, updated. "New Case" modal.

**Case detail:** case metadata + the grouped issues (links to issue detail).

- [ ] Implement pages + sidebar → `tsc && lint && build` clean → sidebar grep test passes.

---

## Layer 6 — Skill + system prompt + docs

**Files:**
- Modify: the XSOAR case-investigation skill (the agent learns to: open an Issue via `issue_create` at the start of an investigation; log findings via `issue_add_event`; fill `issue_update` fields; group related issues via `case_create`/`case_add_issue`).
- Modify: `mcp/agent/lib/system-prompt.ts` (reference the investigation tools + the open-an-issue behavior).
- Docs: `app/help/architecture/page.tsx` (`#investigation` — store, tables, 6-layer wiring, inter-service path), `app/help/user/page.tsx` (`#investigation` — what Issues/Cases are, the layout, how agent + operator create them), `lib/journeys.ts` (`investigate-to-issue` journey + an `investigation` JourneyComponent + COMPONENT_META), `CHANGELOG.md` + `lib/release-notes.ts` (v0.1.3 entry).

- [ ] Implement → full gate (tsc/lint/build + MCP pytest) → docs render.

---

## Verification (before the operator's review)
- Full pre-deploy gate: `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build` + `cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x`.
- Push milestones → auto-deploy → live smoke: operator-create an issue (UI), agent-create via `^issue_create` direct tool call, the investigation-loop end-to-end (incident → issue → case rendered in the UI).

## Self-review (against spec)
- Spec §2 model → Layer 1. §3 layers → Layers 1-6. §4 data flow → exercised by the loop + Layer 6 skill. §6 testing → per-layer TDD + live smoke. §7 docs → Layer 6. All covered.
- Signature consistency: store methods ↔ API routes ↔ MCP tools ↔ proxy routes all use {issue_id, case_id, status, severity, kind, origin, source_ref, summary, scope, recommendations, conclusions, next_steps, type, content} consistently.
