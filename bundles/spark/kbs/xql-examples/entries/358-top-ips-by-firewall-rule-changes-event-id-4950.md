---
id: XQL-358-83688b19
title: Top IPs by Firewall Rule Changes (Event ID 4950)
category: investigation
dataset: microsoft_windows_raw
tags:
  - alter
  - filter
  - comp
  - sort
  - limit
  - microsoft_windows_raw
  - source:dataset
  - operator-authored
---

# Top IPs by Firewall Rule Changes (Event ID 4950)

**Dataset**: `microsoft_windows_raw`

```sql
dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter IpAddress = event_data -> IpAddress
| filter event_id_num = 4950
| comp count() as firewall_changes by IpAddress
| sort desc firewall_changes
| limit 10
```

## When to use

Lists the top IP addresses involved in firewall rule changes in the last month based on event ID 4950

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
