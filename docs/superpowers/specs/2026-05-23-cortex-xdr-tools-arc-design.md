# R4 — Cortex XDR tools arc (v0.14.0 → v0.14.4)

**Status**: Approved 2026-05-23 — autonomous implementation per operator directive.

## Goal

Expose the entire Cortex XDR public API as MCP tools the chat agent can call.
Per-instance toggle UX lets operators prune which tools the agent sees.
Vendor docs are pulled into a new repo-level knowledge tree under
`data/knowledge/external/<vendor>/<product>/action/` so each tool has a
markdown reference next to its code.

## Non-goals

- Scraping authentication-protected XDR docs pages (we use public sources only)
- Auto-rotating XDR credentials (credential-guardrail forbids)
- Multi-tenant XDR ops (single-tenant per instance; multiple instances OK)
- Building tools for other Palo Alto products (XSIAM/Prisma) in this arc

## Repo conventions (new)

### Vendor knowledge tree

```
data/                                       # NEW top-level dir
  knowledge/
    external/
      paloaltonetworks/
        cortex-xdr/
          action/                            # API docs for tool calls
            INDEX.md                         # cross-ref of every endpoint → tool name
            auth.md                          # bearer / advanced auth headers
            incidents/
              list.md                        # GET /public_api/v1/incidents/get_incidents/
              get-extra-data.md
              update.md
            alerts/
            endpoints/
            actions/
            scripts/
            xql/
            ioc/
            download/
            audit/
            assets/
            distribution/
            alert-exclusions/
            exploits/
          simulation/                        # placeholder for R3.C-style YAMLs
            README.md                        # "future: AcmeCorp-shaped sim recipes"
```

### Markdown template per endpoint

```markdown
# <Endpoint Name>

**HTTP**: `<METHOD> /public_api/v1/<path>`
**Auth**: Bearer (`Authorization` + `x-xdr-auth-id` + `x-xdr-nonce` + `x-xdr-timestamp` when advanced auth)
**MCP tool**: `xdr_<category>_<action>`

## Request body
```json
{ ...example with all fields, comments via line-suffix `  // <desc>` where readable }
```

## Response
```json
{ ...example }
```

## Filters / query params
| Param | Type | Required | Description |

## Errors
| Code | Meaning |

## Notes
- Rate limits, pagination, edge cases
- Cross-ref to related tools (e.g. action_id from isolate → get_action_status)
```

## Doc-pull strategy

**Hybrid sourcing**:

1. **Scaffold from `ebarti/cortex-xdr-client`** (GitHub Python wrapper):
   - Parse 8 `*_api.py` modules
   - Extract: endpoint URL, HTTP method, Python wrapper signature, body/response shapes
   - ~25 endpoints covered: `incidents / alerts / endpoints / actions / scripts / xql / ioc / download`

2. **Chrome MCP for gaps**:
   - Categories the Python wrapper misses (audit logs, asset management, distribution lists, alert exclusions, exploits)
   - Navigate to `docs-cortex.paloaltonetworks.com/r/Cortex-XDR/Cortex-XDR-API-Reference/...` pages
   - Extract via `mcp__Claude_in_Chrome__read_page` or `mcp__plugin_playwright_playwright__browser_snapshot`
   - Save as markdown per the template above
   - ~25-30 additional endpoints expected

3. **Final inventory**: ~50-60 markdown files. INDEX.md catalogs all with their `xdr_*` tool names.

## Per-instance tool toggle

### Storage

```sql
ALTER TABLE instances ADD COLUMN disabled_tools TEXT NOT NULL DEFAULT '[]';
-- JSON array of tool names; empty = all enabled (opt-out)
```

Migration is forward-only + idempotent (matches existing Phantom migration style).

### Tool registration filter

In `bundles/spark/mcp/src/usecase/connector_loader.py`:
- After loading instance config, read `disabled_tools`
- When iterating the connector's exposed tools, skip any whose name appears in the instance's list
- Tools are never registered to FastMCP if disabled → agent's catalog never shows them

### UI

`/connectors` instance detail gains a "Tools" tab:
- New endpoint `GET /api/v1/connectors/<id>/tools` introspects the connector module
- Lists every tool: name + one-line docstring summary + enabled checkbox
- Checkbox change → `PATCH /api/v1/instances/<id>` with updated `disabled_tools`
- Tab header: "N enabled / M total"
- Mass actions: Enable all / Disable all / Reset to defaults

### Audit

Toggle change → audit event `action=instance_tool_toggle, target=instance:<id>:tool:<name>`.

## Tool implementation pattern

### Naming

