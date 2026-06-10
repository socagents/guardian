---
id: XQL-359-ed7cc7cd
title: Top Logon Types in Last Month (Event ID 4624)
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

# Top Logon Types in Last Month (Event ID 4624)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =30D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter logon_type = event_data -> LogonType
| filter event_id_num = 4624
| comp count() as logon_count by logon_type
| sort desc logon_count
| limit 10
```

## When to use

Lists the most common logon types in the last month based on event ID 4624, which are grouped by the logon type and includes a count

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
