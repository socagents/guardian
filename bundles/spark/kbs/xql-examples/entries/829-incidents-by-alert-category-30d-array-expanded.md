---
id: XQL-829-90fc902c
title: Incidents by alert-category (30d) — array-expanded
category: investigation
dataset: incidents
tags:
  - filter
  - arrayexpand
  - comp
  - sort
  - limit
  - incidents
---

# Incidents by alert-category (30d) — array-expanded

**Dataset**: `incidents`

```sql
config timeframe = 30d
| dataset = incidents
| filter alert_categories != null
| arrayexpand alert_categories
| comp count() as cnt by alert_categories
| sort desc cnt
| limit 10
```

## When to use

Per-alert-category incident distribution. `alert_categories` is an array of categories from the constituent alerts.

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
