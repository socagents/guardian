---
id: XQL-719-36e10225
title: Endpoints grouped by OS family
category: investigation
dataset: endpoints
tags:
  - comp
  - sort
  - limit
  - endpoints
---

# Endpoints grouped by OS family

**Dataset**: `endpoints`

```sql
dataset = endpoints
| comp count() as cnt, count_distinct(endpoint_id) as unique_endpoints by platform, operating_system
| sort desc cnt
| limit 10
```

## When to use

OS distribution baseline — useful for capacity planning + identifying outliers (e.g. an old Windows 7 box in a Windows-11-only fleet).

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
