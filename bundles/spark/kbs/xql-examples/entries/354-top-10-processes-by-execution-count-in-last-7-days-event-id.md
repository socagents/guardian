---
id: XQL-354-24cef861
title: Top 10 Processes by Execution Count in Last 7 Days (Event ID 4688)
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

# Top 10 Processes by Execution Count in Last 7 Days (Event ID 4688)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter process_name_format = coalesce(event_data -> ProcessName, arrayindex(regextract(message, "Process Name:\s*(\S+)"), 0))
| filter event_id_num = 4688
| comp count() as execution_count by process_name_format
| sort desc execution_count
| limit 10
```

## When to use

Lists the top 10 most frequently executed processes in the last 7 days based on event ID 4688 for process creation

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
