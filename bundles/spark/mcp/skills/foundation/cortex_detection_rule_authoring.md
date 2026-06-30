---
name: cortex_detection_rule_authoring
displayName: Cortex detection / correlation-rule authoring
category: foundation
description: 'Author Cortex XSIAM correlation rules (scheduled XQL-backed detections) — the detection-engineering counterpart to ad-hoc XQL hunting. Turns a hunt query into a continuously-running detection: the right stage set (Scheduled vs Real Time restrictions), a deterministic time anchor, time-window aggregation with a threshold, projecting entity columns that map to the generated alert, dedup/suppression to avoid alert storms, and severity/MITRE which live in the rule wrapper (not the XQL). Builds on cortex_xql_query_authoring for the query body, cortex_compute_unit_forecasting for cost, and xsiam.datamodel_describe for guess-free field discovery. Triggers when the operator wants to write, tune, or review a correlation rule / BIOC / scheduled detection in Cortex XSIAM.'
icon: notifications_active
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Cortex detection / correlation-rule authoring

## Purpose

A **correlation rule** is an XQL-backed detection: XSIAM runs the query on a schedule (or in real time as data is ingested) and **each output row becomes one issue/alert**. This skill is the detection-engineering counterpart to [`cortex_xql_query_authoring`](cortex_xql_query_authoring.md) — that skill authors the query body; this one turns a hunt query into a *continuously-running detection* and wires it to the alert it produces.

**The XQL / rule-wrapper boundary — internalize this first.** The XQL body only does five things: scope the data, bucket time, aggregate, threshold, and project entity columns. Everything else — **schedule, time window, severity, suppression, MITRE mapping, issue-field mapping, drill-down** — is a **rule-wrapper setting in the editor** (Threat Management → Detection Rules → Correlations, or *Save as → Correlation Rule* from XQL Search). It is NOT expressible in the XQL. When the operator asks "set this to High severity / map to T1110 / suppress per user," that's the wrapper, not the query — say so.

## Hunt query → detection query: the changes that matter

1. **Stage restrictions block Create/Save.** `call`, `top`, the `tag` stage, and dataset wildcards (`dataset in (prefix_*)`) are rejected in any correlation rule. **Real Time** rules allow only `dataset`, `datamodel`, `filter`, `alter`, `fields`, `config case_sensitive` (and a `filter` stage is mandatory) — no `comp`/`join`/`dedup`/`bin`. Rule of thumb: anything needing aggregation → **Scheduled**; a pure single-event field-match → **Real Time**.
2. **Deterministic time anchor.** In scheduled rules prefer **`time_frame_end()`** over `current_time()` for time math — `current_time()` drifts during lag/downtime/recovery. (`time_frame_end()` is unavailable in Real Time.)
3. **Window + schedule are independent knobs.** *Query time frame* = how far back each run looks (≤ 7 days). *Time Schedule* = how often it fires (min 10 min; default hourly over a 1-hour window). The "N events in M minutes" pattern = set the query time frame to M and put the threshold in the XQL.
4. **Constrain output size** (prevents *"A server error occurred while generating the alert"* and "resources exceeded"): precede a heavy `comp` with a `fields` stage keeping only what you need, cap arrays with `arrayrange(arr, 0, 1000)`, keep Alert Name/Description short. **Project early.**
5. **One row = one meaningful alert.** Aggregate to the entity granularity you want to alert on, threshold it, then `fields` the entity columns.
6. **Stay under the auto-disable ceiling.** XSIAM **auto-disables any rule that generates 5000+ issues in a rolling 24h**. Design every threshold to stay well under that, or the rule silently stops detecting. Add suppression (below).

## The core shape (every scheduled threshold detection)

```
dataset = xdr_data
| filter <event scope>
| fields _time, <entity columns>          // project early — cheaper + avoids resources-exceeded
| bin _time span = <window>               // standalone stage; buckets rows by time
| comp <aggregation> as <metric> by _time, <entity columns>
| filter <metric> > <threshold>
| fields _time, <entity columns>, <metric>
```

