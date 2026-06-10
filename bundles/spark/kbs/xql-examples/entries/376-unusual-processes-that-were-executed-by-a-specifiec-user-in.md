---
id: XQL-376-1bf0930c
title: Unusual Processes That Were Executed By A Specifiec User In Last Month
category: investigation
dataset: xdr_process
tags:
  - config
  - preset
  - dedup
  - join
  - alter
  - fields
  - filter
  - xdr_process
  - source:preset
  - operator-authored
---

# Unusual Processes That Were Executed By A Specifiec User In Last Month

**Dataset**: `xdr_process`

```sql
config timeframe between "30d" and "2d"
| preset = xdr_process
| dedup agent_hostname,actor_effective_username, action_process_image_path , action_process_image_name  , action_process_image_sha256
| join type = right conflict_strategy = right (config timeframe =1d|preset = xdr_process|dedup agent_hostname,actor_effective_username, action_process_image_path , action_process_image_name  , action_process_image_sha256|alter executable = action_process_image_name|fields -action_process_image_name) as right right.executable = action_process_image_name
| filter action_process_image_name = null and (action_process_username contains $username or actor_effective_username contains $username)
| alter action_process_image_name = executable
```

## When to use

Lists all the proccess that were initiated by a given username that weren't conducted in the last month, but were performed in the last 24 hours

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
