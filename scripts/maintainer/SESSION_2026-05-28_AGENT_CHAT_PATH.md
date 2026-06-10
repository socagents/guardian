# Session 2026-05-28 — Agent chat path can drive vendor-faithful streaming

This session shipped four sub-releases (v0.17.75 → v0.17.78) that turn the
agent's chat-driven `phantom_create_data_worker` call into a working,
end-to-end MCP-tool path. The agent (or the operator via the chat surface)
can now ask for vendor-faithful synthetic logs and they actually arrive in
the right XSIAM dataset.

## Final smoke matrix (verified 2026-05-28 06:56 UTC)

| Step | Result |
|---|---|
| 1. Agent's chat → MCP proxy → `phantom_create_data_worker(type=CEF, vendor=okta, product=okta, schema_override=<okta fields>)` | ✅ Worker created: `worker_20260528065657` status=Running |
| 2. Worker thread → OverrideSender → CEF over UDP → broker `10.10.0.8:514` | ✅ 5 events arrived in `okta_okta_raw` within 60s |
| 3. Raw dataset query via XSIAM MCP | ✅ status=SUCCESS, n=5, fields=`[_time, published, uuid, actor, client, target, ...]` |
| 4. Datamodel XDM query | ❌ status=SUCCESS, n=0 — follow-on (composite-JSON synthesis gap, below) |

The chain is **proven end-to-end** to the dataset boundary. The remaining
gap is in synthesis quality (random strings where JSON-typed composites
need to be valid JSON), not in the MCP-tool plumbing.

## Sub-releases shipped this session

### v0.17.75 — `how_to_use` field + 22 validated-vendor YAMLs

New `how_to_use:` block on `data_source.yaml` carries multi-line markdown
distilled from L1-L20 lessons:

- Schema: `bundles/spark/data-sources/data_source.schema.json` declares
  the optional field (additive, backward-compatible)
- Loader: `YamlDataSource.how_to_use` threaded through `from_doc`/`to_doc`
- API: `_enrich_with_vendor_meta` overlays the value onto the schema
  endpoint response (mirrors v0.17.68 YAML-canonical pattern)
- UI: DetailDrawer renders a collapsible "How to simulate" section
  beneath the description, via shared `MarkdownContent`

Populated for 22 vendors:
- Okta (× 2 datasets)
- Alibaba ActionTrail
- AWS CloudTrail / Security Hub / WAF
- Jira / ServiceNow / CyberArk ISP
- Microsoft Entra ID (audit + sign-in)
- O365 (× 5 workloads: General, Exchange, SharePoint, Emails, DLP)
- Qualys / ProofPoint Email Security / ProofPoint TAP
- Azure Flow Logs / Azure WAF / Azure Kubernetes Services

Each entry covers: MR pattern (flat-field / mixed / nested-JSON),
composite-field CEF-wrap recipe, sentinel values, PR-filter quirks,
single-event XDM ceiling, sibling-dataset list, ready-to-paste XQL.

### v0.17.76 — connector.yaml args list alignment

The agent's `phantom_create_data_worker` proxy rejected every meaningful
field with "Unexpected keyword argument" — root cause: `_build_container_proxy`
in `connector_loader.py` synthesizes the agent-side proxy from
`connector.yaml`'s `spec.tools[].args`, NOT from the connector's Python
signature. The xlog yaml was stale (5 legacy fields) vs the actual
Pydantic `CreateDataWorkerRequest` (~17 fields).

Fix: rewrote `create_data_worker.args[]` to match the Python model
field-for-field.

### v0.17.77 — phantom_create_data_worker signature flatten

With v0.17.76, the agent's proxy accepts the right shape — but the
connector container's Python tool still rejected the flat args with
11 Pydantic validation errors. Root cause: `(request: CreateDataWorkerRequest, ctx)`
advertises ONE parameter named `request` to FastMCP, and the agent
sends individual fields.

Fix: refactored signature to `(type, *, destination, count, interval,
vendor, product, schema_override, ..., ctx)`. The function body
reconstructs `CreateDataWorkerRequest` from the flat kwargs inside,
preserving Pydantic field-type validation and minimizing the diff.

