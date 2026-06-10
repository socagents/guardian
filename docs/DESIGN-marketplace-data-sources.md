# Design: Marketplace Data Sources + Vendor-Faithful Log Simulation

**Status**: DRAFT — awaiting operator review before implementation
**Author**: agent design pass, 2026-05-21
**Operator brief (paraphrased)**: extract real vendor schemas from Cortex `ModelingRules` (which contain the inverse function: raw vendor field → XDM field; reading them backward gives the raw schema for free). Make those schemas available as installable "Data Sources" in the Phantom marketplace. When an operator simulates logs for an installed data source, xlog uses that schema instead of Rosetta's predefined fields — so the simulated logs match what the real vendor would emit, and Cortex's out-of-box modeling rules will parse them correctly.

## North-star use case

```
Operator: "simulate 50 FortiGate firewall logs"
  │
  ▼
Agent: checks installed data sources → finds "Fortinet FortiGate (1.2.3)"
  │
  ▼
Agent: calls xlog with FortiGate's raw-field schema
  │
  ▼
xlog: generates 50 logs using FortiGate's actual field names + value patterns
  │
  ▼
Logs ship to Cortex XSIAM
  │
  ▼
Cortex's out-of-box FortiGate modeling rule parses them → XDM-correct
  │
  ▼
Detection content authored against XDM fields fires as expected
```

End-state: operators can validate detection content against realistic, vendor-faithful log streams without ever asking a real FortiGate to emit logs.

## Discovery — what already exists vs what's missing

### Already built (the foundation, ~1/3 of the work)

| Component | Where | What it does |
|---|---|---|
| `cortex-content` connector | `bundles/spark/connectors/cortex-content/` | 9 tools that fetch packs + modeling rules + parsing rules from `demisto/content` GitHub repo. 942 lines of code. |
| `cortex_get_modeling_rule` | tool in above | Returns `{xif, yml, schema}` for a single rule. The `xif` is the XQL source code; `schema` is `dataset → field-type` JSON. |
| `cortex_index_kb` | tool in above | Indexes a pack's rules into the `cortex-content` KB for semantic search by the agent. |
| Marketplace UI | `mcp/agent/app/connectors/` + `api/marketplace/` | Browse + install connectors. State stored in `marketplace.db`. |
| xlog | `xlog/` (separate service) | Generates fake logs via the `rosetta-ce` library. Accepts a per-request `required_fields` list. |
| xlog GraphQL schema | `xlog/app/schema.py` | `get_supported_fields()` returns Rosetta's static list. `generate_fake_data()` takes a `DataFakerInput` with `required_fields`, `vendor`, `observables_dict`. |

### Missing (the work to deliver, ~2/3 of the project)

| Component | Why we need it |
|---|---|
| **Schema extraction** | Parse the .xif XQL to extract raw vendor field names from the right-hand side of `alter xdm.foo = vendor_raw_field` statements. Returns `{dataset_name, vendor_fields: [...], xdm_mappings: {...}}`. |
| **Data source store** | New table/db separate from `marketplace.db` connector instances. Schema: `{id, vendor_name, dataset_name, source_pack, source_rule, version, schema_json, installed_at, enabled}`. |
| **Marketplace UI: Data Sources tab** | New UI section, distinct from Connectors. Cards show vendor + dataset + field count + Install button. No "create instance" step. |
| **xlog dynamic schema API** | New GraphQL field `generate_fake_data_v2` or extension of `DataFakerInput` to accept a `schema_override` parameter. When set, xlog uses those fields instead of Rosetta's static list. |
| **MCP tool: `data_sources_list` / `data_sources_get_schema`** | Agent-callable tools for the skill to query installed data sources + retrieve their schemas. |
| **Skill: `simulate_logs`** | New or updated skill that: (1) checks installed data sources, (2) picks one matching operator's request, (3) calls xlog with the schema. |
| **Migration: backward-compat with existing technology_stack contract** | Today operators pass a `technology_stack` JSON to set defaults. Don't break that — make it a fallback when no data source is installed. |

