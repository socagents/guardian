---
id: XQL-844-380f20b9
title: Endpoints with server-tag count (JSON tags)
category: investigation
dataset: endpoints
tags:
  - filter
  - alter
  - fields
  - sort
  - limit
  - endpoints
  - json_extract_array
  - array_length
---

# Endpoints with server-tag count (JSON tags)

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter tags != null
| alter server_tags = json_extract_array(tags, "$.server_tags")
| alter tag_count = array_length(server_tags)
| filter tag_count > 0
| fields endpoint_name, server_tags, tag_count
| sort desc tag_count
| limit 10
```

## When to use

Per-endpoint server-tag inventory. Uses `json_extract_array` to pull the nested array, then `array_length` to count tags per endpoint.

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
