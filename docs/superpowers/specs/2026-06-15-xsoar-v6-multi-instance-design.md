# Multi-active-instance connectors + XSOAR v6/v8 — design

**Date:** 2026-06-15
**Status:** approved (operator answered the 3 design forks; full autonomy granted incl. release)
**Scenario:** 1 (code-only, installer unchanged, volumes preserved, minor bump)

## Goal

Let a single connector run **multiple enabled instances at once**, and let the
agent pick which one a tool call targets via an **`instance` argument**. First
real user: two XSOAR tenants live simultaneously — XSOAR 6 (on-prem) + XSOAR 8
(Cortex cloud) — with the agent routing per prompt ("investigate the v6 case" →
the call carries `instance: "xsoar-v6"`).

## Operator decisions (locked)

1. **Routing model:** both instances live; agent selects via an `instance`
   argument (NOT name-discriminated tool names).
2. **Scope:** general multi-instance capability for any connector; ship + validate
   with XSOAR v6+v8 first.
3. **Version field:** explicit `Version` dropdown (v6/v8) on the form; also make
   connector.yaml `enum` config fields render as dropdowns natively.

## Current reality (from the codebase map)

- **`instance_store.py`** — schema is `UNIQUE(connector_id, name)`, so multiple
  rows per connector are allowed, BUT `create()`/`update()` raise `ValueError`
  ("one enabled per connector") if a second `enabled=True` instance is requested
  → HTTP 409. (lines ~325-332, ~487-493; dataclass docstring ~63-66.)
- **`connector_loader.iter_registrations()`** — for each connector with ≥1
  instance row, hard-picks `primary = instances[0]` (alphabetical by name) and
  registers each tool ONCE, wrapped bound to that one instance. No instance
  discriminator anywhere. Explicit TODO comment at lines 953-957 names exactly
  this follow-up.
- **`_build_container_proxy()`** (lines 379-494) — synthesizes an async fn whose
  signature mirrors `connector.yaml` args; body reads `get_config().container_url`
  (a ContextVar) at call time and POSTs to the container. FastMCP introspects
  THIS signature (the wrapper copies it via `functools.wraps`).
- **`_wrap_with_instance()`** (lines ~636-876) — sets the ContextVar to the bound
  instance's `merged_config`, runs the approval gate (per-instance `trusted`
  bypass), records audit (`instance_id`/`instance_name`), calls the proxy.
- **XSOAR connector** — generation is detected from `api_id` presence (blank → v6:
  `Authorization` header only, no path prefix; set → v8: adds `x-xdr-auth-id` +
  `/xsoar/public/v1`). All 23 tools generation-agnostic; only `_full_url()` +
  `_headers()` branch. No explicit `version` field.
- **Config dropdowns** — render when `ConfigParam.type === "select"` + `options[]`.
  `loadLiveMeta()` in `route.ts` does NOT map connector.yaml `enum` → `select`, so
  today a dropdown requires hardcoding in `GUARDIAN_CONNECTORS[]`.
- **Agent awareness** — the agent sees a flat tool list (name + description). It
  has ZERO signal about instances; the system prompt never lists them.

## Design

### A. Lift the one-enabled-per-connector guard (`instance_store.py`)

Remove the `ValueError` in `create()` + `update()` that blocks a second
`enabled=True` instance for the same `connector_id`. Keep `UNIQUE(connector_id,
name)`. Update the dataclass docstring + the tests that assert the 409.

### B. Per-connector shared tool set + call-time instance resolution (`connector_loader.py`)

- `iter_registrations()`: replace `primary = instances[0]` with
  `enabled = [i for i in store.list_for(cid) if i.enabled]`. If `enabled` is
  empty → skip the connector (advertise gate now = ≥1 ENABLED instance, not just
  ≥1 row). `multi = len(enabled) > 1`.
- Register each tool ONCE (shared `cid.tool` + legacy alias, unchanged names).
- **`instance` parameter (only when `multi`):** thread `instance_names` through
  `_resolve_callable()` → `_build_container_proxy()`. When `multi`, add an
  optional `instance: str = None` parameter to the synthesized signature (last),
  and EXCLUDE it from the args dict forwarded to the container. When single,
  synthesize exactly as today (no `instance` param → existing setups byte-identical).
