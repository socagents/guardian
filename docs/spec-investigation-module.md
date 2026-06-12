# Investigation Module — Issues & Cases — Design Spec

- **Date:** 2026-06-12
- **Status:** Approved-to-build (operator pre-authorized autonomous decisions: *"go with the recommendations, don't wait for me"*). Design decisions below are mine, documented for operator review.
- **Scope:** a new first-class **Investigation** domain in Guardian — local **Issues** + **Cases** that the agent (and operator) create during investigations, with a rich issue UI. Distinct from upstream XSOAR incidents: an Issue is *Guardian's own* record of investigating something.

---

## 1. Problem / intent

When Guardian investigates — whether prompted by the operator or by an autonomous job, and whether the subject is a fetched XSOAR incident or a standalone finding — there's nowhere to **record the investigation locally**. The operator wants Guardian to:

1. **Open a local Issue** for an investigation (agent-created via an MCP tool, or operator-created in the UI).
2. **Capture the investigation** on that issue: what's being investigated, the conversation/activity, recommendations, conclusions, summary, next steps, and a timeline of what Guardian did.
3. **Group related Issues into Cases** (agent- or operator-decided) when they're similar/related.
4. **Present all of this in the UI** under a new **Investigation** area (sidebar) with **Issues** and **Cases** sub-pages + rich detail layouts.

This is the substrate the autonomous investigation loop writes to: seed XSOAR incidents → Guardian investigates each → opens a local Issue → records findings → groups into Cases.

## 2. Domain model

Three SQLite tables in a new **`investigations.db`** store (the catalog domain per the state taxonomy — not credentials, not operator-personal; mutable investigation metadata the agent reads + the UI displays).

**`issues`**
| col | type | notes |
|---|---|---|
| `id` | TEXT PK | uuid4 |
| `title` | TEXT | short title |
| `status` | TEXT | `open` / `investigating` / `resolved` / `closed` |
| `severity` | TEXT | `low` / `medium` / `high` / `critical` |
| `kind` | TEXT | incident type: `phishing` / `lateral_movement` / `access_violation` / `malware` / `other` (free-form allowed) |
| `origin` | TEXT | `agent` / `operator` (who created it) |
| `source_ref` | TEXT NULL | upstream XSOAR incident id, if fetched from the store |
| `case_id` | TEXT NULL FK→cases.id | the case it's grouped under (one-to-many; nullable) |
| `summary` | TEXT NULL | the investigation summary (markdown) |
| `scope` | TEXT NULL | what's being investigated (markdown) |
| `recommendations` | TEXT NULL | markdown |
| `conclusions` | TEXT NULL | markdown |
| `next_steps` | TEXT NULL | markdown |
| `created_at` / `updated_at` | TEXT | ISO-8601 UTC |

**`cases`** — `id` (uuid4 PK), `title`, `description` NULL, `status` (`open`/`closed`), `created_at`, `updated_at`. A case groups many issues.

**`issue_events`** — the timeline of what Guardian (or the operator) did on an issue: `id` (uuid4 PK), `issue_id` FK→issues.id ON DELETE CASCADE, `ts`, `type` (`action` / `finding` / `note` / `conversation`), `content` (text). Appended over the investigation; renders as the issue's activity feed (captures "conversation data" + "what has been done by Guardian").

**Relationship decision (one-to-many, not many-to-many):** an Issue belongs to **at most one** Case (`issues.case_id`). Simpler for the agent + UI; matches the "group these issues under a case" mental model. Many-to-many is YAGNI for v1.

## 3. Architecture (6 layers, following existing conventions)

1. **Store** — `bundles/spark/mcp/src/usecase/investigation_store.py`: `InvestigationStore` (threading.Lock + sqlite3 WAL, frozen DTOs `Issue`/`Case`/`IssueEvent`), mirrors `instance_store.py`. CRUD for issues, cases, events, + `add_issue_to_case`/`list_issues(case_id=…)`. Singleton accessor; instantiated + wired at MCP boot in `main.py`.
2. **REST API** — `bundles/spark/mcp/src/api/issues.py` + `api/cases.py`: FastAPI routers (MCP_TOKEN bearer) — `GET/POST /api/v1/issues`, `GET/PATCH/DELETE /api/v1/issues/{id}`, `POST /api/v1/issues/{id}/events`, `GET/POST /api/v1/cases`, `GET/PATCH/DELETE /api/v1/cases/{id}`, `POST /api/v1/cases/{id}/issues`. Registered in `main.py`.
3. **MCP tools (agent-facing)** — registered as builtins (the catalog side of the credential boundary — issues/cases are NOT secrets, so the agent CAN create + mutate them): `issue_create`, `issue_update`, `issue_add_event`, `issue_get`, `issues_list`, `case_create`, `case_add_issue`, `cases_list`, `case_get`. The agent calls these during an investigation. **Credential-guardrail note:** these touch ONLY investigation metadata — no SecretStore read/write — so they pass the guardrail and are `mcp.tool()`-registered.
4. **Agent proxies (Next.js)** — `mcp/agent/app/api/agent/issues/route.ts` (+ `[id]`, `[id]/events`), `app/api/agent/cases/route.ts` (+ `[id]`, `[id]/issues`) via `resolveMcp()`. Operator-session OR API-key gated (NOT credential routes — both can read/write).
5. **UI** — sidebar **Investigation** group with **Issues** + **Cases** entries:
   - `app/investigation/issues/page.tsx` — issue list (status/severity/kind/origin/case/updated; filters; "New Issue").
   - `app/investigation/issues/[id]/page.tsx` — **rich issue layout**: header (title/status/severity/kind/origin/source_ref/case), the structured investigation (Summary · Scope · Recommendations · Conclusions · Next steps — markdown, operator-editable), and the **activity timeline** (issue_events). Status/severity controls; "assign to case".
   - `app/investigation/cases/page.tsx` — case list (+ issue counts; "New Case").
   - `app/investigation/cases/[id]/page.tsx` — case detail (metadata + grouped issues).
   - Sidebar entries added in `components/sidebar.tsx` (v0.5.49 discipline). Material-3 tokens, AuthGate, theme-aware.
