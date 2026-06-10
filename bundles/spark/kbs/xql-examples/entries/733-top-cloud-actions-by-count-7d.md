---
id: XQL-733-53a23ac6
title: Top cloud actions by count (7d)
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - comp
  - sort
  - limit
  - cloud_audit_logs
  - cloud
---

# Top cloud actions by count (7d)

**Dataset**: `cloud_audit_logs`

```sql
config timeframe = 7d
| dataset = cloud_audit_logs
| comp count() as cnt by cloud_provider, operation_name
| sort desc cnt
| limit 10
```

## When to use

Cloud audit-log activity baseline. Reveals the most-frequent cloud operations across providers. Spikes in unusual operations (CreateUser, DeleteBucket) warrant attention.

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