## Schema extraction — MUCH SIMPLER THAN INITIALLY DESIGNED

**Discovery during design**: every ModelingRule ships a sibling `_schema.json` file that already contains the raw vendor field inventory as structured JSON. No XQL parsing needed for the majority of packs.

Sample: `Packs/FortiGate/ModelingRules/FortiGate_1_3/FortiGate_1_3_schema.json` is 13.8 KB:

```json
{
  "fortinet_fortigate_raw": {
    "_id":                {"type": "string", "is_array": false},
    "_product":           {"type": "string", "is_array": false},
    "_raw_log":           {"type": "string", "is_array": false},
    "_vendor":            {"type": "string", "is_array": false},
    "act":                {"type": "string", "is_array": false},
    "app":                {"type": "string", "is_array": false},
    "FTNTFGTpolicyname":  {"type": "string", "is_array": false},
    "FTNTFGTqclass":      {"type": "string", "is_array": false},
    "FTNTFGTdhcp_msg":    {"type": "string", "is_array": false},
    ...176 fields total
  }
}
```

This IS the schema. Phase 1 implementation collapses to "fetch the JSON, store it."

### Two pack styles (catalog survey, 2026-05-21)

Surveyed all 217 ModelingRules across demisto/content. Two styles emerged:

| Style | Schema.json size | Count | Phase 1 support? |
|---|---|---|---|
| **Structured** (explicit raw field inventory) | > 1000 bytes | 101 (46%) | ✓ YES — direct JSON read |
| **Mid** (partial structured) | 300-1000 bytes | 45 (21%) | ✓ YES with same parser |
| **Rawlog-only** (single `_raw_log` field + regex extraction in .xif) | < 300 bytes | 71 (33%) | ✗ Phase 1.5 — needs regex template extraction |

**Phase 1 coverage**: ~92 unique vendor packs (146 modeling rules) get full schema support immediately. Sample: AWS-CloudTrail, AWS-GuardDuty, AbnormalSecurity, Absolute, Armis, AzureAppService, AzureDevOps, AzureFlowLogs, AzureKubernetesServices, AzureWAF, AtlassianConfluenceCloud, FortiGate, plus 80+ more.

**Phase 1.5 (post-v0.8.0)**: regex-template extraction for the 71 rawlog packs. The .xif files contain `regextract(_raw_log, "pattern")` calls; we'd extract the patterns and use a library like `rstr` or `exrex` to generate strings that MATCH those patterns. Higher complexity, lower ROI per pack.

### Skipped algorithm (the XQL parser we DON'T need now)

Original design proposed parsing the .xif to extract raw fields from `alter xdm.x = raw_field` statements. That approach handles BOTH structured and rawlog packs uniformly. We'd still need it for Phase 1.5 to handle rawlog regex patterns, but for v0.8.0 we ship the simpler JSON-read path first.

