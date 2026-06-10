---
id: XQL-819-96c8afce
title: Recently-observed assets
category: investigation
dataset: asset_inventory
tags:
  - filter
  - fields
  - sort
  - limit
  - asset_inventory
  - xdm
---

# Recently-observed assets

**Dataset**: `asset_inventory`

```sql
dataset = asset_inventory
| filter xdm.asset.last_observed != null
| fields xdm.asset.name, xdm.asset.type.category, xdm.asset.provider, xdm.asset.last_observed
| sort desc xdm.asset.last_observed
| limit 10
```

## When to use

Most-recently-observed assets. Useful for spotting newly-discovered or recently-active assets.

## Variations

_(v0.7.0 hand-curated — variations not yet authored. Operator's
curation pass adds these.)_

## Source

Hand-curated for v0.7.0's 100-query KB expansion. Validated against
the operator's live XDR tenant before being written to this file:
the query body was POSTed to `xdr_run_xql_query` and returned
`status: SUCCESS` (any row count, including 0). The `## When to use`
description above was hand-written to match the operator-language
norms of the existing KB.
