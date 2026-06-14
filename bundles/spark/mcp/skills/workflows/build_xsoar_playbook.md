---
name: build_xsoar_playbook
displayName: Build a Cortex XSOAR playbook from examples
category: workflows
description: '**LOAD-FIRST WHEN THE OPERATOR ASKS TO BUILD / CREATE / DRAFT / GENERATE / SCAFFOLD a Cortex XSOAR (SOAR) PLAYBOOK.** Whenever the request is to author a new automation/response playbook (e.g. "build a phishing-triage playbook", "draft a CrowdStrike host-isolation playbook", "generate a playbook for X"), call `skills_read({file_path: "workflows/build_xsoar_playbook.md"})` IMMEDIATELY as your first tool call. The skill body is the retrieval-augmented authoring lifecycle: GROUND in real examples from the `soar-playbooks` KB via `knowledge_search` (study their `raw_yaml` task graph), DRAFT a new valid playbook YAML following those patterns, VALIDATE it with `playbook_validate`, then PRESENT it as a reviewable draft with the examples cited. This is for AUTHORING a new playbook — distinct from `xsoar_run_playbook` (run an existing one) and `xsoar_case_investigation` (investigate a case). ALSO load this skill when the operator asks to DEPLOY / IMPORT / TEST-RUN a drafted playbook into the tenant — the "Deploy + test-run" lifecycle (import → disposable test incident → run → report → close) is at the bottom of the skill body and is an explicit, approval-gated, operator-triggered step.'
icon: automation
source: platform
loadingMode: on-demand
locked: false
attack: []
---

> **WHY YOU ARE READING THIS:** the operator asked you to BUILD a new Cortex
> XSOAR playbook. Do NOT free-hand the YAML from memory — Guardian ships ~800
> real, vetted playbooks (`soar-playbooks` KB) precisely so you can ground a new
> one in proven structure. Follow the lifecycle in order; the result is a
> DRAFT. Deploying + test-running that draft into a tenant is a SEPARATE,
> explicit, approval-gated step — see "Deploy + test-run" at the bottom, and
> only do it when the operator asks.

# Skill: Build a Cortex XSOAR playbook from examples

## Purpose

Author a new Cortex XSOAR playbook tailored to the operator's use-case, grounded
in the closest real playbooks from the bundled `soar-playbooks` knowledge base
(retrieval-augmented generation). The output is valid, importable playbook YAML
plus the example citations — a starting point, not a finished product.

## Lifecycle (in order)

### Step 1 — Frame the use-case

Restate, in one line, what the playbook must DO and for which product/integration
(e.g. "isolate a host on CrowdStrike Falcon, then notify the analyst"). If the
operator's ask is ambiguous on the trigger, the product, or the success
condition, ask ONE clarifying question before drafting — a playbook built on the
wrong assumption wastes the review.

### Step 2 — Ground in real examples (mandatory)

Find the 2-3 closest existing playbooks and study their structure:

```
knowledge_search(query="<the use-case in plain terms — e.g. 'isolate a compromised endpoint and collect forensics'>",
                 kb_name="soar-playbooks", limit=3)
# Filter by product / use-case when relevant:
#   tags=["product:crowdstrike"]  or  tags=["phishing"]
```

Each hit's metadata carries the **full `raw_yaml`** of a real playbook. Study, for
the closest matches: the `tasks` map (task ids, `type` of each — `start` / `title`
/ `regular` / `condition` / `playbook`), the `nexttasks` wiring (the task graph),
the `inputs` / `outputs`, and which integrations the tasks call (`task.script` /
`task.brand`). Build your draft on these patterns — do not invent task shapes.

### Step 3 — Draft the playbook

Write a NEW playbook YAML that follows the example patterns. Include at minimum:
`id` (kebab-case), `name`, a clear `description`, `starttaskid`, and a `tasks` map
with a `type: start` task whose `nexttasks` chains to the real steps, ending in a
`type: title` "Done" task. Add `inputs` the playbook needs and `outputs` it
produces. Wire every `nexttasks` reference to a task that exists. Reuse the exact
integration/command names you saw in the examples — don't guess command names.

