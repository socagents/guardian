---
id: XQL-843-9c340c02
title: Detection volume — alerts + agent_auditing combined (7d, union)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - alter
  - union
  - sort
  - limit
  - alerts
  - agent_auditing
---

# Detection volume — alerts + agent_auditing combined (7d, union)

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| comp count() as cnt by severity
| alter source = "alerts"
| union (dataset = agent_auditing | comp count() as cnt by agent_auditing_subtype | alter severity = agent_auditing_subtype, source = "agent_auditing" | fields severity, cnt, source)
| sort desc cnt
| limit 10
```

## When to use

Combines aggregated counts from two datasets (alerts + agent_auditing) into one unified view tagged with source. Demonstrates UNION with sub-query syntax + field projection per branch.

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
