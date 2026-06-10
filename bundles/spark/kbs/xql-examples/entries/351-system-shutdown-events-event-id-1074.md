---
id: XQL-351-1af067f3
title: System Shutdown Events (Event ID 1074)
category: investigation
dataset: microsoft_windows_raw
tags:
  - alter
  - filter
  - fields
  - sort
  - microsoft_windows_raw
  - source:dataset
  - operator-authored
---

# System Shutdown Events (Event ID 1074)

**Dataset**: `microsoft_windows_raw`

```sql
dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter target_username = event_data -> TargetUserName,shutdown_reason = arrayindex(regextract(message, "reason\:\s+(.*?)\n"), 0)
| filter event_id_num = 1074
| fields _time, target_username, shutdown_reason, message,*
| sort desc _time
```

## When to use

Lists details of system shutdown events based on event ID 1074, and includes who performed the shutdown and the reason

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
