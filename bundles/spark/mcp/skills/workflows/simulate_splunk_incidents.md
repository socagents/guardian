---
name: simulate_splunk_incidents
displayName: Simulate Splunk incidents in XSOAR
category: workflows
description: '**LOAD-FIRST when the operator asks to simulate / seed / generate Splunk incidents (or Splunk notables / findings / investigations / ES events) in Cortex XSOAR.** Whenever the request is "create simulated Splunk incidents", "seed some Splunk ES findings", "make test Splunk notables as if SplunkPy fetched them", "generate Splunk investigation cases", or similar — call `skills_read({file_path: "workflows/simulate_splunk_incidents.md"})` IMMEDIATELY as your first tool call, BEFORE any `xsoar_*` call. The skill body carries the exact SplunkPy content-pack schema: the three Splunk incident TYPES (`Splunk Notable Generic`, `Splunk Finding`, `Splunk Investigation`) and, per type, the POST-MAPPING XSOAR incident-field cliNames + valid select values that go into `xsoar_create_incident`''s `custom_fields`. The whole point: create the incident with the fields XSOAR uses AFTER the SplunkPy incoming mapper runs (e.g. `splunkurgency`, `splunkstatus`, `splunkdisposition`, `notableid`) — NOT the raw Splunk fields (`urgency`, `status_label`, `event_id`, `src`). This requires the SplunkPy pack to be installed on the target XSOAR tenant; if create fails or the splunk* fields don''t persist on read-back, SplunkPy is not installed. The xsoar connector has TWO instances (`primary-xsoar` = v8 cloud, `xsoar-v6` = v6 on-prem) — you MUST pass `instance=` on every call.'
icon: science
source: platform
loadingMode: on-demand
locked: false
attack: []
---

> **WHY YOU ARE READING THIS:** the operator wants synthetic Splunk incidents in XSOAR that look exactly as if the SplunkPy integration fetched and mapped them — for testing layouts, playbooks, the Guardian investigation loop, or a demo. Your job is to call `xsoar_create_incident` with the right Splunk **incident type** and its **post-mapping** `custom_fields` (cliNames), populated with realistic, varied values. You do NOT map anything — you write the already-mapped XSOAR field names directly. Do not invent cliNames or select values: use only the ones listed below.

# Skill: Simulate Splunk incidents in XSOAR

## Category

workflows

## Purpose

Create simulated Splunk incidents in Cortex XSOAR **as if SplunkPy fetched them from Splunk Enterprise Security**, across the three incident types the SplunkPy content pack defines. Each incident is created via `xsoar_create_incident` using the XSOAR fields the SplunkPy **incoming mapper** produces (cliNames under `CustomFields`), so the resulting cases render in the Splunk layouts and drive the Splunk playbooks identically to real fetched events.

This is a generation/seeding workflow, not an investigation. For investigating a case once it exists, use `xsoar_case_investigation`.

## Prerequisites — read before creating anything

1. **Pick the target instance.** The xsoar connector is multi-instance — pass `instance=` on EVERY tool call:
   - `instance="xsoar-v6"` — v6 on-prem lab tenant (default for simulation/seeding).
   - `instance="primary-xsoar"` — v8 cloud tenant (production-leaning; only seed here if the operator explicitly asks).
   If the operator didn't say which, default to `xsoar-v6` and state which you used.
2. **Confirm SplunkPy is installed on that tenant.** The Splunk incident types + `splunk*` / `notable*` incident fields exist only if the SplunkPy pack is installed from the XSOAR marketplace. Verify cheaply: create ONE incident (below), then `xsoar_get_incident` it and confirm the `splunk*`/`notable*` keys came back under `CustomFields`. If they did NOT persist (or create errored), STOP and tell the operator: *"SplunkPy is not installed on `<instance>` — install it from the XSOAR marketplace, then re-run."*
3. **Use post-mapping fields only.** Put values under `custom_fields` using the cliNames in the tables below. NEVER put raw Splunk field names (`event_id`, `rule_name`, `urgency`, `status_label`, `src`, `dest`, `disposition_label`, …) into `custom_fields`. Raw source context, if you want it for realism, goes in `labels` (e.g. `["src:10.0.0.5", "rule:Threat - Suspicious Email - URL - Rule"]`) — it is decoration, not the mapped data.

