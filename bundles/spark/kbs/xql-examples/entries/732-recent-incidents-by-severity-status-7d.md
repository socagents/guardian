---
id: XQL-732-160ffc92
title: Recent incidents by severity + status (7d)
category: investigation
dataset: incidents
tags:
  - filter
  - comp
  - sort
  - limit
  - incidents
---

# Recent incidents by severity + status (7d)

**Dataset**: `incidents`

```sql
config timeframe = 7d
| dataset = incidents
| comp count() as cnt by severity, status
| sort desc cnt
| limit 10
```

## When to use

Incident triage matrix — severity × status. New + critical = highest priority; resolved + low = ready to archive.

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
