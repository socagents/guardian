---
id: XQL-333-828bfdd9
title: Failed Log in Attempts by Source IP (Event ID 4625)
category: investigation
dataset: microsoft_windows_raw
tags:
  - alter
  - filter
  - comp
  - microsoft_windows_raw
  - source:dataset
  - operator-authored
---

# Failed Log in Attempts by Source IP (Event ID 4625)

**Dataset**: `microsoft_windows_raw`

```sql
dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter IpAddress = event_data -> IpAddress,
        target_username = event_data -> TargetUserName
| filter event_id_num = 4625
| comp count(target_username) as failed_login_count by IpAddress
```

## When to use

Tracks the number of failed log in attempts (event ID 4625) and groups them by the source IP address

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
