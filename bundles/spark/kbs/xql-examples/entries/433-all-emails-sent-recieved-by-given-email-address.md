---
id: XQL-433-1f1da216
title: All Emails Sent/Recieved by Given Email Address
category: investigation
dataset: email_data
tags:
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# All Emails Sent/Recieved by Given Email Address

**Dataset**: `email_data`

```sql
dataset = email_data
| filter to_string(sender) contains $sender or to_string(recipients) contains $sender or to_string(cc_recipients) contains $sender or to_string(bcc_recipients) contains $sender
| fields _time, sender , sender_ip , recipients , from, attachments , has_attachments , *
```

## When to use

Lists all the related emails that were sent/recieved by this email address

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
