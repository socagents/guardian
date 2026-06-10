---
id: XQL-801-20de0616
title: Alerts with category + tactic (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
  - mitre
---

# Alerts with category + tactic (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter category != null
| comp count() as cnt by category, mitre_attack_tactic
| sort desc cnt
| limit 10
```

## When to use

Cross-tab of alert category vs MITRE tactic. Reveals how categories distribute across tactics.

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
