---
id: XQL-339-1cc8eae2
title: Group Policy Changes in Last 7 Days (Event ID 5136)
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

# Group Policy Changes in Last 7 Days (Event ID 5136)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter target_username = event_data -> TargetUserName,event_name = arrayindex(regextract(message, "([^\.]+)\."), 0),IpAddress = event_data -> IpAddress
| filter event_id_num = 5136
| fields _time, target_username, event_name, IpAddress,*
| sort desc _time
```

## When to use

Details any changes made to Group Policy settings in the last 7 days based on event ID 5136

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