- **Wrapper resolves at call time:** generalize `_wrap_with_instance` →
  `_wrap_connector_tool(raw_fn, enabled_instances, ...)`. Per call:
  - `inst_arg = kwargs.pop("instance", None)`.
  - Resolve `target`: by exact name, then case-insensitive; if `inst_arg` is
    None and not `multi` → the single instance; if None and `multi` → raise a
    clear error listing valid names (NO silent wrong-tenant); if unmatched →
    raise listing valid names.
  - Set the ContextVar to `target.merged_config` (translated keys).
  - Approval gate computed per call: `instance_trusted = target.config.trusted`.
  - Audit `instance_id`/`instance_name` = the resolved target.
  - Per-instance `disabled_tools`: catalog = union across enabled instances (a
    tool is hidden only if disabled by EVERY enabled instance); at call time, if
    `target` disabled the tool, return a clear "disabled for this instance" error.
- **Description augmentation (only when `multi`):** after wrapping, append to
  `wrapped.__doc__` a line naming the valid `instance` values + roles so the
  agent sees them inline in the tool description.

### C. Enable/disable triggers a tool reload

Creating a second instance already triggers re-registration via the
container-start → `PUT /container_url` → `reload_tools_now()` path. Ensure the
PATCH `enabled` path also calls `reload_tools_now()` so single↔multi transitions
update the schemas (the `instance` param appears/disappears).

### D. XSOAR explicit `version` field (`xsoar/connector.yaml` + `src/`)

- `connector.yaml configSchema`: add `version` — `type: string`, `enum: ["v6","v8"]`,
  optional, with a clear description. (Keep `api_id` — still the v8 auth key id.)
- `src/connector.py _get_fetcher()`: if `version` config is set, force the
  generation (`v8` → `is_v8=True`; `v6` → `is_v8=False`); else fall back to the
  existing `api_id`-presence inference (backward compat for existing instances).
- Connector tests for the explicit-version override + the inference fallback.

### E. connector.yaml `enum` → dropdown (`route.ts`)

- Extend `loadLiveMeta()`: read `enum` from configSchema properties; when a
  `string` property has a non-empty `enum`, emit `type: "select", options: enum`.
- Update the `ConfigParam`/`MarketplaceConnector.config` types to carry `options`.
- Result: the XSOAR `version` dropdown renders from connector.yaml alone (no
  hardcoding in `GUARDIAN_CONNECTORS[]`), and so does any future enum field.

### F. Agent awareness — "Connected instances" system-prompt block (`system-prompt.ts`)

- Add a dynamic block to `buildSystemPromptText()` listing, per connector with
  2+ enabled instances, the instance names + a role hint (for XSOAR: derived
  `v6`/`v8` from the instance's `version`/`api_id`). Tells the agent which
  `instance` value maps to which tenant. Complements the schema-level `instance`
  param + its description.

## Data flow (multi-instance tool call)

```
agent → tools/call xsoar_list_incidents {status:"active", instance:"xsoar-v6"}
  → wrapper pops instance="xsoar-v6" → resolve target = the v6 instance
  → set ContextVar = v6.merged_config (container_url = v6 container)
  → approval gate (v6.trusted?) → audit (instance_id=v6)
  → synthesized proxy reads container_url → POST {status:"active"} to v6 container
  → v6 connector (is_v8=False) → XSOAR 6 on-prem at api_url
```

## Error handling

- `instance` omitted with 2+ enabled → structured error listing valid names
  (forces the agent to be explicit; no silent default).
- `instance` unknown → error listing valid names.
- Tool disabled for the resolved instance → clear per-instance error.
- Container not started for the target → existing "no container_url" error +
  v0.2.28 self-heal restarts it within the reconcile interval.

## Testing

- `instance_store`: multiple enabled instances per connector now allowed; the
  former 409 tests are updated to assert success.
- `connector_loader`: single-instance path unchanged (no `instance` param);
  multi-instance path adds `instance`, resolves by name, errors on missing/unknown,
  routes ContextVar to the right instance. New unit tests.
- `xsoar` connector: explicit `version` override + `api_id` inference fallback.
- Live smoke on guardian-vm: two enabled xsoar instances (v6 on the xsoar6 VM
  `10.10.0.71` + v8 cloud + the new Core-API v8); 15-20 mixed prompts verify the
  agent passes the right `instance` and the right tenant is hit; plus
  `xsoar_import_playbook` on v8 (now that the Core REST API integration exists).

## Acceptance (capability complete)

Two enabled XSOAR instances coexist; the agent, prompted about a v6 case, calls
the tool with `instance="xsoar-v6"` and the v6 tenant is hit; prompted about v8,
it targets v8. 15-20 mixed prompts route correctly with no cross-tenant leakage.
Single-tenant connectors (cortex-docs, web, xsiam) are completely unchanged.

## Out of scope (YAGNI)

- Name-discriminated tool names (operator chose the argument approach).
- Active-active load balancing / failover across instances.
- Per-instance enum in the JSON schema (string + rich description + system-prompt
  block is sufficient; can add a dynamic `enum` later if the agent mis-routes).