### Step 4 — Validate (mandatory before presenting)

```
playbook_validate(playbook_yaml="<your full draft>")
```

It returns `{valid, errors, warnings, task_count}`. If `valid` is false, FIX every
error (missing fields, a `starttaskid` not in `tasks`, a `nexttasks` pointing at a
non-existent task) and re-validate. Do not present an invalid draft. Address the
warnings too where reasonable (add a description, declare inputs).

### Step 5 — Present the draft

Present the validated YAML in a single ```yaml fenced block. Then:
- **Cite the examples** you grounded it on (the `soar-playbooks` doc ids / names).
- State it is a **DRAFT** — the operator should review it and import it into
  Cortex XSOAR (Playbooks → Import) and test in a non-production playground first.
- Note any assumptions you made (the trigger, the product) and any TODOs (e.g. a
  task whose exact command the operator must confirm for their tenant).

## Deploy + test-run (only when the operator explicitly asks)

Authoring stops at a draft. **Deploying + test-running is a separate step**,
triggered by the operator — the "Deploy + test-run" button on `/playbooks/build`,
or a direct "deploy / import / test-run this playbook" request. Every step below
WRITES to the connected XSOAR tenant. Never deploy a playbook the operator didn't
explicitly ask you to deploy.

**When the operator triggers this flow, they have approved the ENTIRE D1–D7
sequence — execute it as one uninterrupted run. Do NOT stop to ask for
confirmation between steps, and ALWAYS reach the cleanup (D6: close the test
incident) even when an earlier step is degraded.** Run in order:

### D1 — Validate first
Re-run `playbook_validate` on the exact YAML you're about to deploy. Never import
an invalid playbook.

### D2 — Import the definition
```
xsoar_import_playbook(playbook_yaml="<the validated YAML>")
```
- On success: `{ok:true, playbook_id, playbook_name}` — the playbook now exists in
  the tenant library. Use `playbook_name` for the run step.
- If it returns `{ok:false, import_unavailable:true}`: the tenant has no direct
  import path (Cortex 8 without the Core REST API integration). This is NOT a draft
  defect. Tell the operator the playbook is valid + downloadable and they should
  import it once via **Settings → Playbooks → Import** (or enable the Core REST API
  integration for one-click), then continue to D3 once the playbook exists (verify
  by name). On any other `{ok:false}`, report the error and stop.

### D3 — Create a disposable test incident
```
xsoar_create_incident(name="[Guardian test] <playbook name> <short timestamp>",
                      details="Auto-created by Guardian to test-run a drafted playbook. Safe to close.",
                      create_investigation=true)
```
Keep the `[Guardian test]` prefix — it's how these are found + cleaned up. Capture
the returned `incident_id`.

### D4 — Run the playbook on it
```
xsoar_run_playbook(incident_id="<from D3>", playbook_id="<playbook_name from D2>")
```

### D5 — Observe the outcome
```
xsoar_get_war_room(incident_id="<from D3>")
```
Summarize what ran: which tasks executed, any errors, key outputs. A freshly
imported playbook may reference integrations not configured on the tenant —
surface those as expected environmental gaps, NOT draft defects.

### D6 — Clean up
```
xsoar_close_incident(incident_id="<from D3>")
```
Close the test incident (the `[Guardian test]` prefix keeps it filterable). Close,
do not delete.

### D7 — Report
Imported playbook (id/name), test incident (id + that you closed it), the run
outcome (task results / errors), and any environmental gaps to wire up before
production use.

## Boundaries

- AUTHORING (Steps 1-5) produces a DRAFT and never touches a tenant. DEPLOY +
  test-run (D1-D7) is a separate, operator-triggered, approval-gated step — run it
  only when explicitly asked, and it always WRITES to the tenant.
- Ground every structural choice in a real example; if `knowledge_search` returns
  nothing close, say so and draft a minimal skeleton, flagged as un-grounded.
- This skill covers AUTHORING + DEPLOY of a playbook. To run an EXISTING playbook
  on a real case use `xsoar_run_playbook`; to investigate a case use
  `xsoar_case_investigation`.
