---
id: XQL-744-578b9aaf
title: Endpoints flagged by tier — critical / high-value / normal
category: investigation
dataset: endpoints
tags:
  - alter
  - comp
  - sort
  - limit
  - endpoints
  - conditional
---

# Endpoints flagged by tier — critical / high-value / normal

**Dataset**: `endpoints`

```sql
dataset = endpoints
| alter tier = if(operating_system contains "Server", "critical", if(cloud_provider != null, "high-value", "normal"))
| comp count() as cnt by tier, operating_system
| sort desc cnt
| limit 10
```

## When to use

Heuristic endpoint tiering — server OSes are 'critical', cloud-hosted are 'high-value', rest are 'normal'. Demonstrates conditional categorization on `endpoints` data.

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