## The three Splunk incident types

| `incident_type` (exact string) | Splunk source | When SplunkPy assigns it |
|---|---|---|
| `Splunk Notable Generic` | ES Notable Events | classic notable fetch |
| `Splunk Finding` | ES Findings / Risk (ES 8.x) | classifier: `splunk_es_event_type == "Finding"` |
| `Splunk Investigation` | ES Investigations (ES 8.x) | classifier: `splunk_es_event_type == "Investigation"` |

Create a spread across all three unless the operator names one. Default batch when unspecified: ~3 of each type (9 total), with varied rules/hosts/IPs/urgencies/dispositions.

## Built-in incident fields (set directly on `xsoar_create_incident`, NOT in custom_fields)

- `name` (required) — the title. Mirror SplunkPy's name derivation per type (see each section).
- `severity` — integer 0–4. Map from urgency: `informational/low → 1`, `medium → 2`, `high → 3`, `critical → 4`.
- `details` — free-text description (the rule/finding description).
- `owner` — optional XSOAR username (often empty on fetch; omit or use a real user).
- `labels` — optional source attribution strings (raw context only — see rule 3).
- `create_investigation` — `true` for realism (spins the war room) unless seeding a large batch where you want it off.

## Per-type post-mapping field schema

### A. `Splunk Notable Generic`

- **name** pattern: `"<event_id> - <rule_name>"` (e.g. `"1A2B3C - Endpoint - Recurring Malware Infection - Rule"`).
- **custom_fields** cliNames:

| cliName | type | valid values / shape |
|---|---|---|
| `notableid` | shortText | the notable event id, e.g. `"1A2B3C4D-..."` |
| `notablestatus` | singleSelect | `New` · `In Progress` · `Pending` · `Resolved` · `Closed` |
| `notableurgency` | singleSelect | `critical` · `high` · `medium` · `low` · `informational` |
| `notabledrilldown` | markdown | drilldown search results as markdown (a small table/code block) |
| `splunknotablereviewer` | user | reviewer username (or omit) |
| `splunkcomments` | multiSelect | list of comment strings |
| `splunknotes` | multiSelect | list of note strings |
| `successfulassetenrichment` | shortText | `"true"` / `"false"` |
| `successfuldrilldownenrichment` | shortText | `"true"` / `"false"` |
| `successfulidentityenrichment` | shortText | `"true"` / `"false"` |

### B. `Splunk Finding`

- **name** pattern: the rule title, e.g. `"Threat - Suspicious Email - URL - Rule"`.
- **custom_fields** cliNames:

| cliName | type | valid values / shape |
|---|---|---|
| `splunkstatus` | singleSelect | `New` · `In Progress` · `Pending` · `Resolved` · `Closed` |
| `splunkurgency` | singleSelect | `critical` · `high` · `medium` · `low` · `informational` |
| `splunkdisposition` | singleSelect | `Unassigned` · `True positive - suspicious activity` · `Benign positive - suspicious but expected` · `False positive - incorrect analytic logic` · `False positive - inaccurate data` · `Other` · `Undetermined` |
| `splunksecuritydomain` | shortText | `threat` · `access` · `endpoint` · `network` · `identity` · `audit` |
| `splunksensitivity` | shortText | e.g. `restricted` / `confidential` / `internal` |
| `splunkdrilldown` | markdown | drilldown payload as markdown |
| `splunkdestriskscore` | number | numeric risk score, e.g. `64` |
| `splunkdestriskobjecttype` | shortText | `host` · `user` · `system` · `other` |
| `splunknotes` | multiSelect | list of note strings |

### C. `Splunk Investigation`

