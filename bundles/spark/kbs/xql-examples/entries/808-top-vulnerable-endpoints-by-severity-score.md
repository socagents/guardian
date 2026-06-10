---
id: XQL-808-30f685fb
title: Top vulnerable endpoints by severity score
category: investigation
dataset: va_endpoints
tags:
  - filter
  - fields
  - sort
  - limit
  - va_endpoints
  - vulnerability
---

# Top vulnerable endpoints by severity score

**Dataset**: `va_endpoints`

```sql
dataset = va_endpoints
| filter severity_score != null
| fields endpoint_name, endpoint_type, os_type, severity, severity_score
| sort desc severity_score
| limit 10
```

## When to use

Endpoints ranked by computed severity_score. Uses only fields confirmed in the va_endpoints schema (endpoint_name, endpoint_type, os_type, severity, severity_score).

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
