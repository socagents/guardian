---
name: xsoar_platform_reference
displayName: XSOAR platform reference (War Room, commands, query syntax)
category: foundation
description: 'Authoritative reference for the Cortex XSOAR PLATFORM itself — what the War Room / Playground / indicator store / Lists are, the exact `!command` catalog (and which `xsoar_*` connector tool wraps each), and the DEFINITIVE incident + indicator query-syntax tables. **Load this BEFORE guessing XSOAR query syntax, before running a raw `!command`, and whenever the operator asks a "what is …" / "what does `!X` do" / "how do I query …" question about XSOAR.** It exists to stop two failure modes: (1) probing many syntax variants of the same filter (e.g. `severity:[1]` vs `severity:low` vs `severity:Low`) because you are unsure which form works, and (2) flailing to cortex-docs/web for an XSOAR concept that is answered here. Holds the per-severity COUNT recipe (read `total` per bucket, do not page-scan) and the v6-vs-v8 differences. Companion skills: `xsoar_case_triage` (triage codes + escalate/close heuristics) and `xsoar_case_investigation` (the end-to-end lifecycle).'
icon: quick_reference
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: XSOAR platform reference

## Category

foundation

## Purpose

The reference card for **the Cortex XSOAR platform itself** — its concepts, its War Room `!command` surface, and its query syntax. The investigation methodology lives in `xsoar_case_investigation`; the triage codes + decision rules live in `xsoar_case_triage`. **This** skill is what you read when you need to know *how XSOAR works* or *the exact syntax to pass a tool* — so you call the right `xsoar_*` tool with the right arguments **once**, instead of probing variants or searching the web for something documented here.

Load this when:

