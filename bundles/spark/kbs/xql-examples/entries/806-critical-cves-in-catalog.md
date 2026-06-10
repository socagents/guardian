---
id: XQL-806-b0c49191
title: Critical CVEs in catalog
category: investigation
dataset: va_cves
tags:
  - filter
  - fields
  - sort
  - limit
  - va_cves
  - vulnerability
---

# Critical CVEs in catalog

**Dataset**: `va_cves`

```sql
dataset = va_cves
| filter severity = "CRITICAL"
| fields cve_id, severity, severity_score, description, publication_date
| sort desc severity_score
| limit 10
```

## When to use

Critical-severity CVEs sorted by CVSS-equivalent severity score. The `severity` field is plain string (CRITICAL/HIGH/MEDIUM/LOW).

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
