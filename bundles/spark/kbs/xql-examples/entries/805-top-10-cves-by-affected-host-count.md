---
id: XQL-805-9f282858
title: Top 10 CVEs by affected-host count
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

# Top 10 CVEs by affected-host count

**Dataset**: `va_cves`

```sql
dataset = va_cves
| filter affected_hosts_count != null
| fields cve_id, severity, affected_hosts_count, severity_score, description
| sort desc affected_hosts_count
| limit 10
```

## When to use

Most-impacted CVEs by affected-host count. Uses the live tenant's `affected_hosts_count` field directly — no aggregation needed.

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
