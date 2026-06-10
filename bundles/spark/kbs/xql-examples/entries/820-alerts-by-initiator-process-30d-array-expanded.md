---
id: XQL-820-2bd0631a
title: Alerts by initiator process (30d) — array-expanded
category: investigation
dataset: alerts
tags:
  - filter
  - arrayexpand
  - comp
  - sort
  - limit
  - alerts
---

# Alerts by initiator process (30d) — array-expanded

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter initiator_path != null
| arrayexpand initiator_path
| comp count() as cnt by initiator_path, severity
| sort desc cnt
| limit 10
```

## When to use

Which initiator processes (the process that triggered the detection) generate the most alerts. `initiator_path` is an array — use arrayexpand before aggregation.

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
