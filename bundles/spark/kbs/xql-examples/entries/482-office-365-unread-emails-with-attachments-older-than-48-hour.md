---
id: XQL-482-943e6039
title: Office 365 | Unread Emails with Attachments Older Than 48 Hours in the Last 60 days
category: investigation
dataset: msft_o365_emails_raw
tags:
  - config
  - alter
  - filter
  - fields
  - msft_o365_emails_raw
  - source:dataset
  - operator-authored
---

# Office 365 | Unread Emails with Attachments Older Than 48 Hours in the Last 60 days

**Dataset**: `msft_o365_emails_raw`

```sql
config timeframe = 7d
| dataset = msft_o365_emails_raw
| alter email_create_time = createdDateTime
| alter currenttime = current_time()
| alter time_diff_in_hours = timestamp_diff (currenttime, email_create_time, "HOUR")
| filter hasAttachments = true and isRead = false and time_diff_in_hours > 48
| fields email_create_time, currenttime, time_diff_in_hours, *
```

## When to use

Lists the unread emails with attachments in Microsoft O365 that are older than 48 hours in the last 7 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
