---
id: XQL-817-cbf0d922
title: Assets by provider (XDM)
category: investigation
dataset: asset_inventory
tags:
  - filter
  - comp
  - sort
  - limit
  - asset_inventory
  - xdm
  - cloud
---

# Assets by provider (XDM)

**Dataset**: `asset_inventory`

```sql
dataset = asset_inventory
| filter xdm.asset.provider != null
| comp count() as cnt by xdm.asset.provider, xdm.asset.realm
| sort desc cnt
| limit 10
```

## When to use

Asset count by cloud provider + realm via the XDM schema. Reveals multi-cloud distribution.

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
