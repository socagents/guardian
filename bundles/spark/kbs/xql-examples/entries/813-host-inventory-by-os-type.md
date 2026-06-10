---
id: XQL-813-eb86396b
title: Host inventory by OS type
category: investigation
dataset: host_inventory
tags:
  - filter
  - comp
  - sort
  - limit
  - host_inventory
---

# Host inventory by OS type

**Dataset**: `host_inventory`

```sql
dataset = host_inventory
| filter os_type != null
| comp count() as cnt by os_type
| sort desc cnt
| limit 10
```

## When to use

Discovered host distribution by OS type. Field is `os_type` (not `operating_system_family`).

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