- The operator asks a **concept** question — "what is the War Room?", "what's a playground?", "what does `!Print` do?", "what XSOAR commands can you run?". Answer from this skill; **do not `web.navigate` or burn cortex-docs searches** for these.
- You are about to **filter** `xsoar_list_incidents` or `xsoar_search_indicators` and want the canonical query form (so you don't try `severity:low`, `severity:Low`, `severity:1`, and `severity:[1]` in turn).
- You are about to run a **raw `!command`** via `xsoar_run_command` and want to know whether a first-class connector tool already wraps it (it usually does — prefer the wrapper).

This skill makes **no tool calls itself** — it is reference only.

---

## XSOAR core concepts

| Concept | What it is |
|---|---|
| **Incident (case)** | XSOAR's unit of work — an alert/event promoted to an investigation. Has an id, type, severity (1-4), status (0-3), owner, `CustomFields`, a `version` (optimistic-concurrency token), and an `investigationId`. Read with `xsoar_get_incident`; list/filter with `xsoar_list_incidents`. |
| **War Room** | The per-incident timeline where notes, command output, playbook task results, and evidence accumulate. Read it with `xsoar_get_war_room`; write to it with `xsoar_add_entry` (free entry) / `xsoar_add_note` (pinned note) / `xsoar_save_evidence` (pin as evidence). **Read the War Room before adding findings — don't repeat work already recorded.** |
| **Playground** | A standalone investigation whose War Room is a scratchpad for running ad-hoc `!commands` outside any real case. Its investigation id is the **`playground_id`** configured on the instance. **Command-engine tools run their `!command` in this playground** and FAIL without it. (Our lab tenants: v6 = `221`, primary v8 = `3967`.) |
| **Indicator store** | XSOAR's IoC database — IPs, domains, URLs, file hashes, CVEs, emails, each with a reputation/DBotScore + relationships. Search it with `xsoar_search_indicators`; get a live verdict for one IoC with `xsoar_enrich_indicator`. |
| **List** | A named key/value or line-delimited store (block/allow lists, lookup tables). Read with `xsoar_get_list`, create-or-overwrite with `xsoar_set_list`, append-one-line with `xsoar_append_to_list`. List tools run as `!commands` → **need `playground_id`.** |
| **Integration** | A configured product connection on the tenant (firewall, EDR, TI feed, the Core REST API integration). List the enabled ones with `xsoar_list_integrations`. |
| **Playbook** | An automation workflow. Run one on a case with `xsoar_run_playbook` (by name, in the case's own War Room — no `playground_id`); import one with `xsoar_import_playbook`. |

> **`playground_id` rule of thumb:** anything that *executes a `!command`* needs it — `xsoar_enrich_indicator`, `xsoar_run_command`, `xsoar_complete_task`, and the three List tools. Anything that hits a REST endpoint directly (`xsoar_list_incidents`, `xsoar_get_incident`, `xsoar_get_war_room`, `xsoar_search_indicators`, `xsoar_update_incident`, `xsoar_close_incident`, `xsoar_create_incident`, `xsoar_run_playbook`) does **not**. If a command-engine tool returns "playground not configured", tell the operator the instance's `playground_id` is missing (set it on the connector instance) and fall back to a REST-path tool where one exists.

---

## War Room `!command` catalog

You rarely need a raw `!command` — a first-class `xsoar_*` tool wraps the common ones, and the wrapper handles auth, the playground, and result parsing. Reach for `xsoar_run_command` only for the long tail (a vendor integration command, an auth-log pull) that has no wrapper.

| `!command` | What it does | Prefer this connector tool | Needs `playground_id`? |
|---|---|---|---|
| `!Print value=<x>` | Echo a value to the War Room. Smoke/diagnostic only. | `xsoar_run_command` (no wrapper) | yes |
| `!ip` / `!url` / `!domain` / `!file` / `!cve` | Reputation enrichment for one IoC → DBotScore. | **`xsoar_enrich_indicator`** | yes |
| `!findIndicators query=<q>` | Search the indicator store via the command engine. | **`xsoar_search_indicators`** (REST path, no playground needed — prefer it) | yes |
| `!getList listName=<n>` | Read a List. | **`xsoar_get_list`** | yes |
| `!createList listName=<n> listData=<d>` | Create-or-overwrite a List. | **`xsoar_set_list`** | yes |
| `!setList listName=<n> listData=<d>` | **Update an EXISTING List only** — errors "Item not found" on a new name. Use `!createList`/`xsoar_set_list` to create. | — (avoid; use `xsoar_set_list`) | yes |
| `!setIncident <field>=<v>` | Mutate incident fields. | **`xsoar_update_incident`** (resolves `version` itself) | no (REST) |
| `!taskComplete id=<n>` | Advance a stuck playbook task. | **`xsoar_complete_task`** | yes |
| `!core-api-post/get/put/delete uri=<u> body=\`<json>\`` | Generic call through the **Core REST API integration** (must be installed on the tenant). Body is wrapped in backticks. The v8 playbook-import path uses `core-api-post uri=/playbook/save body=\`[{…}]\``. | `xsoar_import_playbook` (for playbook import); else `xsoar_run_command` | yes |

**Backtick rule for `!core-api-*`:** the JSON `body` is delimited by backticks, so the JSON itself must not contain a backtick. `/playbook/save` expects a JSON **array** of playbooks, not a bare object.

---

## Incident query syntax (`xsoar_list_incidents`)

`xsoar_list_incidents` accepts **structured** filters (numeric codes) *and* a free-text `query`. **Use the structured form — it is unambiguous and it is what powers counts.** When you supply `query`, XSOAR mostly ignores the structured `status`/`severity` args, so don't mix the two.

```
# Open work (active status). status is a list of CODES.
xsoar_list_incidents(status=[1])

# Open high + critical (the triage queue).
xsoar_list_incidents(status=[1], severity=[3, 4])

# Free-text / fields the codes can't express (owner, text, time) — use `query` alone.
xsoar_list_incidents(query="owner:\"\"")            # unassigned
xsoar_list_incidents(query="type:Phishing")          # by type name
```

| Field | Codes / form |
|---|---|
| **status** | `0` Pending · `1` Active (**open**) · `2` Closed · `3` Archived. Pass as a list: `status=[1]`. |
| **severity** | `1` Low · `2` Medium · `3` High · `4` Critical (`0` Unknown on some tenants). Pass as a list: `severity=[3,4]`. |
| **time** | `from_date` / `to_date` ISO strings (e.g. `from_date="2026-06-01T00:00:00Z"`). |
| **everything else** | `query=` free-text (type name, owner, label, full text). One approach OR the other — not both. |

### Per-severity COUNT recipe (do NOT page-scan)

To answer "how many open cases of each severity?" you do **not** need to page through every incident. Each call returns `total` for its filter. Query **once per bucket** with `page_size=1` and read `total`:

```
xsoar_list_incidents(status=[1], severity=[1], page_size=1)   # -> total = # Low open
xsoar_list_incidents(status=[1], severity=[2], page_size=1)   # -> total = # Medium open
xsoar_list_incidents(status=[1], severity=[3], page_size=1)   # -> total = # High open
xsoar_list_incidents(status=[1], severity=[4], page_size=1)   # -> total = # Critical open
```

Four calls, one per severity — not a page-scan, and not a dozen syntax variants. Use the **structured `severity=[N]` form** here (the free-text `query="severity:low"` form is for the search box, and its label spelling varies by tenant — the numeric code does not).

**The structured per-bucket count is authoritative.** Do NOT then re-run the same buckets in the free-text `query` form to "double-check" — that just doubles the calls for the same answer. One call per bucket (plus, if you want it, one `status=[1]` call for the total) IS the complete breakdown. Report it and stop.

---

## Indicator query syntax (`xsoar_search_indicators`)

`xsoar_search_indicators(query=…)` passes an XSOAR **indicator-search** query verbatim to `/indicators/search`. Build it from these fields (XSOAR's indicator query DSL):

```
xsoar_search_indicators(query="type:IP and reputation:Bad")      # bad-rep IPs
xsoar_search_indicators(query="type:Domain")                      # all domains
xsoar_search_indicators(query="value:1.2.3.4")                    # one value (any type)
xsoar_search_indicators(query="type:File and reputation:Bad")     # malicious hashes
```

| Field | Values |
|---|---|
| **type** | `IP` · `Domain` · `URL` · `File` (hash) · `CVE` · `Email` · `Host` · `Account`. Capitalize as shown — these are XSOAR indicator-type names, not the lowercase `indicator_type` of `xsoar_enrich_indicator`. |
| **reputation** | `Good` · `Suspicious` · `Bad` · `None`/`Unknown`. |
| **value** | An exact IoC value — `value:8.8.8.8`. |

- The reputation field is **`reputation:`** with values `Good` / `Suspicious` / `Bad` / `None`. That is the correct field — do **NOT** try `verdict:`, `score:`, or `dbotscore:` (those are not indicator-search query fields), and do not go to cortex-docs to "find the right field." `reputation:Bad` is it.
- **An empty result means the store is empty for that filter — NOT that your syntax is wrong.** If `type:IP` or `reputation:Bad` returns 0, report "no such indicators in the store" and STOP. Do not retry with `verdict:` / `score:` / `!findIndicators` variants or fall back to docs — the syntax above is correct; the store simply holds none.
- "Top by reputation" = filter `reputation:Bad` and read the list — there is **no server-side reputation sort**, so neither `search_indicators` nor `!findIndicators` can rank for you. If the stored indicators aren't reputation-scored, say so rather than hunting for a ranking that doesn't exist.
- **`search_indicators` already returns each indicator's `score` (0-3) + `reputation` label directly** (a compact `{id, type, value, score, reputation, source, …}` per hit). Read them straight from the result and sort/count client-side — there is **never** a reason to fall back to `!findIndicators` for a "readable" or scored result; it has nothing `search_indicators` doesn't.
- **For "how many", read `total` from the result — do NOT enumerate pages to count.** The result carries `total` (XSOAR's full-store count for the filter) and `result_count` (this page).
- **If every hit's `reputation` is `Unknown` (score 0), the store simply isn't reputation-scored for that type.** Report the count (from `total`) + "none are reputation-scored" and **STOP** — there is no "top by reputation" to give. Do NOT run `!findIndicators`, `!py demisto.executeCommand`, or cortex-docs trying to find a ranking: those return the SAME unscored values, and the data has no ranking to find. Hunting for a ranking that doesn't exist is the exact flail this skill exists to prevent.
- For a **live verdict on a specific IoC**, use `xsoar_enrich_indicator` (DBotScore) — `search_indicators` tells you what's already in the store + cross-case correlation, not a fresh verdict.

---

## v6 vs v8 — what actually differs (and what doesn't)

The connector auto-detects the generation; **you call the same `xsoar_*` tool name regardless.** The differences are internal:

| | XSOAR 6 (on-prem) | XSOAR 8 / Cortex cloud |
|---|---|---|
| Auth | single API key in `Authorization` | API key **+** key id via `x-xdr-auth-id` |
| Base path | none | `/xsoar/public/v1` prefix |
| Playbook import | direct multipart upload | Core REST API integration → `core-api-post /playbook/save` (a JSON array) |

**Same for both:** the playground/`playground_id` requirement, the status/severity codes, the query syntax above, and every tool's behavior. Don't special-case the version in your reasoning — if two instances are enabled, the only thing you choose is the `instance` argument (see the connected-instances guidance), never the generation.

---

## Anti-patterns this skill exists to prevent

- **Probing syntax variants.** Trying `severity:[1]`, then `severity:low`, then `severity:Low`, then `severity:1` for the same count is wasted turns. Use the structured `severity=[N]` form once.
- **Page-scanning for a count.** Reading every page to tally severities — read `total` per bucket instead.
- **Web-searching an XSOAR concept.** "What is the War Room / what does `!Print` do" is answered here. `web.navigate` to a search engine for a documented XSOAR concept is a failure, not research.
- **Raw `!command` when a wrapper exists.** Prefer `xsoar_enrich_indicator` over `!ip`, `xsoar_get_list` over `!getList`, etc. — the wrapper handles the playground + parsing.

## Constraints

- Numeric **codes** (status/severity) are the safe filter form — label spellings vary by tenant; codes don't.
- Command-engine tools (`enrich_indicator`, `run_command`, `complete_task`, the List tools) **require `playground_id`** — if it's missing, the fix is on the instance config, not the query.
- This skill is reference-only — the calls live in `xsoar_case_investigation`.

## Cross-references

- **Triage skill**: `xsoar_case_triage` — severity/status/close-reason tables + escalate-vs-close decision rule.
- **Workflow skill**: `xsoar_case_investigation` — the end-to-end monitor → fetch → research → enrich → document → resolve lifecycle.
- **Research skill**: `cortex_kb_search` — query discipline for `cortex-docs` lookups (use for Cortex *product* questions this skill doesn't cover, not for the syntax/concepts above).
- **Connector**: `xsoar` — wraps the Cortex XSOAR API (v6 on-prem + v8 / Cortex cloud). See `bundles/spark/connectors/xsoar/`.
