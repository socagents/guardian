# XSOAR Action Toolset — Design Spec

- **Date:** 2026-06-12
- **Status:** Approved (design). Next: implementation plan (writing-plans).
- **Author:** brainstormed with operator.
- **Scope:** add 8 tools to the XSOAR connector (`bundles/spark/connectors/xsoar/`), taking it from 13 → 21 tools, plus one new optional config field (`playground_id`).
- **Reference code mined:** `docs/ref/trevor-mcp.py`, `docs/ref/xsoar-bot.py`, `docs/ref/trevor-bot.py` (operator's prior XSOAR/XSIAM integrations).

---

## 1. Problem / motivation

The current XSOAR connector exposes 13 **read + lifecycle** tools (list/get incidents, war-room, entries, notes,
update/close, fields, indicators, evidence, health). It has **no command-execution surface** — the operator can't
ask Guardian to run an arbitrary XSOAR `!command`, enrich an indicator, manage allow/block Lists, create a case, run
a playbook, or complete a playbook task. The operator's prior integrations (the `docs/ref/` files) solved
command-execution via a **playground/war-room** workaround; this spec ports the relevant, XSOAR-only subset into
Guardian's connector following the established connector conventions.

## 2. Objectives & non-goals

**Objectives**
1. Add a **command-execution engine** (`run_command`) that runs any XSOAR `!command` synchronously in a configured
   playground/war-room and returns the war-room output + optional context keys.
2. Add **indicator enrichment** (`enrich_indicator`) layered on the engine (the `!ip`/`!url`/`!domain`/`!file`/`!cve`
   command map → DBotScore/reputation context).
3. Add **playbook-task completion** (`complete_task`) via the documented `!taskComplete` command (engine-based).
4. Add **XSOAR Lists** management (`get_list`, `set_list`, `append_to_list`) via the real XSOAR Lists REST API.
5. Add **incident lifecycle** gaps: `create_incident` (`POST /incident`) and `run_playbook`
   (`POST /inv-playbook/{playbookId}/{invId}`).
6. Add one **optional config field** `playground_id`, collected on the instance-create form, used by the engine-based
   tools.

**Non-goals**
- **No XSIAM-side tools.** The reference code's XQL, datasets, issues, assets, tenant-info, and vendor lookups
  (Arista/Umbrella/Corelight/PAN firewall) are XSIAM/XDR; Guardian pivoted to XSOAR-only. Out of scope. (Many remain
  reachable opportunistically via `run_command` with the right `!xdr-*` command, but no dedicated tools.)
- **No `close_investigation` tool.** The existing `close_incident` (`POST /incident/close`) already closes the
  incident and its investigation; a separate tool would be redundant (operator decision).
- **No new installer change.** `playground_id` is a runtime connector-instance config field, backwards-compatible.
- **No credential surface.** None of these tools read/write a SecretStore value; they are connector tools, not
  credential-management tools — consistent with the agent credential guardrail.

## 3. Architecture

**REST-native where the endpoint is stable; the playground engine only where XSOAR exposes a capability solely as a
war-room command.** All 8 tools follow the existing connector pattern exactly:

```
xsoar_<name>(...)  ──@_wrap_xsoar_call──▶  _get_fetcher()  ──▶  XSOARFetcher.post/get(path, body)
        │                    │                                         │
   async fn,           catches 6 exc types                    dual v6/v8 auth:
   declared in         → {ok:false, error, retryable?,         Authorization:<key> always,
   connector.yaml         is_auth_error?}                      + x-xdr-auth-id:<id> if v8,
   spec.tools[]         success → {ok:true, ...}               + /xsoar/public/v1 prefix if v8
```

The existing `XSOARFetcher._full_url()` already prepends `/xsoar/public/v1` only on v8/Cortex, so calling
`fetcher.post('/entry/execute/sync', …)` resolves correctly on **both** generations — the new tools need **no new HTTP
machinery**, only new logical paths + request shapes.

### Three cohesive groups

| Group | Tools | Mechanism | Needs `playground_id`? |
|---|---|---|---|
| **A — Command engine** | `run_command`, `enrich_indicator`, `complete_task` | `POST /entry/execute/sync` + context retrieval | **Yes** |
| **B — XSOAR Lists** | `get_list`, `set_list`, `append_to_list` | `GET /lists/` + `POST /lists/save` | No |
| **C — Incident lifecycle** | `create_incident`, `run_playbook` | `POST /incident`, `POST /inv-playbook/{pb}/{inv}` | No |

## 4. The command engine (shared internals)

A private helper `_execute_command(fetcher, playground_id, command, return_context_keys=None)` implements the
workaround once; `run_command`, `enrich_indicator`, and `complete_task` all call it.

**Flow** (ported from `docs/ref/trevor-mcp.py:489-577`):
1. **Resolve playground** — read `playground_id` from config. If blank → return
   `{ok:false, error:"playground_id is not configured; set it on the XSOAR instance to use command execution"}`.
   No auto-discovery (operator decision: it's a config parameter).
2. **Clear context** (only if `return_context_keys` given) — for each key:
   `POST /entry {investigationId: playground_id, data: "!DeleteContext key=<key>"}`. Failures are logged, non-fatal.
3. **Execute** — `POST /entry/execute/sync {investigationId: playground_id, data: <command>}`.
4. **Parse entries** — response is a list (or single) of war-room entries: `type==1` → skip (metadata);
   `type==4` → error (use `contents` as the error message); else → collect `contents` text. Concatenate to
   `output`. Empty → `"Command executed (no text output returned)."`.
5. **Retrieve context** (only if `return_context_keys` given) — for each key:
   `POST /investigation/{playground_id}/context {query: "${<Key>}"}` → collect into `{key: value}`. Note the
   uppercase `${Key}` syntax is literal XSOAR context-path syntax.

**Returns** (success): `{ok:true, output: <war-room text>, context: {<key>: <value>, …} | null}`.

**Playground-not-found detection** — if the execute call raises `XSOARRequestError` whose message contains
`"Could not find investigation"` or `"noInv"`, return a specific
`{ok:false, error:"playground '<id>' not found — check the playground_id on the instance"}` rather than the raw 4xx.

### 4.1 `run_command`
- **Signature:** `xsoar_run_command(command: str, return_context_keys: str = None)`
- `command` — full XSOAR command, e.g. `"!ip ip=8.8.8.8"`. `return_context_keys` — optional comma-separated keys,
  e.g. `"IP,DBotScore"`.
- Thin wrapper over `_execute_command`.

### 4.2 `enrich_indicator`
- **Signature:** `xsoar_enrich_indicator(indicator_type: str, value: str)`
- `indicator_type ∈ {ip, url, domain, file, cve}` (normalized lowercase). Unknown type →
  `{ok:false, error:"unsupported indicator_type '<x>' (expected ip|url|domain|file|cve)"}`.
- **cmd_map** (from `trevor-mcp.py:580`): the indicator value is double-quoted into the command.

  | type | command | return context keys |
  |---|---|---|
  | ip | `!ip ip="<value>"` | `IP,DBotScore,IPinfo,AutoFocus` |
  | url | `!url url="<value>"` | `URL,DBotScore,AutoFocus` |
  | domain | `!domain domain="<value>"` | `Domain,DBotScore,Whois,AutoFocus` |
  | file | `!file file="<value>"` | `File,DBotScore` |
  | cve | `!cve cve_id="<value>"` | `CVE` |
- Calls `_execute_command(command, return_context_keys=<keys>)`. Returns
  `{ok:true, indicator_type, value, output, context}`.

### 4.3 `complete_task`
- **Signature:** `xsoar_complete_task(incident_id: str, task_id: str, comment: str = None)`
- Builds the documented command: `!taskComplete id=<task_id> incidentId=<incident_id>` (+ ` comment="<comment>"` if
  given). `taskComplete` is an automation/war-room command (confirmed: xsoar.pan.dev/docs/integrations/task-complete),
  **not** a REST endpoint, so engine-based execution is the version-stable path.
- Runs via `_execute_command` (no context keys). Returns `{ok:true, incident_id, task_id, output}`.

## 5. Group B — XSOAR Lists (direct REST)

The reference code's "lists" are XSIAM **dataset-lookups** (`/public_api/v1/xql/lookups/*`) — XSIAM-specific and out
of scope. The correct XSOAR-only equivalent is the **XSOAR Lists API**.

### 5.1 `get_list`
- **Signature:** `xsoar_get_list(name: str)`
- `GET /lists/` returns all lists (each with `name`, `data`, `type`). Filter by `name`.
- Not found → `{ok:false, error:"list '<name>' not found"}`.
- Returns `{ok:true, name, data, type}` (`type` is `plain_text` or `json`).

### 5.2 `set_list`
- **Signature:** `xsoar_set_list(name: str, data: str, type: str = "plain_text")`
- `POST /lists/save {name, data, type}` — **overwrites** the list contents (creates if absent).
- Returns `{ok:true, name, type}`.

### 5.3 `append_to_list`
- **Signature:** `xsoar_append_to_list(name: str, value: str)`
- Read current via the `get_list` internal; append: for `plain_text`, join existing + `value` with `\n` (skip leading
  `\n` if the list was empty); for `json`, parse the array, push `value`, re-serialize. Then `POST /lists/save`.
- If the list doesn't exist yet → create it as `plain_text` with `value`.
- Returns `{ok:true, name, data, type}`.

## 6. Group C — Incident lifecycle (direct REST)

### 6.1 `create_incident`
- **Signature:** `xsoar_create_incident(name: str, type: str = None, severity: int = None, details: str = None,
  owner: str = None, labels: list = None, custom_fields: dict = None, create_investigation: bool = True)`
- `POST /incident` with body assembled from non-None args:
  `{name, type, severity, details, owner, labels:[{type,value}…], createInvestigation, CustomFields:{…}}`.
  `severity` is the XSOAR int scale 0–4. `labels` accepts a list of strings → mapped to
  `[{"type":"Label","value":"<s>"}]`; `custom_fields` is passed through as `CustomFields`.
- Returns `{ok:true, incident_id, name, raw_response}` (parse the created incident's `id` from the response).
- Grounded: docs-cortex "Create or update an incident" (`POST /incident`).

### 6.2 `run_playbook`
- **Signature:** `xsoar_run_playbook(incident_id: str, playbook_id: str)`
- `POST /inv-playbook/{playbook_id}/{incident_id}` — assigns the playbook to the investigation and starts it.
- Returns `{ok:true, incident_id, playbook_id, raw_response}`.
- ⚠️ **OPEN ITEM (live-verify):** the exact `/inv-playbook/{playbookId}/{invId}` path + body is the widely-documented
  XSOAR endpoint but is **not** in the mined reference code. Verify against the live Cortex XSOAR 8 tenant during the
  build (we have validated access — see task #19). If the path differs on v8/Cortex, adjust + document. **Fallback if
  no REST endpoint is exposed:** set the playbook on the incident via `update_incident` (`playbookId` field) — tracked,
  not silently deferred.

## 7. Config — the `playground_id` field

Add to `connector.yaml` `configSchema.properties` (operator decision: a config parameter collected at instance
creation):

```yaml
playground_id:
  type: string
  description: >-
    Playground / War Room investigation ID used to run XSOAR commands
    (required for run_command, enrich_indicator, complete_task). Find it in
    XSOAR: open your Playground, copy the investigation ID from the URL.
```

- **Optional** in `configSchema.required` (NOT added to `required[]`) so existing instances + the 13 non-command tools
  keep working unchanged — backwards-compatible. The 3 engine tools return a clean, operator-actionable error if it's
  blank.
- Read it in `_get_xsoar_config()` (add `playground_id` to the returned dict via
  `getattr(proxy, "playground_id", None)`), thread it to the engine tools.

## 8. Data flow (run_command example)

```
agent → xsoar_run_command(command="!ip ip=8.8.8.8", return_context_keys="IP,DBotScore")
  → _get_xsoar_config() → {api_url, api_id, api_key, verify_ssl, playground_id}
  → playground_id blank? → {ok:false, error:"playground_id not configured…"}   [guard]
  → _execute_command:
      POST /entry {investigationId: pg, data:"!DeleteContext key=IP"}          [clear]
      POST /entry {investigationId: pg, data:"!DeleteContext key=DBotScore"}
      POST /entry/execute/sync {investigationId: pg, data:"!ip ip=8.8.8.8"}    [execute]
      parse entries → output text
      POST /investigation/{pg}/context {query:"${IP}"}                         [retrieve]
      POST /investigation/{pg}/context {query:"${DBotScore}"}
  → {ok:true, output:"…", context:{IP:{…}, DBotScore:{…}}}
```

## 9. Error handling

Reuses the existing 6-type exception → envelope mapping in `_wrap_xsoar_call`:
`XSOARAuthError`→`is_auth_error`, `XSOARRateLimitError`/`XSOARServerError`→`retryable`, others→plain `error`.

Tool-specific guards (all return `{ok:false, error}`):
- engine tools: `playground_id` blank; playground-not-found (4xx with `noInv`/`Could not find investigation`).
- `enrich_indicator`: unknown `indicator_type`.
- `get_list`: list not found.
- `append_to_list`: malformed existing JSON list (surface, don't silently overwrite).

## 10. Testing

Follow `tests/test_connector.py` exactly — `_FakeAsyncClient` records `{method, url, headers, json}` + returns queued
`_FakeResponse`; assert request shape (URL has the right base + v8 prefix, headers have Authorization + x-xdr-auth-id
on v8) and the `{ok, …}` envelope. Per tool, for **both v6 and v8**:

- `run_command`: asserts the `/entry/execute/sync` body `{investigationId, data}`; entry parsing (type 1 skip / type 4
  error / contents); context clear + retrieve calls; blank-`playground_id` guard.
- `enrich_indicator`: asserts the cmd_map command string per type; unknown-type guard.
- `complete_task`: asserts the `!taskComplete id=… incidentId=…` command string.
- `get_list`/`set_list`/`append_to_list`: assert `/lists/` GET filter, `/lists/save` POST body, append for both
  `plain_text` (newline) and `json` (array push); not-found behavior.
- `create_incident`: asserts `/incident` body assembly (labels mapping, CustomFields, createInvestigation, omit None).
- `run_playbook`: asserts `POST /inv-playbook/{pb}/{inv}` path.

**Pre-deploy gate** (root CLAUDE.md): `PYTHONPATH=$PWD/src python3 -m pytest tests/ -x` in `bundles/spark/mcp` (the
embedded MCP) AND the connector's own tests; plus tsc/lint/build on the agent (no agent-side change expected, but the
gate runs anyway).

**Live smoke** (agent-side headless, against guardian-vm per the dev cycle): set `playground_id` on the live XSOAR
instance → `run_command "!Print value=hello"` returns the printed text → `enrich_indicator ip 8.8.8.8` returns a
DBotScore → `get_list`/`set_list`/`append_to_list` round-trip a test list → `create_incident` returns an id →
`run_playbook` verified (or the endpoint adjusted) → `complete_task` on a test incident's task. Per the connector-system
end-to-end probe contract, hit `POST /api/v1/instances/<id>/test` and a `tools/call` dispatch.

## 11. Docs (ship with the code, same arc)

- **Architecture page** (`app/help/architecture/page.tsx`): one new anchor `#xsoar-actions` documenting the expanded
  action surface — the command engine + playground_id, Lists, lifecycle — and the inter-service path (agent → MCP →
  connector container → XSOAR `/entry/execute/sync`).
- **User guide** (`app/help/user/page.tsx`): one `#xsoar-actions` subsection — what the operator can now ask Guardian
  to do, and that `playground_id` must be set on the instance for command/enrich/complete_task.
- **Journeys** (`lib/journeys.ts`): a click-path — create XSOAR instance with `playground_id` → ask Guardian to run a
  command / enrich an indicator.
- **`connector.yaml`** `spec.tools[]`: 8 new entries (bare names, args, returns) — required for the agent catalog to
  see them.
- **`CHANGELOG.md` + `mcp/agent/lib/release-notes.ts`:** the operator-visible delta (newest first in release-notes).
- **MCP tool docstrings:** the connector functions' docstrings ARE the agent-facing contract — each gets a complete
  Args/Returns docstring with "when to use" guidance.

## 12. Release shape

- **Change scenario: 1** (code-only; installer unchanged; `playground_id` is a backwards-compatible optional config
  field; volumes preserved) → **minor version bump**, customers re-run the existing installer.
- **One capability arc**, 3 commits (Group A → B → C), each self-contained with tests + its slice of docs; the arc's
  docs anchor (`#xsoar-actions`) lands incrementally. **Tag once** at arc completion, only after all 8 tools are
  live-verified on the tenant (and `run_playbook`'s endpoint confirmed/adjusted).
- **GitHub issue** opened before code (spec-driven workflow); commits reference it via `Refs #N`; mid-arc commits get
  CHANGELOG entries naming their prerequisite role.

## 13. Decisions captured

- **`playground_id`:** a config parameter on the instance-create form, **optional in schema** (backwards-compatible),
  **no auto-discovery**. (Operator-approved.)
- **`complete_task` only**, no `close_investigation` (redundant with `close_incident`). (Operator-approved.)
- **Lists target the XSOAR Lists API**, not the ref's XSIAM dataset-lookups. (Design correction.)
- **`complete_task` via the command engine** (`!taskComplete`), since taskComplete is a command not a REST endpoint.
- **REST-native + playground-only-where-required** (Approach A) over all-via-playground (B) or all-REST (C).

## 14. Open items (resolved in the plan / at build time)

- **`run_playbook` endpoint** — confirm `POST /inv-playbook/{playbookId}/{invId}` path + body against the live Cortex
  XSOAR 8 tenant during the build; fallback to `update_incident` `playbookId` if not exposed (§6.2).
- **`get_list` retrieval shape** — confirm `GET /lists/` returns `data` inline per list on the live tenant; if a v8
  tenant requires `GET /lists/{name}` or a download path instead, adjust the `get_list` internal (single point of
  change, also used by `append_to_list`).
- **Whether `complete_task` should also accept a `tag` instead of `task_id`** — the `taskComplete` command supports
  tag-based identification; start with `task_id` only, add `tag` later if a use case emerges (YAGNI).
