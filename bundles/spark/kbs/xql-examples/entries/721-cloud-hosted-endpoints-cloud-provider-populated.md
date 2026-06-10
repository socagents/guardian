---
id: XQL-721-4ffff89f
title: Cloud-hosted endpoints (cloud_provider populated)
category: detection
dataset: endpoints
tags:
  - filter
  - fields
  - sort
  - limit
  - endpoints
  - cloud
---

# Cloud-hosted endpoints (cloud_provider populated)

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter cloud_provider != null
| fields endpoint_name, cloud_provider, cloud_region, cloud_instance_id, operating_system, endpoint_status
| sort desc cloud_provider
| limit 10
```

## When to use

Identifies endpoints hosted in cloud providers (AWS, Azure, GCP). Useful for cloud-workload visibility + correlating with cloud-side audit events.

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
