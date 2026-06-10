---
id: XQL-348-5877eca6
title: Remote Desktop Connections in Last 7 Days (Event ID 4624)
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

# Remote Desktop Connections in Last 7 Days (Event ID 4624)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =7D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter target_username = event_data -> TargetUserName,IpAddress = event_data -> IpAddress,logonType = event_data -> LogonType
| filter event_id_num = 4624 and logonType = "10"
| fields _time, target_username, IpAddress, logonType,*
| sort desc _time
```

## When to use

Lists the Remote Desktop Protocol (RDP) connections in the last 7 days based on event ID 4624, and includes user and IP details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
