---
id: XQL-350-0cf03e48
title: Scheduled Task Deletion in Last 7 Days (Event ID 4699)
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

# Scheduled Task Deletion in Last 7 Days (Event ID 4699)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter task_name = arrayindex(regextract(message, "Task Name:\s*(.+?)\s+"), 0),target_username = event_data -> TargetUserName,IpAddress = event_data -> IpAddress
| filter event_id_num = 4699
| fields _time, task_name, target_username, IpAddress,*
| sort desc _time
```

## When to use

Lists the scheduled tasks deleted in the last 7 days based on event ID 4699, and includes task and user details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
