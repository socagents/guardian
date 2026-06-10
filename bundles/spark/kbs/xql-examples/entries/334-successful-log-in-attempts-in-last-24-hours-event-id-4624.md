---
id: XQL-334-22b03fd3
title: Successful Log in Attempts in Last 24 Hours (Event ID 4624)
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

# Successful Log in Attempts in Last 24 Hours (Event ID 4624)

**Dataset**: `microsoft_windows_raw`

```sql
config timeframe =24H
| dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter IpAddress = event_data -> IpAddress,
        target_username = event_data -> TargetUserName
| filter event_id_num = 4624
| fields _time, target_username, IpAddress,*
| sort desc _time
```

## When to use

Lists all successful log in attempts in the last 24 hours based on event ID 4624 and includes the relevant details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
