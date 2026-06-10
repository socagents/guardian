---
id: XQL-361-58c540f3
title: Top Files Accessed in Last 7 Days (Event ID 4663)
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

# Top Files Accessed in Last 7 Days (Event ID 4663)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter  file_path = arrayindex(regextract(message , "Path:\s*(.+?\\\w+);?\s+\w+\s+\w+"), 0)
| filter event_id_num = 4663
| comp count() as access_count by file_path
| sort desc access_count
| limit 10
```

## When to use

Lists the top files accessed in the last 7 days based on event ID 4663, and includes the count of access events by file path

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
