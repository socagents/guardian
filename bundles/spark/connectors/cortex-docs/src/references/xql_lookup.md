# XQL Lookup Guidance

Use this reference when the user asks how to use an XQL stage, function, dataset, syntax pattern, or query technique.

## Core Rule

XQL is used across Cortex XDR, Cortex XSIAM, Cortex AgentiX, and Cortex Cloud. Do not assume XQL is limited to AgentiX.

When the user's product context is explicit, scope to that product:

| User context | Preferred product scope |
|---|---|
| Cortex XDR, endpoint, agent, Broker VM | `xdr` |
| Cortex XSIAM, SOC, SIEM, analytics, incidents | `xsiam` |
| Cortex Cloud, CSPM, DSPM, CIEM, runtime security | `cloud` |
| AgentiX or assistant workflows | `agentix` |
| No product context, just XQL syntax | `xql` |

The `xql` scope intentionally searches all XQL-capable Cortex product docs.
Canonical stage/function topics can be mirrored under several product publications. Prefer `scripts/xql_lookup.py` for direct syntax questions because it ranks exact stage/function pages above overview pages and release notes while still searching the cross-product XQL scope.

## Search Strategy

For stage questions, use:

```bash
python3 scripts/search.py search "Cortex Query Language <stage>" --product xql --json
```

If the user names a product, narrow it:

```bash
python3 scripts/search.py search "Cortex Query Language filter" --product xsiam --json
python3 scripts/search.py search "Cortex Query Language filter" --product xdr --json
python3 scripts/search.py search "Cortex Query Language filter" --product cloud --json
```

For function questions, search the exact function name first, then add XQL if needed:

```bash
python3 scripts/search.py search "arrayindexof" --product xql --json
python3 scripts/search.py search "json_extract_scalar XQL" --product xql --json
python3 scripts/search.py suggest "arrayindexof" --product xql
```

Do not expand `XQL` into a long phrase in queries unless the docs do. Exact product vocabulary usually retrieves better.

## Stage Quick Lookup

Common XQL stages:

| Stage | Use |
|---|---|
| `alter` | Add, transform, or derive fields |
| `arrayexpand` | Expand array values into rows |
| `bin` | Bucket numeric or time values |
| `call` | Call a subquery or reusable query |
| `comp` | Aggregate and group results |
| `config` | Set query configuration |
| `dedup` | Remove duplicate rows |
| `fields` | Select, rename, or limit output fields |
| `filter` | Keep rows matching a condition |
| `sort` | Sort result rows |

## Answer Shape

For XQL lookup answers, prefer:

1. What the stage/function does.
2. Basic syntax.
3. One minimal example.
4. Important notes or common mistakes.
5. Source citation.

Use code fences for XQL examples.