- **name** pattern: the investigation name (e.g. `"Coordinated phishing campaign — Q2"`).
- **custom_fields** cliNames:

| cliName | type | valid values / shape |
|---|---|---|
| `splunkinvestigationguid` | shortText | a GUID |
| `splunkinvestigationid` | shortText | e.g. `"ES-00015"` |
| `splunkinvestigationname` | shortText | the investigation name |
| `splunkinvestigationtype` | shortText | e.g. `"default"` |
| `splunkincidentorigin` | shortText | e.g. `"MC Incident"` |
| `splunkstatus` | singleSelect | `New` · `In Progress` · `Pending` · `Resolved` · `Closed` |
| `splunkurgency` | singleSelect | `critical` · `high` · `medium` · `low` · `informational` |
| `splunkdisposition` | singleSelect | (same values as Splunk Finding) |
| `splunksensitivity` | shortText | as above |
| `splunkincidentids` | multiSelect | list of associated incident ids |
| `splunkexcludedfindingids` | multiSelect | list of finding ids |
| `splunkimplicitfindingids` | multiSelect | list of finding ids |
| `splunkintermediatefindingids` | multiSelect | list of finding ids |
| `splunkriskobject` | multiSelect | list of risk objects (hosts/users) |
| `splunkconsolidatedfindings` | longText | JSON-ish text summarizing rolled-up findings |
| `splunknotes` | multiSelect | list of note strings |

> Reference: the `splunkeseventtype` field (`Finding`/`Investigation`) is what SplunkPy's classifier reads to choose the type — you don't need to set it; you choose the type directly via `incident_type`.

## Procedure

1. **Read this skill** (you're here). Decide the target `instance` (default `xsoar-v6`) and the batch (default ~3 per type).
2. **Probe once.** Create the first incident (any type) with its mapped `custom_fields`, then `xsoar_get_incident` it and confirm the `splunk*`/`notable*` keys persisted. If not → SplunkPy missing → STOP + report.
3. **Generate the batch.** For each incident: choose a realistic Splunk ES rule/finding/investigation, set `name`/`severity`/`details` (built-ins), and the type's mapped `custom_fields`. Vary everything — rules (Endpoint/Access/Threat/Network domains), hosts, src/dest IPs, users, urgencies, dispositions, statuses. Keep singleSelect values strictly from the allowed lists.
4. **Confirm + report.** List the created incident ids + types (`xsoar_list_incidents instance=<inst>` filtered to recent, or echo the ids from `xsoar_create_incident` returns). Tell the operator how many of each type landed and on which instance.

## Example call (Splunk Finding)

```
xsoar_create_incident(
  instance="xsoar-v6",
  name="Threat - Suspicious Email - URL - Rule",
  incident_type="Splunk Finding",
  severity=3,
  details="ES finding: user clicked a URL flagged by threat intel; dest host quarantined pending review.",
  labels=["src:10.0.4.21","rule:Threat - Suspicious Email - URL - Rule","domain:threat"],
  custom_fields={
    "splunkstatus":"New",
    "splunkurgency":"high",
    "splunkdisposition":"Undetermined",
    "splunksecuritydomain":"threat",
    "splunksensitivity":"confidential",
    "splunkdestriskobjecttype":"host",
    "splunkdestriskscore":64,
    "splunkdrilldown":"| _time | url | action |\n|---|---|---|\n| 2026-06-19T10:02Z | hxxp://bad.example/p | allowed |",
    "splunknotes":["auto-enriched via TI feed"]
  },
  create_investigation=true
)
```

## Hard rules

- **Post-mapping cliNames only** in `custom_fields`. No raw Splunk field names there.
- **singleSelect values must match** the allowed lists exactly (case-sensitive as listed).
- **Always pass `instance=`** (multi-instance connector).
- **Verify install once** before bulk-creating; if the splunk*/notable* fields don't persist, SplunkPy isn't installed — stop and say so.
- **Don't invent fields or types.** If the operator wants a field not listed here, discover it with `xsoar_get_incident_fields({instance, incident_type})` first.
