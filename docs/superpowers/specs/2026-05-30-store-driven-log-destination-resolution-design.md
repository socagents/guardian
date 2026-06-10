# Store-driven log-destination resolution — design

**Date:** 2026-05-30
**Status:** Approved (brainstorming complete) — ready for implementation plan
**Scenario:** 1 (code-only · patch bump · volumes preserved)
**Target version:** v0.17.111 (single contained release)

---

## Problem

When Phantom generates simulated logs, the target destination is **not** resolved from the operator-configured **Log Destinations** (`log_destinations.db`). Instead it comes from three hardcoded/disconnected paths:

1. A caller-supplied raw string passed to `phantom_create_data_worker(destination=…)` (default `"XSIAM_WEBHOOK"`).
2. The `XSIAM_WEBHOOK` sentinel → xlog reads `WEBHOOK_ENDPOINT`/`WEBHOOK_KEY` **env vars** (not the store row).
3. The chat skill's default from `phantom_get_technology_stack` (xlog's *own* config store).

Consequences: editing a destination's URL in the UI does **not** change where live workers send; a bare "simulate FortiGate logs" does not route to the operator's configured destination; `dispatch_send()` (the would-be bridge) is dead code; the architecture page (`#log-destinations`) claims a wired `send()` path that does not exist.

## Goal

**No hardcoded log destination.** When a prompt names a log source, the agent resolves the destination **from the operator's configured Log Destinations** — using it silently when unambiguous, asking when not, and able to cold-start a plain syslog destination itself. The secret-bearing path becomes store-driven too, with the agent never seeing the secret.

## Non-goals

- `webhook` and `splunk_hec` destination types — **out of scope** (not wired into xlog; the agent already tells the operator they're tracked for a later release).
- Any change to the Log Destinations CRUD UI, the destination types, or the secret-at-rest model.
- Letting the agent create or read secret-bearing destinations (credential guardrail stays intact).

---

## Resolution model (the operator's confirmed flow)

1. **Derive transport** for the run, priority order:
   - (a) explicit operator words ("via syslog", "to the HTTP collector"); else
   - (b) the data source's declared format — CEF/LEEF/syslog → `type_id=syslog`; raw-JSON/HTTP-collector → `type_id=xsiam_http`.
2. **List** destinations of that type (`log_destinations_list(type_id=…)`).
3. **Branch on count:**
   - **1** → use it silently.
   - **2+** → if the prompt named one (match on `name` OR on `host`/IP) → use that; else **stop and ask** the operator to pick from the list. Never guess.
   - **0** → if `syslog` → **offer to create** it (secretless, see below); if a secret type → **guide** the operator to the UI (do not create). Re-resolve after.
4. **Format** the choice and call the worker:
   - syslog → `destination="<protocol>:<host>:<port>"` (no secret).
   - xsiam_http → `destination="logdest:<id>"` (a reference; the MCP resolves URL + secret — see §4).

---

## Components

### 1. Resolution recipe — lives in the simulation skills
**Files:** `bundles/spark/skills/generate-logs.md`, `bundles/spark/skills/run-scenario.md`

Both worker-creating skills get the step-by-step recipe above (transport → list → count → use/ask/create → format). Replaces today's "use `phantom_get_technology_stack.full_address`" guidance. Keep it tight and deterministic so the LLM follows it reliably.

### 2. System-prompt invariant
**File:** `mcp/agent/lib/system-prompt.ts`

One line, always in force even outside the skill:
> *"Never hardcode or invent a log destination. Always resolve the target from the operator's configured Log Destinations (`log_destinations_list`); if none match, ask or offer to create one — never fall back to a hardcoded address."*

### 3. New MCP tool — `log_destinations_create` (secretless syslog only)
**Files:** `bundles/spark/mcp/src/usecase/connector_loader.py` (register in `_BUILTIN_LEGACY_TOOLS`), handler wrapping `log_destinations_store.create()`.

- Args: `name, host, port, protocol` (`udp`|`tcp`).
- **Structurally rejects** anything that would write a secret: `type_id` is forced to `syslog`, protocol must be `udp`/`tcp` (not TLS), no secret slots. Any secret-bearing request returns a clear "add this type in the UI" message.
- **`is_default`:** if no destination of `type_id=syslog` exists yet, the created one is marked `is_default=True` (cold-start convenience, operator-confirmed). Otherwise created enabled, not default.
- **Guardrail classification:** writes **no SecretStore value** → *catalog* side of the boundary → safe to expose as an `mcp.tool()`. Documented in CLAUDE.md's catalog-vs-credential section.

### 4. Worker tool + the secret resolution (the load-bearing piece)
**Files:** `bundles/spark/connectors/xlog/src/workers.py`, `bundles/spark/mcp/src/usecase/connector_loader.py` (`proxy_call_tool`), `xlog/app/schema.py`.

- **`workers.py`:** remove the hardcoded `destination="XSIAM_WEBHOOK"` default → destination becomes **required**. Accept optional MCP-injected `webhook_url` / `webhook_key`. Rewrite the docstring (retire the "XSIAM_WEBHOOK reads env" guidance; document the resolved-by-MCP contract).
- **`proxy_call_tool()` (the dispatch chokepoint, runs in the MCP / phantom-agent — the only layer that can read the store *and* secrets):** when a `phantom_create_data_worker` call carries `destination="logdest:<id>"`, resolve it from `log_destinations_store` (with secrets, via the existing loopback `include_secrets` path) **before forwarding to the connector**:
  - `type_id=syslog` → rewrite `destination` → `"<protocol>:<host>:<port>"`.
  - `type_id=xsiam_http` → set `destination="XSIAM_WEBHOOK"` and inject `webhook_url` + `webhook_key` from the row. The secret travels only MCP→connector over the internal Docker network; the agent (LLM) never sees it.
- **`xlog/app/schema.py`:** the `createDataWorker` mutation input gains optional `webhookUrl` / `webhookKey`; the `XSIAM_WEBHOOK` branch (≈ line 644, `_get_webhook_headers` + `WebhookSender`) uses the passed values when present, falling back to the env vars only if absent. This retires the `WEBHOOK_ENDPOINT`/`WEBHOOK_KEY` hardcode as the authoritative source.

### 5. Spec-drift fix + dead code
**Files:** `mcp/agent/app/help/architecture/page.tsx` (`#log-destinations`).

Rewrite the section to describe the actual resolution path (store → MCP dispatch resolution → xlog), and remove the "`send()` forwards a batch" claim that implies a wired delivery path. `dispatch_send()` in `destination_handler_registry.py` stays for probe symmetry but the doc no longer implies it's the generation path. (Optional: a code comment marking it probe-only.)

---

## Data flow (end state)

```
operator: "simulate 50 FortiGate logs"
  → skill derives transport: CEF → type_id=syslog
  → log_destinations_list(type_id="syslog")   [secrets sentinel'd; agent-safe]
  → count==1 → choose it   (==2+ → match name/IP or ASK; ==0 → create syslog / guide)
  → phantom_create_data_worker(type=CEF, vendor=Fortinet, product=FortiGate,
                               destination="logdest:<id>")
  → MCP proxy_call_tool() resolves logdest:<id> from the store:
        syslog     → destination="udp:10.10.0.8:514"
        xsiam_http → destination="XSIAM_WEBHOOK" + webhook_url/key injected
  → forwards resolved args to phantom-connector-xlog:9000
  → xlog createDataWorker uses the resolved address (+ passed url/key for webhook)
  → Sender / WebhookSender → wire → XSIAM / syslog broker
```

The agent only ever holds a destination **reference** (`logdest:<id>`) or a secretless `udp:host:port`. Secrets resolve inside the MCP.

## Security / guardrail analysis

- **Agent never writes a secret:** `log_destinations_create` is secretless-syslog-only (structural). Secret-bearing destinations remain UI/REST-only.
- **Agent never reads a secret:** `log_destinations_get`/`list` keep the `"***"` sentinels. The real secret is read only inside `proxy_call_tool()` (MCP, MCP_TOKEN-gated loopback) and travels MCP→connector internally.
- **Injection safety:** the agent only creates/routes on explicit operator instruction. The create tool cannot point at an arbitrary secret endpoint (no secret slot). Routing to an existing destination cannot exfiltrate a secret (the agent passes a reference, not the value).

## Error handling / edges

| Situation | Behavior |
|---|---|
| 0 destinations, syslog | Offer to create (secretless); on yes, create + use. |
| 0 destinations, secret type | Explain + point to the Log Destinations UI; do not create. |
| 2+ of the type, none named | List them; ask the operator to choose. Never guess. |
| Operator asks agent to create a secret type | Refuse + explain the guardrail + point to UI. |
| Resolved destination's last probe failed | Warn but proceed (operator's call). |
| `logdest:<id>` not found at dispatch | Return a clear tool error; do not fall back to a hardcoded address. |

