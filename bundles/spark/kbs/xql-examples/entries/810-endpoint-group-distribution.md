---
id: XQL-810-add3d68f
title: Endpoint group distribution
category: investigation
dataset: endpoints
tags:
  - filter
  - arrayexpand
  - comp
  - sort
  - limit
  - endpoints
---

# Endpoint group distribution

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter group_names != null
| arrayexpand group_names
| comp count() as cnt by group_names
| sort desc cnt
| limit 10
```

## When to use

Endpoints aggregated by group via `group_names` (the live tenant's field name) using arrayexpand for multi-value flattening.

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
