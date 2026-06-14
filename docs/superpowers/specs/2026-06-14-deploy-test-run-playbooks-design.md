# Deploy + test-run playbooks — design (v0.2.26)

**Goal:** Close the Playbook Builder loop. From a drafted playbook, the operator (or the agent) can import it into the connected Cortex XSOAR tenant, run it on a disposable test incident, see the run outcome in Guardian, and have the test incident auto-closed.

**Status:** brainstormed + operator-approved (issue #40). Operator authorized full autonomous completion incl. release.

## Decisions (from brainstorming)

- **Loop depth:** import → create disposable test incident → run → show result → close incident.
- **Trigger:** operator button on `/playbooks/build` **and** agent-callable (approval-gated, like every connector write).
- **Test-incident cleanup:** auto-close when done, tagged `[Guardian test]` (not deleted — XSOAR incidents are audit records; the prefix makes them filterable).
- **Spiked first** against the live tenant, then **checked docs**.

## The platform constraint (spike + docs finding)

Auto-importing a playbook is **generation-dependent**:

| Tenant | Import path | Status |
|---|---|---|
| XSOAR 6 (on-prem) | `POST /playbook/import` (multipart YAML) | Works directly. |
| Cortex 8 + Core REST API integration | `!core-api-multipart uri=/playbook/import` (war room) | Works (integration required). |
| Cortex 8 **without** Core REST API (our live tenant) | none | **HTTP 405** on the public gateway; no public JSON `/playbook/save`. |

The **test-run half** (`create_incident` + `run_playbook` + `get_war_room`) works on Cortex 8 — proven. Only *import* is blocked on a plain Cortex 8 tenant.

## Design — generation-aware

The feature adapts to what the tenant supports; the test-run automation is constant.

### 1. Connector tool `xsoar_import_playbook(playbook_yaml, filename?)` (built in the spike)
- Direct `POST /playbook/import` multipart via `XSOARFetcher.post_multipart()`. Correct for XSOAR 6 and for Cortex 8 + Core REST API.
- **Refinement:** when the tenant returns a 405 / redirect (Cortex 8 public gateway can't reach the internal route), return a structured, recognizable envelope — `{ok:false, import_unavailable:true, reason, hint}` — instead of a raw HTTP error, so the skill + UI branch cleanly into the guided-import fallback.
- Catalog/connector-action side of the credential boundary (uses the instance API key), agent-callable, approval-gated.

### 2. Skill `build_xsoar_playbook.md` — deploy + test-run lifecycle
A new section the agent follows when asked to deploy/test-run a draft:
1. `playbook_validate` the YAML (block on structural errors).
2. `xsoar_import_playbook`.
   - On success → continue.
   - On `import_unavailable` → tell the operator to import the downloaded YAML via **Playbooks → Import** (or enable the Core REST API integration for one-click), then continue to test-run once they confirm the playbook name exists.
3. `xsoar_create_incident` named `[Guardian test] <playbook> <ts>`, `create_investigation: true`.
4. `xsoar_run_playbook(incident_id, playbook_name)`.
5. Poll `xsoar_get_war_room(incident_id)` briefly for task outcomes.
6. `xsoar_close_incident(incident_id)` (tagged).
7. Report: imported id, test-incident id, run status, task outcomes, cleanup confirmation.

### 3. UI — `/playbooks/build`
- A third button **"Deploy + test-run"** next to Validate/Download, behind an explicit confirm ("this imports + runs in your XSOAR tenant").
- Sends a templated deploy message to `/api/chat` (same mechanism as Build) and streams the agent's import → run → result summary into a result panel.
- The graceful Cortex-8 fallback (guided manual import) renders in the same panel; Download stays available.

### 4. Docs
Architecture `#playbook-builder` deploy note (incl. the generation matrix), user guide, `deploy-playbook` journey, CHANGELOG + release-notes (v0.2.26), connector docs, the skill.

## What's verifiable on the live tenant now
- Automated test-run loop (create `[Guardian test]` incident → run → poll → close).
- The graceful Cortex-8 `import_unavailable` fallback (clear guidance, Download).
- Direct one-click import is verifiable only on XSOAR 6 / a Core-REST-API-enabled Cortex 8 tenant → documented as a **dev-cycle gap**, not claimed tested.

## Acceptance
- From a drafted playbook on `/playbooks/build`, **Deploy + test-run** either (a) one-click imports + test-runs + closes (v6 / core-api), or (b) on plain Cortex 8 returns clear import guidance + runs the automated test-run once the playbook exists — verified live.
- The agent can do the same conversationally, approval-gated.
- `import_unavailable` is a clean structured signal, not a raw 405.

## Out of scope
- Installing/enabling the Core REST API integration automatically.
- Auto-deleting test incidents (close only).
- A bespoke v8 core-api-multipart import implementation (documented as the one-click path when the integration is present; not built/tested this arc unless the tenant gets it).