Adding `_time` to the `comp ... by` list makes each aggregate per-window-per-entity. **Confirmed aggregations** (live-verified): `count()`, `count_distinct(x)`, `sum`, `avg`, `min`, `max`, `var(x)`, `values(x)`, `earliest(x)`, `latest(x)`. **Never** use `dcount` (→ `count_distinct`), `stddev`/`std` (→ `sqrt(var(x))`), `percentile`, `case` (→ nested `if`), or `lead` — each returns a SILENT generic HTTP 500. (Full vocabulary + the rest of the "names that 500": see [`cortex_xql_query_authoring`](cortex_xql_query_authoring.md).)

## Discover fields before you write the rule — do NOT guess (load-bearing)

Detection rules ship to production; a guessed field name is a detection that silently never fires. **Always** resolve field names from the live schema first — `xsiam.datamodel_describe(dataset="…")` or a `dataset = X | fields * | limit 1` probe. Live-found gotchas this skill was built on:

- **`event_sub_type`: filter on it, but never GROUP BY it.** `filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START` works (live-verified) and narrows to true process starts. But `comp ... by event_sub_type` FAILS — `validation_message: "The event_sub_type field cannot be queried…"` — so it can't be an aggregation key. Always pair an `event_sub_type` filter with its `event_type`.
- **Login outcome is `auth_outcome`** (`= "FAILURE"`), the IdP/cloud-auth field — it is populated for identity/SaaS login events and is frequently **null for raw endpoint logons**, so a brute-force rule on endpoint data may need a different signal. Confirm population on the target tenant. (A reasonable-sounding `action_login_result` does NOT exist — this is exactly why you verify.)
- **File events**: `action_file_path`, `action_file_name`, `action_file_extension` are real; `actor_process_image_sha256` is the stable initiator artifact.

## Projecting entity fields for the alert

