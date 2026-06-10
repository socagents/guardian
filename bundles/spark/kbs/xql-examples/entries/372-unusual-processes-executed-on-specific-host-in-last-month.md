---
id: XQL-372-6c882c31
title: Unusual Processes Executed on Specific Host in Last Month
category: investigation
dataset: xdr_data
tags:
  - config
  - filter
  - fields
  - comp
  - sort
  - xdr_data
  - source:dataset
  - operator-authored
---

# Unusual Processes Executed on Specific Host in Last Month

**Dataset**: `xdr_data`

```sql
config timeframe = 30d case_sensitive = false |
dataset = xdr_data |
filter agent_hostname = $host |
fields action_process_image_sha256 as sha256sig, action_process_image_path as path, event_id, agent_hostname as hostname  |
comp count(event_id) as counter by sha256sig, path,hostname |
filter counter < 3 |
sort desc counter
```

## When to use

Lists unusual processes that were executed on a specific host in the last month

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
