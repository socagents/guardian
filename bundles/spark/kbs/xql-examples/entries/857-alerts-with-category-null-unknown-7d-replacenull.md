---
id: XQL-857-1630205b
title: Alerts with category null → "unknown" (7d, replacenull)
category: investigation
dataset: alerts
tags:
  - filter
  - replacenull
  - comp
  - sort
  - limit
  - alerts
---

# Alerts with category null → "unknown" (7d, replacenull)

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| replacenull category = "unknown"
| replacenull host_name = "unknown"
| comp count() as cnt by category, host_name
| sort desc cnt
| limit 10
```

## When to use

Replaces nulls in named fields with literal defaults BEFORE aggregation. The `replacenull <field> = <value>` syntax — one statement per field. Cleans sparse fields so they aggregate into a visible bucket instead of being dropped.

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