The final `fields` columns are what you map to alert entities (manual on raw `xdr_data` — the XDM auto-map isn't available there). Project at least the host + offending actor + target/IP, and name columns to mean what they are:

| Project this column | Map to alert field | Why |
|---|---|---|
| `agent_hostname` (+ Agent ID if available) | Host Name | Agent ID is the most stable host identity (survives rename/reinstall) |
| `auth_identity` / `action_username` / `actor_primary_username` | User name | normalize to `domain\user`; SYSTEM/service accounts are excluded from grouping |
| `actor_process_image_sha256` | Initiator SHA256 | stable process/file artifact |
| `action_remote_ip` | Remote IP | IPv4 artifact for grouping |

**Field substitution** in Alert Name / Description / Drill-Down: `$fieldName` (dotted XDM names bare: `$xdm.source.user.username`; names with spaces in backticks: `` $`Failed Logins` ``; double-quoted text is literal; an absent field renders as literal `NULL`). E.g. *"`$auth_identity` made `$fails` failed logins from `$action_remote_ip`."*

## Tuning, suppression, severity (rule-wrapper, not XQL)

- **Test-before-promote:** set the rule Action to **`Save to dataset`** instead of `Generate issue` — it writes what it *would* match (auto-adds `_rule_id`/`_rule_name`/`_insert_time`) so you tune thresholds against real data with zero analyst impact, then flip to `Generate issue`.
- **Baseline via lookups:** a rule can `Add to / Remove from lookup` (≤ 50 MB) to maintain an allow-list; the detection `join`s against it to exclude known-good (`join type=left (<allow-list>) as r r.k = k`, then keep where the right side is null — but note the left-join anti-match `r.col = null` gotcha in the authoring skill; prefer a presence flag in the sub-query).
- **Issue Suppression** (off by default) collapses *generated issues* over a Duration (default 1h, max 1 day) by selected Fields: empty Fields → one issue for the whole window; specific fields → suppress matching values; all fields → one per distinct row.
- **Severity drives case creation:** an issue of **Medium or above auto-opens a case**; **Low issues are NOT grouped into cases**. Keep high-volume/low-confidence detections at **Low** (visible as issues, no case noise); reserve Medium+ for high-confidence. **MITRE ATT&CK**, Category, and Issue Domain are selected on the rule, not derived from the XQL.

## CU cost

A correlation rule runs on every schedule tick — its cost is paid repeatedly. Apply [`cortex_compute_unit_forecasting`](cortex_compute_unit_forecasting.md): narrow the query time frame, filter/project early, and verify the per-run cost with `xsiam.xql_verify` before promoting. A cheap-looking rule on an hourly schedule still scans 24×/day.

## Worked examples (live-verified XQL bodies)

All four run to `SUCCESS` on a real XSIAM tenant with confirmed fields; set the schedule/threshold/severity in the wrapper. See KB entries `xql-examples/329-332`.

**Failed-logon brute force (T1110, Medium)** — >20 failures per source/account in 10 min:
```
dataset = xdr_data
| filter event_type = ENUM.LOGIN_EVENT and auth_outcome = "FAILURE"
| fields _time, action_remote_ip, auth_identity, agent_hostname
| bin _time span = 10m
| comp count() as fails, count_distinct(agent_hostname) as targets by _time, action_remote_ip, auth_identity
| filter fails > 20
| fields _time, action_remote_ip, auth_identity, fails, targets
```

**Office app spawning a shell/script host (T1059, High)** — scoped on `event_type` only; you can add `and event_sub_type = ENUM.PROCESS_START` to narrow to true process starts (filtering on it is fine; just never GROUP BY it):
```
dataset = xdr_data
| filter event_type = ENUM.PROCESS and causality_actor_process_image_name in ("winword.exe","excel.exe","outlook.exe","powerpnt.exe") and actor_process_image_name in ("powershell.exe","cmd.exe","wscript.exe","cscript.exe","mshta.exe")
| fields _time, agent_hostname, causality_actor_process_image_name, actor_process_image_name, actor_process_command_line, actor_process_image_sha256
| comp count() as spawns, values(actor_process_command_line) as cmdlines by agent_hostname, causality_actor_process_image_name, actor_process_image_name, actor_process_image_sha256
| fields agent_hostname, causality_actor_process_image_name, actor_process_image_name, actor_process_image_sha256, spawns, cmdlines
```

**Beaconing / C2 cadence (T1071, Low)** — many connections, few ports, one destination per host/hour:
```
dataset = xdr_data
| filter event_type = ENUM.NETWORK
| fields _time, agent_hostname, action_remote_ip, action_remote_port
| bin _time span = 1h
| comp count() as conns, count_distinct(action_remote_port) as ports by _time, agent_hostname, action_remote_ip
| filter conns > 60 and ports < 3
| fields _time, agent_hostname, action_remote_ip, conns, ports
```

**Mass file write / ransomware (T1486, Critical)** — one process touching >100 files in 5 min:
```
dataset = xdr_data
| filter event_type = ENUM.FILE
| fields _time, agent_hostname, actor_process_image_name, actor_process_image_sha256, action_file_path, action_file_extension
| bin _time span = 5m
| comp count_distinct(action_file_path) as files_touched, count() as ops, count_distinct(action_file_extension) as exts by _time, agent_hostname, actor_process_image_name, actor_process_image_sha256
| filter files_touched > 100
| fields _time, agent_hostname, actor_process_image_name, actor_process_image_sha256, files_touched, ops, exts
```

## Failure handling

- "A server error occurred while generating the alert" / resources exceeded → project earlier (`fields` before `comp`), cap arrays, shorten the Alert Name/Description.
- Rule auto-disabled → it crossed 5000 issues/24h; tighten the filter, raise the threshold, or add suppression.
- Create/Save rejected → a forbidden stage (`call`/`top`/`tag`/wildcard) or, for Real Time, an aggregation stage. Move to Scheduled or remove the stage.
