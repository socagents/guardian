---
id: XQL-818-2475e5c9
title: Assets by class within category (XDM)
category: investigation
dataset: asset_inventory
tags:
  - filter
  - comp
  - sort
  - limit
  - asset_inventory
  - xdm
---

# Assets by class within category (XDM)

**Dataset**: `asset_inventory`

```sql
dataset = asset_inventory
| filter xdm.asset.type.class != null
| comp count() as cnt by xdm.asset.type.category, xdm.asset.type.class
| sort desc cnt
| limit 10
```

## When to use

Hierarchical asset breakdown: category → class. XDM normalizes these as a 2-level taxonomy.

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
