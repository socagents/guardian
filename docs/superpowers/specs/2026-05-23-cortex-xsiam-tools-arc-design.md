# R5 — Cortex XSIAM tools arc (v0.15.0 → v0.15.4)

**Status**: Approved 2026-05-23 — autonomous implementation per operator directive (multi-day OK).

## Goal

Mirror R4's XDR arc for the XSIAM connector. Expand from 14 existing tools to ~61 covering the full Cortex XSIAM public API. Reuses R4.0's per-instance `disabled_tools` infrastructure (instances.db column, connector_loader filter, Tools toggle UI) — no new infra needed.

## Non-goals

- Refactoring XDR + XSIAM into a SHARED cortex-public-api library (deferred to a future arc; both share the same `/public_api/v1/...` surface but the consolidation is its own design)
- Scraping authentication-protected XSIAM docs (use ebarti scaffold where possible + Chrome MCP only when needed for XSIAM-unique surfaces)
- Auto-rotating XSIAM credentials (credential-guardrail)

## Baseline (existing 14 tools in xsiam connector.yaml)

```
xsiam_run_xql_query
xsiam_get_cases
xsiam_send_webhook_log
xsiam_add_lookup_data
xsiam_get_lookup_data
xsiam_remove_lookup_data
xsiam_get_datasets
xsiam_create_dataset
xsiam_find_xql_examples_rag
xsiam_get_dataset_fields
xsiam_get_xql_examples
xsiam_get_asset_by_id
xsiam_get_assets
xsiam_get_issues
```

These follow `xsiam_*` naming already — NO renames needed. They cover XQL + cases/issues + assets + lookup tables + the local RAG.

## Phased delivery (~47 net-new tools)

| Release | Scope | New tools | Notes |
|---|---|---|---|
| **R5.0 (v0.15.0)** | Docs pull + spec | 0 | `data/knowledge/external/paloaltonetworks/cortex-xsiam/action/` populated. Audit existing tools, classify coverage gaps. |
| **R5.1 (v0.15.1)** | Incidents + Alerts + IoC + Download | ~12 | Same shape as R4.1 — `xsiam_incidents_*`, `xsiam_alerts_*`, `xsiam_ioc_*`, `xsiam_download_*`. |
| **R5.2 (v0.15.2)** | Endpoints + Response + Scripts | ~15 | Mirrors R4.2 with `xsiam_*` prefix. |
| **R5.3 (v0.15.3)** | Admin endpoints + XSIAM-unique | ~20 | audit/distribution/exclusions/hash/exploits/asset-admin from R4.3 + **XSIAM-unique**: parsers, datamodel introspection, broker config. |
| **R5.4 (v0.15.4)** | E2E battery + UI verification + screenshots | 0 | `scripts/e2e_xsiam_tools_battery.py` mirrors R4.4. Playwright screenshots both XDR + XSIAM Tools panels (or operator-hands-on path documented if credential guardrail blocks). |

## Tool naming convention

`xsiam_<category>_<action>` — flat snake_case, same as `xdr_*`. Examples:
- `xsiam_incidents_list`, `xsiam_incidents_get_extra_data`, `xsiam_incidents_update`
- `xsiam_alerts_list`, `xsiam_alerts_update`
- `xsiam_endpoints_list`, `xsiam_endpoints_isolate`, etc.
- `xsiam_xql_*` (rename `xsiam_run_xql_query` → `xsiam_xql_run_query`? — TBD in R5.0 audit)
- `xsiam_parsers_list`, `xsiam_parsers_create`, `xsiam_parsers_delete` (XSIAM-unique)
- `xsiam_datamodel_describe` (XSIAM-licensed; XDR returns "Invalid License" here)
- `xsiam_broker_list` (XSIAM-unique)

## Repo conventions

### Vendor knowledge tree

```
data/knowledge/external/
  paloaltonetworks/
    cortex-xsiam/                              # NEW (parallel to cortex-xdr/)
      action/
        INDEX.md                                # cross-ref every endpoint → tool
        auth.md                                 # shares the same scheme as XDR
        incidents/, alerts/, endpoints/, response/, scripts/, ioc/, download/,
        audit/, assets/, distribution/, alert-exclusions/, exploits/, hash/,
        parsers/, datamodel/, broker/           # XSIAM-unique categories
      simulation/
        README.md                               # placeholder, same as XDR
```

### Code layout

Stay in single `bundles/spark/connectors/xsiam/src/connector.py` until file crosses ~2000 lines (matches XDR's threshold). Add new tool blocks at the end of the file with `# v0.15.x R5.x` section markers. Keep `_xsiam_client.py` (the Fetcher) shared across all new tool calls.

## Per-instance toggle (no schema change needed)

The R4.0 infrastructure is already in place:
- `disabled_tools` column on instances table
- `connector_loader.py` filter (applies to ALL connectors, including xsiam)
- `GET /api/v1/connectors/xsiam/tools` endpoint
- UI Tools toggle panel (works for any connector with ≥1 tool)

When XSIAM tools land, they automatically appear in the panel + are toggle-able. Zero new agent-side code for R5.

## E2E battery (R5.4)

`scripts/e2e_xsiam_tools_battery.py`:
- Mirrors `e2e_xdr_tools_battery.py` structure
- Catalog presence assertion (~61 tools expected)
- Toggle filter probe (disable + re-enable round-trip via REST)
- Per-tool classification: CALL_AND_ASSERT_OK / CATALOG_ONLY (destructive) / SKIP-needs-context

Visual screenshot verification (Playwright via IAP tunnel) is a stretch goal; falls back to documented operator-hands-on checklist if credential guardrail blocks login.

## Capability acceptance criteria (R5 arc end-state)

End-to-end on the deployed install with a configured XSIAM instance:
1. ~61 `xsiam_*` tools visible in `/connectors/xsiam-<instance>` Tools panel
2. Each enabled tool exists in agent's catalog
3. Operator can toggle XSIAM tools independently of XDR tools (per-instance scope)
4. `e2e_xsiam_tools_battery.py` exits 0
5. `data/knowledge/external/paloaltonetworks/cortex-xsiam/action/INDEX.md` cross-references every endpoint

## Forbidden going forward

- Mixing `xdr_*` and `xsiam_*` prefixes in the same tool implementation
- Sharing tool functions between connectors (each connector self-contained until the cross-connector refactor lands)
- Adding XSIAM-unique surface (parsers/datamodel/broker) under `xsiam_admin_*` — they get their own category prefix
- Skipping the markdown doc per endpoint — every tool needs `data/knowledge/external/.../action/<endpoint>.md`
