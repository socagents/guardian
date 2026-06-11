---
name: xsoar_case_triage
displayName: XSOAR case triage reference
category: foundation
description: 'Reference skill for triaging Cortex XSOAR cases (incidents). Holds the lookup tables — severity codes (1 Low · 2 Medium · 3 High · 4 Critical), status codes (0 Pending · 1 Active · 2 Closed · 3 Archived), and the common close reasons (Resolved / False Positive / Duplicate / Other) — plus how to filter `xsoar_list_incidents` effectively (open = active status), and the escalate-vs-close decision heuristics. Load this when you need the case codes or the triage decision rule without the full investigation lifecycle. The companion workflow skill is `xsoar_case_investigation` (the load-first end-to-end procedure).'
icon: rule
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: XSOAR case triage reference

## Category

foundation

## Purpose

The lookup tables and triage heuristics for Cortex XSOAR cases (incidents). The `xsoar_case_investigation` workflow skill drives the full monitor → fetch → research → enrich → document → resolve lifecycle; **this** skill is the reference card it leans on — the numeric field codes, the close-reason vocabulary, the `xsoar_list_incidents` filter recipes, and the rule for deciding whether a case should be escalated or closed.

Load this when you only need the codes or the decision rule (e.g. "what severity is 3?", "how do I list just open cases?", "should I escalate or close this?") without re-reading the whole lifecycle.

---

## Case field codes

### Severity

| Code | Severity |
|---|---|
| `0` | Unknown (some tenants) |
| `1` | Low |
| `2` | Medium |
| `3` | High |
| `4` | Critical |

### Status

| Code | Status | Meaning |
|---|---|---|
| `0` | Pending | Created, not yet actively worked. |
| `1` | Active | **Open** — the working set. |
| `2` | Closed | Resolved/closed; carries a close reason. |
| `3` | Archived | Retired from the active store. |

> "Open cases" = `status:1` (Active). "Critical open cases" = `status:1 severity:4`.

## Common close reasons

XSOAR tenants configure their own close-reason list; these are the standard defaults:

| Reason | Use when |
|---|---|
| `Resolved` | Investigated and remediated — a real issue that's now handled. |
| `False Positive` | The detection did not represent a real threat. |
| `Duplicate` | Already tracked by another case — reference the other id in the close notes. |
| `Other` | Anything else; the close note MUST explain. |

If the tenant's reasons differ from these, confirm the exact label via the `cortex_kb_search` skill (search "incident close reason") before calling `xsoar_close_incident` — an unknown label is rejected.

---

## Filtering `xsoar_list_incidents` effectively

`xsoar_list_incidents` takes a query string built from the field codes above. Filter on codes, not free text.

```
# All open cases
xsoar_list_incidents(query="status:active")

# Open high + critical only (the triage queue)
xsoar_list_incidents(query="status:active AND (severity:high OR severity:critical)")

# Open cases assigned to nobody (need an owner)
xsoar_list_incidents(query="status:active AND owner:\"\"")

# Recently opened (combine with the tenant's time filter syntax)
xsoar_list_incidents(query="status:active created:>=now-24h")
```

Triage discipline:

1. Pull the **open** set first (`status:active`) — closed/archived cases are history, not work.
2. Sort attention by severity: Critical (4) → High (3) → Medium (2) → Low (1).
3. Within a severity, prefer unassigned and oldest-open cases.
4. Take every incident id from the live response — never fabricate one.

---

## Escalate vs close — the decision rule

After reading a case (`xsoar_get_incident` + `xsoar_get_war_room`) and enriching its indicators (`xsoar_search_indicators`):

| Signal | Action |
|---|---|
| Indicators clean, behavior explained by benign activity, no impact | **Close** as `False Positive` — document why in the war room first. |
| Real but already contained/remediated, no further action needed | **Close** as `Resolved` — pin the remediation evidence with `xsoar_save_evidence`. |
| Same root cause as an existing case | **Close** as `Duplicate`, referencing the other id. |
| True positive with active impact, lateral movement, or scope beyond this case | **Escalate** — raise severity via `xsoar_update_incident` (pass the case `version`), assign an owner, add a note stating what's unconfirmed, and leave it **Active**. |
| Evidence inconclusive after research + enrichment | **Do not close.** Add a note describing the gap and what's needed; leave it Active and tell the operator what's blocking. |

**Never close a case you couldn't document.** The war-room note/evidence is the justification for the close or escalation — write it (Step 5 of the lifecycle) before you resolve.

---

## Constraints

- Severity/status are **numeric codes** — map them via the tables above; don't pass label strings the tenant might not parse the same way.
- Confirm tenant-specific close reasons via `cortex_kb_search` before closing with a non-default label.
- Escalation that raises severity uses `xsoar_update_incident`, which needs the `version` from `xsoar_get_incident` (optimistic concurrency).
- This skill is reference-only — it makes no tool calls itself. The calls live in `xsoar_case_investigation`.

## Cross-references

- **Workflow skill**: `xsoar_case_investigation` — the load-first end-to-end investigation procedure that uses these codes.
- **Research skill**: `cortex_kb_search` — query discipline for confirming Cortex field/close-reason definitions in the docs.
- **Connector**: `xsoar` — wraps the Cortex XSOAR API (v6 on-prem + v8 / Cortex cloud). See `bundles/spark/connectors/xsoar/`.
