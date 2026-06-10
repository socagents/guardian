---
id: XQL-823-8ba4206d
title: Alerts by MITRE tactic (30d) — scalar field
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

# Alerts by MITRE tactic (30d) — scalar field

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter mitre_attack_tactic != null
| comp count() as cnt by mitre_attack_tactic
| sort desc cnt
| limit 10
```

## When to use

Per-tactic alert distribution. `mitre_attack_tactic` is a scalar string in this tenant — direct aggregation works, no arrayexpand needed.

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
