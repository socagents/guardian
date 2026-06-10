---
id: XQL-802-0164bfcc
title: Issues by severity (7d)
category: investigation
dataset: issues
tags:
  - filter
  - comp
  - sort
  - limit
  - issues
  - xdm
---

# Issues by severity (7d)

**Dataset**: `issues`

```sql
config timeframe = 7d
| dataset = issues
| comp count() as cnt by xdm.issue.severity
| sort desc cnt
| limit 10
```

## When to use

XDM-normalized severity distribution using `xdm.issue.severity` (the actual XDM path; xdm.alert.severity is the alerts-level path).

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
