---
id: XQL-386-7d1c4e9e
title: Users Connected with Specific Domain in Last Month
category: investigation
dataset: xdr_data
tags:
  - config
  - fields
  - filter
  - dedup
  - xdr_data
  - source:dataset
  - operator-authored
---

# Users Connected with Specific Domain in Last Month

**Dataset**: `xdr_data`

```sql
config timeframe = 30d | dataset = xdr_data
| fields actor_effective_username , action_remote_ip , action_external_hostname
| filter action_external_hostname contains $domain
| filter actor_effective_username != null
| dedup actor_effective_username
| fields actor_effective_username , action_remote_ip , action_external_hostname
```

## When to use

Searches the given domain across all the normalized data sources over the last month, and lists the related user details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
