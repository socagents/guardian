---
id: XQL-349-0485095e
title: Scheduled Task Creation in Last 7 Days (Event ID 4698)
category: investigation
dataset: microsoft_windows_raw
tags:
  - config
  - alter
  - filter
  - fields
  - sort
  - microsoft_windows_raw
  - source:dataset
  - operator-authored
---

# Scheduled Task Creation in Last 7 Days (Event ID 4698)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D | dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter task_name = arrayindex(regextract(message, "Task Name:\s*(.+?)\s+"), 0),target_username = event_data -> TargetUserName,IpAddress = event_data -> IpAddress
| filter event_id_num = 4698
| fields _time, task_name, target_username, IpAddress,*
| sort desc _time
```

## When to use

Lists the scheduled tasks created in the last 7 days based on event ID 4698, and includes task and user information

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
