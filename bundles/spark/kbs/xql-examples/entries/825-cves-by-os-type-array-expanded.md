---
id: XQL-825-9cad7191
title: CVEs by OS type (array-expanded)
category: detection
dataset: va_cves
tags:
  - filter
  - arrayexpand
  - comp
  - sort
  - limit
  - va_cves
  - vulnerability
---

# CVEs by OS type (array-expanded)

**Dataset**: `va_cves`

```sql
dataset = va_cves
| filter os_type != null
| arrayexpand os_type
| comp count() as cnt by os_type, severity
| sort desc cnt
| limit 10
```

## When to use

CVE distribution by OS type. `os_type` in va_cves is an array (a CVE can affect multiple OS families); arrayexpand flattens before aggregation.

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
