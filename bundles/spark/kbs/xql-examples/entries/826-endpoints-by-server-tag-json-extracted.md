---
id: XQL-826-7206a8d8
title: Endpoints by server-tag (JSON-extracted)
category: investigation
dataset: endpoints
tags:
  - filter
  - alter
  - arrayexpand
  - comp
  - sort
  - limit
  - endpoints
  - json_extract
---

# Endpoints by server-tag (JSON-extracted)

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter tags != null
| alter server_tags = json_extract_array(tags, "$.server_tags")
| filter server_tags != null
| arrayexpand server_tags
| comp count() as cnt by server_tags
| sort desc cnt
| limit 10
```

## When to use

Endpoint server-tag distribution. The `tags` field is a JSON string with `server_tags` + `endpoint_tags` subarrays. Uses `json_extract_array` to pull the nested array.

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
