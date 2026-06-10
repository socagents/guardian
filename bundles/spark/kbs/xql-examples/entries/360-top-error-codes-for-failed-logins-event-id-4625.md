---
id: XQL-360-31022668
title: Top Error Codes for Failed Logins (Event ID 4625)
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

# Top Error Codes for Failed Logins (Event ID 4625)

**Dataset**: `microsoft_windows_raw`

```sql
dataset = microsoft_windows_raw
| alter event_id_num = to_integer(event_id)
| alter error_code = coalesce(event_data ->error, arrayindex(regextract(message, "Failure\sReason\:\t\t(.*)\n"), 0))
| filter event_id_num = 4625
| comp count() as occurrence_count by error_code
| sort desc occurrence_count
| limit 10
```

## When to use

Lists the most common error codes for failed login attempts based on event ID 4625, which are grouped by error code and includes a count

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