## Testing

- **MCP (`bundles/spark/mcp/tests/`):** `log_destinations_create` happy path (syslog) + rejects TLS-syslog/xsiam_http/splunk_hec; `is_default` set only when first of type. `proxy_call_tool` resolution: `logdest:<id>` syslog → `udp:host:port`; xsiam_http → injects url/key; unknown id → error.
- **xlog (`xlog/tests/`):** `createDataWorker` with `webhookUrl`/`webhookKey` uses passed values; absent → env fallback.
- **E2E (headless, phantom-vm):** configure one syslog destination → "simulate FortiGate" routes there with no hardcoded address; two syslog destinations → agent asks; zero → agent creates. Verify via the xsiam connector XQL that records land in the expected dataset.

## Docs impact (same release)

- `mcp/agent/app/help/architecture/page.tsx` `#log-destinations` — resolution flow + drift fix.
- `mcp/agent/app/help/user/page.tsx` — "Phantom routes simulated logs to your configured Log Destinations; it asks when ambiguous and can create a plain syslog destination for you."
- `mcp/agent/lib/journeys.ts` — a "simulate → auto-routed destination" journey.
- `CHANGELOG.md` + `mcp/agent/lib/release-notes.ts` — v0.17.111.
- `CLAUDE.md` — catalog-side note for `log_destinations_create`; the MCP-dispatch secret-resolution contract.
- `workers.py` docstring — updated per §4.

## Rollout / migration

Scenario 1, volumes preserved. Existing installs already have a migrated `xsiam_http` row (`migrate_webhook_endpoint_to_destination()` at boot). After this release xlog uses the **row** (via MCP resolution); the `WEBHOOK_ENDPOINT`/`WEBHOOK_KEY` env vars stay only as the migration bootstrap + a fallback. A customer who never edited the row sees identical behavior; one who edited the URL now has it honored (the fix). No storage-schema change.

## Open items to pin during planning

1. Exact arg-injection shape for `webhook_url`/`webhook_key` through `proxy_call_tool` → connector → `createDataWorker` mutation input (camelCase mapping).
2. Whether `run-scenario.md`'s `phantom_create_scenario_worker` shares the same `destination` resolution (likely yes — same `CreateDataWorkerRequest`).
3. Confirm `log_destinations_store` exposes a secretless-create + an `include_secrets` read usable from `proxy_call_tool` without a network hop (same process).
