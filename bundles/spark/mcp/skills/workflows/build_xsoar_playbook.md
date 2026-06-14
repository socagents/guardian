---
name: build_xsoar_playbook
displayName: Build a Cortex XSOAR playbook from examples
category: workflows
description: '**LOAD-FIRST WHEN THE OPERATOR ASKS TO BUILD / CREATE / DRAFT / GENERATE / SCAFFOLD a Cortex XSOAR (SOAR) PLAYBOOK.** Whenever the request is to author a new automation/response playbook (e.g. "build a phishing-triage playbook", "draft a CrowdStrike host-isolation playbook", "generate a playbook for X"), call `skills_read({file_path: "workflows/build_xsoar_playbook.md"})` IMMEDIATELY as your first tool call. The skill body is the retrieval-augmented authoring lifecycle: GROUND in real examples from the `soar-playbooks` KB via `knowledge_search` (study their `raw_yaml` task graph), DRAFT a new valid playbook YAML following those patterns, VALIDATE it with `playbook_validate`, then PRESENT it as a reviewable draft with the examples cited. This is for AUTHORING a new playbook — distinct from `xsoar_run_playbook` (run an existing one) and `xsoar_case_investigation` (investigate a case).'
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
> DRAFT for the operator to review + import, never something you apply to a
> tenant yourself.

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

## Boundaries

- You AUTHOR YAML; you do NOT create, run, or deploy the playbook on any tenant
  (no `xsoar_run_playbook` / writes here). The operator imports + runs it.
- Ground every structural choice in a real example; if `knowledge_search` returns
  nothing close, say so and draft a minimal skeleton, flagged as un-grounded.
- This skill is for AUTHORING. To run an existing playbook use `xsoar_run_playbook`;
  to investigate a case use `xsoar_case_investigation`.
