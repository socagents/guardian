# Plan — API / REST reference cleanup (`lib/api-catalog.ts` → `/help/api`)

**Goal:** The REST reference lists the **complete current** endpoint surface, every description in present tense, **no version markers / process notes / "Auto-added" placeholders**. The `/help/api` page renders from `lib/api-catalog.ts`, so all edits are in the catalog.

**Scope:** Audit found **19 version markers**, **5 stub descriptions**, and **4 implemented-but-undocumented investigation endpoints**. This is the one surface with a real *completeness gap*, not just cleanup.

## Tasks

1. **Delete internal section-header comments** (5): the `// ─── v0.X.X overnight quality pass …` divider comments — internal process notes, no customer value.

2. **Strip version markers from descriptions** (rewrite to present tense): `knowledge-tags` (drop `(v0.2.20). Read-only.`); `personality-get` (drop `(v0.1.23+)`); `personality-put` (drop `v0.1.23+:`); `operator-state-get` (drop "the v0.5.1 canonical home that replaced browser localStorage"); `plugins-list` (drop "Round-15 / Phase X"); `bench-runs` `limit` param (drop the pre-/post-v0.6.10 conditional, state current behavior); `version` endpoint (drop `v0.3.0+`); `auth-session-get` (drop "The pre-v0.4.0 setupRequired field was removed").

3. **Fix the `instances-update` 409 block**: determine if the 409 is reachable today; if not, remove it; if so, rewrite cleanly. Drop the "as of v0.2.29 / multi-active-instance / unreachable handler branch" archaeology.

4. **Replace the 5 observability stub descriptions** (`Auto-added v0.7.1. Full request/response schema is a follow-up…` on the 5 observability endpoints) with substantive 1–2 sentence descriptions of what each returns.

5. **Update the `version` response example**: hard-coded `"v0.2.36"` → a generic/current placeholder (or describe it as "the running stack version") so it can't go stale.

6. **ADD the 4 missing investigation endpoints** (implemented in `bundles/spark/mcp/src/api/investigation.py`; absent from the catalog — customers can't discover them). Add full `ApiEndpoint` entries to the INVESTIGATION array after `issues-by-id-events-post`:
   - `GET /api/agent/issues/{id}/report` — the generated report markdown (404 if not generated).
   - `GET /api/agent/cases/{id}/related` — typed cross-case links (related cases).
   - `GET /api/agent/issues/{id}/stix` — issue as a STIX 2.1 bundle (application/json).
   - `GET /api/agent/cases/{id}/stix` — case (campaign) as a STIX 2.1 bundle.
   Each with summary, present-tense description, `id` path param, 200/404/401 responses, read-only tags. (Optional stretch: also surface `incidents_by_technique` / `playbooks/{doc}/issues` pivots if they're operator-reachable via `/api/agent`.)

## Verification
- `grep -nE 'v[0-9]+\.[0-9]+\.[0-9]+|Auto-added|Round-1|Phase [0-9]|pre-v0' lib/api-catalog.ts` → 0 (except a deliberate generic example).
- `npm run build` parses the catalog; `/help/api` renders all endpoints incl. the 4 new ones with working try-it-out forms.