The earlier algorithm is preserved in git history (this section's previous revision) for reference.

### Logo location (confirmed)

Vendor logos live at `Packs/<pack>/Integrations/<integration>/<integration>_image.png` (PNG, typically 2-5 KB) and `<integration>_dark.svg` (SVG, typically 3-8 KB). FortiGate example:
- `Packs/FortiGate/Integrations/FortiGate/FortiGate_image.png` — 2837 bytes
- `Packs/FortiGate/Integrations/FortiGate/FortiGate_dark.svg` — 3366 bytes

Not all packs ship an integration (some are modeling-rule-only, e.g. F5APM). For those, fall back to:
1. `Packs/<pack>/Author_image.png` if present
2. Generic vendor placeholder (a stylized first-letter glyph, NOT auto-generated brand art)

Phantom marketplace UI shows `_dark.svg` (theme-friendly, scales perfectly) when available; falls back to `_image.png` for raster-only packs.

## 4-phase delivery plan

### Phase 1 — Foundation (2-3 days; was 1 week, simplified after schema.json discovery)
- Goal: extraction + storage works on 92 structured packs. No UI yet.
- Deliverables:
  - New function `cortex_extract_vendor_schema(pack_name, rule_name)` in cortex-content connector — fetches the `_schema.json` directly (no XQL parser).
  - New function `cortex_extract_vendor_logo(pack_name)` — locates + returns PNG/SVG bytes for the vendor logo from `Packs/<pack>/Integrations/<integration>/<integration>_image.png` or `_dark.svg`.
  - New filter in `cortex_list_packs`: `xsiam_only=true` (default) — restricts to packs with `supportedModules` containing `"xsiam"`.
  - Run extraction across the 92 structured XSIAM-tagged packs — gather real-world coverage data.
  - Schema extraction quality report: per-pack field count + any anomalies.
- Out of scope: storage, UI, xlog changes.

### Phase 2 — Data Source Store + MCP Tools (1 week)
- Goal: operators can install/list data sources via API. Agent can query them.
- Deliverables:
  - New SQLite store: `data_sources.db` (3 tables: `data_sources`, `data_source_fields`, `data_source_xdm_mappings`).
  - New REST endpoints: `GET /api/agent/data-sources`, `POST /api/agent/data-sources/install`, `DELETE /api/agent/data-sources/{id}`, `GET /api/agent/data-sources/{id}/schema`.
  - New MCP tools: `data_sources_list`, `data_sources_get_schema`, `data_sources_install`.
- Out of scope: UI, xlog changes, skill changes.

### Phase 3 — Marketplace UI + xlog Dynamic Schema (1-2 weeks)
- Goal: operators can browse + install data sources from the UI. xlog can use installed schemas.
- Deliverables:
  - `/marketplace` UI: split into "Connectors" + "Data Sources" tabs. Reuses existing connector card pattern.
  - `/data-sources` page: list installed data sources with field-count badges + uninstall buttons.
  - xlog GraphQL extension: `generate_fake_data_v2(input, schema_override)` accepts `{vendor_fields: [...], xdm_mappings: {...}}`. Falls back to Rosetta if no override.
  - xlog's existing surface unchanged → backward-compat preserved.
- Out of scope: skill rewrite (still uses current technology_stack contract).

### Phase 4 — Skill Integration + End-to-End (1 week)
- Goal: the north-star use case works from chat prompt.
- Deliverables:
  - Updated `simulate_logs` skill (or new dedicated `simulate_vendor_logs` skill) that:
    1. Calls `data_sources_list` to see what's installed.
    2. Picks the best match for the operator's request (semantic match on vendor name).
    3. Calls `data_sources_get_schema` to load the field schema.
    4. Calls xlog's `generate_fake_data_v2` with the schema as override.
    5. Reports per-log field selection back to the operator.
  - End-to-end smoke: install FortiGate data source → operator says "simulate 50 FortiGate traffic logs" → 50 logs land in XSIAM → FortiGate modeling rule parses them → XDM events visible in xdr_data dataset.

## Migration path (don't break what works)

| Existing surface | Treatment |
|---|---|
| `technology_stack` JSON env (xlog defaults) | Stays as the fallback when no data source is installed. |
| xlog `generate_fake_data` GraphQL field | Stays unchanged. New `_v2` field is additive. |
| xlog `Events.get_supported_fields()` (Rosetta static list) | Stays as the default field universe when no schema override is provided. |
| Existing `simulate_logs` skill | Existing prompts continue to work via current path. New behavior is opt-in via `vendor=` arg or explicit "use installed data source" phrasing. |

Net effect: zero customer breakage. All upgrade.

## Operator decisions (2026-05-21 review)

1. **Naming**: ✓ **"Data Sources"**.
2. **Marketplace split**: ✓ **Separate top-level page** (`/data-sources`), NOT a tab inside `/connectors`. Sidebar gets a new entry.
3. **Install scope**: ✓ **Drill-down hierarchy with vendor logos**.
   - Top level: vendor (e.g., F5, Fortinet) with the vendor's product logo from the pack.
   - Click vendor → list of products/rules under that vendor (F5APM, F5LTM, etc.).
   - Click product/rule → data source detail page (schema, install button, install state).
   - **Logos**: use the ACTUAL vendor logos from the pack (typically base64-encoded inside the pack — likely in the integration YAML or pack metadata). DO NOT create random SVGs ("will put us in a problem later"). If a logo isn't available for a given vendor, fall back to a generic placeholder; never auto-generate brand art.
4. **Schema versioning**: ✓ **Manual update only**. The data-source detail page shows an "Update Schema" button when a newer version is available. NO auto-update on cache refresh — operator must opt in.
5. **Discovery scope**: ✓ **Only XSIAM-tagged packs** (filter `supportedModules` contains `xsiam`). Reason: the demisto/content marketplace is shared between XSOAR + XSIAM; only XSIAM-tagged packs have ingestion-relevant content. SOAR-only packs (Slack, Jira, ServiceNow integrations for playbook automation) aren't useful as log-simulation schemas.
6. **Rosetta long-term**: ✓ **Keep as fallback** when no data source is installed. Don't deprecate.

## What this design intentionally DOESN'T do

- **Field VALUE generation** (e.g. realistic IPs, sane port numbers). Phase 4 still relies on Rosetta's faker for value patterns; only the field NAMES come from the vendor schema. A future phase could extract value constraints from the modeling rule (e.g., port numbers must be 1-65535) but that's a separate body of work.
- **ParsingRules** (the .xif files in `Packs/<pack>/ParsingRules/`). These are pre-XDM parsers — they normalize raw text formats into structured fields. We're using ModelingRules (XDM mappers) instead because the reverse-engineering trick only works on the XDM mapping layer.
- **Multi-format schemas** (e.g., FortiGate emits CEF AND syslog AND JSON). Phase 4 picks one format per data source (the canonical one the modeling rule consumes). Multi-format support deferred.
- **Real-time pack updates**. The cortex-content fetch is cached at 24h TTL. New pack versions land in Phantom on the next cache refresh, not instantly.

## Implementation start point

If approved, the very first commit would be:

```python
# bundles/spark/connectors/cortex-content/src/connector.py

@_register_tool
async def extract_vendor_schema(
    pack_name: str,
    rule_name: str,
) -> dict[str, Any]:
    """Parse a ModelingRule's .xif to extract the raw vendor field schema.

    This is the inverse of the rule's XDM-mapping function: by reading
    `alter xdm.<field> = <raw_expr>` statements backward, we recover
    the raw vendor field names that the rule expects to consume.

    Returns:
        {
          dataset_name: str,           # from [MODEL: dataset="..."]
          vendor_fields: list[str],    # all raw field names referenced
          xdm_mappings: dict,          # xdm_path → raw_field_or_expr
          coverage: {
            n_xdm_fields: int,
            n_raw_fields: int,
            extraction_confidence: float,  # 0-1, how cleanly we parsed
          },
        }
    """
    bundle = await _get_rule_bundle(pack_name, rule_name, "ModelingRules")
    if not bundle.get("ok"):
        return bundle
    xif = bundle["xif"]
    schema = _extract_schema_from_xif(xif)  # the parser
    return {"ok": True, "pack_name": pack_name, "rule_name": rule_name, **schema}
```

After that lands + works on 10 packs, Phase 2 (storage + REST) follows.

## Operator review checklist

Please respond with one of:

- ✓ **Approved with all 6 open questions answered** — proceed to Phase 1 implementation.
- 🔄 **Changes requested** — list which sections need rework before Phase 1.
- ❌ **Different approach preferred** — describe.

## Cross-references

- v0.5.61 — cortex-content connector landed
- v0.3.8 (planned) — KB embedding of content rules
- xlog `app/schema.py` — current `generate_fake_data` GraphQL surface
- `Rosetta-CE` library — current field universe source
- `bundles/spark/connectors/cortex-content/src/connector.py:491-525` — `_get_rule_bundle` (extraction hook point)