Matches caldera's working pattern (e.g. `caldera_get_abilities_by_tactic(
tactic, ctx)`).

### v0.17.78 — bug-family fix for `get_xlog_url` lifespan key

With v0.17.77, the connector container accepts the args — but the body
raised `KeyError('get_xlog_url')`. Root cause: xlog tools were
copy-pasted from agent-runtime code that reads the xlog URL via
`lifespan_context["get_xlog_url"]()` — a key the **agent's** lifespan
provides but the **per-instance connector runtime** does not.

Fix: new helper `_xlog_url_resolver.resolve_xlog_url(ctx)` tries the
agent-runtime key first, falls back to `config.get_config().baseUrl`
from the per-instance runtime's contextvar.

Bug-family pass: all 14 `lifespan_context["get_xlog_url"]()` call sites
converted across `workers.py`, `field_info.py`, `data_faker.py`,
`scenarios.py`, `simulation_runs.py`, `observables_catalog.py`.

## Known follow-ons (out of scope for this arc)

### 1. xsiam / cortex-xdr Pydantic-model-wrap gap (parallel to v0.17.77)

Same `(request: SomeModel, ctx)` pattern in xsiam's `run_xql_query`,
likely cortex-xdr too. Manifests as "Unexpected keyword argument"
when the agent's chat tries to invoke them.

Workaround in this session's smoke harness: hit the connector's MCP
directly at port 9000 with the nested `{request: {...}}` shape, which
still works (the connector's Python sig wraps it for Pydantic).

Real fix: apply the same flatten treatment to xsiam_run_xql_query,
xsiam_get_xql_examples, xsiam_find_xql_examples_rag, etc. Catalog
via `grep -rn "request: [A-Z][A-Za-z]*Request" bundles/spark/connectors/`.

### 2. `_generate_value` doesn't honor controlled YAML types (XDM saturation gap)

`xlog/app/dynamic_schema.py:_generate_value` only branches on a
handful of types (`int`, `float`, `boolean`, `datetime`, `ipv4`).
Falls through to `_rand_string()` for the rest of the data_source.yaml
controlled vocabulary:

- `json` (composite) — random string, MR's `json_extract_scalar`
  returns null on the dependent XDM mappings (L19/L20)
- `enum` — random string instead of pick-from-enum_values
- `regex` — random string instead of regex-matching value
- `string_short`/`string_long` — works by accident (default fallback)
- `mac` / `ipv6` / `hash_*` / `url` / `domain` / `email` / `file_path`
  / `country_code` / `timestamp_ms` / `user` / `host` — name-pattern
  matching catches some but not all

Schema override path also doesn't propagate `enum_values` or
`regex_pattern` from the YAML's `fields[]` array.

This is the substantive XDM-saturation work — once fixed, the agent
chat path can saturate XDM the same way the direct-UDP smoke harnesses
do today (which manually pack nested JSON, enum values, etc.).

### 3. PANW NGFW × 6 packs aren't bundled yet

The hand-curated packs live under `scripts/maintainer/generated_data_sources/`
(not under `bundles/spark/data-sources/`). They're operator-blocked on
upstream Cortex pack install + per-vendor broker applet config — the
v0.17.75 enhancement pass intentionally skipped them.

## Files touched

### v0.17.75
- `bundles/spark/data-sources/<22-packs>/data_source.yaml` — `how_to_use:` added
- `bundles/spark/data-sources/data_source.schema.json` — schema declaration (was in earlier commit 486c615f)
- `bundles/spark/mcp/src/usecase/data_sources_yaml_loader.py` — loader threading (was 486c615f)
- `bundles/spark/mcp/src/api/data_sources.py` — `_enrich_with_vendor_meta` overlay
- `mcp/agent/app/data-sources/page.tsx` — interface + drawer rendering
- `mcp/agent/app/help/architecture/page.tsx` — new paragraph
- `scripts/maintainer/enhance_validated_vendor_yamls.py` — builder

### v0.17.76
- `bundles/spark/connectors/xlog/connector.yaml` — `create_data_worker.args[]` rewritten

### v0.17.77
- `bundles/spark/connectors/xlog/src/workers.py` — signature flattened

### v0.17.78
- `bundles/spark/connectors/xlog/src/_xlog_url_resolver.py` — new helper
- `bundles/spark/connectors/xlog/src/{workers,field_info,data_faker,scenarios,simulation_runs,observables_catalog}.py` — 14 call sites converted

### Maintainer harnesses
- `scripts/maintainer/e2e_okta_via_mcp_tool.py` — agent-chat-path smoke (Okta canary)
- `scripts/maintainer/e2e_smoke_via_mcp_tool.py` — generalized scaffolding for other vendors
