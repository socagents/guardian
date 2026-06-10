---
id: XQL-812-691e10de
title: Incidents grouped by assigned operator (30d)
category: investigation
dataset: incidents
tags:
  - filter
  - comp
  - sort
  - limit
  - incidents
---

# Incidents grouped by assigned operator (30d)

**Dataset**: `incidents`

```sql
config timeframe = 30d
| dataset = incidents
| filter assigned_user != null
| comp count() as cnt by assigned_user, status
| sort desc cnt
| limit 10
```

## When to use

Per-operator workload distribution. Field is `assigned_user` in this tenant (not `assigned_user_pretty_name`).

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
