---
id: XQL-839-3ec02fb7
title: Endpoint last-seen age in days via epoch math
category: investigation
dataset: endpoints
tags:
  - filter
  - alter
  - fields
  - sort
  - limit
  - endpoints
  - to_epoch
  - math
---

# Endpoint last-seen age in days via epoch math

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter last_seen != null
| alter age_seconds = divide(subtract(to_epoch(current_time(), "SECONDS"), to_epoch(last_seen, "SECONDS")), 1)
| alter age_days = floor(divide(age_seconds, 86400))
| fields endpoint_name, last_seen, age_days, endpoint_status
| sort desc age_days
| limit 10
```

## When to use

Endpoint last-seen age in days. `to_epoch(timestamp, 'SECONDS')` converts both `current_time()` and `last_seen` to epoch seconds; subtraction + floor + divide-by-86400 gives integer days. Robust pattern for date-arithmetic on date-typed fields.

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
