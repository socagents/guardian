---
id: XQL-809-b8156e4c
title: Endpoints with vulnerabilities by OS type
category: investigation
dataset: va_endpoints
tags:
  - filter
  - comp
  - sort
  - limit
  - va_endpoints
  - vulnerability
---

# Endpoints with vulnerabilities by OS type

**Dataset**: `va_endpoints`

```sql
dataset = va_endpoints
| filter os_type != null
| comp count() as endpoints, avg(severity_score) as avg_severity_score by os_type
| sort desc endpoints
| limit 10
```

## When to use

Vulnerable endpoint count + average severity per OS. Useful for OS-level patch-prioritization.

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
