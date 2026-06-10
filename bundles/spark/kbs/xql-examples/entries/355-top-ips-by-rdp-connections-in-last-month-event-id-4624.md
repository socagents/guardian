---
id: XQL-355-c3f6194a
title: Top IPs by RDP Connections in Last Month (Event ID 4624)
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

# Top IPs by RDP Connections in Last Month (Event ID 4624)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =30D
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter IpAddress = event_data -> IpAddress,logonType = event_data -> LogonType
| filter event_id_num = 4624 and logonType ="10"
| comp count() as rdp_connections by IpAddress
| sort desc rdp_connections
| limit 10
```

## When to use

Lists the top IP addresses involved in Remote Desktop Protocol (RDP) connections over the last month based on event ID 4624, and is filtered by logon type 10, the RDP logon

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
