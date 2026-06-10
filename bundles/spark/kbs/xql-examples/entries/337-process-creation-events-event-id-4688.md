---
id: XQL-337-7147e6a6
title: Process Creation Events (Event ID 4688)
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

# Process Creation Events (Event ID 4688)

**Dataset**: `microsoft_windows_raw`

```sql
dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter process_name_format = coalesce(event_data -> ProcessName, arrayindex(regextract(message, "Process Name:\s*(\S+)"), 0)),
        Command_Path = arrayindex(regextract(message, "Command Path = (.*?)\s{2, }"), 0)
| filter event_id_num = 4688
| fields _time, process_name_format, Command_Path,*
| sort desc _time
```

## When to use

Details the processes that were created on Windows machines based on event ID 4688 and includes the process name and command path

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
