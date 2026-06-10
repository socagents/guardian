---
id: XQL-790-dec89110
title: Endpoints by content-version (rollout-progress view)
category: investigation
dataset: endpoints
tags:
  - filter
  - comp
  - sort
  - limit
  - endpoints
---

# Endpoints by content-version (rollout-progress view)

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter content_version != null
| comp count() as cnt by content_version
| sort desc cnt
| limit 10
```

## When to use

Content-version distribution across endpoints. Reveals signature/content rollout progress + identifies endpoints lagging the latest content.

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
