---
id: XQL-730-be66fa63
title: Recent agent events by subtype (7d)
category: investigation
dataset: agent_auditing
tags:
  - filter
  - comp
  - sort
  - limit
  - agent_auditing
---

# Recent agent events by subtype (7d)

**Dataset**: `agent_auditing`

```sql
config timeframe = 7d
| dataset = agent_auditing
| comp count() as cnt by agent_auditing_subtype
| sort desc cnt
| limit 10
```

## When to use

Agent self-audit event distribution — start/stop, policy applied, upgrade, error, etc. Useful for understanding agent fleet health.

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
