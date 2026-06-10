---
id: XQL-804-145174fa
title: Critical issues with platform-severity (7d)
category: detection
dataset: issues
tags:
  - filter
  - fields
  - sort
  - limit
  - issues
  - xdm
---

# Critical issues with platform-severity (7d)

**Dataset**: `issues`

```sql
config timeframe = 7d
| dataset = issues
| filter xdm.issue.severity = "SEV_040_HIGH" or xdm.issue.severity = "SEV_050_CRITICAL"
| fields _time, xdm.issue.name, xdm.issue.severity, xdm.issue.platform_severity
| sort desc _time
| limit 10
```

## When to use

High/Critical XDM-normalized issues. XDM severity is `SEV_NNN_LABEL` strings — note the prefix when filtering.

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