`xdr_<category>_<action>` — flat snake_case. Examples:
- `xdr_incidents_list`, `xdr_incidents_get_extra_data`, `xdr_incidents_update`
- `xdr_alerts_list`, `xdr_alerts_update`
- `xdr_endpoints_list`, `xdr_endpoints_isolate`, `xdr_endpoints_unisolate`, `xdr_endpoints_scan`
- `xdr_response_retrieve_file`, `xdr_response_quarantine_file`, `xdr_response_get_action_status`
- `xdr_scripts_list`, `xdr_scripts_run`, `xdr_scripts_get_execution_status`
- `xdr_xql_start_query`, `xdr_xql_get_results`, `xdr_xql_get_results_stream`
- `xdr_ioc_insert_json`, `xdr_ioc_disable`, `xdr_ioc_enable`
- `xdr_audit_list_management_logs`, `xdr_audit_list_agent_logs`
- `xdr_assets_list`, `xdr_assets_get`
- `xdr_distribution_create`, `xdr_distribution_list`, `xdr_distribution_get_url`
- `xdr_alert_exclusions_list`, `xdr_alert_exclusions_create`

### Mandatory docstring template

```python
async def xdr_<category>_<action>(...) -> dict:
    """One-line purpose.

    Args:
        <param>: type, default, description, when the agent should set it.

    Returns:
        {ok: bool, ...payload}

    When to use:
        Concrete operator phrases that should trigger this tool.

    Docs: data/knowledge/external/paloaltonetworks/cortex-xdr/action/<category>/<action>.md
    """
```

### Existing 8 tools — deprecation cycle

- v0.14.0 — renames `get_alerts` → `xdr_alerts_list`, etc. Old names registered as deprecated aliases.
- v0.15.0 — aliases removed. Operators get one minor cycle to update their workflows.

### Code layout

Keep single `bundles/spark/connectors/cortex-xdr/src/connector.py` for now; split into per-category modules when the file crosses ~1500 lines.

## Phased delivery

| Release | Scope | New tools |
|---|---|---|
| **v0.14.0** | Doc pull + toggle infra + rename existing tools to `xdr_*` (aliased) | 0 net new (8 renames) |
| **v0.14.1** | Incidents + Alerts + IoC + Download | ~12 |
| **v0.14.2** | Endpoints + Response actions + Scripts | ~15 |
| **v0.14.3** | Admin endpoints (audit / asset / distribution / alert-exclusions / exploits) | ~15 |
| **v0.14.4** | E2E smoke battery + final docs sweep | 0 |

Each sub-release ships its own CHANGELOG entry, smoke matrix, and capability acceptance criteria. Capability acceptance for the full arc declared in v0.14.0's CHANGELOG (end-state E2E criterion).

## E2E smoke battery (v0.14.4)

`scripts/e2e_xdr_tools_battery.py`:
- For each new `xdr_*` tool, sends a chat prompt designed to trigger it
- Captures conversation transcript via `/api/chat` streaming endpoint
- Asserts: tool was called + non-error response payload + audit event recorded
- Prints `N tools tested, M passed, K failed`
- Any failure blocks tag approval; the relevant function gets fixed in fast-follow patch

## Capability acceptance criteria (R4 arc)

End-to-end on the deployed install with a configured Cortex_XDR instance:
1. `/connectors/cortex-xdr-Cortex_XDR` page shows a "Tools" tab listing all ~50 tools
2. Operator can disable a tool → next chat invocation doesn't expose it (verified via tool catalog dump)
3. Agent prompted with `"List the 5 most recent XDR incidents"` → calls `xdr_incidents_list` → returns real data
4. Agent prompted with `"Show the XDR endpoints isolated in the last 30 days"` → calls `xdr_endpoints_list` with isolate filter → returns real data
5. `e2e_xdr_tools_battery.py` runs against deployed install: all enabled tools return non-error
6. Audit feed shows one `instance_tool_toggle` event per toggle change
7. `data/knowledge/external/paloaltonetworks/cortex-xdr/action/INDEX.md` lists every tool with its docs file

## Forbidden going forward

- Adding new vendor connector tools without populating `data/knowledge/external/<vendor>/<product>/action/<tool>.md`
- Skipping the per-instance `disabled_tools` filter in `connector_loader.py` for new tools
- Bypassing the `xdr_` prefix for XDR tools (collisions with other connectors)
- Reading XDR API docs from `docs-cortex.paloaltonetworks.com` via WebFetch (JS-rendered; use Chrome MCP or the ebarti repo)
- Storing per-tool config beyond enabled/disabled in `disabled_tools` (if rate-limits or per-tool audit-level become needed, design the migration to a proper `instance_tool_config` table — don't overload the JSON list)

## Tool-enable policy on upgrade

When a new release adds tools (e.g. v0.14.1 adds 12 new `xdr_*` tools), existing instances pick them up with all tools enabled by default. The operator's existing `disabled_tools` list stays unchanged; new tool names are added to the agent's catalog automatically. To opt out, the operator visits the Tools tab and disables the unwanted ones.

This is intentional: the opt-out model is simpler than tracking "tools known at instance-creation time" and matches the operator's stated preference. Operators retain full control via the Tools tab; the cost is one extra visit per release if they want to prune additions.
