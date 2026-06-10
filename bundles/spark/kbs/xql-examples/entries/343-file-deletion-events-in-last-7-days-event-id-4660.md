---
id: XQL-343-0b721b22
title: File Deletion Events in Last 7 Days (Event ID 4660)
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

# File Deletion Events in Last 7 Days (Event ID 4660)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter target_username = event_data -> TargetUserName,file_path = arrayindex(regextract(message, "Path:\s*(.+?\\\w+);?\s+\w+\s+\w+"), 0)
| filter event_id_num = 4660
| fields _time, target_username, file_path,*
| sort desc _time
```

## When to use

Lists the files that were deleted in the last 7 days based on event ID 4660, and includes the user and file path

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
