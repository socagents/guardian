---
id: XQL-837-34d7abf9
title: Endpoints with endpoint-tags JSON sub-count
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

# Endpoints with endpoint-tags JSON sub-count

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter tags != null
| alter endpoint_tag_count = array_length(json_extract_array(tags, "$.endpoint_tags"))
| alter server_tag_count = array_length(json_extract_array(tags, "$.server_tags"))
| filter endpoint_tag_count > 0 or server_tag_count > 0
| fields endpoint_name, endpoint_tag_count, server_tag_count
| sort desc endpoint_tag_count
| limit 10
```

## When to use

Endpoint vs server tag counts per host. The `tags` field is JSON with both arrays nested; `json_extract_array` + `array_length` gets the per-subarray count.

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
