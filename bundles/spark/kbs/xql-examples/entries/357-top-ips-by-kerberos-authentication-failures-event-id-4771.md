---
id: XQL-357-c65dbf12
title: Top IPs by Kerberos Authentication Failures (Event ID 4771)
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

# Top IPs by Kerberos Authentication Failures (Event ID 4771)

**Dataset**: `microsoft_windows_raw`

```sql
dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter IpAddress = event_data -> IpAddress,
        failure_reason = arrayindex(regextract(message, "Failure Code:\s*(.+?)\s+"), 0)
| filter event_id_num = 4771
| comp count() as auth_failures by IpAddress
| sort desc auth_failures
| limit 10
```

## When to use

Lists the IP addresses with the most Kerberos authentication failures based on event ID 4771, and includes the failure reason and IP address details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
