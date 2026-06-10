---
id: XQL-364-b755c829
title: Top Users by Failed Login Attempts in Last Month (Event ID 4625)
category: investigation
dataset: microsoft_windows_raw
tags:
  - config
  - alter
  - filter
  - comp
  - sort
  - limit
  - microsoft_windows_raw
  - source:dataset
  - operator-authored
---

# Top Users by Failed Login Attempts in Last Month (Event ID 4625)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =30D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter target_username = event_data -> TargetUserName
| filter event_id_num = 4625
| comp count() as failed_attempts by target_username
| sort desc failed_attempts
| limit 10
```

## When to use

Lists the users with the highest number of failed login attempts in the last month based on event ID 4625

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
