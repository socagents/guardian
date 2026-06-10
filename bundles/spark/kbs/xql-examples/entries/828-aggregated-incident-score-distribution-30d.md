---
id: XQL-828-0a977d26
title: Aggregated incident score distribution (30d)
category: investigation
dataset: incidents
tags:
  - filter
  - comp
  - sort
  - limit
  - incidents
---

# Aggregated incident score distribution (30d)

**Dataset**: `incidents`

```sql
config timeframe = 30d
| dataset = incidents
| filter aggregated_score != null
| comp count() as cnt, avg(aggregated_score) as avg_score, max(aggregated_score) as max_score by severity
| sort desc max_score
| limit 10
```

## When to use

Per-severity incident score statistics (avg + max). aggregated_score is XSIAM's composite incident-risk score.

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