6. **Skill + system prompt** — extend the XSOAR case-investigation skill + `lib/system-prompt.ts` so the agent, during an investigation: opens an Issue (`issue_create`), logs actions/findings (`issue_add_event`), fills the structured fields (`issue_update`), and groups related Issues into a Case (`case_create` / `case_add_issue`). This is what drives the autonomous loop.

## 4. Data flow

```
Operator: "investigate XSOAR incident 1234"
  → agent: xsoar_get_incident(1234) + xsoar_get_war_room(1234)
  → agent: issue_create(title, kind, severity, source_ref="1234", scope=…)   [local Issue opened]
  → agent investigates (enrich_indicator, run_command, …) → issue_add_event(…) per finding
  → agent: issue_update(summary, recommendations, conclusions, next_steps, status="resolved")
  → (if related to a prior issue) case_create / case_add_issue
UI: /investigation/issues → the new issue → rich layout shows everything Guardian did.
```

## 5. Error handling
- Store: missing issue/case → 404 envelope; FK violations guarded; WAL + lock for concurrent agent writes.
- MCP tools: return `{ok, …}` envelopes (agent branches on ok). Unknown id → `{ok:false, error}`.
- UI: empty states (no issues/cases yet); optimistic + refetch on mutation; markdown rendered safely.

## 6. Testing
- **Store (pytest):** CRUD round-trips, case grouping, event append, cascade delete, status/severity filters.
- **MCP tools (pytest):** each tool create→get→update→list round-trip; case grouping; envelope shapes; guardrail (tools registered + reachable).
- **API (pytest):** route shapes + MCP_TOKEN auth.
- **Agent (tsc/lint/build):** proxy routes + pages compile under strict route validation; sidebar grep test passes.
- **Live smoke (deployed):** operator-create an issue in the UI; agent-create via `^issue_create` direct-tool-call; the autonomous loop's end-to-end (incident → issue → case).

## 7. Docs (ship with the code)
- Architecture `#investigation` (the new store + tables + the 6-layer wiring + inter-service path).
- User guide `#investigation` (what Issues/Cases are, how the agent + operator create them, the layout).
- `lib/journeys.ts` — an `investigate-to-issue` journey (investigate → issue opened → grouped into case).
- CHANGELOG + release-notes.ts.
- New MCP tool docstrings (the agent picks tools by docstring).

## 8. Release shape
- **Scenario 1** (code-only; new `investigations.db` is created fresh on first boot; no installer change; existing volumes gain the new db file). Minor bump (next is **v0.1.3**), customers re-run the existing installer. The new store is additive — no migration of existing data.
- One capability arc, built in layers (store → API → MCP tools → proxies → UI → skill/docs). Tagged once at completion (operator approval). Built incrementally on `main` during the autonomous session; pushed at milestones.

## 9. Decisions captured (autonomous)
- New `investigations.db` store in the **catalog** domain (agent-readable/writable; not credentials).
- Issue↔Case **one-to-many** (issue.case_id nullable). Many-to-many deferred (YAGNI).
- Activity timeline as a separate `issue_events` table (clean appends) vs a JSON blob.
- Issue MCP tools are **agent-accessible** (catalog side of the guardrail) — this is the whole point (the agent opens issues during investigation).
- Sidebar: an **Investigation** group with **Issues** + **Cases** sibling entries (not a nested parent route) — matches the existing flat-group nav pattern.

## 10. Open items (resolve in the plan / build)
- Exact `issue_update` partial-update semantics (PATCH only provided fields).
- Whether `case_add_issue` moves an issue (sets case_id) vs copies — it **sets** `issues.case_id` (move).
- Markdown rendering component reuse in the issue layout (use the existing chat/markdown renderer if present).
