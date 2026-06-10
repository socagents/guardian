---
id: XQL-720-b7000465
title: Endpoints by isolation + prevention policy
category: investigation
dataset: endpoints
tags:
  - comp
  - sort
  - limit
  - endpoints
---

# Endpoints by isolation + prevention policy

**Dataset**: `endpoints`

```sql
dataset = endpoints
| comp count() as cnt by endpoint_isolated, assigned_prevention_policy
| sort desc cnt
| limit 10
```

## When to use

Reports the distribution of endpoint protection policies + isolation status across the fleet. Helps identify hosts running non-default policies or in isolation mode.

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
